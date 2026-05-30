from typing import Iterable, List, cast, Optional

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator, Material, UIList, Object, FileHandler, Event, Context, SpaceProperties, \
    Collection, Panel, Depsgraph
from mathutils import Matrix, Vector

from .builder import ASEBuildOptions, ASEBuildError, build_ase
from .writer import write_ase
from .properties import TransformMixin, TransformSourceMixin, MaterialMappingMixin, get_vertex_color_attributes_from_objects


def get_unique_materials(depsgraph: Depsgraph, mesh_objects: Iterable[Object]) -> List[Material]:
    materials = []
    for mesh_object in mesh_objects:
        eo = mesh_object.evaluated_get(depsgraph)
        for i, material_slot in enumerate(eo.material_slots):
            material = material_slot.material
            # if material is None:
                # raise RuntimeError(f'Material slots cannot be empty ({mesh_object.name}, material slot index {i})')
            if material not in materials:
                materials.append(material)
    return materials


def get_collection_from_context(context: Context) -> Optional[Collection]:
    if context.space_data.type != 'PROPERTIES':
        return None

    space_data = cast(SpaceProperties, context.space_data)

    if space_data.use_pin_id:
        return cast(Collection, space_data.pin_id)
    else:
        return context.collection


def get_collection_export_operator_from_context(context: Context) -> Optional['ASE_OT_export_collection']:
    collection = get_collection_from_context(context)
    if collection is None or collection.active_exporter_index is None:
        return None
    if 0 > collection.active_exporter_index >= len(collection.exporters):
        return None
    exporter = collection.exporters[collection.active_exporter_index]
    # TODO: make sure this is actually an ASE exporter.
    return exporter.export_properties


class MaterialsSource:
    @staticmethod
    def _get_materials(context: Context) -> List[Material]:
        return []


class MaterialsSourceCollection(MaterialsSource):
    @staticmethod
    def _get_materials(context) -> List[Material]:
        collection = get_collection_from_context(context)
        operator = get_collection_export_operator_from_context(context)
        if collection is None or operator is None:
            return []

        from .dfs import dfs_collection_objects

        mesh_objects = list(map(lambda x: x.obj, filter(lambda x: x.obj.type == 'MESH', dfs_collection_objects(collection))))

        return get_unique_materials(context.evaluated_depsgraph_get(), mesh_objects)


def _get_unique_materials_from_selected_objects(context: Context):
    if context.selected_objects is None:
            return []
    from .dfs import dfs_objects_recursive
    dfs_objects = list(filter(lambda x: x.obj.type == 'MESH', dfs_objects_recursive(context.selected_objects)))
    mesh_objects = list(map(lambda x: x.obj, dfs_objects))
    return get_unique_materials(context.evaluated_depsgraph_get(), mesh_objects)


class MaterialsSourceScene(MaterialsSource):
    @staticmethod
    def _get_materials(context) -> List[Material]:
        # Get materials from the the selected objects in the scene.
        return _get_unique_materials_from_selected_objects(context)


class MaterialMappingSource:
    @classmethod
    def _get_props(cls, context) -> MaterialMappingMixin | None:
        pass


class MaterialMappingSourceCollection(MaterialMappingSource):
    @classmethod
    def _get_props(cls, context: Context) -> MaterialMappingMixin | None:
        return get_collection_export_operator_from_context(context)


class MaterialMappingSourceScene(MaterialMappingSource):
    @classmethod
    def _get_props(cls, context: Context) -> MaterialMappingMixin | None:
        return getattr(context.scene, 'ase_export')


class MaterialMappingAddOperator(Operator, MaterialMappingSource):
    bl_label = 'Add'
    bl_description = 'Add a material mapping to the list'

    def execute(self, context: 'Context'):
        props = self.__class__._get_props(context)

        if props is None:
            return {'CANCELLED'}

        material_mapping = props.material_mapping.add()
        material_mapping.key = 'Material'
        props.material_mapping_index = len(props.material_mapping) - 1

        return {'FINISHED'}


class ASE_OT_export_collection_material_mapping_add(MaterialMappingAddOperator, MaterialMappingSourceCollection, MaterialsSourceCollection):
    bl_idname = 'ase_export.collection_material_mapping_add'


class ASE_OT_export_scene_material_mapping_add(MaterialMappingAddOperator, MaterialMappingSourceScene, MaterialsSourceScene):
    bl_idname = 'ase_export.scene_material_mapping_add'


