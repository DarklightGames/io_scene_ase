from typing import List, Tuple


class AseFace(object):
    def __init__(self):
        self.a = 0
        self.b = 0
        self.c = 0
        self.ab = 0
        self.bc = 0
        self.ca = 0
        self.smoothing = 0
        self.material_index = 0


class AseVertexNormal(object):
    def __init__(self):
        self.vertex_index = 0
        self.normal = (0.0, 0.0, 0.0)


class AseFaceNormal(object):
    def __init__(self):
        self.normal = (0.0, 0.0, 1.0)
        self.vertex_normals = [AseVertexNormal()] * 3


class AseUVLayer(object):
    def __init__(self):
        self.texture_vertices: List[Tuple[float, float, float]] = []


class AseGeometryObject(object):
    def __init__(self):
        self.name = ''
        self.vertices: List[Tuple[float, float, float]] = []
        self.uv_layers: List[AseUVLayer] = []
        self.faces: List[AseFace] = []
        self.texture_vertex_faces = []
        self.face_normals: List[AseFaceNormal] = []
        self.vertex_colors: List[Tuple[float, float, float]] = []
        self.vertex_offset = 0
        self.texture_vertex_offset = 0


class Ase(object):
    def __init__(self):
        self.materials: List[str] = []
        self.geometry_objects: List[AseGeometryObject] = []
