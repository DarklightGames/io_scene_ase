import bpy
import bpy_extras
from bpy.props import StringProperty, FloatProperty, EnumProperty
from .builder import *
from .writer import *


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
        items=(('M', 'Meters', ''),
               ('U', 'Unreal', '')),
        name='Units'
    )

    units_scale = {
        'M': 60.352,
        'U': 1.0
    }

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'units', expand=False)

    def execute(self, context):
        options = ASEBuilderOptions()
        options.scale = self.units_scale[self.units]
        try:
            ase = ASEBuilder().build(context, options)
            ASEWriter().write(self.filepath, ase)
            self.report({'INFO'}, 'ASE exported successful')
            return {'FINISHED'}
        except ASEBuilderError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
