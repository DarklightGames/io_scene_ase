bl_info = {
    'name': 'ASCII Scene Export (ASE)',
    'description': 'Export ASE (ASCII Scene Export) files',
    'author': 'Colin Basnett (Darklight Games)',
    'version': (2, 0, 0),
    'blender': (4, 0, 0),
    'location': 'File > Import-Export',
    'warning': 'This add-on is under development.',
    'wiki_url': 'https://github.com/DarklightGames/io_scene_ase/wiki',
    'tracker_url': 'https://github.com/DarklightGames/io_scene_ase/issues',
    'support': 'COMMUNITY',
    'category': 'Import-Export'
}

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

classes = (
    exporter.ASE_OT_ExportOperator,
    exporter.ASE_OT_ExportCollections,
)


def menu_func_export(self, context):
    self.layout.operator(exporter.ASE_OT_ExportOperator.bl_idname, text='ASCII Scene Export (.ase)')
    self.layout.operator(exporter.ASE_OT_ExportCollections.bl_idname, text='ASCII Scene Export Collections (.ase)')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    for cls in classes:
        bpy.utils.unregister_class(cls)
