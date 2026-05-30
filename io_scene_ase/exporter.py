from abc import ABCMeta, abstractmethod
from collections import abc
from typing import Iterable, List, Literal, cast, Optional

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator, Material, UILayout, UIList, Object, FileHandler, Event, Context, SpaceProperties, \
    Collection, Panel, Depsgraph
from mathutils import Matrix, Vector

from .builder import ASEBuildOptions, ASEBuildError, build_ase
from .writer import write_ase
from .properties import AseExportMixin, TransformMixin, MaterialMappingMixin, VertexColorMixin, get_vertex_color_attributes_from_objects
from .dfs import dfs_collection_objects, dfs_objects_recursive


def _get_unique_materials(depsgraph: Depsgraph, mesh_objects: Iterable[Object]) -> List[Material]:
    materials = []
    for mesh_object in mesh_objects:
        eo = mesh_object.evaluated_get(depsgraph)
        for i, material_slot in enumerate(eo.material_slots):
            material = material_slot.material
            if material not in materials:
                materials.append(material)
    return materials


def _get_collection_from_context(context: Context) -> Optional[Collection]:
    if context.space_data.type != 'PROPERTIES':
        return None

    space_data = cast(SpaceProperties, context.space_data)

    if space_data.use_pin_id:
        return cast(Collection, space_data.pin_id)
    else:
        return context.collection


def _get_collection_export_operator_from_context(context: Context) -> ASE_OT_export_collection | None:
    collection = _get_collection_from_context(context)
    if collection is None or collection.active_exporter_index is None:
        return None
    if 0 > collection.active_exporter_index >= len(collection.exporters):
        return None
    exporter = collection.exporters[collection.active_exporter_index]
    # TODO: make sure this is actually an ASE exporter.
    return exporter.export_properties


class ObjectsSource:
    __metaclass__ = ABCMeta

    @staticmethod
    @abstractmethod
    def _get_objects(context: Context) -> List[Object]:
        """Hey"""


class ObjectsSourceCollection(ObjectsSource):
    @staticmethod
    def _get_objects(context: Context) -> List[Object]:
        collection = _get_collection_from_context(context)
        operator = _get_collection_export_operator_from_context(context)
        if collection is None or operator is None:
            return []
        return list(map(lambda x: x.obj, filter(lambda x: x.obj.type == 'MESH', dfs_collection_objects(collection))))


class ObjectsSourceScene(ObjectsSource):
    @staticmethod
    def _get_objects(context: Context) -> List[Object]:
        if context.selected_objects is None:
            return []
        return list(map(lambda x: x.obj, filter(lambda x: x.obj.type == 'MESH', dfs_objects_recursive(context.selected_objects))))


class MaterialsSource(ObjectsSource):
    @classmethod
    def _get_materials(cls, context: Context) -> List[Material]:
        return _get_unique_materials(context.evaluated_depsgraph_get(), cls._get_objects(context))


def _get_unique_materials_from_selected_objects(context: Context):
    if context.selected_objects is None:
            return []
    from .dfs import dfs_objects_recursive
    dfs_objects = list(filter(lambda x: x.obj.type == 'MESH', dfs_objects_recursive(context.selected_objects)))
    mesh_objects = list(map(lambda x: x.obj, dfs_objects))
    return _get_unique_materials(context.evaluated_depsgraph_get(), mesh_objects)


class AseExportSource:
    __metaclass__ = ABCMeta

    @staticmethod
    @abstractmethod
    def _get_props(context) -> AseExportMixin | None:
        pass


class AseExportSourceCollection(AseExportSource):
    @staticmethod
    def _get_props(context: Context) -> AseExportMixin | None:
        return _get_collection_export_operator_from_context(context)


class AseExportSourceScene(AseExportSource):
    @staticmethod
    def _get_props(context: Context) -> AseExportMixin | None:
        return getattr(context.scene, 'ase_export')


