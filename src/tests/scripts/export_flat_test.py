import bpy

try:
    bpy.ops.object.mode_set(mode='OBJECT')
except:
    pass

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.mesh.primitive_monkey_add()
bpy.ops.object.select_all(action='SELECT')

mesh_object = bpy.context.view_layer.objects.active
material = bpy.data.materials.new('asd')
mesh_object.data.materials.append(material)

r = bpy.ops.io_scene_ase.ase_export(filepath=r'.\\flat.ase')