from typing import Iterable, Optional, List, Dict, cast
from collections import OrderedDict


from bpy.types import Context, Material, Mesh

from .ase import ASE, ASEGeometryObject, ASEFace, ASEFaceNormal, ASEVertexNormal, ASEUVLayer, is_collision_name
import bpy
import bmesh
import math
from mathutils import Matrix, Vector

from .dfs import DfsObject

SMOOTHING_GROUP_MAX = 32

class ASEBuildError(Exception):
    pass


class ASEBuildOptions(object):
    def __init__(self):
        self.object_eval_state = 'EVALUATED'
        self.materials: Optional[List[Material]] = None
        self.material_mapping: Dict[str, str] = OrderedDict()
        self.transform = Matrix.Identity(4)
        self.should_export_vertex_colors = True
        self.vertex_color_mode = 'ACTIVE'
        self.has_vertex_colors = False
        self.vertex_color_attribute = ''
        self.should_invert_normals = False
        self.scale = 1.0
        self.forward_axis = 'X'
        self.up_axis = 'Z'
        self.scct_versus_mcdcx_flip = False


def get_vector_from_axis_identifier(axis_identifier: str) -> Vector:
    match axis_identifier:
        case 'X':
            return Vector((1.0, 0.0, 0.0))
        case 'Y':
            return Vector((0.0, 1.0, 0.0))
        case 'Z':
            return Vector((0.0, 0.0, 1.0))
        case '-X':
            return Vector((-1.0, 0.0, 0.0))
        case '-Y':
            return Vector((0.0, -1.0, 0.0))
        case '-Z':
            return Vector((0.0, 0.0, -1.0))


def get_coordinate_system_transform(forward_axis: str = 'X', up_axis: str = 'Z') -> Matrix:
    forward = get_vector_from_axis_identifier(forward_axis)
    up = get_vector_from_axis_identifier(up_axis)
    left = up.cross(forward)
    return Matrix((
        (forward.x, forward.y, forward.z, 0.0),
        (left.x, left.y, left.z, 0.0),
        (up.x, up.y, up.z, 0.0),
        (0.0, 0.0, 0.0, 1.0)
    ))


