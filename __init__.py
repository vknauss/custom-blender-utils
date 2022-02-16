bl_info = {
    "name": "VK's Custom Blender Utils",
    "description": "A collection of blender scripts for various tasks I need to automate",
    "author": "Vincent Knauss",
    "version": (0, 1, 0),
    "blender" : (2, 80, 0),
    "location": "Anywhere > Surprise",
    "category": "Miscellaneous"   
}

import importlib

if "bpy" in locals():
    if "custom_mesh_export" in locals():
        importlib.reload(custom_mesh_export)

from . import custom_mesh_export

import bpy

modules = [custom_mesh_export]

# classes = ()
# vkcbu_classes_register, vkcbu_classes_unregister = bpy.utils.register_classes_factory(classes)

def register():
    # vkcbu_classes_register()
    for module in modules:
        module.register()

def unregister():
    for module in modules:
        module.unregister()
    # vkcbu_classes_unregister()

if __name__ == "__main__":
    register()