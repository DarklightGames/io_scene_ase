import bpy
from bpy.props import StringProperty
import bpy_extras



from asepy import read_ase


class ASE_OT_ImportOperator(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = 'io_scene_ase.ase_export'  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = 'Export ASE'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    filename_ext = '.ase'
    filter_glob: StringProperty(
        default="*.ase",
        options={'HIDDEN'},
        maxlen=255,
    )


classes = (
    ASE_OT_ImportOperator
)
