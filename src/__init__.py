bl_info = {
    'name': 'ASCII Scene Export',
    'description': 'Export ASE (ASCII Scene Export) files',
    'author': 'Colin Basnett (Darklight Games)',
    'version': (1, 1, 2),
    'blender': (2, 90, 0),
    'location': 'File > Import-Export',
    'warning': 'This add-on is under development.',
    'wiki_url': 'https://github.com/DarklightGames/io_scene_ase/wiki',
    'tracker_url': 'https://github.com/DarklightGames/io_scene_ase/issues',
    'support': 'COMMUNITY',
    'category': 'Import-Export'
}

import subprocess
import os
import sys
from collections import namedtuple
import bpy


def install_pip():
    """
    Installs pip if not already present. Please note that ensurepip.bootstrap() also calls pip, which adds the
    environment variable PIP_REQ_TRACKER. After ensurepip.bootstrap() finishes execution, the directory doesn't exist
    anymore. However, when subprocess is used to call pip, in order to install a package, the environment variables
    still contain PIP_REQ_TRACKER with the now nonexistent path. This is a problem since pip checks if PIP_REQ_TRACKER
    is set and if it is, attempts to use it as temp directory. This would result in an error because the
    directory can't be found. Therefore, PIP_REQ_TRACKER needs to be removed from environment variables.
    :return:
    """

    try:
        # Check if pip is already installed
        subprocess.run([sys.executable, '-m', 'pip', '--version'], check=True)
    except subprocess.CalledProcessError:
        import ensurepip

        ensurepip.bootstrap()
        os.environ.pop('PIP_REQ_TRACKER', None)


def install_and_import_module(module_name, package_name=None, global_name=None):
    """
    Installs the package through pip and attempts to import the installed module.
    :param module_name: Module to import.
    :param package_name: (Optional) Name of the package that needs to be installed. If None it is assumed to be equal
       to the module_name.
    :param global_name: (Optional) Name under which the module is imported. If None the module_name will be used.
       This allows to import under a different name with the same effect as e.g. "import numpy as np" where "np" is
       the global_name under which the module can be accessed.
    :raises: subprocess.CalledProcessError and ImportError
    """
    if package_name is None:
        package_name = module_name

    if global_name is None:
        global_name = module_name

    # Blender disables the loading of user site-packages by default. However, pip will still check them to determine
    # if a dependency is already installed. This can cause problems if the packages is installed in the user
    # site-packages and pip deems the requirement satisfied, but Blender cannot import the package from the user
    # site-packages. Hence, the environment variable PYTHONNOUSERSITE is set to disallow pip from checking the user
    # site-packages. If the package is not already installed for Blender's Python interpreter, it will then try to.
    # The paths used by pip can be checked with `subprocess.run([bpy.app.binary_path_python, "-m", "site"], check=True)`

    # Create a copy of the environment variables and modify them for the subprocess call
    environ_copy = dict(os.environ)
    environ_copy['PYTHONNOUSERSITE'] = '1'

    subprocess.run([sys.executable, '-m', 'pip', 'install', package_name], check=True, env=environ_copy)

    # The installation succeeded, attempt to import the module again
    import_module(module_name, global_name)


class EXAMPLE_OT_install_dependencies(bpy.types.Operator):
    bl_idname = 'io_scene_ase.install_dependencies'
    bl_label = 'Install dependencies'
    bl_description = ('Downloads and installs the required python packages for this add-on. '
                      'Internet connection is required. Blender may have to be started with '
                      'elevated permissions in order to install the package')
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(self, context):
        # Deactivate when dependencies have been installed
        return not dependencies_installed

    def execute(self, context):
        try:
            install_pip()
            for dependency in dependencies:
                install_and_import_module(module_name=dependency.module,
                                          package_name=dependency.package,
                                          global_name=dependency.name)
        except (subprocess.CalledProcessError, ImportError) as err:
            self.report({'ERROR'}, str(err))
            return {'CANCELLED'}

        global dependencies_installed
        dependencies_installed = True

        # Register the panels, operators, etc. since dependencies are installed
        for cls in classes:
            bpy.utils.register_class(cls)

        return {'FINISHED'}


class EXAMPLE_preferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        layout.operator(EXAMPLE_OT_install_dependencies.bl_idname, icon='CONSOLE')


Dependency = namedtuple('Dependency', ['module', 'package', 'name'])

dependencies = (Dependency(module='asepy', package=None, name=None),)

dependencies_installed = False


def import_module(module_name, global_name=None, reload=True):
    """
    Import a module.
    :param module_name: Module to import.
    :param global_name: (Optional) Name under which the module is imported. If None the module_name will be used.
       This allows to import under a different name with the same effect as e.g. "import numpy as np" where "np" is
       the global_name under which the module can be accessed.
    :raises: ImportError and ModuleNotFoundError
    """
    if global_name is None:
        global_name = module_name

    if global_name in globals():
        importlib.reload(globals()[global_name])
    else:
        # Attempt to import the module and assign it to globals dictionary. This allow to access the module under
        # the given name, just like the regular import would.
        globals()[global_name] = importlib.import_module(module_name)


preference_classes = (EXAMPLE_OT_install_dependencies,
                      EXAMPLE_preferences)

if __name__ == 'io_scene_ase':
    if 'bpy' in locals():
        import importlib
        if 'ase'        in locals(): importlib.reload(ase)
        if 'builder'    in locals(): importlib.reload(builder)
        if 'writer'     in locals(): importlib.reload(writer)
        if 'exporter'   in locals(): importlib.reload(exporter)
        if 'reader'     in locals(): importlib.reload(reader)

    import bpy
    import bpy.utils.previews
    from . import ase
    from . import builder
    from . import writer
    from . import exporter

    print('dependencies installed??')
    print(dependencies_installed)

    if dependencies_installed:
        from . import reader

    classes = (
        exporter.ASE_OT_ExportOperator,
    )

    if dependencies_installed:
        classes += reader.classes


    def menu_func_export(self, context):
        self.layout.operator(exporter.ASE_OT_ExportOperator.bl_idname, text='ASCII Scene Export (.ase)')

    def menu_func_import(self, context):
        self.layout.operator(reader.ASE_OT_ImportOperator.bl_idname, text='ASCII Scene Export (.ase)')


    def register():
        global dependencies_installed

        for cls in preference_classes:
            bpy.utils.register_class(cls)

        try:
            for dependency in dependencies:
                import_module(module_name=dependency.module, global_name=dependency.name)
            dependencies_installed = True
        except ModuleNotFoundError:
            # Don't register other panels, operators etc.
            return

        for cls in classes:
            bpy.utils.register_class(cls)

        bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

        if 'reader' in locals():
            bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


    def unregister():
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
        if 'reader' in locals():
            bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

        for cls in classes:
            bpy.utils.unregister_class(cls)
