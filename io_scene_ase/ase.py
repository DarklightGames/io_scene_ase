from typing import List


class ASEFace:
    def __init__(self):
        self.a: int = 0
        self.b: int = 0
        self.c: int = 0
        self.ab: int = 0
        self.bc: int = 0
        self.ca: int = 0
        self.smoothing: int = 0
        self.material_index: int = 0


class ASEVertexNormal:
    def __init__(self):
        self.vertex_index: int = 0
        self.normal: tuple[float, float, float] = (0.0, 0.0, 0.0)


class ASEFaceNormal:
    def __init__(self):
        self.normal: tuple[float, float, float] = (0.0, 0.0, 1.0)
        self.vertex_normals: list[ASEVertexNormal] = [ASEVertexNormal()] * 3


def is_collision_name(name: str) -> bool:
    return name.startswith('MCDCX_')


class ASEUVLayer:
    def __init__(self):
        self.texture_vertices: list[tuple[float, float, float]] = []


class ASEGeometryObject:
    def __init__(self):
        self.name: str = ''
        self.vertices: list[tuple[float, float, float]] = []
        self.uv_layers: list[ASEUVLayer] = []
        self.faces: list[ASEFace] = []
        self.texture_vertex_faces: list[tuple[int, int, int]] = []
        self.face_normals: list[ASEFaceNormal] = []
        self.vertex_colors: list[tuple[float, float, float]] = []
        self.vertex_offset: int = 0
        self.texture_vertex_offset: int = 0

    @property
    def is_collision(self):
        return is_collision_name(self.name)


class ASE(object):
    def __init__(self):
        self.materials: List[str] = []
        self.geometry_objects: List[ASEGeometryObject] = []