class MaterialMappingAddOperator(Operator, AseExportSource):
    bl_label = 'Add'
    bl_description = 'Add a material mapping to the list'

    def execute(self, context: 'Context'):
        props = self._get_props(context)

        if props is None:
            return {'CANCELLED'}

        material_mapping = props.material_mapping.add()
        material_mapping.key = 'Material'
        props.material_mapping_index = len(props.material_mapping) - 1

        return {'FINISHED'}


class ASE_OT_export_collection_material_mapping_add(MaterialMappingAddOperator, AseExportSourceCollection, ObjectsSourceCollection, MaterialsSource):
    bl_idname = 'ase_export.collection_material_mapping_add'


class ASE_OT_export_scene_material_mapping_add(MaterialMappingAddOperator, AseExportSourceScene, ObjectsSourceScene, MaterialsSource):
    bl_idname = 'ase_export.scene_material_mapping_add'


class MaterialMappingRemoveOperator(Operator, AseExportSource):
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


class ASE_OT_export_collection_material_mapping_remove(MaterialMappingRemoveOperator, AseExportSourceCollection, ObjectsSourceCollection, MaterialsSource):
    bl_idname = 'ase_export.collection_material_mapping_remove'


class ASE_OT_export_scene_material_mapping_remove(MaterialMappingRemoveOperator, AseExportSourceScene, ObjectsSourceScene, MaterialsSource):
    bl_idname = 'ase_export.scene_material_mapping_remove'


class MaterialMappingMoveUpOperator(Operator, AseExportSource):
    bl_label = 'Move Up'
    bl_description = 'Move the selected material mapping up one slot'

    @classmethod
    def poll(cls, context: Context):
        props = cls._get_props(context)
        if props is None:
            return False
        return props.material_mapping_index > 0

    def execute(self, context: 'Context'):
        props = self._get_props(context)

        if props is None:
            return {'CANCELLED'}
    
        props.material_mapping.move(props.material_mapping_index, props.material_mapping_index - 1)
        props.material_mapping_index -= 1

        return {'FINISHED'}


class ASE_OT_export_collection_material_mapping_move_up(AseExportSourceCollection, MaterialMappingMoveUpOperator):
    bl_idname = 'ase_export.collection_material_mapping_move_up'


class ASE_OT_export_scene_material_mapping_move_up(AseExportSourceScene, MaterialMappingMoveUpOperator):
    bl_idname = 'ase_export.scene_material_mapping_move_up'


class MaterialMappingMoveDownOperator(Operator, AseExportSource):
    bl_label = 'Move Down'
    bl_description = 'Move the selected material mapping down one slot'

    @classmethod
    def poll(cls, context: Context):
        props = cls._get_props(context)
        if props is None:
            return False
        return props.material_mapping_index < len(props.material_mapping) - 1

    def execute(self, context: 'Context'):
        props = self._get_props(context)

        if props is None:
            return {'CANCELLED'}
    
        props.material_mapping.move(props.material_mapping_index, props.material_mapping_index + 1)
        props.material_mapping_index += 1

        return {'FINISHED'}


class ASE_OT_export_collection_material_mapping_move_down(AseExportSourceCollection, MaterialMappingMoveDownOperator):
    bl_idname = 'ase_export.collection_material_mapping_move_down'


class ASE_OT_export_scene_material_mapping_move_down(AseExportSourceCollection, MaterialMappingMoveDownOperator):
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


def _vertex_color_attributes_populate(props: VertexColorMixin, mesh_objects: Iterable[Object]):
    props.vertex_color_attributes.clear()
    for name in get_vertex_color_attributes_from_objects(mesh_objects):
        x = props.vertex_color_attributes.add()
        x.name = name


