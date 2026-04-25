from typing import Iterable, List, Set, Union, cast, Optional

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, CollectionProperty, IntProperty, EnumProperty, BoolProperty
from bpy.types import Operator, Material, UIList, Object, FileHandler, Event, Context, SpaceProperties, \
    Collection, Panel, Depsgraph
from mathutils import Matrix, Vector

from .builder import ASEBuildOptions, ASEBuildError, build_ase
from .writer import ASEWriter
from .properties import TransformMixin, TransformSourceMixin, MaterialModeMixin, ASE_PG_key_value, get_vertex_color_attributes_from_objects


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


def populate_material_list(depsgraph: Depsgraph, mesh_objects: Iterable[Object], material_list):
    materials = get_unique_materials(depsgraph, mesh_objects)
    material_list.clear()
    for index, material in enumerate(materials):
        m = material_list.add()
        m.material = material
        m.index = index


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
    if collection is None:
        return None
    if 0 > collection.active_exporter_index >= len(collection.exporters):
        return None
    exporter = collection.exporters[collection.active_exporter_index]
    # TODO: make sure this is actually an ASE exporter.
    return exporter.export_properties


class ASE_OT_material_mapping_add(Operator):
    bl_idname = 'ase_export.material_mapping_add'
    bl_label = 'Add'
    bl_description = 'Add a material mapping to the list'

    def invoke(self, context: Context, event: Event) -> Union[Set[str], Set[int]]:
        # TODO: get the region that this was invoked from and set the collection to the collection of the region.
        print(event)
        return self.execute(context)

    def execute(self, context: 'Context') -> Union[Set[str], Set[int]]:
        # Make sure this is being invoked from the properties region.
        operator = get_collection_export_operator_from_context(context)

        if operator is None:
            return {'INVALID_CONTEXT'}

        material_mapping = operator.material_mapping.add()
        material_mapping.key = 'Material'

        return {'FINISHED'}


class ASE_OT_material_mapping_remove(Operator):
    bl_idname = 'ase_export.material_mapping_remove'
    bl_label = 'Remove'
    bl_description = 'Remove the selected material mapping from the list'

    @classmethod
    def poll(cls, context: Context):
        operator = get_collection_export_operator_from_context(context)
        if operator is None:
            return False
        return 0 <= operator.material_mapping_index < len(operator.material_mapping)

    def execute(self, context: 'Context') -> Union[Set[str], Set[int]]:
        operator = get_collection_export_operator_from_context(context)

        if operator is None:
            return {'INVALID_CONTEXT'}

        operator.material_mapping.remove(operator.material_mapping_index)

        return {'FINISHED'}


class ASE_OT_material_mapping_move_up(Operator):
    bl_idname = 'ase_export.material_mapping_move_up'
    bl_label = 'Move Up'
    bl_description = 'Move the selected material mapping up one slot'

    @classmethod
    def poll(cls, context: Context):
        operator = get_collection_export_operator_from_context(context)
        if operator is None:
            return False
        return operator.material_mapping_index > 0

    def execute(self, context: 'Context') -> Union[Set[str], Set[int]]:
        operator = get_collection_export_operator_from_context(context)

        if operator is None:
            return {'INVALID_CONTEXT'}

        operator.material_mapping.move(operator.material_mapping_index, operator.material_mapping_index - 1)
        operator.material_mapping_index -= 1

        return {'FINISHED'}


class ASE_OT_material_mapping_move_down(Operator):
    bl_idname = 'ase_export.material_mapping_move_down'
    bl_label = 'Move Down'
    bl_description = 'Move the selected material mapping down one slot'

    @classmethod
    def poll(cls, context: Context):
        operator = get_collection_export_operator_from_context(context)
        if operator is None:
            return False
        return operator.material_mapping_index < len(operator.material_mapping) - 1

    def execute(self, context: 'Context') -> Union[Set[str], Set[int]]:
        operator = get_collection_export_operator_from_context(context)

        if operator is None:
            return {'INVALID_CONTEXT'}

        operator.material_mapping.move(operator.material_mapping_index, operator.material_mapping_index + 1)
        operator.material_mapping_index += 1

        return {'FINISHED'}


class ASE_OT_material_list_move_up(Operator):
    bl_idname = 'ase_export.material_list_item_move_up'
    bl_label = 'Move Up'
    bl_options = {'INTERNAL'}
    bl_description = 'Move the selected material up one slot'

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'ase_export')
        return pg.material_list_index > 0

    def execute(self, context):
        pg = getattr(context.scene, 'ase_export')
        pg.material_list.move(pg.material_list_index, pg.material_list_index - 1)
        pg.material_list_index -= 1
        return {'FINISHED'}


