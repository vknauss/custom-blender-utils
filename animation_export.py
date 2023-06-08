import bpy
import struct
from bpy_extras.io_utils import ExportHelper
from mathutils import Vector

def get_bone_pose(bone):
    return (Vector((0, bone.parent.length, 0)) + bone.head if bone.parent else bone.head,
        bone.matrix.to_quaternion())
        
def write_transform(f, position, rotation):
    f.write(struct.pack("<3f", -position.x, position.z, position.y))
    f.write(struct.pack("<4f", -rotation.x, rotation.z, rotation.y, rotation.w))
    
def export_animation(armature, context, filename):
    action = armature.animation_data.action
    armature.pose.backup_create(action)
    base_poses = [get_bone_pose(bone) for bone in armature.data.bones]
    
    with open(filename, "wb") as f:
        first_frame, last_frame = map(int, action.frame_range)
        f.write(struct.pack("<8sBI", "animfile".encode("utf-8"), len(armature.data.bones), last_frame - first_frame + 1))
        for frame in range(first_frame, last_frame + 1):
            armature.pose.apply_pose_from_action(action, evaluation_time = frame)
            context.view_layer.update()
            for ((base_position, base_rotation), bone) in zip(base_poses, armature.pose.bones):
                offset_matrix = bone.parent.matrix.inverted() @ bone.matrix if bone.parent else bone.matrix
                write_transform(f, offset_matrix.translation, offset_matrix.to_quaternion())
    
    armature.pose.backup_restore()
    return {'FINISHED'}

class AnimationExport(bpy.types.Operator, ExportHelper):
    """Export animation to custom binary file"""
    bl_idname = "vkcbu.export_animation"
    bl_label = "Export Animation"
    
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
            armature = (context.active_object if type(context.active_object.data) == bpy.types.Armature else
                context.active_object.find_armature())
            return armature is not None and armature.animation_data.action is not None
        return False

    def execute(self, context):
        armature = (context.active_object if type(context.active_object.data) == bpy.types.Armature else
            context.active_object.find_armature())
        return export_animation(armature, context, self.filepath)

def register():
    bpy.utils.register_class(AnimationExport)

def unregister():
    bpy.utils.unregister_class(AnimationExport)

if __name__ == "__main__":
    register()
