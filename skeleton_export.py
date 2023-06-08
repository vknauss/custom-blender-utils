import bpy
import struct
from bpy_extras.io_utils import ExportHelper
from mathutils import Vector

def c_str(s):
    return struct.pack("<" + str(len(s) + 1) + "s", s.encode("utf-8"))

def export_skeleton(armature, filename):
    with open(filename, "wb") as f:
        f.write(struct.pack("<8sB", "skelfile".encode("utf-8"), len(armature.data.bones)))
        
        for bone in armature.data.bones:
            position = Vector((0, bone.parent.length, 0)) + bone.head if bone.parent else bone.head
            f.write(struct.pack("<3f", -position.x, position.z, position.y))
            rotation = bone.matrix.to_quaternion()
            f.write(struct.pack("<4f", -rotation.x, rotation.z, rotation.y, rotation.w))
            f.write(struct.pack("<b", next((i for i in range(len(armature.data.bones)) if armature.data.bones[i] == bone.parent), -1)))
    
    return {'FINISHED'}

class CustomSkeletonExport(bpy.types.Operator, ExportHelper):
    """Export skeleton to custom binary file"""
    bl_idname = "vkcbu.export_skeleton"
    bl_label = "Export Skeleton"

    # ExportHelper mixin class uses this
    filename_ext = ".bin"

    filter_glob: bpy.props.StringProperty(
        default="*.bin",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    
    @classmethod
    def poll(cls, context):
        if context.active_object:
            return (type(context.active_object.data) == bpy.types.Armature or
                context.active_object.find_armature() is not None)
        return False

    def execute(self, context):
        armature = (context.active_object if type(context.active_object.data) == bpy.types.Armature else
            context.active_object.find_armature())
        return export_skeleton(armature, self.filepath)

def register():
    bpy.utils.register_class(CustomSkeletonExport)

def unregister():
    bpy.utils.unregister_class(CustomSkeletonExport)

if __name__ == "__main__":
    register()