class ASE_OT_material_list_move_down(Operator):
    bl_idname = 'ase_export.material_list_item_move_down'
    bl_label = 'Move Down'
    bl_options = {'INTERNAL'}
    bl_description = 'Move the selected material down one slot'

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'ase_export')
        return pg.material_list_index < len(pg.material_list) - 1

    def execute(self, context):
        pg = getattr(context.scene, 'ase_export')
        pg.material_list.move(pg.material_list_index, pg.material_list_index + 1)
        pg.material_list_index += 1
        return {'FINISHED'}


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


class ASE_OT_material_names_populate(Operator):
    bl_idname = 'ase_export.material_names_populate'
    bl_label = 'Populate Material Names List'
    bl_description = 'Populate the material names with the materials used by objects in the collection'

    def execute(self, context):
        collection = get_collection_from_context(context)
        operator = get_collection_export_operator_from_context(context)
        if operator is None:
            return {'CANCELLED'}

        from .dfs import dfs_collection_objects

        mesh_objects = list(map(lambda x: x.obj, filter(lambda x: x.obj.type == 'MESH', dfs_collection_objects(collection))))

        # Exclude objects that are not visible.
        materials = get_unique_materials(context.evaluated_depsgraph_get(), mesh_objects)

        operator.material_mapping.clear()
        for material in materials:
            m = operator.material_mapping.add()
            m.key = material.name
            m.value = material.name

        return {'FINISHED'}


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
        pg = context.scene.ase_export

        flow = layout.grid_flow()
        flow.use_property_split = True
        flow.use_property_decorate = False

        materials_header, materials_panel = layout.panel('Materials', default_closed=False)
        materials_header.label(text='Materials')

        if materials_panel:
            row = materials_panel.row()
            row.template_list('ASE_UL_materials', '', pg, 'material_list', pg, 'material_list_index')
            col = row.column(align=True)
            col.operator(ASE_OT_material_list_move_up.bl_idname, icon='TRIA_UP', text='')
            col.operator(ASE_OT_material_list_move_down.bl_idname, icon='TRIA_DOWN', text='')

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

    def invoke(self, context: 'Context', event: 'Event' ) -> Union[Set[str], Set[int]]:
        from .dfs import dfs_view_layer_objects

        mesh_objects = list(map(lambda x: x.obj, filter(lambda x: x.is_selected and x.obj.type == 'MESH', dfs_view_layer_objects(context.view_layer))))

        if len(mesh_objects) == 0:
            self.report({'ERROR'}, 'No mesh objects selected')
            return {'CANCELLED'}

        pg = getattr(context.scene, 'ase_export')

        try:
            populate_material_list(context.evaluated_depsgraph_get(), mesh_objects, pg.material_list)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        self.filepath = f'{context.active_object.name}.ase'

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        pg = getattr(context.scene, 'ase_export')

        options = ASEBuildOptions()
        options.object_eval_state = self.object_eval_state
        options.should_export_vertex_colors = pg.should_export_vertex_colors
        options.vertex_color_mode = pg.vertex_color_mode
        options.has_vertex_colors = len(get_vertex_color_attributes_from_objects(context.selected_objects)) > 0
        options.vertex_color_attribute = pg.vertex_color_attribute
        options.materials = [x.material for x in pg.material_list]
        options.should_invert_normals = pg.should_invert_normals
        options.scct_versus_mcdcx_flip = pg.scct_versus_mcdcx_flip

        match self.transform_source:
            case 'SCENE':
                transform_source = getattr(context.scene, 'ase_settings')
            case 'OBJECT':
                transform_source = self

        options.scale = transform_source.scale
        options.forward_axis = transform_source.forward_axis
        options.up_axis = transform_source.up_axis

        from .dfs import dfs_view_layer_objects

        dfs_objects = list(filter(lambda x: x.is_selected and x.obj.type == 'MESH', dfs_view_layer_objects(context.view_layer)))

        try:
            ase = build_ase(context, options, dfs_objects)

            # Calculate some statistics about the ASE file to display in the console.
            object_count = len(ase.geometry_objects)
            material_count = len(ase.materials)
            face_count = sum(len(x.faces) for x in ase.geometry_objects)
            vertex_count = sum(len(x.vertices) for x in ase.geometry_objects)

            ASEWriter().write(self.filepath, ase)
            self.report({'INFO'}, f'ASE exported successfully ({object_count} objects, {material_count} materials, {face_count} faces, {vertex_count} vertices)')
            return {'FINISHED'}
        except ASEBuildError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