class MaterialMappingRemoveOperator(Operator, MaterialMappingSource):
    bl_label = 'Remove'
    bl_description = 'Remove the selected material mapping from the list'

    @classmethod
    def poll(cls, context: Context):
        props = cls._get_props(context)
        if props is None:
            return False
        return 0 <= props.material_mapping_index < len(props.material_mapping)

    def execute(self, context: Context):
        props = self._get_props(context)

        if props is None:
            return {'CANCELLED'}

        props.material_mapping.remove(props.material_mapping_index)
        props.material_mapping_index -= 1

        return {'FINISHED'}


class ASE_OT_export_collection_material_mapping_remove(MaterialMappingRemoveOperator, MaterialMappingSourceCollection, MaterialsSourceCollection):
    bl_idname = 'ase_export.collection_material_mapping_remove'


class ASE_OT_export_scene_material_mapping_remove(MaterialMappingRemoveOperator, MaterialMappingSourceScene, MaterialsSourceScene):
    bl_idname = 'ase_export.scene_material_mapping_remove'


class MaterialMappingMoveUpOperator(Operator, MaterialMappingSource):
    bl_label = 'Move Up'
    bl_description = 'Move the selected material mapping up one slot'

    @classmethod
    def poll(cls, context: Context):
        props = cls._get_props(context)
        if props is None:
            return False
        return props.material_mapping_index > 0

    def execute(self, context: 'Context'):
        props = self.__class__._get_props(context)

        if props is None:
            return {'CANCELLED'}
    
        props.material_mapping.move(props.material_mapping_index, props.material_mapping_index - 1)
        props.material_mapping_index -= 1

        return {'FINISHED'}


class ASE_OT_export_collection_material_mapping_move_up(MaterialMappingSourceCollection, MaterialMappingMoveUpOperator):
    bl_idname = 'ase_export.collection_material_mapping_move_up'


class ASE_OT_export_scene_material_mapping_move_up(MaterialMappingSourceScene, MaterialMappingMoveUpOperator):
    bl_idname = 'ase_export.scene_material_mapping_move_up'


class MaterialMappingMoveDownOperator(Operator, MaterialMappingSource):
    bl_label = 'Move Down'
    bl_description = 'Move the selected material mapping down one slot'

    @classmethod
    def poll(cls, context: Context):
        props = cls._get_props(context)
        if props is None:
            return False
        return props.material_mapping_index < len(props.material_mapping) - 1

    def execute(self, context: 'Context'):
        props = self.__class__._get_props(context)

        if props is None:
            return {'CANCELLED'}
    
        props.material_mapping.move(props.material_mapping_index, props.material_mapping_index + 1)
        props.material_mapping_index += 1

        return {'FINISHED'}


class ASE_OT_export_collection_material_mapping_move_down(MaterialMappingSourceCollection, MaterialMappingMoveDownOperator):
    bl_idname = 'ase_export.collection_material_mapping_move_down'


class ASE_OT_export_scene_material_mapping_move_down(MaterialMappingSourceCollection, MaterialMappingMoveDownOperator):
    bl_idname = 'ase_export.scene_material_mapping_move_down'


class ASE_UL_materials(UIList):
    bl_idname = 'ASE_UL_materials'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        row.prop(item.material, 'name', text='', emboss=False, icon_value=layout.icon(item.material))


class ASE_UL_material_names(UIList):
    bl_idname = 'ASE_UL_material_names'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        material = bpy.data.materials.get(item.key, None)
        col= row.column()
        col.enabled = False
        col.prop(item, 'key', text='', emboss=False, icon_value=layout.icon(material) if material is not None else 0)
        row.label(icon='RIGHTARROW', text='')
        material = bpy.data.materials.get(item.value, None)
        row.prop(item, 'value', text='', emboss=False, icon_value=layout.icon(material) if material is not None else 0)


def _material_mapping_populate(props: MaterialMappingMixin, materials: Iterable[Material]):
    props.material_mapping.clear()
    for material in materials:
        m = props.material_mapping.add()
        m.key = material.name
        m.value = material.name


class MaterialMappingPopulateOperator(MaterialMappingSource, MaterialsSource, Operator):
    bl_label = 'Populate Material Mapping'
    bl_description = 'Populate the material mapping with the materials used by the relevant objects'

    def execute(self, context):
        props = self._get_props(context)
        if props is None:
            return {'CANCELLED'}
        materials = self._get_materials(context)
        _material_mapping_populate(props, materials)
        return {'FINISHED'}


class ASE_OT_export_collection_material_mapping_populate(MaterialMappingPopulateOperator, MaterialMappingSourceCollection, MaterialsSourceCollection):
    bl_idname = 'ase_export.collection_material_mapping_populate'


