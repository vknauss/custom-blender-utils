import bpy
import struct
import math

# Header format string
# https://docs.python.org/3.5/library/struct.html#struct.pack
# < : little-endian byte order, standard type sizes and no padding
# 8s : 8-character formatted string (encoded ascii in this case) : "meshfile"
# B : unsigned char : number of attributes
# 2Q : 2 unsigned long long (uint64_t) : number of vertices and indices
header_fmt = "<8sB2Q"

attrib_fmt = "<2B2Q"

def c_str(s, encoding = "ascii"):
    return struct.pack("<" + str(len(s) + 1) + "s", s.encode(encoding))

def export_mesh(object, filename):
    print("Exporting mesh to: " + filename)
    mesh = object.data
    with open(filename, "wb") as f:
        # number of attributes, vertices, and indices must be computed
        # blender mesh data does not 1-1 represent the sort of data we need
        # so there are some decoding steps we need to take
        
        # check for uvs, todo: allow an option to enable/disable uv exporting,
        # as well as choosing a particular uv layer for export
        uv_layer = mesh.uv_layers[0] if mesh.uv_layers else None
        
        # you know what, I think for now lets just assume we are writing
        # texcoords, positions, and normals
        
        # the vertex position and normal are right there in the vertex info
        # the uv is a bit trickier, it's stored in a uv_layer where each element
        # in its data has a uv and vertex index, theoretically (and in fact),
        # multiple uv loop items may exist for a given vertex. some of those
        # items may have the same uv coordinate
        
        # calculate triangulation
        if not mesh.loop_triangles:
            mesh.calc_loop_triangles()
            
        uv_list_list = [ [] for i in range(len(mesh.vertices)) ]
        
        vertex_count = 0
        for loop_item, uv_item in zip(mesh.loops, uv_layer.data):
                l = uv_list_list[loop_item.vertex_index]
                c_uv = uv_item.uv
                found = False
                for (loop_inds, uv) in l:
                    if abs(uv.x - c_uv.x) < 0.0001 and abs(uv.y - c_uv.y) < 0.0001:
                        found = True
                        loop_inds.append(loop_item.index)
                        break
                if not found:
                    ++vertex_count
                    uv_list_list[loop_item.vertex_index].append(([loop_item.index], c_uv))
        
        vertices = []
        loop_vert_inds = [-1] * len(mesh.loops)
        for i in range(len(uv_list_list)):
            for (loop_inds, uv) in uv_list_list[i]:
                for index in loop_inds:
                    loop_vert_inds[index] = len(vertices)
                vertex = mesh.vertices[i]
                vertices.append((
                    vertex.co,
                    vertex.normal,
                    uv))
            
        triangle_vert_inds = [0] * 3 * len(mesh.loop_triangles)
        for i in range(len(mesh.loop_triangles)):
            tri = mesh.loop_triangles[i]
            positions = [mesh.vertices[i].co for i in tri.vertices]
            normal = (positions[1] - positions[0]).cross(positions[2] - positions[1])
            loop_inds = tri.loops
            if normal.dot(tri.normal) < 0.0:
                loop_inds[1], loop_inds[2] = loop_inds[2], loop_inds[1]
            for j in range(3):
                triangle_vert_inds[3 * i + j] = loop_vert_inds[loop_inds[j]]
        
        # write header
        header = (
            "meshfile".encode("ascii"),
            3, 
            len(vertices), 
            len(triangle_vert_inds))
            
        f.write(struct.pack(header_fmt, *header))
            
        # write attributes
        # let's do position, normal, uv (in that order, very normal :) )
        attrib_sizes = []
        attrib_offsets = []
        vertex_size = 0
        vertex_fmt = "<"
        for i in range(3):
            num_components = len(vertices[0][i])
            attrib_sizes.append(4 * num_components)
            attrib_offsets.append(vertex_size)
            vertex_size += attrib_sizes[i]
            vertex_fmt += str(num_components) + "f"
            
        attrib_names = [
            "position",
            "normal",
            "texCoord"]
            
        for i in range(3):
            name = attrib_names[i]
            f.write(c_str(name))
            attribute = (
                0,  # float
                len(vertices[0][i]),
                attrib_offsets[i],
                vertex_size)
            f.write(struct.pack(attrib_fmt, *attribute))
            
        # write vertex buffer
        for vertex in vertices:
            components = []
            for element in vertex:
                components += list(element)
            f.write(struct.pack(vertex_fmt, *components))
            
        # write index buffer
        f.write(struct.pack("<" + str(len(triangle_vert_inds)) + "I", *triangle_vert_inds))
    
    return {'FINISHED'}

def export_scene(context, filename):
    return export_mesh(context.object, filename)

# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


class CustomMeshExport(Operator, ExportHelper):
    """Export to .mbin"""
    bl_idname = "vkcbu.export_mbin"
    bl_label = "Export binary .mbin"

    # ExportHelper mixin class uses this
    filename_ext = ".mbin"

    filter_glob: StringProperty(
        default="*.mbin",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    use_setting: BoolProperty(
        name="Example Boolean",
        description="Example Tooltip",
        default=True,
    )

    type: EnumProperty(
        name="Example Enum",
        description="Choose between two items",
        items=(
            ('OPT_A', "First Option", "Description one"),
            ('OPT_B', "Second Option", "Description two"),
        ),
        default='OPT_A',
    )

    def execute(self, context):
        return export_scene(context, self.filepath)


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(CustomMeshExport.bl_idname, text="Export binary .mbin")

# Register and add to the "file selector" menu (required to use F3 search "Text Export Operator" for quick access)
def register():
    bpy.utils.register_class(CustomMeshExport)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(CustomMeshExport)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.export_test.some_data('INVOKE_DEFAULT')