export_space_items = [
    ('WORLD', 'World Space', 'Export the collection in world space'),
    ('INSTANCE', 'Instance Space', 'Export the collection in instance space'),
    ('OBJECT', 'Object Space', 'Export the collection in the active object\'s local space'),
]


class ASE_OT_export_collection(Operator, ExportHelper, TransformSourceMixin, TransformMixin, MaterialModeMixin):
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
    material_mapping: CollectionProperty(name='Materials', type=ASE_PG_key_value)
    material_mapping_index: IntProperty(name='Index', default=0)
    export_space: EnumProperty(name='Export Space', items=export_space_items, default='INSTANCE')

    def draw(self, context):
        layout = self.layout

        flow = layout.grid_flow()
        flow.use_property_split = True
        flow.use_property_decorate = False

        materials_header, materials_panel = layout.panel('Materials', default_closed=True)
        materials_header.label(text='Materials')

        if materials_panel:
            materials_panel.prop(self, 'material_mode', text='Material Mode')
            if self.material_mode == 'MANUAL':
                row = materials_panel.row()
                row.template_list(ASE_UL_material_names.bl_idname, '', self, 'material_mapping', self, 'material_mapping_index')
                col = row.column(align=True)
                col.operator(ASE_OT_material_mapping_add.bl_idname, icon='ADD', text='')
                col.operator(ASE_OT_material_mapping_remove.bl_idname, icon='REMOVE', text='')
                col.separator()
                col.operator(ASE_OT_material_mapping_move_up.bl_idname, icon='TRIA_UP', text='')
                col.operator(ASE_OT_material_mapping_move_down.bl_idname, icon='TRIA_DOWN', text='')
                col.separator()
                col.operator(ASE_OT_material_names_populate.bl_idname, icon='FILE_REFRESH', text='')

        transform_header, transform_panel = layout.panel('Transform', default_closed=True)
        transform_header.label(text='Transform')

        if transform_panel:
            transform_panel.use_property_split = True
            transform_panel.use_property_decorate = False
            transform_panel.prop(self, 'transform_source')

            flow = transform_panel.grid_flow()
            match self.transform_source:
                case 'SCENE':
                    transform_source = getattr(context.scene, 'ase_settings')
                    flow.enabled = False
                case 'OBJECT':
                    transform_source = self

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
            advanced_panel.prop(self, 'export_space')

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection)

        options = ASEBuildOptions()
        options.object_eval_state = self.object_eval_state

        match self.transform_source:
            case 'SCENE':
                transform_source = getattr(context.scene, 'ase_settings')
            case 'OBJECT':
                transform_source = self

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
            case 'BONE':
                options.transform = Matrix

        from .dfs import dfs_collection_objects

        dfs_objects = list(filter(lambda x: x.obj.type == 'MESH', dfs_collection_objects(collection)))
        mesh_objects = [x.obj for x in dfs_objects]

        # Get all the materials used by the objects in the collection.
        options.materials = get_unique_materials(context.evaluated_depsgraph_get(), mesh_objects)

        if self.material_mode == 'MANUAL':
            # Build material mapping.
            for material_mapping in self.material_mapping:
                options.material_mapping[material_mapping.key] = material_mapping.value

            # Sort the materials based on the order in the material order list, keeping in mind that the material order list
            # may not contain all the materials used by the objects in the collection.
            material_names = [x.key for x in self.material_mapping]
            material_names_map = {x: i for i, x in enumerate(material_names)}

            # Split the list of materials into two lists: one for materials that appear in the material order list, and one
            # for materials that do not. Then append the two lists together, with the ordered materials first.
            ordered_materials = []
            unordered_materials = []
            for material in options.materials:
                if material.name in material_names_map:
                    ordered_materials.append(material)
                else:
                    unordered_materials.append(material)

            ordered_materials.sort(key=lambda x: material_names_map.get(x.name, len(material_names)))
            options.materials = ordered_materials + unordered_materials

        try:
            ase = build_ase(context, options, dfs_objects)
        except ASEBuildError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        try:
            ASEWriter().write(self.filepath, ase)
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
    ASE_OT_material_list_move_down,
    ASE_OT_material_list_move_up,
    ASE_OT_material_mapping_add,
    ASE_OT_material_mapping_remove,
    ASE_OT_material_mapping_move_down,
    ASE_OT_material_mapping_move_up,
    ASE_OT_material_names_populate,
    ASE_PT_export_scene_settings,
    ASE_FH_export,
)
