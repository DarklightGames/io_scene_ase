from typing import Iterable, Set
from bpy.types import PropertyGroup, Context, Material, Object
from bpy.props import CollectionProperty, IntProperty, BoolProperty, EnumProperty, FloatProperty, StringProperty, PointerProperty


axis_identifiers = ('X', 'Y', 'Z', '-X', '-Y', '-Z')
forward_items = (
    ('X', 'X Forward', ''),
    ('Y', 'Y Forward', ''),
    ('Z', 'Z Forward', ''),
    ('-X', '-X Forward', ''),
    ('-Y', '-Y Forward', ''),
    ('-Z', '-Z Forward', ''),
)

up_items = (
    ('X', 'X Up', ''),
    ('Y', 'Y Up', ''),
    ('Z', 'Z Up', ''),
    ('-X', '-X Up', ''),
    ('-Y', '-Y Up', ''),
    ('-Z', '-Z Up', ''),
)


def forward_axis_update(self, _context: Context):
    if self.forward_axis[-1] == self.up_axis[-1]:
        self.up_axis = next((axis for axis in axis_identifiers if axis[-1] != self.forward_axis[-1]), 'Z')


def up_axis_update(self, _context: Context):
    if self.up_axis[-1] == self.forward_axis[-1]:
        self.forward_axis = next((axis for axis in axis_identifiers if axis[-1] != self.up_axis[-1]), 'X')


transform_source_items = (
    ('SCENE', 'Scene', ''),
    ('CUSTOM', 'Custom', ''),
)


class TransformSourceMixin:
    transform_source: EnumProperty(name='Transform Source', items=transform_source_items, default='SCENE', description='The source of the transform to apply to the exported geometry')


class TransformMixin:
    scale: FloatProperty(name='Scale', default=1.0, min=0.0001, soft_max=1000.0, description='Scale factor to apply to the exported geometry')
    forward_axis: EnumProperty(name='Forward', items=forward_items, default='X', update=forward_axis_update)
    up_axis: EnumProperty(name='Up', items=up_items, default='Z', update=up_axis_update)


material_mode_items = (
    ('AUTOMATIC', 'Automatic', ''),
    ('MANUAL', 'Manual', ''),
)


class MaterialModeMixin:
    material_mode: EnumProperty(name='Material Mode', items=material_mode_items, default='AUTOMATIC', description='The material mode to use for the exported geometry')


class ASE_PG_material(PropertyGroup):
    material: PointerProperty(type=Material)


class ASE_PG_key_value(PropertyGroup):
    key: StringProperty()
    value: StringProperty()


def get_vertex_color_attributes_from_objects(objects: Iterable[Object]) -> Set[str]:
    '''
    Get the unique vertex color attributes from all the selected objects.
    :param objects: The objects to search for vertex color attributes.
    :return: A set of unique vertex color attributes.
    '''
    items = set()
    for obj in filter(lambda x: x.type == 'MESH', objects):
        for layer in filter(lambda x: x.domain == 'CORNER', obj.data.color_attributes):
            items.add(layer.name)
    return items


def vertex_color_attribute_items(self, context):
    # Get the unique color attributes from all the selected objects.
    return [(x, x, '') for x in sorted(get_vertex_color_attributes_from_objects(context.selected_objects))]


vertex_color_mode_items = (
    ('ACTIVE', 'Active', 'Use the active vertex color attribute'),
    ('EXPLICIT', 'Explicit', 'Use the vertex color attribute specified below'),
)


class ASE_PG_export(PropertyGroup, TransformSourceMixin, TransformMixin):
    material_list: CollectionProperty(name='Materials', type=ASE_PG_material)
    material_list_index: IntProperty(name='Index', default=0)
    should_export_vertex_colors: BoolProperty(name='Export Vertex Colors', default=True)
    vertex_color_mode: EnumProperty(name='Vertex Color Mode', items=vertex_color_mode_items)
    has_vertex_colors: BoolProperty(name='Has Vertex Colors', default=False, options={'HIDDEN'})
    vertex_color_attribute: EnumProperty(name='Attribute', items=vertex_color_attribute_items)
    should_invert_normals: BoolProperty(name='Invert Normals', default=False, description='Invert the normals of the exported geometry. This should be used if the software you are exporting to uses a different winding order than Blender')
    scct_versus_mcdcx_flip: BoolProperty(name='SCCT MCDCX Flip', default=False, description='Flip X and Y axes for MCDCX collision meshes only (for Splinter Cell: Chaos Theory Versus compatibility)')


class ASE_PG_scene_settings(PropertyGroup, TransformMixin):
    pass


classes = (
    ASE_PG_material,
    ASE_PG_key_value,
    ASE_PG_export,
    ASE_PG_scene_settings,
)
