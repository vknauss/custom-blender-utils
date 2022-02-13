import bpy

bl_info = {
    "name": "Material Bake",
    "description": "Automates the process of baking materials for export in the GLTF 2.0 format.",
    "author": "Vincent Knauss",
    "version": (0, 1, 0),
    "blender" : (2, 80, 0),
    "location": "View3D > Object",
    "category": "Material"   
}

# Properties used for material baking

class VKMaterialBakeProperties(bpy.types.PropertyGroup):
    
    bake_diffuse: bpy.props.BoolProperty(name="Bake Diffuse", default=True)
    diffuse_texture_size: bpy.props.IntProperty(name="Size", default=2048, min=1)
    
    bake_normals: bpy.props.BoolProperty(name="Bake Normals", default=True)
    normals_texture_size: bpy.props.IntProperty(name="Size", default=2048, min=1)
    
    bake_emission: bpy.props.BoolProperty(name="Bake Emission", default=True)
    emission_texture_size: bpy.props.IntProperty(name="Size", default=2048, min=1)
    
    bake_metallic_roughness: bpy.props.BoolProperty(name="Bake Metallic + Roughness", default=True)
    metallic_roughness_texture_size: bpy.props.IntProperty(name="Size", default=2048, min=1)
    
    create_material: bpy.props.BoolProperty(name="Create Material from Bake", default=True)


# N-Panel GUI

