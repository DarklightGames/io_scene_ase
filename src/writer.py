from .ase import *


class ASEFile(object):
    def __init__(self):
        self.commands = []

    def add_command(self, name):
        command = ASECommand(name)
        self.commands.append(command)
        return command


class ASECommand(object):
    def __init__(self, name):
        self.name = name
        self.data = []
        self.children = []
        self.sub_commands = []

    @property
    def has_data(self):
        return len(self.data) > 0

    @property
    def has_children(self):
        return len(self.children)

    @property
    def has_sub_commands(self):
        return len(self.sub_commands) > 0

    def push_datum(self, datum):
        self.data.append(datum)
        return self

    def push_data(self, data):
        self.data += data
        return self

    def push_sub_command(self, name):
        command = ASECommand(name)
        self.sub_commands.append(command)
        return command

    def push_child(self, name):
        child = ASECommand(name)
        self.children.append(child)
        return child


class ASEWriter(object):

    def __init__(self):
        self.fp = None
        self.indent = 0

    def write_datum(self, datum):
        if type(datum) is str:
            self.fp.write(f'"{datum}"')
        elif type(datum) is int:
            self.fp.write(str(datum))
        elif type(datum) is float:
            self.fp.write('{:0.4f}'.format(datum))
        elif type(datum) is dict:
            for index, (key, value) in enumerate(datum.items()):
                if index > 0:
                    self.fp.write(' ')
                self.fp.write(f'{key}: ')
                self.write_datum(value)

    def write_sub_command(self, sub_command):
        self.fp.write(f' *{sub_command.name}')
        if sub_command.has_data:
            for datum in sub_command.data:
                self.fp.write(' ')
                self.write_datum(datum)

    def write_command(self, command):
        self.fp.write('\t' * self.indent)
        self.fp.write(f'*{command.name}')
        if command.has_data:
            for datum in command.data:
                self.fp.write(' ')
                self.write_datum(datum)
        if command.has_sub_commands:
            # Sub-commands are commands that appear inline with their parent command
            for sub_command in command.sub_commands:
                self.write_sub_command(sub_command)
        if command.has_children:
            self.fp.write(' {\n')
            self.indent += 1
            for child in command.children:
                self.write_command(child)
            self.indent -= 1
            self.fp.write('\t' * self.indent + '}\n')
        else:
            self.fp.write('\n')

    def write_file(self, file: ASEFile):
        for command in file.commands:
            self.write_command(command)

    @staticmethod
    def build_ase_tree(ase) -> ASEFile:
        root = ASEFile()
        root.add_command('3DSMAX_ASCIIEXPORT').push_datum(200)

        # Materials
        if len(ase.materials) > 0:
            material_list = root.add_command('MATERIAL_LIST')
            material_list.push_child('MATERIAL_COUNT').push_datum(len(ase.materials))
            material_node = material_list.push_child('MATERIAL')
            material_node.push_child('NUMSUBMTLS').push_datum(len(ase.materials))
            for material_index, material in enumerate(ase.materials):
                submaterial_node = material_node.push_child('SUBMATERIAL')
                submaterial_node.push_datum(material_index)
                submaterial_node.push_child('MATERIAL_NAME').push_datum(material)
                diffuse_node = submaterial_node.push_child('MAP_DIFFUSE')
                diffuse_node.push_child('MAP_NAME').push_datum('default')
                diffuse_node.push_child('UVW_U_OFFSET').push_datum(0.0)
                diffuse_node.push_child('UVW_V_OFFSET').push_datum(0.0)
                diffuse_node.push_child('UVW_U_TILING').push_datum(1.0)
                diffuse_node.push_child('UVW_V_TILING').push_datum(1.0)

        for geometry_object in ase.geometry_objects:
            geomobject_node = root.add_command('GEOMOBJECT')
            geomobject_node.push_child('NODE_NAME').push_datum(geometry_object.name)

            mesh_node = geomobject_node.push_child('MESH')

            # Vertices
            mesh_node.push_child('MESH_NUMVERTEX').push_datum(len(geometry_object.vertices))
            vertex_list_node = mesh_node.push_child('MESH_VERTEX_LIST')
            for vertex_index, vertex in enumerate(geometry_object.vertices):
                mesh_vertex = vertex_list_node.push_child('MESH_VERTEX').push_datum(vertex_index)
                mesh_vertex.push_data([x for x in vertex])

            # Faces
            mesh_node.push_child('MESH_NUMFACES').push_datum(len(geometry_object.faces))
            faces_node = mesh_node.push_child('MESH_FACE_LIST')
            for face_index, face in enumerate(geometry_object.faces):
                face_node = faces_node.push_child('MESH_FACE')
                face_node.push_datum({str(face_index): {'A': face.a, 'B': face.b, 'C': face.c, 'AB': 0, 'BC': 0, 'CA': 0}})
                face_node.push_sub_command('MESH_SMOOTHING').push_datum(face.smoothing)
                face_node.push_sub_command('MESH_MTLID').push_datum(face.material_index)

            # Texture Coordinates
            if len(geometry_object.texture_vertices) > 0:
                mesh_node.push_child('MESH_NUMTVERTEX').push_datum(len(geometry_object.texture_vertices))
                tvertlist_node = mesh_node.push_child('MESH_TVERTLIST')
                for tvert_index, tvert in enumerate(geometry_object.texture_vertices):
                    tvert_node = tvertlist_node.push_child('MESH_TVERT')
                    tvert_node.push_datum(tvert_index)
                    tvert_node.push_data(list(tvert))

            # Texture Faces
            if len(geometry_object.texture_vertex_faces) > 0:
                mesh_node.push_child('MESH_NUMTVFACES').push_datum(len(geometry_object.texture_vertex_faces))
                texture_faces_node = mesh_node.push_child('MESH_TFACELIST')
                for texture_face_index, texture_face in enumerate(geometry_object.texture_vertex_faces):
                    texture_face_node = texture_faces_node.push_child('MESH_TFACE')
                    texture_face_node.push_data([texture_face_index] + list(texture_face))

            # Normals
            if len(geometry_object.face_normals) > 0:
                normals_node = mesh_node.push_child('MESH_NORMALS')
                for normal_index, normal in enumerate(geometry_object.face_normals):
                    normal_node = normals_node.push_child('MESH_FACENORMAL')
                    normal_node.push_datum(normal_index)
                    normal_node.push_data(list(normal.normal))
                    for vertex_normal in normal.vertex_normals:
                        vertex_normal_node = normals_node.push_child('MESH_VERTEXNORMAL')
                        vertex_normal_node.push_datum(vertex_normal.vertex_index)
                        vertex_normal_node.push_data(list(vertex_normal.normal))

            geomobject_node.push_child('MATERIAL_REF').push_datum(0)

        return root

    def write(self, filepath, ase):
        self.indent = 0
        ase_file = self.build_ase_tree(ase)
        with open(filepath, 'w') as self.fp:
            self.write_file(ase_file)