class VertexColorAttributesPopulateOperator(Operator, ObjectsSource, VertexColorMixin, AseExportSource):
    bl_label = 'Populate Vertex Colors'
    bl_description = 'Populate the vertex colors list with those used by the relevant objects'

    def execute(self, context: Context):
        objects = self._get_objects(context)
        props = self._get_props(context)
        if props is None:
            return {'CANCELLED'}
        _vertex_color_attributes_populate(props, objects)
        return {'FINISHED'}


class ASE_OT_export_scene_vertex_color_attributes_populate(VertexColorAttributesPopulateOperator, ObjectsSourceScene, AseExportSourceScene):
    bl_idname = 'ase_export.scene_vertex_color_attributes_populate'


class ASE_OT_export_collection_vertex_color_attributes_populate(VertexColorAttributesPopulateOperator, ObjectsSourceCollection, AseExportSourceCollection):
    bl_idname = 'ase_export.collection_vertex_color_attributes_populate'


class MaterialMappingPopulateOperator(AseExportSource, MaterialsSource, Operator):
    bl_label = 'Populate Material Mapping'
    bl_description = 'Populate the material mapping with the materials used by the relevant objects'

    def execute(self, context):
        props = self._get_props(context)
        if props is None:
            return {'CANCELLED'}
        materials = self._get_materials(context)
        _material_mapping_populate(props, materials)
        return {'FINISHED'}


class ASE_OT_export_collection_material_mapping_populate(MaterialMappingPopulateOperator, AseExportSourceCollection, ObjectsSourceCollection, MaterialsSource):
    bl_idname = 'ase_export.collection_material_mapping_populate'


class ASE_OT_export_scene_material_mapping_populate(MaterialMappingPopulateOperator, AseExportSourceScene, ObjectsSourceScene, MaterialsSource):
    bl_idname = 'ase_export.scene_material_mapping_populate'


def _get_selected_mesh_objects(context: Context):
    if context.selected_objects is None:
        return []
    dfs_objects = list(filter(lambda x: x.obj.type == 'MESH', dfs_objects_recursive(context.selected_objects)))
    return [x.obj for x in dfs_objects]


def _options_build(options, props: AseExportMixin, mesh_objects: Iterable[Object]):
    options.object_eval_state = props.object_eval_state
    options.should_export_vertex_colors = props.should_export_vertex_colors
    options.vertex_color_mode = props.vertex_color_mode
    options.has_vertex_colors = len(get_vertex_color_attributes_from_objects(mesh_objects)) > 0
    options.vertex_color_attribute = props.vertex_color_attribute
    options.should_invert_normals = props.should_invert_normals
    options.scct_versus_mcdcx_flip = props.scct_versus_mcdcx_flip

    match props.transform_source:
        case 'SCENE':
            transform_source = getattr(bpy.context.scene, 'ase_settings')
        case 'CUSTOM':
            transform_source = props
        case _:
            assert False, f'Unknown transform source {props.transform_source}'

    options.scale = transform_source.scale
    options.forward_axis = transform_source.forward_axis
    options.up_axis = transform_source.up_axis

    options.materials = _get_unique_materials(bpy.context.evaluated_depsgraph_get(), mesh_objects)
    if props.material_mode == 'MANUAL':
        options.materials = apply_material_mapping(options.materials, props)