class ASE_OT_export_scene_material_mapping_populate(MaterialMappingPopulateOperator, MaterialMappingSourceScene, MaterialsSourceScene):
    bl_idname = 'ase_export.scene_material_mapping_populate'


object_eval_state_items = [
    ('EVALUATED', 'Evaluated', 'Use data from fully evaluated object'),
    ('ORIGINAL', 'Original', 'Use data from original object with no modifiers applied'),
]


class ASE_OT_export(Operator, ExportHelper, TransformMixin, TransformSourceMixin):
    bl_idname = 'io_scene_ase.ase_export'
    bl_label = 'Export ASE'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_description = 'Export selected objects to ASE'
    filename_ext = '.ase'
    filter_glob: StringProperty(default="*.ase", options={'HIDDEN'}, maxlen=255)
    object_eval_state: EnumProperty(
        items=object_eval_state_items,
        name='Data',
        default='EVALUATED'
    )

    @classmethod
    def poll(cls, context):
        if not any(x.type == 'MESH' or (x.type == 'EMPTY' and x.instance_collection is not None) for x in context.selected_objects):
            cls.poll_message_set('At least one mesh or instanced collection must be selected')
            return False
        return True

    def draw(self, context):
        layout = self.layout
        assert layout is not None
        pg = context.scene.ase_export

        materials_header, materials_panel = layout.panel('Materials', default_closed=False)
        materials_header.label(text='Materials')

        if materials_panel:
            flow = layout.grid_flow()
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'material_mode')
            if pg.material_mode == 'MANUAL':
                row = flow.row()
                row.template_list(ASE_UL_material_names.bl_idname, '', pg, 'material_mapping', pg, 'material_mapping_index')
                col = row.column(align=True)
                col.operator(ASE_OT_export_scene_material_mapping_populate.bl_idname, icon='FILE_REFRESH', text='')
                col.separator()
                col.operator(ASE_OT_export_scene_material_mapping_add.bl_idname, icon='ADD', text='')
                col.operator(ASE_OT_export_scene_material_mapping_remove.bl_idname, icon='REMOVE', text='')
                col.separator()
                col.operator(ASE_OT_export_scene_material_mapping_move_up.bl_idname, icon='TRIA_UP', text='')
                col.operator(ASE_OT_export_scene_material_mapping_move_down.bl_idname, icon='TRIA_DOWN', text='')

        if context.selected_objects is None:
            return

        has_vertex_colors = len(get_vertex_color_attributes_from_objects(context.selected_objects)) > 0
        vertex_colors_header, vertex_colors_panel = layout.panel_prop(pg, 'should_export_vertex_colors')
        row = vertex_colors_header.row()
        row.enabled = has_vertex_colors
        row.prop(pg, 'should_export_vertex_colors', text='Vertex Colors')

        if vertex_colors_panel:
            vertex_colors_panel.use_property_split = True
            vertex_colors_panel.use_property_decorate = False
            if has_vertex_colors:
                vertex_colors_panel.prop(pg, 'vertex_color_mode', text='Mode')
                if pg.vertex_color_mode == 'EXPLICIT':
                    vertex_colors_panel.prop(pg, 'vertex_color_attribute', icon='GROUP_VCOL')
            else:
                vertex_colors_panel.label(text='No vertex color attributes found')

        transform_header, transform_panel = layout.panel('Transform', default_closed=True)
        transform_header.label(text='Transform')

        if transform_panel:
            transform_panel.use_property_split = True
            transform_panel.use_property_decorate = False
            transform_panel.prop(self, 'scale')
            transform_panel.prop(self, 'forward_axis')
            transform_panel.prop(self, 'up_axis')

        advanced_header, advanced_panel = layout.panel('Advanced', default_closed=True)
        advanced_header.label(text='Advanced')

        if advanced_panel:
            advanced_panel.use_property_split = True
            advanced_panel.use_property_decorate = False
            advanced_panel.prop(self, 'object_eval_state')

            fixes_header, fixes_panel = advanced_panel.panel('Fixes', default_closed=True)
            fixes_header.label(text='Fixes')

            if fixes_panel:
                fixes_panel.use_property_split = True
                fixes_panel.use_property_decorate = False
                fixes_panel.prop(pg, 'should_invert_normals')
                fixes_panel.prop(pg, 'scct_versus_mcdcx_flip')

    def invoke(self, context: Context, event: Event):
        if context.active_object is None:
            return {'CANCELLED'}
        
        pg = getattr(context.scene, 'ase_export')

        # Populate the material mapping list.
        materials = _get_unique_materials_from_selected_objects(context)
        _material_mapping_populate(pg, materials)

        self.filepath = f'{context.active_object.name}.ase'

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        pg = getattr(context.scene, 'ase_export')

        if context.selected_objects is None:
            return {'CANCELLED'}

        options = ASEBuildOptions()
        options.object_eval_state = self.object_eval_state
        options.should_export_vertex_colors = pg.should_export_vertex_colors
        options.vertex_color_mode = pg.vertex_color_mode
        options.has_vertex_colors = len(get_vertex_color_attributes_from_objects(context.selected_objects)) > 0
        options.vertex_color_attribute = pg.vertex_color_attribute
        options.should_invert_normals = pg.should_invert_normals
        options.scct_versus_mcdcx_flip = pg.scct_versus_mcdcx_flip

        match self.transform_source:
            case 'SCENE':
                transform_source = getattr(context.scene, 'ase_settings')
            case 'CUSTOM':
                transform_source = self
            case _:
                assert False, "Invalid transform source"

        options.scale = transform_source.scale
        options.forward_axis = transform_source.forward_axis
        options.up_axis = transform_source.up_axis

        from .dfs import dfs_objects_recursive
        dfs_objects = list(filter(lambda x: x.obj.type == 'MESH', dfs_objects_recursive(context.selected_objects)))

        mesh_objects = [x.obj for x in dfs_objects]
        options.materials = get_unique_materials(context.evaluated_depsgraph_get(), mesh_objects)
        if pg.material_mode == 'MANUAL':
            options.materials = apply_material_mapping(options.materials, pg)

        try:
            ase = build_ase(context, options, dfs_objects)

            # Calculate some statistics about the ASE file to display in the console.
            object_count = len(ase.geometry_objects)
            material_count = len(ase.materials)
            face_count = sum(len(x.faces) for x in ase.geometry_objects)
            vertex_count = sum(len(x.vertices) for x in ase.geometry_objects)

            write_ase(self.filepath, ase)
            self.report({'INFO'}, f'ASE exported successfully ({object_count} objects, {material_count} materials, {face_count} faces, {vertex_count} vertices)')
            return {'FINISHED'}
        except ASEBuildError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


