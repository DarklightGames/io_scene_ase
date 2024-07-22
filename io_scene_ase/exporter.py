import os.path
from typing import Iterable, List, Set, Union

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, CollectionProperty, PointerProperty, IntProperty, EnumProperty
from bpy.types import Operator, Material, PropertyGroup, UIList, Object, FileHandler, Collection
from .builder import ASEBuilder, ASEBuilderOptions, ASEBuilderError, get_mesh_objects
from .writer import ASEWriter


class ASE_PG_material(PropertyGroup):
    material: PointerProperty(type=Material)


class ASE_PG_export(PropertyGroup):
    material_list: CollectionProperty(name='Materials', type=ASE_PG_material)
    material_list_index: IntProperty(name='Index', default=0)


def get_unique_materials(mesh_objects: Iterable[Object]) -> List[Material]:
    materials = set()
    for mesh_object in mesh_objects:
        for i, material_slot in enumerate(mesh_object.material_slots):
            material = material_slot.material
            if material is None:
                raise RuntimeError('Material slot cannot be empty (index ' + str(i) + ')')
            materials.add(material)
    return list(materials)


def populate_material_list(mesh_objects: Iterable[Object], material_list):
    materials = get_unique_materials(mesh_objects)
    material_list.clear()
    for index, material in enumerate(materials):
        m = material_list.add()
        m.material = material
        m.index = index


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
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        row.prop(item.material, 'name', text='', emboss=False, icon_value=layout.icon(item.material))


object_eval_state_items = (
    ('EVALUATED', 'Evaluated', 'Use data from fully evaluated object'),
    ('ORIGINAL', 'Original', 'Use data from original object with no modifiers applied'),
)


class ASE_OT_export(Operator, ExportHelper):
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
        if not any(x.type == 'MESH' for x in context.selected_objects):
            cls.poll_message_set('At least one mesh must be selected')
            return False
        return True

    def draw(self, context):
        layout = self.layout

        materials_header, materials_panel = layout.panel('Materials', default_closed=False)
        materials_header.label(text='Materials')

        if materials_panel:
            row = materials_panel.row()
            row.template_list('ASE_UL_materials', '', context.scene.ase_export, 'material_list', context.scene.ase_export, 'material_list_index')
            col = row.column(align=True)
            col.operator(ASE_OT_material_list_move_up.bl_idname, icon='TRIA_UP', text='')
            col.operator(ASE_OT_material_list_move_down.bl_idname, icon='TRIA_DOWN', text='')

        advanced_header, advanced_panel = layout.panel('Advanced', default_closed=True)
        advanced_header.label(text='Advanced')

        if advanced_panel:
            advanced_panel.use_property_split = True
            advanced_panel.use_property_decorate = False
            advanced_panel.prop(self, 'object_eval_state')

    def invoke(self, context: 'Context', event: 'Event' ) -> Union[Set[str], Set[int]]:
        mesh_objects = [x[0] for x in get_mesh_objects(context.selected_objects)]

        pg = getattr(context.scene, 'ase_export')
        populate_material_list(mesh_objects, pg.material_list)

        self.filepath = f'{context.active_object.name}.ase'

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        options = ASEBuilderOptions()
        options.object_eval_state = self.object_eval_state
        pg = getattr(context.scene, 'ase_export')
        options.materials = [x.material for x in pg.material_list]
        try:
            ase = ASEBuilder().build(context, options, context.selected_objects)
            ASEWriter().write(self.filepath, ase)
            self.report({'INFO'}, 'ASE exported successfully')
            return {'FINISHED'}
        except ASEBuilderError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class ASE_OT_export_collection(Operator, ExportHelper):
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


    def draw(self, context):
        layout = self.layout

        advanced_header, advanced_panel = layout.panel('Advanced', default_closed=True)
        advanced_header.label(text='Advanced')

        if advanced_panel:
            advanced_panel.use_property_split = True
            advanced_panel.use_property_decorate = False
            advanced_panel.prop(self, 'object_eval_state')

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection)

        options = ASEBuilderOptions()
        options.object_eval_state = self.object_eval_state

        # Iterate over all the objects in the collection.
        mesh_objects = get_mesh_objects(collection.all_objects)
        # Get all the materials used by the objects in the collection.
        options.materials = get_unique_materials([x[0] for x in mesh_objects])

        try:
            ase = ASEBuilder().build(context, options, collection.all_objects)
        except ASEBuilderError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        try:
            ASEWriter().write(self.filepath, ase)
        except PermissionError as e:
            self.report({'ERROR'}, 'ASCII Scene Export: ' + str(e))
            return {'CANCELLED'}

        return {'FINISHED'}


class ASE_FH_export(FileHandler):
    bl_idname = 'ASE_FH_export'
    bl_label = 'ASCII Scene Export'
    bl_export_operator = ASE_OT_export_collection.bl_idname
    bl_file_extensions = '.ase'



classes = (
    ASE_PG_material,
    ASE_UL_materials,
    ASE_PG_export,
    ASE_OT_export,
    ASE_OT_export_collection,
    ASE_OT_material_list_move_down,
    ASE_OT_material_list_move_up,
    ASE_FH_export,
)
