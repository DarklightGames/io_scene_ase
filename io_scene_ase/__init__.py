if 'bpy' in locals():
    import importlib
    if 'ase'        in locals(): importlib.reload(ase)
    if 'builder'    in locals(): importlib.reload(builder)
    if 'writer'     in locals(): importlib.reload(writer)
    if 'exporter'   in locals(): importlib.reload(exporter)

import bpy
import bpy.utils.previews
from . import ase
from . import builder
from . import writer
from . import exporter

classes = exporter.classes


def menu_func_export(self, context):
    self.layout.operator(exporter.ASE_OT_export.bl_idname, text='ASCII Scene Export (.ase)')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.ase_export = bpy.props.PointerProperty(type=exporter.ASE_PG_export)

    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    del bpy.types.Scene.ase_export

    for cls in classes:
        bpy.utils.unregister_class(cls)
