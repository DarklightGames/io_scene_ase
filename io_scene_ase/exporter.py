import os.path

from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, EnumProperty, BoolProperty
from bpy.types import Operator
from .builder import *
from .writer import *


class ASE_OT_ExportOperator(Operator, ExportHelper):
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

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'units', expand=False)
        layout.prop(self, 'use_raw_mesh_data')

    def execute(self, context):
        options = ASEBuilderOptions()
        options.scale = self.units_scale[self.units]
        options.use_raw_mesh_data = self.use_raw_mesh_data
        try:
            ase = ASEBuilder().build(context, options, context.selected_objects)
            ASEWriter().write(self.filepath, ase)
            self.report({'INFO'}, 'ASE exported successful')
            return {'FINISHED'}
        except ASEBuilderError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class ASE_OT_ExportCollections(Operator, ExportHelper):
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

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'units', expand=False)
        layout.prop(self, 'use_raw_mesh_data')

    def execute(self, context):
        options = ASEBuilderOptions()
        options.scale = self.units_scale[self.units]
        options.use_raw_mesh_data = self.use_raw_mesh_data

        # Iterate over all the visible collections in the scene.
        layer_collections = context.view_layer.layer_collection.children
        collections = [x.collection for x in layer_collections if not x.hide_viewport]

        context.window_manager.progress_begin(0, len(layer_collections))

        for i, collection in enumerate(collections):
            print(type(collection), collection, collection.hide_viewport)
            # Iterate over all the objects in the collection.
            try:
                ase = ASEBuilder().build(context, options, collection.objects)
                dirname = os.path.dirname(self.filepath)
                ASEWriter().write(os.path.join(dirname, collection.name + '.ase'), ase)
            except ASEBuilderError as e:
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}

            context.window_manager.progress_update(i)

        context.window_manager.progress_end()

        self.report({'INFO'}, f'{len(collections)} collections exported successfully')

        return {'FINISHED'}
