import os.path
import typing

from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, CollectionProperty, PointerProperty, IntProperty
from bpy.types import Operator, Material, PropertyGroup, UIList
from .builder import *
from .writer import *


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



class ASE_OT_export(Operator, ExportHelper):
    bl_idname = 'io_scene_ase.ase_export'
    bl_label = 'Export ASE'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    filename_ext = '.ase'
    filter_glob: StringProperty(default="*.ase", options={'HIDDEN'}, maxlen=255)
    use_raw_mesh_data: BoolProperty(default=False, name='Raw Mesh Data', description='No modifiers will be evaluated as part of the exported mesh')

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
            advanced_panel.prop(self, 'use_raw_mesh_data')

    def invoke(self, context: 'Context', event: 'Event' ) -> typing.Union[typing.Set[str], typing.Set[int]]:
        mesh_objects = [x[0] for x in get_mesh_objects(context.selected_objects)]

        pg = getattr(context.scene, 'ase_export')
        populate_material_list(mesh_objects, pg.material_list)

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        options = ASEBuilderOptions()
        options.use_raw_mesh_data = self.use_raw_mesh_data
        pg = getattr(context.scene, 'ase_export')
        options.materials = [x.material for x in pg.material_list]
        try:
            ase = ASEBuilder().build(context, options, context.selected_objects)
            ASEWriter().write(self.filepath, ase)
            self.report({'INFO'}, 'ASE exported successful')
            return {'FINISHED'}
        except ASEBuilderError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class ASE_OT_export_collections(Operator, ExportHelper):
    bl_idname = 'io_scene_ase.ase_export_collections'  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = 'Export Collections to ASE'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    filename_ext = '.ase'
    filter_glob: StringProperty(
        default="*.ase",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be hilighted.
    )
    use_raw_mesh_data: BoolProperty(
        default=False,
        description='No modifiers will be evaluated as part of the exported mesh',
        name='Raw Mesh Data')

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'use_raw_mesh_data')

    def execute(self, context):
        options = ASEBuilderOptions()
        options.use_raw_mesh_data = self.use_raw_mesh_data

        # Iterate over all the visible collections in the scene.
        layer_collections = context.view_layer.layer_collection.children
        collections = [x.collection for x in layer_collections if not x.hide_viewport and not x.exclude]

        context.window_manager.progress_begin(0, len(layer_collections))

        for i, collection in enumerate(collections):
            # Iterate over all the objects in the collection.
            mesh_objects = get_mesh_objects(collection.all_objects)
            # Get all the materials used by the objects in the collection.
            options.materials = get_unique_materials([x[0] for x in mesh_objects])

            print(collection, options.materials)

            try:
                ase = ASEBuilder().build(context, options, collection.all_objects)
                dirname = os.path.dirname(self.filepath)
                filepath = os.path.join(dirname, collection.name + '.ase')
                ASEWriter().write(filepath, ase)
            except ASEBuilderError as e:
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}

            context.window_manager.progress_update(i)

        context.window_manager.progress_end()

        self.report({'INFO'}, f'{len(collections)} collections exported successfully')

        return {'FINISHED'}


classes = (
    ASE_PG_material,
    ASE_UL_materials,
    ASE_PG_export,
    ASE_OT_export,
    ASE_OT_export_collections,
    ASE_OT_material_list_move_down,
    ASE_OT_material_list_move_up,
)
