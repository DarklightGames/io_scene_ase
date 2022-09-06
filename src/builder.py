from .ase import *
import bpy
import bmesh
import math
from mathutils import Matrix


def is_collision_name(name: str):
    return name.startswith('MCDCX_')


def is_collision(geometry_object: AseGeometryObject):
    return is_collision_name(geometry_object.name)


class AseBuilderError(Exception):
    pass


class AseBuilderOptions(object):
    def __init__(self):
        self.scale = 1.0
        self.use_raw_mesh_data = False


def build_ase(context: bpy.types.Context, options: AseBuilderOptions):
    ase = Ase()

    main_geometry_object = None
    for selected_object in context.view_layer.objects.selected:
        if selected_object is None or selected_object.type != 'MESH':
            continue

        # Evaluate the mesh after modifiers are applied
        if options.use_raw_mesh_data:
            mesh_object = selected_object
            mesh_data = mesh_object.data
        else:
            depsgraph = context.evaluated_depsgraph_get()
            bm = bmesh.new()
            bm.from_object(selected_object, depsgraph)
            mesh_data = bpy.data.meshes.new('')
            bm.to_mesh(mesh_data)
            del bm
            mesh_object = bpy.data.objects.new('', mesh_data)
            mesh_object.matrix_world = selected_object.matrix_world

        if not is_collision_name(selected_object.name) and main_geometry_object is not None:
            geometry_object = main_geometry_object
        else:
            geometry_object = AseGeometryObject()
            geometry_object.name = selected_object.name
            if not is_collision(geometry_object):
                main_geometry_object = geometry_object
            ase.geometry_objects.append(geometry_object)

        if is_collision(geometry_object):
            # Test that collision meshes are manifold and convex.
            bm = bmesh.new()
            bm.from_mesh(mesh_data)
            for edge in bm.edges:
                if not edge.is_manifold:
                    del bm
                    raise AseBuilderError(f'Collision mesh \'{selected_object.name}\' is not manifold')
                if not edge.is_convex:
                    del bm
                    raise AseBuilderError(f'Collision mesh \'{selected_object.name}\' is not convex')

        if not is_collision(geometry_object) and len(selected_object.data.materials) == 0:
            raise AseBuilderError(f'Mesh \'{selected_object.name}\' must have at least one material')

        vertex_transform = Matrix.Scale(options.scale, 4) @ Matrix.Rotation(math.pi, 4, 'Z') @ mesh_object.matrix_world
        for vertex in mesh_data.vertices:
            geometry_object.vertices.append(vertex_transform @ vertex.co)

        material_indices = []
        if not is_collision(geometry_object):
            for mesh_material_index, material in enumerate(selected_object.data.materials):
                if material is None:
                    raise AseBuilderError(f'Material slot {mesh_material_index + 1} for mesh \'{selected_object.name}\' cannot be empty')
                try:
                    # Reuse existing material entries for duplicates
                    material_index = ase.materials.index(material.name)
                except ValueError:
                    material_index = len(ase.materials)
                    ase.materials.append(material.name)
                material_indices.append(material_index)

        mesh_data.calc_loop_triangles()
        mesh_data.calc_normals_split()
        poly_groups, groups = mesh_data.calc_smooth_groups(use_bitflags=False)

        # Faces
        for loop_triangle in mesh_data.loop_triangles:
            face = AseFace()
            face.a = geometry_object.vertex_offset + mesh_data.loops[loop_triangle.loops[0]].vertex_index
            face.b = geometry_object.vertex_offset + mesh_data.loops[loop_triangle.loops[1]].vertex_index
            face.c = geometry_object.vertex_offset + mesh_data.loops[loop_triangle.loops[2]].vertex_index
            if not is_collision(geometry_object):
                face.material_index = material_indices[loop_triangle.material_index]
            # The UT2K4 importer only accepts 32 smoothing groups. Anything past this completely mangles the
            # smoothing groups and effectively makes the whole model use sharp-edge rendering.
            # The fix is to constrain the smoothing group between 0 and 31 by applying a modulo of 32 to the actual
            # smoothing group index.
            # This may result in bad calculated normals on export in rare cases. For example, if a face with a
            # smoothing group of 3 is adjacent to a face with a smoothing group of 35 (35 % 32 == 3), those faces
            # will be treated as part of the same smoothing group.
            face.smoothing = (poly_groups[loop_triangle.polygon_index] - 1) % 32
            geometry_object.faces.append(face)

        if not is_collision(geometry_object):
            # Normals
            for loop_triangle in mesh_data.loop_triangles:
                face_normal = AseFaceNormal()
                face_normal.normal = loop_triangle.normal
                face_normal.vertex_normals = []
                for i in range(3):
                    vertex_normal = AseVertexNormal()
                    vertex_normal.vertex_index = geometry_object.vertex_offset + mesh_data.loops[loop_triangle.loops[i]].vertex_index
                    vertex_normal.normal = loop_triangle.split_normals[i]
                    face_normal.vertex_normals.append(vertex_normal)
                geometry_object.face_normals.append(face_normal)

            # Texture Coordinates
            for i, uv_layer_data in enumerate([x.data for x in mesh_data.uv_layers]):
                if i >= len(geometry_object.uv_layers):
                    geometry_object.uv_layers.append(AseUVLayer())
                uv_layer = geometry_object.uv_layers[i]
                for loop_index, loop in enumerate(mesh_data.loops):
                    u, v = uv_layer_data[loop_index].uv
                    uv_layer.texture_vertices.append((u, v, 0.0))

            # Texture Faces
            for loop_triangle in mesh_data.loop_triangles:
                geometry_object.texture_vertex_faces.append((
                    geometry_object.texture_vertex_offset + loop_triangle.loops[0],
                    geometry_object.texture_vertex_offset + loop_triangle.loops[1],
                    geometry_object.texture_vertex_offset + loop_triangle.loops[2]
                ))

            # Vertex Colors
            if len(mesh_data.vertex_colors) > 0:
                vertex_colors = mesh_data.vertex_colors.active.data
                for color in map(lambda x: x.color, vertex_colors):
                    geometry_object.vertex_colors.append(tuple(color[0:3]))

        # Update data offsets for next iteration
        geometry_object.texture_vertex_offset += len(mesh_data.loops)
        geometry_object.vertex_offset = len(geometry_object.vertices)

    if len(ase.geometry_objects) == 0:
        raise AseBuilderError('At least one mesh object must be selected')

    if main_geometry_object is None:
        raise AseBuilderError('At least one non-collision mesh must be exported')

    return ase
