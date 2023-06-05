from functools import reduce
import bpy
import struct
from mathutils import Vector

# Header format string
# https://docs.python.org/3.5/library/struct.html#struct.pack
# < : little-endian byte order, standard type sizes and no padding
# 8s : 8-character formatted string (encoded ascii in this case) : "meshfile"
# B : unsigned char : number of attributes
# 3I : 3 uint32_t : vertex size, vertex count, index count
header_fmt = "<8sB3I"

attrib_fmt = "<2I"

def c_str(s, encoding = "ascii"):
    return struct.pack("<" + str(len(s) + 1) + "s", s.encode(encoding))

# find all the uv coords used by each vertex, and which loops use which uvs
# return a tuple of lists
# the first list contains a list per mesh vertex, whose items are a tuple containing
# a uv coordinate and a list of loop indices for that uv
# the second list contains an index per loop, of which uv it uses for its corresponding vertex
def map_vertex_uvs(mesh, uv_layer):
    vertex_uv_lists = [[] for _ in mesh.vertices]
    loop_uv_inds = [0] * len(mesh.loops)
    for loop, uv_loop in zip(mesh.loops, uv_layer.data):
        uv_list = vertex_uv_lists[loop.vertex_index]
        c_uv = uv_loop.uv
        found = False
        for i in range(len(uv_list)):
            (uv, loop_inds) = uv_list[i]
            if (c_uv - uv).length < 0.001:
                found = True
                loop_uv_inds[loop.index] = i
                loop_inds.append(loop.index)
                break
        if not found:
            loop_uv_inds[loop.index] = len(uv_list)
            uv_list.append((c_uv, [loop.index]))
    return (vertex_uv_lists, loop_uv_inds)

# find all normals for each vertex, and which loops use which normals
# returns similar info to above, except for normals rather than uvs
# this method handles smooth and flat shading per polygon
# if only smooth shading is used, every normal will just be the vertex normal
def map_vertex_normals(mesh):
    # list containing lists of tuples of vertex normals and list of indices for that normal
    # for each vertex 
    vertex_normals_list = [[] for _ in mesh.vertices]
    loop_normal_inds = [0] * len(mesh.loops)
    for poly in mesh.polygons:
        # use polygon normal if flat shaded otherwise use vertex normal
        normals = ([poly.normal] * len(poly.loop_indices) if not poly.use_smooth else
            [mesh.vertices[v].normal for v in [mesh.loops[i].vertex_index for i in poly.loop_indices]])

        # iterate both the normals and loops that make up this polygon
        for (c_n, loop) in zip(normals, [mesh.loops[i] for i in poly.loop_indices]):
            normals_list = vertex_normals_list[loop.vertex_index]
            # try to find if this normal is in the list of normals for this vertex already
            found = False
            for i in range(len(normals_list)):
                (n, loop_inds) = normals_list[i]
                if (c_n - n).length < 0.001:
                    # if found, add this loop index to the list
                    found = True
                    loop_normal_inds[loop.index] = i
                    loop_inds.append(loop.index)
                    break
            # if not found, add an item to the list for this normal and loop
            if not found:
                loop_normal_inds[loop.index] = len(normals_list)
                normals_list.append((c_n, [loop.index]))
    
    return (vertex_normals_list, loop_normal_inds)

# compute and enumerate the combinations of uv and normal for each vertex in the mesh
# also compute the index into the final vertex loop for each loop in the mesh
#
# returns a tuple containing two lists and the total output vertex (permutation) count
#
# the first list contains for each vertex a list of tuples, which in turn contain
# the index into the final vertex list for this permutation, and the indices of the uv and
# normal used by this permutation each as numbers in the range of 0 until the count of either
# uvs or normals for this vertex, so they can index into the per-vertex lists returned by
# the map_* functions above
#
# the second list contains the index for each loop of the loop's vertex permutation, i.e.
# the vertex index we need to write for this loop
def find_vertex_permutations(mesh, loop_uv_inds, loop_normal_inds):
    # figure out which combinations of vertex uvs and normals we need to export
    # also figure out what the indices will be since the info we need is all here
    vertex_permutations = [[] for _ in mesh.vertices]
    loop_inds = [0] * len(mesh.loops)
    c_index = 0
    for (loop, c_uv_ind, c_normal_ind) in zip(mesh.loops, loop_uv_inds, loop_normal_inds):
        found = False
        perms = vertex_permutations[loop.vertex_index]
        for i in range(len(perms)):
            (ind, uv_ind, normal_ind) = perms[i]
            if c_uv_ind == uv_ind and c_normal_ind == normal_ind:
                found = True
                loop_inds[loop.index] = ind
        if not found:
            perms.append((c_index, c_uv_ind, c_normal_ind))
            loop_inds[loop.index] = c_index
            c_index += 1

    return (vertex_permutations, loop_inds, c_index)


