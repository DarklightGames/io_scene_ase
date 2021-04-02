from .ase import *
import bpy
import bmesh
import math
from mathutils import Matrix


class ASEBuilderError(Exception):
    pass


class ASEBuilderOptions(object):
    def __init__(self):
        self.scale = 1.0


class ASEBuilder(object):
    def build(self, context, options: ASEBuilderOptions):
        ase = ASE()

        main_geometry_object = None
        for obj in context.selected_objects:
            if obj is None or obj.type != 'MESH':
                continue

            mesh_data = obj.data

            if not is_collision_name(obj.name) and main_geometry_object is not None:
                geometry_object = main_geometry_object
            else:
                geometry_object = ASEGeometryObject()
                geometry_object.name = obj.name
                if not geometry_object.is_collision:
                    main_geometry_object = geometry_object
                ase.geometry_objects.append(geometry_object)

            if not geometry_object.is_collision and len(mesh_data.materials) == 0:
                raise ASEBuilderError(f'Mesh \'{obj.name}\' must have at least one material')

            geometry_object.vertex_offset += len(geometry_object.vertices)
            vertex_transform = Matrix.Scale(options.scale, 4) @ Matrix.Rotation(math.pi, 4, 'Z') @ obj.matrix_world
            for vertex_index, vertex in enumerate(mesh_data.vertices):
                geometry_object.vertices.append(vertex_transform @ vertex.co)

            material_indices = []
            if not geometry_object.is_collision:
                for mesh_material_index, material in enumerate(mesh_data.materials):
                    if material is None:
                        raise ASEBuilderError(f'Material slot {mesh_material_index + 1} for mesh \'{obj.name}\' cannot be empty')
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
            for face_index, loop_triangle in enumerate(mesh_data.loop_triangles):
                face = ASEFace()
                face.a = geometry_object.vertex_offset + mesh_data.loops[loop_triangle.loops[0]].vertex_index
                face.b = geometry_object.vertex_offset + mesh_data.loops[loop_triangle.loops[1]].vertex_index
                face.c = geometry_object.vertex_offset + mesh_data.loops[loop_triangle.loops[2]].vertex_index
                if not geometry_object.is_collision:
                    face.material_index = material_indices[loop_triangle.material_index]
                # The UT2K4 importer only accepts 32 smoothing groups. Anything past this completely mangles the
                # smoothing groups and effectively makes the whole model use sharp-edge rendering.
                face.smoothing = (poly_groups[loop_triangle.polygon_index] - 1) % 32
                geometry_object.faces.append(face)

            # Normals
            if not geometry_object.is_collision:
                for face_index, loop_triangle in enumerate(mesh_data.loop_triangles):
                    face_normal = ASEFaceNormal()
                    face_normal.normal = loop_triangle.normal
                    face_normal.vertex_normals = []
                    for i in range(3):
                        vertex_normal = ASEVertexNormal()
                        vertex_normal.vertex_index = geometry_object.vertex_offset + mesh_data.loops[loop_triangle.loops[i]].vertex_index
                        vertex_normal.normal = loop_triangle.split_normals[i]
                        face_normal.vertex_normals.append(vertex_normal)
                    geometry_object.face_normals.append(face_normal)

            uv_layer = mesh_data.uv_layers.active.data

            # Texture Coordinates
            geometry_object.texture_vertex_offset += len(geometry_object.texture_vertices)
            if not geometry_object.is_collision:
                for loop_index, loop in enumerate(mesh_data.loops):
                    u, v = uv_layer[loop_index].uv
                    geometry_object.texture_vertices.append((u, v, 0.0))

            # Texture Faces
            if not geometry_object.is_collision:
                for loop_triangle in mesh_data.loop_triangles:
                    geometry_object.texture_vertex_faces.append((
                        geometry_object.texture_vertex_offset + loop_triangle.loops[0],
                        geometry_object.texture_vertex_offset + loop_triangle.loops[1],
                        geometry_object.texture_vertex_offset + loop_triangle.loops[2]
                    ))

        if len(ase.geometry_objects) == 0:
            raise ASEBuilderError('At least one mesh object must be selected')

        if main_geometry_object is None:
            raise ASEBuilderError('At least one non-collision mesh must be exported')

        return ase