export_space_items = [
    ('WORLD', 'World Space', 'Export the collection in world space'),
    ('INSTANCE', 'Instance Space', 'Export the collection in instance space'),
]

def apply_material_mapping(materials: list[Material], material_mapping_mixin: MaterialMappingMixin):
    # Sort the materials based on the order in the material order list, keeping in mind that the material order list
    # may not contain all the materials used by the objects in the collection.
    material_names = [x.key for x in material_mapping_mixin.material_mapping]
    material_names_map = {x: i for i, x in enumerate(material_names)}

    # Split the list of materials into two lists: one for materials that appear in the material order list, and one
    # for materials that do not. Then append the two lists together, with the ordered materials first.
    ordered_materials = []
    unordered_materials = []
    for material in materials:
        if material.name in material_names_map:
            ordered_materials.append(material)
        else:
            unordered_materials.append(material)

    ordered_materials.sort(key=lambda x: material_names_map.get(x.name, len(material_names)))
    return ordered_materials + unordered_materials


class ASE_OT_export_collection(Operator, ExportHelper, TransformSourceMixin, TransformMixin, MaterialMappingMixin):
    bl_idname = 'io_scene_ase.ase_export_collection'
    bl_label = 'Export collection to ASE'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_description = 'Export collection to ASE'
    filename_ext = '.ase'
    filter_glob: StringProperty(
        default="*.ase",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be highlighted.
    )
    object_eval_state: EnumProperty(
        items=object_eval_state_items,
        name='Data',
        default='EVALUATED'
    )

    collection: StringProperty()
    export_space: EnumProperty(name='Export Space', items=export_space_items, default='INSTANCE')

    def draw(self, context):
        layout = self.layout

        if layout is None:
            return

        flow = layout.grid_flow()
        flow.use_property_split = True
        flow.use_property_decorate = False

        materials_header, materials_panel = layout.panel('Materials', default_closed=True)
        materials_header.label(text='Materials')

        if materials_panel:
            flow = layout.grid_flow()
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(self, 'material_mode')
            if self.material_mode == 'MANUAL':
                row = flow.row()
                row.template_list(ASE_UL_material_names.bl_idname, '', self, 'material_mapping', self, 'material_mapping_index')
                col = row.column(align=True)
                col.operator(ASE_OT_export_collection_material_mapping_populate.bl_idname, icon='FILE_REFRESH', text='')
                col.separator()
                col.operator(ASE_OT_export_collection_material_mapping_add.bl_idname, icon='ADD', text='')
                col.operator(ASE_OT_export_collection_material_mapping_remove.bl_idname, icon='REMOVE', text='')
                col.separator()
                col.operator(ASE_OT_export_collection_material_mapping_move_up.bl_idname, icon='TRIA_UP', text='')
                col.operator(ASE_OT_export_collection_material_mapping_move_down.bl_idname, icon='TRIA_DOWN', text='')

        transform_header, transform_panel = layout.panel('Transform', default_closed=True)
        transform_header.label(text='Transform')

        if transform_panel:
            transform_panel.use_property_split = True
            transform_panel.use_property_decorate = False
            transform_panel.prop(self, 'export_space')
            transform_panel.prop(self, 'transform_source')

            flow = transform_panel.grid_flow()
            match self.transform_source:
                case 'SCENE':
                    transform_source = getattr(context.scene, 'ase_settings')
                    flow.enabled = False
                case 'CUSTOM':
                    transform_source = self
                case _:
                    assert False, f'Unknown transform source {self.transform_source}'

            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(transform_source, 'scale')
            flow.prop(transform_source, 'forward_axis')
            flow.prop(transform_source, 'up_axis')

        advanced_header, advanced_panel = layout.panel('Advanced', default_closed=True)
        advanced_header.label(text='Advanced')

        if advanced_panel:
            advanced_panel.use_property_split = True
            advanced_panel.use_property_decorate = False
            advanced_panel.prop(self, 'object_eval_state')

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection)

        options = ASEBuildOptions()
        options.object_eval_state = self.object_eval_state

        match self.transform_source:
            case 'SCENE':
                transform_source = getattr(context.scene, 'ase_settings')
            case 'CUSTOM':
                transform_source = self
            case _:
                assert False, f'Unknown transform source {self.transform_source}'

        options.scale = transform_source.scale
        options.forward_axis = transform_source.forward_axis
        options.up_axis = transform_source.up_axis
        
        # Get SCCT Versus MCDCX flip option from scene
        pg = getattr(context.scene, 'ase_export')
        options.scct_versus_mcdcx_flip = pg.scct_versus_mcdcx_flip

        match self.export_space:
            case 'WORLD':
                options.transform = Matrix.Identity(4)
            case 'INSTANCE':
                options.transform = Matrix.Translation(-Vector(collection.instance_offset))

        from .dfs import dfs_collection_objects

        dfs_objects = list(filter(lambda x: x.obj.type == 'MESH', dfs_collection_objects(collection)))

        # Get all the materials used by the objects in the collection.
        mesh_objects = [x.obj for x in dfs_objects]
        options.materials = get_unique_materials(context.evaluated_depsgraph_get(), mesh_objects)
        if self.material_mode == 'MANUAL':
            options.materials = apply_material_mapping(options.materials, self)

        try:
            ase = build_ase(context, options, dfs_objects)
        except ASEBuildError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        try:
            write_ase(self.filepath, ase)
        except PermissionError as e:
            self.report({'ERROR'}, 'ASCII Scene Export: ' + str(e))
            return {'CANCELLED'}

        return {'FINISHED'}