def export_mesh(object, filename, export_skinning_data):
    print("Exporting mesh to: " + filename)
    mesh = object.data
    with open(filename, "wb") as f:
        # number of attributes, vertices, and indices must be computed
        # blender mesh data does not 1-1 represent the sort of data we need
        # so there are some decoding steps we need to take
        
        # check for uvs, todo: allow an option to enable/disable uv exporting,
        # as well as choosing a particular uv layer for export
        uv_layer = mesh.uv_layers[0] if mesh.uv_layers else None
        
        # for now lets just assume we are writing texcoords, positions, and normals
        
        # calculate triangulation
        if not mesh.loop_triangles:
            mesh.calc_loop_triangles()

        # get all info needed to write vertex permutations
        # permutations of position, normal, and uv per mesh vertex that is
        # each needs to be exported as a separate vertex, but we still don't want duplicates
        # so we do some computation
        (vertex_uvs, loop_uv_inds) = map_vertex_uvs(mesh, uv_layer)
        (vertex_normals, loop_normal_inds) = map_vertex_normals(mesh)
        (vertex_perms, loop_inds, num_vertices) = find_vertex_permutations(mesh, loop_uv_inds, loop_normal_inds)

        # get the loop indices in the proper number and order for triangulation
        # iterate over each triangle and get the permutation index of each loop
        # concatenating the lists as we go
        tri_inds = reduce(list.__add__, [[loop_inds[i] for i in tri.loops] for tri in mesh.loop_triangles], [])

        # compute the actual vertex permutations using the indices we computed
        positions = [None] * num_vertices
        normals = [None] * num_vertices
        uvs = [None] * num_vertices
        joint_weights = [None] * num_vertices if export_skinning_data else []
        joint_indices = [None] * num_vertices if export_skinning_data else []
        for (vert, perms) in zip(mesh.vertices, vertex_perms):
            if export_skinning_data:
                joint_inds = [0, 0, 0, 0]
                weights = [0, 0, 0, 0]
                num_joints = 0
                for group in vert.groups:
                    if num_joints < 4:
                        joint_inds[num_joints] = group.group
                        weights[num_joints] = group.weight
                        num_joints += 1
                    else:
                        for i in range(num_joints):
                            if weights[i] < group.weight:
                                joint_inds[i] = group.group
                                weights[i] = group.weight
                                break
                weight_sum = 0
                for weight in weights:
                    weight_sum += weight
                if weight_sum > 0:
                    for weight in weights:
                        weight = weight / weight_sum
                for (ind, _, _) in perms:
                    joint_weights[ind] = weights
                    joint_indices[ind] = joint_inds
                    
            for (ind, uv_ind, normal_ind) in perms:
                (normal, _) = vertex_normals[vert.index][normal_ind]
                (uv, _) = vertex_uvs[vert.index][uv_ind]
                positions[ind] = Vector((-vert.co.x, vert.co.z, vert.co.y))
                normals[ind] = normal
                uvs[ind] = uv
        
        attrib_infos = [
            ("position", "<3f", positions),
            ("normal", "<3f", normals),
            ("texCoord", "<2f", uvs)]
        
        if export_skinning_data:
            attrib_infos += [
                ("jointWeights", "<4f", joint_weights),
                ("jointIndices", "<4B", joint_indices)]
                
        attrib_sizes = []
        attrib_offsets = []
        vertex_size = 0
        for (name, format, _) in attrib_infos:
            attrib_sizes.append(struct.calcsize(format))
            attrib_offsets.append(vertex_size)
            vertex_size += attrib_sizes[-1]
        
        # write header
        header = (
            "meshfile".encode("ascii"),
            len(attrib_infos),
            vertex_size,
            num_vertices, 
            len(tri_inds))
            
        f.write(struct.pack(header_fmt, *header))
            
        # write attributes
        # interleaved as position, normal, uv (in order)
        for i in range(len(attrib_infos)):
            (name, _, _) = attrib_infos[i]
            f.write(c_str(name))
            attribute = (
                attrib_sizes[i],
                attrib_offsets[i])
            f.write(struct.pack(attrib_fmt, *attribute))
            
        # write vertex buffer
        for i in range(num_vertices):
            for (_, format, elements) in attrib_infos:
                f.write(struct.pack(format, *(elements[i])))
            
        # write index buffer
        f.write(struct.pack("<" + str(len(tri_inds)) + "I", *tri_inds))
    
    return {'FINISHED'}

def export_scene(context, filename, export_skinning_data):
    return export_mesh(context.object, filename, export_skinning_data)

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
    export_skinning_data: BoolProperty(
        name="Export skinning data",
        description="Export skinning data",
        default=False,
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
        return export_scene(context, self.filepath, self.export_skinning_data)


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
    bpy.ops.vkcbu.export_mbin('INVOKE_DEFAULT')