def build_ase(context: Context, options: ASEBuildOptions, dfs_objects: Iterable[DfsObject]) -> ASE:
    ase = ASE()
    ase.materials = [x.name if x is not None else 'None' for x in options.materials]

    # If no materials are assigned to the object, add an empty material.
    # This is necessary for the ASE format to be compatible with the UT2K4 importer.
    if len(ase.materials) == 0:
        ase.materials.append('')

    dfs_objects = list(dfs_objects)
    dfs_objects_processed = 0

    context.window_manager.progress_begin(0, len(dfs_objects))

    class GeometryObjectInfo:
        def __init__(self, name: str):
            self.name = name
            self.dfs_objects = []

    main_geometry_object_info = GeometryObjectInfo('io_scene_ase')
    geometry_object_infos: List[GeometryObjectInfo] = [
        main_geometry_object_info,
    ]

    for object_index, dfs_object in enumerate(dfs_objects):
        if is_collision_name(dfs_object.obj.name):
            geometry_object_info = GeometryObjectInfo(dfs_object.obj.name)
            geometry_object_info.dfs_objects.append(dfs_object)
            geometry_object_infos.append(geometry_object_info)
        else:
            main_geometry_object_info.dfs_objects.append(dfs_object)

    # Sort the DFS objects into collision and non-collision objects.
    coordinate_system_transform = get_coordinate_system_transform(options.forward_axis, options.up_axis)

    for geometry_object_info in geometry_object_infos:
        geometry_object = ASEGeometryObject()
        geometry_object.name = geometry_object_info.name

        max_uv_layers = 0
        for dfs_object in geometry_object_info.dfs_objects:
            mesh_data = cast(Mesh, dfs_object.obj.data)
            max_uv_layers = max(max_uv_layers, len(mesh_data.uv_layers))

        geometry_object.uv_layers = [ASEUVLayer() for _ in range(max_uv_layers)]

        for dfs_object in geometry_object_info.dfs_objects:
            obj = dfs_object.obj

            if geometry_object.is_collision:
                # Test that collision meshes are manifold and convex.
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                for edge in bm.edges:
                    if not edge.is_manifold:
                        del bm
                        raise ASEBuildError(f'Collision mesh \'{obj.name}\' is not manifold')
                    if not edge.is_convex:
                        del bm
                        raise ASEBuildError(f'Collision mesh \'{obj.name}\' is not convex')

            matrix_world = dfs_object.matrix_world

            # Save the active color name for vertex color export.
            active_color_name = obj.data.color_attributes.active_color_name

            match options.object_eval_state:
                case 'ORIGINAL':
                    mesh_object = obj
                    mesh_data = mesh_object.data
                case 'EVALUATED':
                    # Evaluate the mesh after modifiers are applied
                    depsgraph = context.evaluated_depsgraph_get()
                    bm = bmesh.new()
                    bm.from_object(obj, depsgraph)
                    mesh_data = bpy.data.meshes.new('')
                    bm.to_mesh(mesh_data)
                    del bm
                    mesh_object = bpy.data.objects.new('', mesh_data)
                    mesh_object.matrix_world = matrix_world

            vertex_transform = (Matrix.Rotation(math.pi, 4, 'Z') @
                                Matrix.Scale(options.scale, 4) @
                                options.transform @
                                matrix_world)

            # Apply SCCT Versus MCDCX flip for collision meshes
            apply_collision_flip = options.scct_versus_mcdcx_flip and geometry_object.is_collision
            full_transform = coordinate_system_transform @ vertex_transform
            if apply_collision_flip:
                flip_transform = Matrix.Scale(-1.0, 4, Vector((1, 0, 0))) @ Matrix.Scale(-1.0, 4, Vector((0, 1, 0)))
                full_transform = flip_transform @ full_transform

            for _, vertex in enumerate(mesh_data.vertices):
                geometry_object.vertices.append(full_transform @ vertex.co)

            material_indices = []
            if not geometry_object.is_collision:
                for mesh_material_index, material in enumerate(obj.data.materials): # TODO: this needs to use the evaluated object, doesn't it?
                    if material is None:
                        raise ASEBuildError(f'Material slot {mesh_material_index + 1} for mesh \'{obj.name}\' cannot be empty')
                    material_indices.append(ase.materials.index(material.name))

            if len(material_indices) == 0:
                # If no materials are assigned to the mesh, just have a single empty material.
                material_indices.append(0)

            mesh_data.calc_loop_triangles()

            # Calculate smoothing groups.
            poly_groups, groups = mesh_data.calc_smooth_groups(use_bitflags=False)

            # Figure out how many scaling axes are negative.
            # This is important for calculating the normals of the mesh.
            _, _, scale = vertex_transform.decompose()
            negative_scaling_axes = sum([1 for x in scale if x < 0])
            should_invert_normals = negative_scaling_axes % 2 == 1
            if options.should_invert_normals:
                should_invert_normals = not should_invert_normals

            loop_triangle_index_order = (2, 1, 0) if should_invert_normals else (0, 1, 2)

            # Gather the list of unique material indices in the loop triangles.
            face_material_indices = {loop_triangle.material_index for loop_triangle in mesh_data.loop_triangles}

            # Make sure that each material index is within the bounds of the material indices list.
            for material_index in face_material_indices:
                if material_index >= len(material_indices):
                    raise ASEBuildError(f'Material index {material_index} for mesh \'{obj.name}\' is out of bounds.\n'
                                        f'This means that one or more faces are assigned to a material slot that does '
                                        f'not exist.\n'
                                        f'The referenced material indices in the faces are: {sorted(list(face_material_indices))}.\n'
                                        f'Either add enough materials to the object or assign faces to existing material slots.'
                                        )

            del face_material_indices

            # TODO: There is an edge case here where if two different meshes have identical or nearly identical
            # vertices and also matching smoothing groups, the engine's importer will incorrectly calculate the
            # normal of any faces that have the shared vertices.
            # The get around this, we could detect the overlapping vertices and display a warning, though checking
            # for unique vertices can be quite expensive (use a KD-tree!)
            # Another thing we can do is; when we find an overlapping vertex, we find out the range of smoothing
            # groups that were used for that mesh. Then we can simply dodge the smoothing group by offseting the
            # smoothing groups for the current mesh. This should work the majority of the time.

            # Faces
            for _, loop_triangle in enumerate(mesh_data.loop_triangles):
                face = ASEFace()
                face.a, face.b, face.c = map(lambda j: geometry_object.vertex_offset + mesh_data.loops[loop_triangle.loops[j]].vertex_index, loop_triangle_index_order)
                if not geometry_object.is_collision:
                    face.material_index = material_indices[loop_triangle.material_index]
                # The UT2K4 importer only accepts 32 smoothing groups. Anything past this completely mangles the
                # smoothing groups and effectively makes the whole model use sharp-edge rendering.
                # The fix is to constrain the smoothing group between 0 and 31 by applying a modulo of 32 to the actual
                # smoothing group index.
                # This may result in bad calculated normals on export in rare cases. For example, if a face with a
                # smoothing group of 3 is adjacent to a face with a smoothing group of 35 (35 % 32 == 3), those faces
                # will be treated as part of the same smoothing group.
                face.smoothing = (poly_groups[loop_triangle.polygon_index] - 1) % SMOOTHING_GROUP_MAX
                geometry_object.faces.append(face)

            if not geometry_object.is_collision:
                # Normals
                for _, loop_triangle in enumerate(mesh_data.loop_triangles):
                    face_normal = ASEFaceNormal()
                    face_normal.normal = loop_triangle.normal
                    face_normal.vertex_normals = []
                    for i in loop_triangle_index_order:
                        vertex_normal = ASEVertexNormal()
                        vertex_normal.vertex_index = geometry_object.vertex_offset + mesh_data.loops[loop_triangle.loops[i]].vertex_index
                        vertex_normal.normal = loop_triangle.split_normals[i]
                        if should_invert_normals:
                            vertex_normal.normal = (-Vector(vertex_normal.normal)).to_tuple()
                        face_normal.vertex_normals.append(vertex_normal)
                    geometry_object.face_normals.append(face_normal)

                # Texture Coordinates
                for i, uv_layer_data in enumerate([x.data for x in mesh_data.uv_layers]):
                    uv_layer = geometry_object.uv_layers[i]
                    for loop_index, loop in enumerate(mesh_data.loops):
                        u, v = uv_layer_data[loop_index].uv
                        uv_layer.texture_vertices.append((u, v, 0.0))

                # Add zeroed texture vertices for any missing UV layers.
                for i in range(len(mesh_data.uv_layers), max_uv_layers):
                    uv_layer = geometry_object.uv_layers[i]
                    for _ in mesh_data.loops:
                        uv_layer.texture_vertices.append((0.0, 0.0, 0.0))

                # Texture Faces
                for loop_triangle in mesh_data.loop_triangles:
                    geometry_object.texture_vertex_faces.append(
                        tuple(map(lambda l: geometry_object.texture_vertex_offset + loop_triangle.loops[l], loop_triangle_index_order))
                    )

                # Vertex Colors
                if options.should_export_vertex_colors and options.has_vertex_colors:
                    match options.vertex_color_mode:
                        case 'ACTIVE':
                            color_attribute_name = active_color_name
                        case 'EXPLICIT':
                            color_attribute_name = options.vertex_color_attribute
                        case _:
                            raise ASEBuildError('Invalid vertex color mode')

                    color_attribute = mesh_data.color_attributes.get(color_attribute_name, None)

                    if color_attribute is not None:
                        # Make sure that the selected color attribute is on the CORNER domain.
                        if color_attribute.domain != 'CORNER':
                            raise ASEBuildError(f'Color attribute \'{color_attribute.name}\' for object \'{obj.name}\' must have domain of \'CORNER\' (found  \'{color_attribute.domain}\')')

                        for color in map(lambda x: x.color, color_attribute.data):
                            geometry_object.vertex_colors.append(tuple(color[0:3]))

            # Update data offsets for next iteration
            geometry_object.texture_vertex_offset += len(mesh_data.loops)
            geometry_object.vertex_offset = len(geometry_object.vertices)

            dfs_objects_processed += 1
            context.window_manager.progress_update(dfs_objects_processed)

        ase.geometry_objects.append(geometry_object)
    
    # Apply the material mapping.
    material_mapping_items: list[tuple[str, str]] = list(options.material_mapping.items())
    material_mapping_keys = list(map(lambda x: x[0], material_mapping_items))
    for i in range(len(ase.materials)):
        try:
            index = material_mapping_keys.index(ase.materials[i])
            ase.materials[i] = material_mapping_items[index][1]
        except ValueError:
            pass

    context.window_manager.progress_end()

    if len(ase.geometry_objects) == 0:
        raise ASEBuildError('At least one mesh object must be selected')

    return ase