class VKMaterialBakePanelBase(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Material Bake"
    bl_context = "objectmode"
    
class VKMB_PT_diffuse(VKMaterialBakePanelBase):
    bl_parent_id = "VKMB_PT_main_panel"
    bl_label = ""
    
    def draw_header(self, context):
        props = context.scene.VKMaterialBakeProps
        self.layout.prop(props, "bake_diffuse")
        
    def draw(self, context):
        props = context.scene.VKMaterialBakeProps
        self.layout.prop(props, "diffuse_texture_size")
        
class VKMB_PT_normals(VKMaterialBakePanelBase):
    bl_parent_id = "VKMB_PT_main_panel"
    bl_label = ""
    
    def draw_header(self, context):
        props = context.scene.VKMaterialBakeProps
        self.layout.prop(props, "bake_normals")
        
    def draw(self, context):
        props = context.scene.VKMaterialBakeProps
        self.layout.prop(props, "normals_texture_size")
        
class VKMB_PT_emission(VKMaterialBakePanelBase):
    bl_parent_id = "VKMB_PT_main_panel"
    bl_label = ""
    
    def draw_header(self, context):
        props = context.scene.VKMaterialBakeProps
        self.layout.prop(props, "bake_emission")
        
    def draw(self, context):
        props = context.scene.VKMaterialBakeProps
        self.layout.prop(props, "emission_texture_size")
        
class VKMB_PT_metallic_roughness(VKMaterialBakePanelBase):
    bl_parent_id = "VKMB_PT_main_panel"
    bl_label = ""
    
    def draw_header(self, context):
        props = context.scene.VKMaterialBakeProps
        self.layout.prop(props, "bake_metallic_roughness")
        
    def draw(self, context):
        props = context.scene.VKMaterialBakeProps
        self.layout.prop(props, "metallic_roughness_texture_size")

class VKMB_PT_main_panel(VKMaterialBakePanelBase):
    bl_idname = "VKMB_PT_main_panel"
    bl_label = "Material Bake"
    
    def draw(self, context):
        props = context.scene.VKMaterialBakeProps
        self.layout.operator("object.vk_bake_material")
        self.layout.prop(props, "create_material")
    
# The meat:

from typing import NamedTuple

class NodeTreeChanges(NamedTuple):
    node_tree: bpy.types.NodeTree
    added_nodes: list
    added_links: list
    removed_links: list
    changed_defaults: dict

# Base class defining the common interface for baking an attribute
class VKMaterialImageBaker:
    
    def __init__(self, enabled, image_size, type, bake_type, bake_pass_filter, image_alpha, image_data):
        self.enabled = enabled
        self.image_size = image_size
        self.node_tree_changes = {}
        self.current_tree_changes = None
        self.type = type
        self.bake_type = bake_type
        self.bake_pass_filter = bake_pass_filter
        self.image_alpha = image_alpha
        self.image_data = image_data
    
    
    def __on_edit_node_tree(self, node_tree):
        if not self.current_tree_changes or self.current_tree_changes.node_tree is not node_tree:
            self.current_tree_changes = self.node_tree_changes.get(node_tree, None)
            if not self.current_tree_changes:
                self.current_tree_changes = NodeTreeChanges(node_tree, [], [], [], {})
                self.node_tree_changes[node_tree] = self.current_tree_changes
                
    def __restore_node_tree(self, node_tree):
        self.__on_edit_node_tree(node_tree)
        
        for socket, value in self.current_tree_changes.changed_defaults.items():
            socket.default_value = value
        
        for link in self.current_tree_changes.added_links:
            node_tree.links.remove(link)
        
        for link_info in self.current_tree_changes.removed_links:
            node_tree.links.new(link_info['from'], link_info['to'])
            
        for node in self.current_tree_changes.added_nodes:
            node_tree.nodes.remove(node)
    
    # Methods to be used by subclasses for preparing the material node tree for baking
    # Using these methods ensures changes are tracked and can be reverted automatically
    
    def add_node(self, node_tree, node_type):
        self.__on_edit_node_tree(node_tree)
        
        node = node_tree.nodes.new(node_type)
        self.current_tree_changes.added_nodes.append(node)
        return node
    
    def add_link(self, node_tree, input, output):
        self.__on_edit_node_tree(node_tree)
        
        link = node_tree.links.new(input, output)
        self.current_tree_changes.added_links.append(link)
        return link
    
    def remove_link(self, node_tree, link):
        self.__on_edit_node_tree(node_tree)
        
        self.current_tree_changes.removed_links.append({'from':link.from_socket, 'to':link.to_socket})
        node_tree.links.remove(link)
        
    def set_default(self, node_tree, socket, value):
        self.__on_edit_node_tree(node_tree)
        
        self.current_tree_changes.changed_defaults[socket] = socket.default_value
        socket.default_value = value
        
    # This may be overridden by subclasses to implement custom node tree modification behavior
    # As long as subclasses use the above methods, these changes will be safely reverted after the bake
    def prepare_node_tree(self, node_tree):
        pass
    
    # The public interface for baking
    # It's assumed the image texture nodes have been created already and are passed in as object_image_texture_nodes,
    # in the format of a dictionary where keys are objects and values are lists of nodes
    # object_images is a dictionary where keys are objects and values are dictionaries, with keys being the bake type strings
    # and values being the images baked to. it should be pre-initialized with a dictionary per object by the caller.
    def execute(self, context, object_image_texture_nodes, object_images):
        ret = None
        if self.enabled:
            images = []
            
            #try:
            for object in context.selected_objects:
                for slot in object.material_slots:
                    self.prepare_node_tree(slot.material.node_tree)
            
            for object, image_texture_nodes in object_image_texture_nodes.items():
                image = bpy.data.images.new(object.name + "_bake_target_" + self.type,
                    self.image_size, self.image_size, alpha=self.image_alpha, is_data=self.image_data)
                
                images.append(image)
                object_images[object][self.type] = image
                for node in image_texture_nodes:
                    node.image = image
                    
            bpy.ops.object.bake(type=self.bake_type, pass_filter=self.bake_pass_filter)
        
            for image in images:
                image.pack()
            #except:
            #    ret = ({'WARNING'}, "One or more materials is not compatible with bake type: " + self.type + ". Bake will be skipped.")
            
            for node_tree in self.node_tree_changes.keys():
                self.__restore_node_tree(node_tree)
                
        return ret

# Baker subclass for diffuse images
class VKDiffuseImageBaker(VKMaterialImageBaker):
    
    def __init__(self, props):
        super().__init__(props.bake_diffuse, props.diffuse_texture_size, "diffuse", 'DIFFUSE', {'COLOR', 'DIFFUSE'}, True, False)
        
    def prepare_node_tree(self, node_tree):
        # Remove any metallic value, which for some reason interferes with diffuse bake
        # I'm not sure which BSDFs have metallic inputs, it may just be Principled, but I'm searching them all anyway
        bsdf_nodes = filter(lambda node: "Bsdf" in node.bl_idname, node_tree.nodes)
        for bsdf_node in bsdf_nodes:
            metallic_input = bsdf_node.inputs.get('Metallic', None)
            if metallic_input:
                if metallic_input.is_linked:
                    self.remove_link(node_tree, metallic_input.links[0])
                self.set_default(node_tree, metallic_input, 0.0)
    
# Baker subclass for normal maps
class VKNormalsImageBaker(VKMaterialImageBaker):
    
    def __init__(self, props):
        super().__init__(props.bake_normals, props.normals_texture_size, "normals", 'NORMAL', set(), False, True)
        
# Baker subclass for emission maps
class VKEmissionImageBaker(VKMaterialImageBaker):
    
    def __init__(self, props):
        super().__init__(props.bake_emission, props.emission_texture_size, "emission", 'EMIT', set(), False, True)
        
# Baker subclass for metallic + roughness maps
class VKMetallicRoughnessImageBaker(VKMaterialImageBaker):
    
    def __init__(self, props):
        super().__init__(props.bake_metallic_roughness, props.metallic_roughness_texture_size, "metallic_roughness", 'DIFFUSE', {'COLOR', 'DIFFUSE'}, False, True)
    
    # In order to bake a combined metallic + roughness image in the format expected by GLTF 2.0,
    # we need to modify the shader to put out metallic in the blue channel and roughness in the green
    # We use the diffuse color output for this, but we could just as well use the emission output or whatever
    def prepare_node_tree(self, node_tree):
        # Search the material for BSDF nodes
        bsdf_nodes = filter(lambda node: "Bsdf" in node.bl_idname, node_tree.nodes)
        for bsdf_node in bsdf_nodes:
            # Most BSDFs have roughness, and I think only Pricipled has metallic, but handle them both
            # as if they may or may not be present
            # If not, just let the unconnected socket default to 0
            metallic_input = bsdf_node.inputs.get('Metallic', None)
            roughness_input = bsdf_node.inputs.get('Roughness', None)
            
            # Try to get the color input (or output? lol)
            # Assuming mostly we're using Principled BSDF, it's called 'Base Color'
            # For basically every other BSDF, it's just 'Color'
            # If there happens to be a strange one that doesn't define either, skip it
            color_input = bsdf_node.inputs.get('Base Color', None)
            if not color_input:
                color_input = bsdf_node.inputs.get('Color', None)
            if not color_input:
                continue
            
            # Create a Combine RGB node to be the color output for this bake
            combine_node = self.add_node(node_tree, 'ShaderNodeCombineRGB')
            combine_metallic_input = combine_node.inputs['B']
            combine_roughness_input = combine_node.inputs['G']
            
            # Link whatever is set to the metallic and roughness, or copy their default values
            if metallic_input:
                if metallic_input.is_linked:
                    old_link = metallic_input.links[0]
                    link = self.add_link(node_tree, old_link.from_socket, combine_metallic_input)
                    # Remove the metallic link, since metalness interferes with diffuse output
                    self.remove_link(node_tree, old_link)
                else:
                    combine_metallic_input.default_value = metallic_input.default_value
                
                # Make sure metallic is set to 0.0 for the bake
                self.set_default(node_tree, metallic_input, 0.0)
                
            if roughness_input:
                # Roughness doesn't interfere with diffuse, so just leave it there for the bake
                if roughness_input.is_linked:
                    link = self.add_link(node_tree, roughness_input.links[0].from_socket, combine_roughness_input)
                else:
                    combine_roughness_input.default_value = roughness_input.default_value
            
            # Unlink and store the color input
            if color_input.is_linked:
                self.remove_link(node_tree, color_input.links[0])
            
            # Link the combined node to the color input
            self.add_link(node_tree, combine_node.outputs[0], color_input)
        

# Material baking operator
class VKMB_OP_bake_material(bpy.types.Operator):
    bl_idname = "object.vk_bake_material"
    bl_label = "Bake Material"
    bl_description = "Create and bake export-ready images from the selected objects' material(s)"
    bl_options = {'REGISTER', 'PRESET'}
    
    @classmethod
    def poll(cls, context):
        return context.selected_objects
    
    def execute(self, context):
        # Note: Bake targets are created per object, and assigned to each material of that object
        # If objects share materials, the results will probably be wrong, and will depend on the ordering of selected_objects
        # To avoid this, make sure no two selected objects share materials. If they do, select them separately
        
        props = context.scene.VKMaterialBakeProps
        
        # Add Image Texture nodes to each material per object, which will reference the bake targets
        added_nodes = {}
        object_image_texture_nodes = {}
        object_images = {}
        for object in context.selected_objects:
            image_texture_nodes = object_image_texture_nodes[object] = []
            object_images[object] = {}
            for slot in object.material_slots:
                tree = slot.material.node_tree
                node = tree.nodes.new("ShaderNodeTexImage")
                tree.nodes.active = node
                added_nodes[tree] = [node]
                image_texture_nodes.append(node)
            
        # Setup state and store old
        old_engine = context.scene.render.engine
        old_samples = context.scene.cycles.samples
        context.scene.render.engine = 'CYCLES'
        context.scene.cycles.samples = 1  # We aren't baking lighting, so more than 1 sample is not necessary
        
        # Execute image bakes
        bakers = [VKDiffuseImageBaker(props), VKNormalsImageBaker(props), VKEmissionImageBaker(props), VKMetallicRoughnessImageBaker(props)]
        for baker in bakers:
            ret = baker.execute(context, object_image_texture_nodes, object_images)
            if ret:
                self.report(*ret)
        
        # Create materials from bake
        if props.create_material:
            self.report({'INFO'}, "Creating material(s) from bakes")
            for object, images in object_images.items():
                bake_material = bpy.data.materials.new(object.name + "_bake")
                bake_material.use_nodes = True
                bsdf_node = bake_material.node_tree.nodes['Principled BSDF']
                
                image_nodes = {}
                for type, image in images.items():
                    image_node = bake_material.node_tree.nodes.new('ShaderNodeTexImage')
                    image_node.image = image
                    image_nodes[type] = image_node
                
                diffuse_image_node = image_nodes.get('diffuse', None)
                normals_image_node = image_nodes.get('normals', None)
                emission_image_node = image_nodes.get('emission', None)
                metallic_roughness_image_node = image_nodes.get('metallic_roughness', None)
                
                if diffuse_image_node:
                    bake_material.node_tree.links.new(diffuse_image_node.outputs[0], bsdf_node.inputs['Base Color'])
                    
                if normals_image_node:
                    normal_map_node = bake_material.node_tree.nodes.new('ShaderNodeNormalMap')
                    bake_material.node_tree.links.new(normals_image_node.outputs[0], normal_map_node.inputs['Color'])
                    bake_material.node_tree.links.new(normal_map_node.outputs['Normal'], bsdf_node.inputs['Normal'])
                    
                if emission_image_node:
                    bake_material.node_tree.links.new(emission_image_node.outputs[0], bsdf_node.inputs['Emission'])
                    
                if metallic_roughness_image_node:
                    separate_rgb_node = bake_material.node_tree.nodes.new('ShaderNodeSeparateRGB')
                    bake_material.node_tree.links.new(metallic_roughness_image_node.outputs[0], separate_rgb_node.inputs['Image'])
                    bake_material.node_tree.links.new(separate_rgb_node.outputs['B'], bsdf_node.inputs['Metallic'])
                    bake_material.node_tree.links.new(separate_rgb_node.outputs['G'], bsdf_node.inputs['Roughness'])
                    
        
        # Put the scene back
        context.scene.cycles.samples = old_samples
        context.scene.render.engine = old_engine
        
        # Cleanup by removing the added nodes from each of the object's materials    
        for tree, nodes in added_nodes.items():
            for node in nodes:
                tree.nodes.remove(node)
            
        return {'FINISHED'}


# Setup for registering

def menu_func(self, context):
    self.layout.operator(VKMaterialBakeOperator.bl_idname)

defined_classes = [
    VKMaterialBakeProperties, 
    VKMB_OP_bake_material,
    VKMB_PT_main_panel,
    VKMB_PT_diffuse,
    VKMB_PT_normals,
    VKMB_PT_emission,
    VKMB_PT_metallic_roughness]

def register():
    for c in defined_classes:
        bpy.utils.register_class(c)
    
    bpy.types.Scene.VKMaterialBakeProps = bpy.props.PointerProperty(type=VKMaterialBakeProperties)
    
    bpy.types.VIEW3D_MT_object.append(menu_func)
     
def unregister():
    for c in reversed(defined_classes):
        bpy.utils.unregister_class(c)
        
    del bpy.types.Scene.VKMaterialBakeProps
    
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    
if __name__ == "__main__":
    register()