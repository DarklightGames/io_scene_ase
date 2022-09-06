import bpy_extras
import typing
from bpy.types import UIList, Context, UILayout, AnyType, Operator
from bpy.props import StringProperty, EnumProperty, BoolProperty, PointerProperty, CollectionProperty, IntProperty
from .builder import *
from .writer import *


class AseExportCollectionPropertyGroup(bpy.types.PropertyGroup):
    is_selected: BoolProperty()
    name: StringProperty()
    collection: PointerProperty(type=bpy.types.Collection)


class AseExportPropertyGroup(bpy.types.PropertyGroup):
    collection_list: CollectionProperty(type=AseExportCollectionPropertyGroup)
    collection_list_index: IntProperty()


class ASE_UL_CollectionList(UIList):
    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        collection: bpy.types.Collection = getattr(item, 'collection')
        row = layout.row()
        row.prop(item, 'is_selected', text='')
        row.label(text=collection.name, icon='OUTLINER_COLLECTION')


class AseExportCollectionsSelectAll(Operator):
    bl_idname = 'ase_export.collections_select_all'
    bl_label = 'All'

    def execute(self, context: Context) -> typing.Union[typing.Set[str], typing.Set[int]]:
        pg = getattr(context.scene, 'ase_export')
        for collection in pg.collection_list:
            collection.is_selected = True
        return {'FINISHED'}


class AseExportCollectionsDeselectAll(Operator):
    bl_idname = 'ase_export.collections_deselect_all'
    bl_label = 'None'

    def execute(self, context: Context) -> typing.Union[typing.Set[str], typing.Set[int]]:
        pg = getattr(context.scene, 'ase_export')
        for collection in pg.collection_list:
            collection.is_selected = False
        return {'FINISHED'}


class ASE_OT_ExportOperator(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    bl_idname = 'io_scene_ase.ase_export'  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = 'Export ASE'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    filename_ext = '.ase'
    filter_glob: StringProperty(
        default="*.ase",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be hilighted.
    )
    units: EnumProperty(
        default='U',
        items=(('M', 'Meters', ''),
               ('U', 'Unreal', '')),
        name='Units'
    )
    use_raw_mesh_data: BoolProperty(
        default=False,
        description='No modifiers will be evaluated as part of the exported mesh',
        name='Raw Mesh Data')
    units_scale = {
        'M': 60.352,
        'U': 1.0
    }
    should_use_sub_materials: BoolProperty(
        default=True,
        description='Material format',  # fill this in with a more human-friendly name/description
        name='Use Sub-materials'
    )

    def draw(self, context):
        pg = getattr(context.scene, 'ase_export')
        layout = self.layout
        rows = max(3, min(len(pg.collection_list), 10))
        layout.prop(self, 'units', expand=False)
        layout.prop(self, 'use_raw_mesh_data')
        layout.prop(self, 'should_use_sub_materials')

        # # SELECT ALL/NONE
        # row = layout.row(align=True)
        # row.label(text='Select')
        # row.operator(AseExportCollectionsSelectAll.bl_idname, text='All', icon='CHECKBOX_HLT')
        # row.operator(AseExportCollectionsDeselectAll.bl_idname, text='None', icon='CHECKBOX_DEHLT')
        #
        # layout.template_list('ASE_UL_CollectionList', '', pg, 'collection_list', pg, 'collection_list_index', rows=rows)

    def invoke(self, context: bpy.types.Context, event):
        # TODO: build a list of collections that have meshes in them
        pg = getattr(context.scene, 'ase_export')
        pg.collection_list.clear()
        for collection in bpy.data.collections:
            has_meshes = any(map(lambda x: x.type == 'MESH', collection.objects))
            if has_meshes:
                c = pg.collection_list.add()
                c.collection = collection

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        options = AseBuilderOptions()
        options.scale = self.units_scale[self.units]
        options.use_raw_mesh_data = self.use_raw_mesh_data
        try:
            ase = build_ase(context, options)
            writer_options = AseWriterOptions()
            writer_options.should_use_sub_materials = self.should_use_sub_materials
            AseWriter().write(self.filepath, ase, writer_options)
            self.report({'INFO'}, 'ASE exported successful')
            return {'FINISHED'}
        except AseBuilderError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


__classes__ = (
    AseExportCollectionPropertyGroup,
    AseExportPropertyGroup,
    AseExportCollectionsSelectAll,
    AseExportCollectionsDeselectAll,
    ASE_UL_CollectionList,
    ASE_OT_ExportOperator
)
