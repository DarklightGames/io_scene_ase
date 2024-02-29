class ASEFace(object):
    def __init__(self):
        self.a = 0
        self.b = 0
        self.c = 0
        self.ab = 0
        self.bc = 0
        self.ca = 0
        self.smoothing = 0
        self.material_index = 0


class ASEVertexNormal(object):
    def __init__(self):
        self.vertex_index = 0
        self.normal = (0.0, 0.0, 0.0)


class ASEFaceNormal(object):
    def __init__(self):
        self.normal = (0.0, 0.0, 1.0)
        self.vertex_normals = [ASEVertexNormal()] * 3


def is_collision_name(name):
    return name.startswith('MCDCX_')


class ASEUVLayer(object):
    def __init__(self):
        self.texture_vertices = []


class ASEGeometryObject(object):
    def __init__(self):
        self.name = ''
        self.vertices = []
        self.uv_layers = []
        self.faces = []
        self.texture_vertex_faces = []
        self.face_normals = []
        self.vertex_colors = []
        self.vertex_offset = 0
        self.texture_vertex_offset = 0

    @property
    def is_collision(self):
        return is_collision_name(self.name)


class ASE(object):
    def __init__(self):
        self.materials = []
        self.geometry_objects = []