class ASE_PT_export_scene_settings(Panel):
    bl_label = 'ASCII Scene Export'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        return context.space_data.type == 'PROPERTIES' and hasattr(context.scene, 'ase_settings')
    
    def draw(self, context: Context):
        layout = self.layout

        transform_source = getattr(context.scene, 'ase_settings')

        transform_header, transform_panel = layout.panel('Transform', default_closed=True)
        transform_header.label(text='Transform')

        if transform_panel:
            flow = transform_panel.grid_flow()
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(transform_source, 'scale')
            flow.prop(transform_source, 'forward_axis')
            flow.prop(transform_source, 'up_axis')



class ASE_FH_export(FileHandler):
    bl_idname = 'ASE_FH_export'
    bl_label = 'ASCII Scene Export'
    bl_export_operator = ASE_OT_export_collection.bl_idname
    bl_file_extensions = '.ase'


classes = (
    ASE_UL_materials,
    ASE_UL_material_names,
    ASE_OT_export,
    ASE_OT_export_collection,

    ASE_OT_export_scene_material_mapping_add,
    ASE_OT_export_scene_material_mapping_remove,
    ASE_OT_export_scene_material_mapping_move_down,
    ASE_OT_export_scene_material_mapping_move_up,
    ASE_OT_export_scene_material_mapping_populate,

    ASE_OT_export_collection_material_mapping_add,
    ASE_OT_export_collection_material_mapping_remove,
    ASE_OT_export_collection_material_mapping_move_down,
    ASE_OT_export_collection_material_mapping_move_up,
    ASE_OT_export_collection_material_mapping_populate,

    ASE_PT_export_scene_settings,
    ASE_FH_export,
)