class ASE_OT_export(Operator, ExportHelper):
    bl_idname = 'io_scene_ase.ase_export'
    bl_label = 'Export ASE'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_description = 'Export selected objects to ASE'
    filename_ext = '.ase'
    filter_glob: StringProperty(default="*.ase", options={'HIDDEN'}, maxlen=255)

    @classmethod
    def poll(cls, context):
        if not context.selected_objects or not any(x.type == 'MESH' or (x.type == 'EMPTY' and x.instance_collection is not None) for x in context.selected_objects):
            cls.poll_message_set('At least one mesh or instanced collection must be selected')
            return False
        return True

    def draw(self, context):
        layout = self.layout
        assert layout is not None
        pg = cast(AseExportMixin, context.scene.ase_export)
        
        _draw_materials_panel(layout, pg,
                              ASE_OT_export_scene_material_mapping_populate.bl_idname,
                              ASE_OT_export_scene_material_mapping_add.bl_idname,
                              ASE_OT_export_scene_material_mapping_remove.bl_idname,
                              ASE_OT_export_scene_material_mapping_move_up.bl_idname,
                              ASE_OT_export_scene_material_mapping_move_down.bl_idname,
                              )
        _draw_transform_panel(layout, pg)
        _draw_vertex_colors_panel(layout, pg, ASE_OT_export_scene_vertex_color_attributes_populate.bl_idname)
        _draw_advanced_panel(layout, pg)

    def invoke(self, context: Context, event: Event):
        pg = cast(AseExportMixin, getattr(context.scene, 'ase_export'))

        # Populate the material mapping list and vertex color attributes.
        materials = _get_unique_materials_from_selected_objects(context)
        _material_mapping_populate(pg, materials)

        mesh_objects = _get_selected_mesh_objects(context)
        _vertex_color_attributes_populate(pg, mesh_objects)

        if context.active_object is not None:
            self.filepath = f'{context.active_object.name}.ase'

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        pg = cast(AseExportMixin, getattr(context.scene, 'ase_export'))

        mesh_objects = _get_selected_mesh_objects(context)
        options = ASEBuildOptions()
        _options_build(options, pg, mesh_objects)

        try:
            assert context.selected_objects is not None
            dfs_objects = dfs_objects_recursive(context.selected_objects)
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


def _draw_materials_panel(
        layout: UILayout,
        props: MaterialMappingMixin,
        populate_operator_idname: str,
        add_operator_idname: str,
        remove_operator_idname: str,
        move_up_operator_idname: str,
        move_down_operator_idname: str
        ):
    materials_header, materials_panel = layout.panel('Materials', default_closed=False)
    materials_header.label(text='Materials')

    if materials_panel:
        flow = materials_panel.grid_flow()
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(props, 'material_mode')
        if props.material_mode == 'MANUAL':
            row = flow.row()
            row.template_list(ASE_UL_material_names.bl_idname, '', props, 'material_mapping', props, 'material_mapping_index')
            col = row.column(align=True)
            col.operator(populate_operator_idname, icon='FILE_REFRESH', text='')
            col.separator()
            col.operator(add_operator_idname, icon='ADD', text='')
            col.operator(remove_operator_idname, icon='REMOVE', text='')
            col.separator()
            col.operator(move_up_operator_idname, icon='TRIA_UP', text='')
            col.operator(move_down_operator_idname, icon='TRIA_DOWN', text='')


def _draw_vertex_colors_panel(layout: UILayout, props: VertexColorMixin, populate_operator_idname: str):
    # has_vertex_colors = len(props.vertex_color_attributes) > 0
    vertex_colors_header, vertex_colors_panel = layout.panel_prop(props, 'should_export_vertex_colors')
    row = vertex_colors_header.row()
    row.prop(props, 'should_export_vertex_colors', text='Vertex Colors')

    if vertex_colors_panel:
        vertex_colors_panel.use_property_split = True
        vertex_colors_panel.use_property_decorate = False
        vertex_colors_panel.prop(props, 'vertex_color_mode', text='Mode')
        if props.vertex_color_mode == 'EXPLICIT':
            row.use_property_split = False
            row = vertex_colors_panel.row()
            split = row.split(factor=0.4, align=True)
            split.alignment = 'RIGHT'
            split.label(text='Attribute')
            row = split.row(align=True)
            row.operator(populate_operator_idname, icon='FILE_REFRESH', text='')
            row.prop(props, 'vertex_color_attribute', icon='GROUP_VCOL', text='')


def _draw_transform_controls(layout: UILayout, props: TransformMixin):
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(props, 'scale')
        layout.prop(props, 'forward_axis')
        layout.prop(props, 'up_axis')


