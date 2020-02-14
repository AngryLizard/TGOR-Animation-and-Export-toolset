
import bpy

from bpy.types import Operator, Panel, UIList, PropertyGroup
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty
from bpy.props import CollectionProperty, PointerProperty

import xml.etree.ElementTree as ElementTree
import numpy as np
import re, os

from . import sl_const
from . import tgor_character
from . import tgor_util

####################################################################################################
############################################# LIST UI ##############################################
####################################################################################################

class SL_UL_MeshList(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        #split = layout.split(0.15)
                    
        # the text field/name property
        main = layout.column()
        main.label(text="%s"%(item.name))
            
    def invoke(self, context, event):
        pass

####################################################################################################
############################################# GROUPS ###############################################
####################################################################################################

class SLMeshProperty(PropertyGroup):

	object: StringProperty(
            name="Object", 
            description="name of the object"
        )

# There is a bug in blender where enum lists need to be referenced in python, otherwise there will be glitches and crashes.
# The list is populated in the __init__ draw function instead.
meshlist = []
def meshListA_callback(scene, context):		
    return meshlist[:32]

def meshListB_callback(scene, context):			
    return meshlist[32:64]

def meshListC_callback(scene, context):			
    return meshlist[64:96]

def meshListD_callback(scene, context):			
    return meshlist[96:128]

class SLMeshExportProperties(PropertyGroup):
    
    file_path: StringProperty(
            name = "Output",
            description = "Path to output file",
            default = "export.dae",
            subtype = "FILE_PATH"
        )

    patchCollada: BoolProperty(
            name="Patch", 
            description="Whether to patch binding matrices so meshes don't appear anorexic in SL",
            default=True
        )

    meshesA: EnumProperty(
            name="Meshes",
            items=meshListA_callback,
            description="Meshes to export",
            options={'ENUM_FLAG'}
        )

    meshesB: EnumProperty(
            name="Meshes",
            items=meshListB_callback,
            description="Meshes to export",
            options={'ENUM_FLAG'}
        )

    meshesC: EnumProperty(
            name="Meshes",
            items=meshListC_callback,
            description="Meshes to export",
            options={'ENUM_FLAG'}
        )

    meshesD: EnumProperty(
            name="Meshes",
            items=meshListD_callback,
            description="Meshes to export",
            options={'ENUM_FLAG'}
        )
    
    def getMeshes(self):
        return self.meshesA | self.meshesB | self.meshesC | self.meshesD

####################################################################################################
############################################# OPERATORS ############################################
####################################################################################################

class SL_OT_FixWeightmaps(Operator):
    bl_idname = "object.sl_mesh_fix_weightmaps"
    bl_label = "Fix weightmaps"
    bl_description = ("Clean, limit total and normalize all weightmaps")
    bl_options = {'REGISTER', 'UNDO'}

    limit: IntProperty(
            name = "Limit",
            description = "Max amount of weights per vertex",
            default = 4
        )

    threshold: FloatProperty(
            name = "Threshold",
            description = "Weight threshold for deletion",
            default = 0.01
        )

    def execute(self, context):

        FoundAny = False
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                FoundAny = True
                for vertex in obj.data.vertices:
                    
                    limit = min(self.limit, len(vertex.groups))
                    
                    # Get weights of remaining
                    weights = []
                    for group in vertex.groups:
                        weights.append((group.group, group.weight))

                    # Only keep n groups with biggest weight
                    weights.sort(key=lambda t: t[1])
                    for (idx, _) in weights[0:-limit]:
                        obj.vertex_groups[idx].remove([vertex.index])

                    # Normalize all weights
                    norm = 0.0
                    for group in vertex.groups:
                        norm += group.weight
                    if norm > 0.0:
                        for group in vertex.groups:
                            group.weight /= norm

                    # Grab weight data
                    cleans = []
                    for group in vertex.groups:
                        if group.weight <= self.threshold:
                            cleans.append(group.group)

                    # Remove groups that are 0
                    for clean in cleans:
                        obj.vertex_groups[clean].remove([vertex.index])

        if not FoundAny:
        	self.report({'ERROR'}, "No Mesh selected")
        	return {'CANCELLED'}

        return {'FINISHED'}


class SL_OT_ApplyModifiers(Operator):
    bl_idname = "object.sl_mesh_apply_modifiers"
    bl_label = "Apply Modifiers"
    bl_description = ("Apply modifiers of the selected object(s)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        error = False
        FoundAny = False
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                FoundAny = True

                # copying context for the operator's override
                contx = bpy.context.copy()
                contx['object'] = obj

                for mod in obj.modifiers[:]:
                    if not mod.type == 'ARMATURE':

                        contx['modifier'] = mod
                        
                        try:
                            # Only apply if visible in viewport
                            if mod.show_viewport:
                                bpy.ops.object.modifier_apply(contx, apply_as='DATA', modifier=mod.name)
                        except:
                            error = True
                            pass
        
        # Display error if we failed
        if error:
            self.report({"ERROR"}, "Applying modifiers failed for some")
            return {'CANCELLED'}

        if not FoundAny:
        	self.report({'ERROR'}, "No Mesh selected")
        	return {'CANCELLED'}

        return {'FINISHED'}

class SL_OT_RenameBones(Operator):
    bl_idname = "object.sl_mesh_rename_bones"
    bl_label = "Rename bones"
    bl_description = ("Rename bones given a mapping")
    bl_options = {'REGISTER', 'UNDO'}

    operation: EnumProperty(
            name = "Rename operation",
            description = "Which direction to rename to",
            items = [
                ("to_sl", "ToSL", "To SL"),
                ("to_blender", "ToBlender", "To Blender"),              
            ],
            default = "to_sl"
        )

    def execute(self, context):
        
        FoundAny = False
        for obj in context.selected_objects:
            if obj.type == 'ARMATURE':
                FoundAny = True
                
                namelist = sl_const.renameList

                # Reverse the renaming list if desired
                if self.operation == 'to_blender':
                    namelist = [(newname, name) for (name, newname) in namelist]

                for (name, newname) in namelist:

                    # get the pose bone with name
                    bone = obj.pose.bones.get(name)

                    # rename if no bone of that name
                    if not bone is None:
                        bone.name = newname

        if not FoundAny:
        	self.report({'ERROR'}, "No Armature selected")
        	return {'CANCELLED'}

        return {'FINISHED'}

class SL_OT_RemoveEmptyGroups(Operator):
    bl_idname = "object.sl_mesh_remove_empty_groups"
    bl_label = "Remove empty groups"
    bl_description = ("Remove all groups without any weights")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        FoundAny = False
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                FoundAny = True
                
                # Initialse weight for all groups to 0 
                maxWeight = {}
                for group in obj.vertex_groups:
                    maxWeight[group.index] = 0

                # Get group with max weight
                for vertex in obj.data.vertices:
                    for group in vertex.groups:
                        weight = obj.vertex_groups[group.group].weight(vertex.index)
                        if (weight > maxWeight[group.group]):
                            maxWeight[group.group] = weight


                # Figure which bones ought not to be decimated
                marked = []
                def mark(bone):


                    # See whether yourself or a child is marked
                    hasMark = False
                    for child in bone.children:
                        if mark(child):
                            hasMark = True
                    
                    # Get group index for this bone
                    group = obj.vertex_groups.find(bone.name)
                    if group >= 0:

                        # Register if marked
                        if (hasMark or (maxWeight[group] > 0.0)) and (bone.name in sl_const.validBones):
                            marked.append(group)
                            return True
                        
                    return hasMark
                
                if not obj.parent is None and obj.parent.type == 'ARMATURE': 
                    mark(obj.parent.data.bones[0])

                # Remove the groups if zero weights and not marked
                keys = list(maxWeight.keys())
                keys.sort(reverse=True)
                for key in keys:
                    if (maxWeight[key] <= 0) and (key not in marked):
                        obj.vertex_groups.remove(obj.vertex_groups[key])

        if not FoundAny:
        	self.report({'ERROR'}, "No Mesh selected")
        	return {'CANCELLED'}

        return {'FINISHED'}

class SL_OT_RemoveUnusedGroups(Operator):
    bl_idname = "object.sl_mesh_remove_unused_groups"
    bl_label = "Remove non-SL groups"
    bl_description = ("Remove all vertex groups not used in SL skeleton")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        FoundAny = False
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                FoundAny = True
                
                # Cannot remove during for loop
                removes = []
                for group in obj.vertex_groups:
                    if group.name not in sl_const.validBones:
                        removes.append(group)
                
                # Actually remove
                for remove in removes:
                    obj.vertex_groups.remove(remove)

        if not FoundAny:
        	self.report({'ERROR'}, "No Mesh selected")
        	return {'CANCELLED'}

        return {'FINISHED'}

class SL_OT_MeshExport(Operator):
    bl_idname = "object.sl_mesh_export"
    bl_label = "SL Mesh Export"
    bl_description = ("Do all preparations above and export mesh to the specified folder")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        # Create a class that houses userful and repetetive character references
        charRefHndlr = tgor_character.CharacterReferenceHandler(context)
        characterScene = charRefHndlr.characterScene
        
        # stop if no scene
        if not characterScene :
        	self.report({'ERROR'}, "Character setup is invalid, no scene.")
        	return {'FINISHED'}
        
        # Get the mesh object reference from the mesh name operator's input string property
        meshes = context.window_manager.sl_mesh_export.getMeshes()
        meshesToExport = [characterScene.objects.get(mesh) for mesh in meshes]
        meshesToExport = [meshToExport for meshToExport in meshesToExport]
        
        # Stop if no mesh
        if meshesToExport == []:
        	self.report({'ERROR'}, "No valid mesh supplied to operator properties")
        	return {'FINISHED'}
        
        # Get export path
        meshFolder = charRefHndlr.meshFolder
        
        # Stop if no paths gotten
        if not meshFolder:
        	self.report({'ERROR'}, "Character doesn't have mesh export path defined")
        	return {'FINISHED'}
        
        # Check path as absolute path TODO: Relative paths https://docs.blender.org/api/blender_python_api_2_77_0/bpy.path.html
        if not os.path.isdir(bpy.path.abspath(meshFolder)):
        	self.report({'ERROR'}, "Path '" + meshFolder + "' doesn't point to an existing directory (has to be absolute path).")
        	return {'FINISHED'}
        
        # getting the full fbx export file path
        filePath = bpy.path.abspath(os.path.join( meshFolder, tgor_util.makeValidFilename(meshesToExport[0].name) + ".dae"))
        # self.report({'WARNING'}, filePath)
        
        # -----------------------------		
        # Scene preparation
        
        # Go to object mode
        tgor_util.exitPoseMode(context)
        
        # Set timeline to 0 frame
        context.scene.frame_set(0)
        	
        # Go to object mode
        if context.object:
        	if not context.object.hide_get():
        		bpy.ops.object.mode_set(mode='OBJECT')
        
        # Deselect all
        for ob in bpy.data.objects:
        	ob.select_set(False)
        
        # Make mesh visible, seletable, and remember how they were 
        meshToExportWasHidden = [bool(meshToExport.hide_get()) for meshToExport in meshesToExport]		
        meshToExportWasSelectable = [bool(meshToExport.hide_select) for meshToExport in meshesToExport]
        for meshToExport in meshesToExport:
        	meshToExport.hide_select = False
        	meshToExport.hide_set(False)
        	meshToExport.select_set(True)
        
        if charRefHndlr.deformRig :
            charRefHndlr.deformRig.select_set(True)

        if charRefHndlr.controlRig :
            charRefHndlr.controlRig.select_set(True)

        # -----------------------------		
        # Making changes to scene
        
        # Duplicate (new objects should stay selected)
        bpy.ops.object.duplicate()
        
        bpy.ops.object.sl_mesh_apply_modifiers()
        bpy.ops.object.sl_mesh_rename_bones(operation='to_sl')
        bpy.ops.object.sl_mesh_remove_unused_groups()
        bpy.ops.object.sl_mesh_remove_empty_groups()
        bpy.ops.object.sl_mesh_fix_weightmaps()
        
        bpy.ops.wm.collada_export(
            filepath=filePath,
            prop_bc_export_ui_section = 'main',
            apply_modifiers = True,
            export_mesh_type = 0,
            export_mesh_type_selection = 'view',
            export_global_forward_selection = '-X',
            export_global_up_selection = 'Z',
            apply_global_orientation = True,
            selected = True,
            include_children = False,
            include_armatures = True,
            include_shapekeys = False,
            deform_bones_only = True,
            include_animations = True,
            include_all_actions = True,
            export_animation_type_selection = 'sample',
            sampling_rate = 1,
            keep_smooth_curves = False,
            keep_keyframes = False,
            keep_flat_curves = False,
            active_uv_only = True,
            use_texture_copies = True,
            triangulate = True,
            use_object_instantiation = False,
            use_blender_profile = True,
            sort_by_name = True,
            export_object_transformation_type = 0,
            export_object_transformation_type_selection = 'matrix',
            export_animation_transformation_type = 0,
            export_animation_transformation_type_selection = 'matrix',
            open_sim = True,
            limit_precision = False,
            keep_bind_info = False)

		# -----------------------------		
		# Cleanup
		
		# Delete duplicated stuff
        bpy.ops.object.delete(use_global=False)
        
        for meshToExport, hide, hide_select in zip(meshesToExport, meshToExportWasHidden, meshToExportWasSelectable):
        	meshToExport.hide_set(hide)
        	meshToExport.hide_select = hide_select

        if context.window_manager.sl_mesh_export.patchCollada:

            # Read namespace first because elementtree needs to know before parsing
            tree = ElementTree.parse(filePath)
            root = tree.getroot()
            ns = re.match(r'{(.*)}', root.tag).group(0)
            ElementTree.register_namespace('', ns[1:-1])

            # Parse again
            tree = ElementTree.parse(filePath)
            root = tree.getroot()

            for libcontrollers in root.findall(f'{ns}library_controllers'):
                for controller in libcontrollers.findall(f'{ns}controller'):
                    for skin in controller.findall(f'{ns}skin'):

                        jointElem = None
                        transformElem = None

                        # Grab joint names and transforms from document
                        for source in skin.findall(f'{ns}source'):
                            accessor = source.find(f'{ns}technique_common').find(f'{ns}accessor').find(f'{ns}param').get('name')
                            if accessor == 'JOINT':
                                jointElem = source.find(f'{ns}Name_array')
                            elif accessor == 'TRANSFORM':
                                transformElem = source.find(f'{ns}float_array')

                        # Extract joint names and transforms (stored in n x 16 list)
                        joints = jointElem.text.split(' ')
                        transforms = np.fromstring(transformElem.text, dtype=float, sep=' ').reshape((len(joints), 16))

                        # Transform if a corresponding scale exists
                        for idx, joint in enumerate(joints):
                            if joint in sl_const.colladaLookup:
                                
                                # Get 4x4 transform from correct row
                                T = transforms[idx, :].reshape((4,4))

                                # Do transformation
                                scale = sl_const.colladaLookup[joint]
                                inv = np.array([1.0/s for s in scale])

                                # Create transform, for now just scaling
                                transform = np.eye(4)
                                transform[:3, :3] = np.diag(inv)
                                T = np.matmul(transform, T)
                                
                                # Set back in row format
                                transforms[idx, :] = T.reshape(16)

                        # Write the transforms back
                        transformElem.text = ' '.join(map(str, transforms.reshape((len(joints) * 16))))

            outFile = open(filePath, "wb")
            tree.write(outFile, encoding='utf-8', xml_declaration=True)
        
        self.report({'INFO'}, "Exported to @ %s" % (filePath))
        return {'FINISHED'}


####################################################################################################
############################################# PANEL ################################################
####################################################################################################

class SL_PT_MeshExportPanel(Panel):
    # SL Export panel
    bl_idname = "SL_PT_MeshExportPanel"
    bl_label = "SL Mesh Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SecondLife"

    def draw(self, context):

        self.layout.label(text="Second Life export tools")

        row = self.layout.row()
        col = row.column()
        col.label(text="Preparation:")
        col.operator("object.sl_mesh_apply_modifiers", icon='IMPORT')
        col.operator("object.sl_mesh_rename_bones", icon='BONE_DATA')
        col.operator("object.sl_mesh_remove_unused_groups", icon='EDITMODE_HLT')
        col.operator("object.sl_mesh_remove_empty_groups", icon='MESH_DATA')
        col.operator("object.sl_mesh_fix_weightmaps", icon='MOD_VERTEX_WEIGHT')

        row.separator()

        row = self.layout.row()
        col = row.column()
        col.label(text="Export collada:")
        col.prop(context.window_manager.sl_mesh_export, 'file_path')
        col.operator("object.sl_mesh_export", icon='FILE_TICK')
        col.operator("object.sl_mesh_patch_collada", icon='FILE_CACHE')


####################################################################################################
############################################# REGISTER #############################################
####################################################################################################

classes = (
    SL_OT_FixWeightmaps,
    SL_OT_ApplyModifiers,
    SL_OT_RenameBones,
    SL_OT_RemoveEmptyGroups,
    SL_OT_RemoveUnusedGroups,
    SL_OT_MeshExport,

    #SL_PT_MeshExportPanel,

    SL_UL_MeshList,

    SLMeshProperty,
    SLMeshExportProperties,
)
    
      
def register():
    from bpy.utils import register_class
    for c in classes:
        register_class(c)

    bpy.types.WindowManager.sl_mesh_export = PointerProperty(type=SLMeshExportProperties)


def unregister():
    del bpy.types.WindowManager.sl_mesh_export

    from bpy.utils import unregister_class
    for c in reversed(classes):
        unregister_class(c)