def _draw_transform_panel(layout: UILayout, props: TransformMixin):
    transform_header, transform_panel = layout.panel('Transform', default_closed=True)
    transform_header.label(text='Transform')

    if transform_panel:
        transform_panel.use_property_split = True
        transform_panel.use_property_decorate = False

        if hasattr(props, 'export_space'):
            transform_panel.prop(props, 'export_space')

        transform_panel.prop(props, 'transform_source')

        flow = transform_panel.grid_flow()
        match props.transform_source:
            case 'SCENE':
                transform_source = getattr(bpy.context.scene, 'ase_settings')
                flow.enabled = False
            case 'CUSTOM':
                transform_source = props
            case _:
                assert False, f'Unknown transform source {props.transform_source}'

        _draw_transform_controls(flow, transform_source)


def _draw_advanced_panel(layout: UILayout, props):
    advanced_header, advanced_panel = layout.panel('Advanced', default_closed=True)
    advanced_header.label(text='Advanced')

    if advanced_panel:
        advanced_panel.use_property_split = True
        advanced_panel.use_property_decorate = False
        advanced_panel.prop(props, 'object_eval_state')

        fixes_header, fixes_panel = advanced_panel.panel('Fixes', default_closed=True)
        fixes_header.label(text='Fixes')

        if fixes_panel:
            fixes_panel.use_property_split = True
            fixes_panel.use_property_decorate = False
            fixes_panel.prop(props, 'should_invert_normals')
            fixes_panel.prop(props, 'scct_versus_mcdcx_flip')


class ASE_OT_export_collection(Operator, ExportHelper, AseExportMixin):
    bl_idname = 'io_scene_ase.ase_export_collection'
    bl_label = 'Export collection to ASE'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_description = 'Export collection to ASE'
    filename_ext = '.ase'
    filter_glob: StringProperty(default="*.ase", options={'HIDDEN'}, maxlen=255)
    collection: StringProperty()
    export_space: EnumProperty(name='Export Space', items=export_space_items, default='INSTANCE')

    def draw(self, context):
        layout = self.layout
        assert layout is not None

        _draw_materials_panel(layout, self,
                              ASE_OT_export_collection_material_mapping_populate.bl_idname,
                              ASE_OT_export_collection_material_mapping_add.bl_idname,
                              ASE_OT_export_collection_material_mapping_remove.bl_idname,
                              ASE_OT_export_collection_material_mapping_move_up.bl_idname,
                              ASE_OT_export_collection_material_mapping_move_down.bl_idname,
                              )
        _draw_transform_panel(layout, self)
        _draw_vertex_colors_panel(layout, self, ASE_OT_export_collection_vertex_color_attributes_populate.bl_idname)
        _draw_advanced_panel(layout, self)

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection)

        if collection is None:
            return {'CANCELLED'}

        dfs_objects = list(filter(lambda x: x.obj.type == 'MESH', dfs_collection_objects(collection)))

        # Get all the materials used by the objects in the collection.
        mesh_objects = [x.obj for x in dfs_objects]

        options = ASEBuildOptions()
        _options_build(options, self, mesh_objects)

        # Only the collection exporter has the export_space option.
        match self.export_space:
            case 'WORLD':
                options.transform = Matrix.Identity(4)
            case 'INSTANCE':
                options.transform = Matrix.Translation(-Vector(collection.instance_offset))

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
        assert layout is not None

        transform_header, transform_panel = layout.panel('Transform', default_closed=True)
        transform_header.label(text='Transform')

        if transform_panel:
            transform_source = getattr(context.scene, 'ase_settings')
            flow = transform_panel.grid_flow()
            _draw_transform_controls(flow, transform_source)



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

    ASE_OT_export_scene_vertex_color_attributes_populate,
    ASE_OT_export_collection_vertex_color_attributes_populate,

    ASE_PT_export_scene_settings,
    ASE_FH_export,
)
