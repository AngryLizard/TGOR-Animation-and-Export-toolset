
import bpy
from bpy.types import Operator, Panel, UIList, PropertyGroup
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty
from bpy.props import CollectionProperty, PointerProperty

import re
import os
import math
from mathutils import Matrix, Vector, Euler, Quaternion

from . import sl_animation
from . import sl_mesh
from . import tgor_character
from . import tgor_util


####################################################################################################
############################################# GROUPS ###############################################
####################################################################################################


class TGORActionsProperty(PropertyGroup):

	action: StringProperty(
            name="Action", 
            description="Assigned action"
        )

class TGORActionSettingsProperty(PropertyGroup):

	# Name field for the new action dialogue
	action_name: StringProperty(
			name="Name", 
			description="Name for new action", 
			default="Action"
		)
        
	# Automatic frame range boolean													
	exportAnimCharacterName: BoolProperty(
			name="Include character name",
			description="Set character name as prefix on exported animation .fbx files",
			default=False
		)

	# Cached name of the selected object's action													
	exportMode: EnumProperty(
			name="Export Mode",
			description="What to export",
			items=	[
				("UEAnim", "UE Animation", "Export current character action for UE as animation to the work folder.", "POSE_DATA", 0),
				("UEMesh", "UE Skel Mesh", "Export all character's geometry for UE as skeletal meshes with LODs to work folder.", "ARMATURE_DATA", 1),
				("SLAnim", "SL Animation", "Export current character action for SL as animation to the work folder.", "POSE_DATA", 2),
				("SLMesh", "SL Skel Mesh", "Export all character's geometry for SL as skeletal meshes with LODs to work folder.", "ARMATURE_DATA", 3),
			]
		)


####################################################################################################
############################################# OPERATORS ############################################
####################################################################################################

class TGOR_OT_ExportSkelMesh(Operator):
	bl_label = "Export Skeletal mesh"
	bl_idname = "object.tgor_export_character_skel_mesh"
	bl_description = "Export specified rigged meshes that belong to the current character"
	
	# helper function to reset armature poses
	def resetArmaturePose(self, armature):

		# if control rig exists
		if armature:

			# Unset control rig's action
			if armature.animation_data:
				armature.animation_data.action = None
			
			# for each pose bone in the armature
			for pb in armature.pose.bones:
				
				# Remove all constraints
				# get a list of all bone's constraints
				constraints = [cn for cn in pb.constraints]

				# iterate through that list and call remove functions for each
				for c in constraints:
					pb.constraints.remove(c)

				# Set the rotation to 0
				pb.rotation_quaternion = Quaternion( (0, 0, 0), 0 )

				# Set the scale to 1
				pb.scale = Vector( (1, 1, 1) )

				# Set the location to 0
				pb.location = Vector( (0, 0, 0) )
				
		return
		
	
	def execute(self, context):
		
		# Create a class that houses userful and repetetive character references
		charRefHndlr = tgor_character.CharacterReferenceHandler(context)
		
		# Get scene
		characterScene = charRefHndlr.characterScene

		# stop if no scene
		if not characterScene :
			self.report({'ERROR'}, "Character setup is invalid, no scene.")
			return {'FINISHED'}
		
		# Get deform rig
		deformRig = charRefHndlr.deformRig

		# Stop if there is no deform rig
		if not deformRig :
			self.report({'ERROR'}, "Character setup is invalid, no deform rig to export.")
			return {'FINISHED'}
		
		# Check if there is any object named Armature in the scene, because if there is, it will break UE4 export/import pipeline
		previousArmature = bpy.data.objects.get("Armature")
		if previousArmature:
			previousArmature.name = "Armature_"

		# Get the mesh object reference from the mesh name operator's input string property
		meshes = context.window_manager.sl_mesh_export.getMeshes()
		meshesToExport = [characterScene.objects.get(mesh) for mesh in meshes]
		meshesToExport = [meshToExport for meshToExport in meshesToExport if tgor_util.exportableMesh(deformRig, meshToExport)]

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
		filePath = bpy.path.abspath(os.path.join( meshFolder, tgor_util.makeValidFilename(meshesToExport[0].name) + ".fbx"))
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
		
		# Make mesh and deform rig visible, seletable, and remember how they were 
		deformRigWasHidden = bool(deformRig.hide_get())
		deformRig.hide_set(False)
		
		deformRigWasSelectable = bool(deformRig.hide_select)
		deformRig.hide_select = False
		
		meshToExportWasHidden = [bool(meshToExport.hide_get()) for meshToExport in meshesToExport]		
		meshToExportWasSelectable = [bool(meshToExport.hide_select) for meshToExport in meshesToExport]
		for meshToExport in meshesToExport:
			meshToExport.hide_select = False
			meshToExport.hide_set(False)
			meshToExport.select_set(True)
		
		# Select deform rig 
		deformRig.select_set(True)
		
		# Make rig as active object
		context.view_layer.objects.active = deformRig
		
		# Before duplication, make sure the object is visible and on correct layer
		if not context.object in context.visible_objects:
			self.report({'ERROR'}, "Can't unhide deformRig, it's either on another scene layer or locked invisible.")
			return {'FINISHED'}
		
		# -----------------------------		
		# Making changes to scene
		
		# Duplicate (new objects should stay selected)
		bpy.ops.object.duplicate()
		dupDeformRig = context.view_layer.objects.active
		
		# Make sure duplication worked
		if dupDeformRig == deformRig:
			self.report({'ERROR'}, "Duplication of deform rig didn't work. Make sure its visible and accessiable.")
			return {'FINISHED'}
			
		# Rename duplicated rig to "Armature"
		dupDeformRig.name = "Armature"
		
		# Remove all bone constraints and reset pose
		self.resetArmaturePose(dupDeformRig)
		
		# -----------------------------		
		# Export selected as FBX (with special UE4 settings)	
		bpy.ops.export_scene.fbx(
			filepath = filePath,
			axis_forward = '-Y',
			axis_up = 'Z',
			#version = 'BIN7400',
			#ui_tab = 'MAIN',
			use_selection = True,
			global_scale = 1.0,
			apply_unit_scale = True,
			apply_scale_options = 'FBX_SCALE_NONE',
			bake_space_transform = False,
			object_types = {'MESH', 'ARMATURE'},
			use_mesh_modifiers = True,
			use_mesh_modifiers_render = True,
			mesh_smooth_type = 'FACE',
			use_mesh_edges = False,
			use_tspace = False,
			use_custom_props = False,
			add_leaf_bones = False,
			primary_bone_axis = 'Y',
			secondary_bone_axis = 'X',
			use_armature_deform_only = True,
			armature_nodetype = 'NULL',
			bake_anim = False,
			bake_anim_use_all_bones = True,
			bake_anim_use_nla_strips = True,
			bake_anim_use_all_actions = True,
			bake_anim_force_startend_keying = True,
			bake_anim_step = 1.0,
			bake_anim_simplify_factor = 0.0,
			#use_anim = True,
			#use_anim_action_all = True,
			#use_default_take = True,
			#use_anim_optimize = True,
			#anim_optimize_precision = 6.0,
			path_mode = 'AUTO',
			embed_textures = False,
			batch_mode = 'OFF',
			use_batch_own_dir = True
		)
		
		# -----------------------------		
		# Cleanup
		
		# Delete duplicated stuff
		bpy.ops.object.delete(use_global=False)
		
		# Check if nothing vital got deleted
		if not deformRig:
			self.report({'ERROR'}, "Something went wrong during the script and the objects got deleted. Try undoing the last step and verify if fbx got exported.")
			return {'FINISHED'}
		
		# Restore object visibility settings  
		deformRig.hide_set(deformRigWasHidden)
		deformRig.hide_select = deformRigWasSelectable

		for meshToExport, hide, hide_select in zip(meshesToExport, meshToExportWasHidden, meshToExportWasSelectable):
			meshToExport.hide_set(hide)
			meshToExport.hide_select = hide_select

		# Rename armature back if renamed
		if previousArmature:
			previousArmature.name = "Armature"
		
		# Report a message about export
		self.report({'INFO'}, "Mesh exported @ "+filePath)
		return {'FINISHED'}
		

# ------------------------------------------------------------------
# Export animation
class TGOR_OT_ExportAnimation(Operator):
	bl_label = "Export Animation"
	bl_idname = "object.tgor_export_character_animation"
	bl_description = "Export current action as animated skeletal mesh fbx"
			
	def execute(self, context):
		selectedName = context.scene.tgor_character_selection.characters_selection
				
		# -----------------------------	
		# Preparations
				
		# Create a class that houses userful and repetetive character references
		charRefHndlr = tgor_character.CharacterReferenceHandler(context)
				
		# Get deform rig
		deformRig = charRefHndlr.deformRig
		# Stop if there is no deform rig
		if not deformRig :
			self.report({'ERROR'}, "Character setup is invalid, no deform rig to export.")
			return {'FINISHED'}
		
		
		
		# Get control rig
		controlRig = charRefHndlr.controlRig
		# Stop if there is no control rig
		if not controlRig :
			self.report({'ERROR'}, "Character setup is invalid, no control rig to get animations from.")
			return {'FINISHED'}
		
		
		
		# Check if both rigs aren't identical
		if deformRig == controlRig:
			self.report({'ERROR'}, "Control rig and deform rig are the same, this is not how the script is intended to be used.")
			return {'FINISHED'}
		
		
		
		# Get action
		action = charRefHndlr.action
		# Stop if there is no action
		if not action :
			self.report({'ERROR'}, "Control rig doesn't have any action assigned to it, nothing to export.")
			return {'FINISHED'}
		
		# Check if there is any object named Armature in the scene, because if there is, it will break UE4 export/import pipeline
		previousArmature = bpy.data.objects.get("Armature")
		if previousArmature:
			previousArmature.name = "Armature_"
		
		# Stop if no paths gotten
		if not charRefHndlr.animFolder:
			self.report({'ERROR'}, "Character doesn't have animation export path defined.")
			return {'FINISHED'}
		
		# Check path as absolute path TODO: Relative paths https://docs.blender.org/api/blender_python_api_2_77_0/bpy.path.html
		if not os.path.isdir(bpy.path.abspath(charRefHndlr.animFolder)):
			self.report({'ERROR'}, "Path '" + charRefHndlr.animFolder + "' doesn't point to an existing directory (has to be absolute path).")
			return {'FINISHED'}
		
		# getting the full fbx export file path
		includeCharacterName = context.window_manager.tgor_action_settings.exportAnimCharacterName
		filename = tgor_util.makeValidFilename(selectedName+"_"+action.name if includeCharacterName else action.name)+".fbx"
		filePath = bpy.path.abspath(os.path.join(charRefHndlr.animFolder, filename))
		
		# ------------------------------------------------------------------
		# Scene preparation	
		
		# Go to object mode
		tgor_util.exitPoseMode(context)
		
		# Deselect all
		for ob in bpy.data.objects:
			ob.select_set(False)
		
		# Make deform rig visible, selectable and remember how it was 
		deformRigWasHidden = bool(deformRig.hide_get())
		deformRig.hide_set(False)
		
		deformRigWasSelectable = bool(deformRig.hide_select)
		deformRig.hide_select = False
		
		# Select deform rig 
		deformRig.select_set(True)
		
		# Make rig as active object
		context.view_layer.objects.active = deformRig
		
		# Before duplication, make sure the object is visible and on correct layer
		if not context.object in context.visible_objects:
			self.report({'ERROR'}, "Can't unhide deformRig, it's either on another scene layer or locked invisible.")
			return {'FINISHED'}

		# -----------------------------		
		# Making changes to scene
		
		# Duplicate (new objects should be selected)
		bpy.ops.object.duplicate()
		dupDeformRig = context.view_layer.objects.active
		
		# Make sure duplication worked
		if dupDeformRig == deformRig:
			self.report({'ERROR'}, "Duplication of deform rig didn't work. Make sure its visible and accessiable.")
			return {'FINISHED'}
		
		# bake action (make a temporary action for it, current frame range only, removing all constraints)
		bpy.ops.nla.bake(frame_start=context.scene.frame_start, frame_end=context.scene.frame_end, visual_keying=True, clear_constraints=True, bake_types={'POSE'})
		
		# Store the reference to that action
		bakedAction = dupDeformRig.animation_data.action
		
		# Rename duplicated rig to "Armature"
		dupDeformRig.name = "Armature"
	
		# -----------------------------		
		# Export selected as FBX (with special UE4 settings)
		bpy.ops.export_scene.fbx(
			filepath = filePath,
			axis_forward = '-Y',
			axis_up = 'Z',
			#version = 'BIN7400',
			#ui_tab = 'MAIN',
			use_selection = True,
			global_scale = 1.0,
			apply_unit_scale = True,
			apply_scale_options = 'FBX_SCALE_NONE',
			bake_space_transform = False,
			object_types = {'ARMATURE'},
			use_mesh_modifiers = True,
			use_mesh_modifiers_render = True,
			mesh_smooth_type = 'OFF',
			use_mesh_edges = False,
			use_tspace = False,
			use_custom_props = False,
			add_leaf_bones = False,
			primary_bone_axis = 'Y',
			secondary_bone_axis = 'X',
			use_armature_deform_only = True,
			armature_nodetype = 'NULL',
			bake_anim = True,
			bake_anim_use_all_bones = True,
			bake_anim_use_nla_strips = False,
			bake_anim_use_all_actions = False,
			bake_anim_force_startend_keying = True,
			bake_anim_step = 1.0,
			bake_anim_simplify_factor = 0.0,
			#use_anim = True,
			#use_anim_action_all = True,
			#use_default_take = True,
			#use_anim_optimize = True,
			#anim_optimize_precision = 6.0,
			path_mode = 'AUTO',
			embed_textures = False,
			batch_mode = 'OFF',
			use_batch_own_dir = True,
		)
			
		# -----------------------------		
		# Cleanup
				
		# Delete action
		bpy.data.actions.remove(bakedAction)
		
		# Delete duplicated stuff
		bpy.ops.object.delete(use_global=False)
				
		# Check if nothing vital got deleted
		if not deformRig and controlRig:
			self.report({'ERROR'}, "Something went wrong during the script and the objects got deleted. Try undoing the last step and verify if fbx got exported.")
			return {'FINISHED'}
		
		# Restore object visibility settings  
		deformRig.hide_set(deformRigWasHidden)
		deformRig.hide_select = deformRigWasSelectable

		# Rename armature back if renamed
		if previousArmature:
			previousArmature.name = "Armature"
		
		# Report a message about export
		self.report({'INFO'}, "Animation exported @ "+filePath)
		return {'FINISHED'}
	
		

# ------------------------------------------------------------------
# Copy selected action
class TGOR_OT_ActionCopyOperator(Operator):
	bl_label = "Copy action"
	bl_idname = "scene.tgor_action_copy_operator"
	bl_description = "Copy action"
	
	def execute(self, context):

		# Get current character name to display it in the label
		selectedAction = context.scene.tgor_character_selection.action_selection		
		
		# Check if action index refers to an actual action in the scene
		if selectedAction < len(bpy.data.actions):
			
			# Get action data object reference from list selection
			action = bpy.data.actions[selectedAction]
			# Check action reference is valid
			if action:
				#Delete the action from the data blocks
				copiedAction = action.copy()
				context.scene.tgor_character_selection.action_selection = bpy.data.actions.find(copiedAction.name)
			else:
				self.report({'ERROR_INVALID_INPUT'}, "Action reference invalid")
		else:
			self.report({'ERROR_INVALID_INPUT'}, "No action selected")
		
		return {'FINISHED'}	
		
# ------------------------------------------------------------------
# Add action
class TGOR_OT_ActionAddOperator(Operator):
	bl_label = "Add new action"
	bl_idname = "scene.tgor_action_add_operator"
	bl_description = "Add a new action"
	
	def check(self, context):
		return True
	
	def draw(self, context):		
		row = self.layout.row()
		row.prop(context.window_manager.tgor_action_settings, "action_name")
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):

		#get new action name
		name = context.window_manager.tgor_action_settings.action_name

		# Check if empty
		if not name:
			self.report({'ERROR_INVALID_INPUT'}, "No name provided")
			
		# add the action
		newAction = bpy.data.actions.new(name)

		# set fake user
		newAction.use_fake_user = True

		# set selection to the new action
		context.scene.tgor_character_selection.action_selection = bpy.data.actions.find(newAction.name)
		
		return {'FINISHED'}


class TGOR_OT_ActionDelOperator(Operator):
	bl_label = "Delete action"
	bl_idname = "scene.tgor_action_del_operator"
	bl_description = "Delete action"
	
	def check(self, context):
		return True
	
	# Draw UI function
	def draw(self, context):
		
		# Get current character name to display it in the label
		selectedAction = context.scene.tgor_character_selection.action_selection		
		row = self.layout.row()
		
		# Check if action index refers to an actual action in the scene
		if selectedAction < len(bpy.data.actions):
			
			# Get action data object reference from list selection
			action = bpy.data.actions[selectedAction]
			# Check action reference is valid
			if action:
				row.label(text='Remove action "'+action.name+'" ?', icon="ERROR")
			else:
				row.label(text="ACTION INVALID!", icon="CANCEL")
				row.label(text="", icon="CANCEL")
		else:
			row.label(text="NO ACTION SELECTED!", icon="CANCEL")
			row.label(text="", icon="CANCEL")
		
		
	
	def invoke(self, context, event):

		return context.window_manager.invoke_props_dialog(self)
	
	
	
	def execute(self, context):

		# Get current character name to display it in the label
		selectedAction = context.scene.tgor_character_selection.action_selection		
		
		# Check if action index refers to an actual action in the scene
		if selectedAction < len(bpy.data.actions):
			
			# Get action data object reference from list selection
			action = bpy.data.actions[selectedAction]
			# Check action reference is valid
			if action:
				#Delete the action from the data blocks
				bpy.data.actions.remove(action)
				#set selection one point back (except not below 0)
				context.scene.tgor_character_selection.action_selection = max(0, context.scene.tgor_character_selection.action_selection-1)
			else:
				self.report({'ERROR_INVALID_INPUT'}, "Action reference invalid")
		else:
			self.report({'ERROR_INVALID_INPUT'}, "No action selected")
		
		return {'FINISHED'}	
                
####################################################################################################
############################################# REGISTER #############################################
####################################################################################################

classes = (
	TGOR_OT_ExportSkelMesh,
	TGOR_OT_ExportAnimation,
	TGOR_OT_ActionCopyOperator,
	TGOR_OT_ActionAddOperator,
	TGOR_OT_ActionDelOperator,

	TGORActionsProperty,
	TGORActionSettingsProperty,
)

def register():

	tgor_character.register()

	from bpy.utils import register_class
	for c in classes:
		register_class(c)

	bpy.types.WindowManager.tgor_action_settings = PointerProperty(type=TGORActionSettingsProperty)

    #TGORArmaturesProp(PropertyGroup)
    #TGORActionsProp(PropertyGroup)


def unregister():

    del bpy.types.WindowManager.tgor_action_settings

    from bpy.utils import unregister_class
    for c in reversed(classes):
        unregister_class(c)

    tgor_character.unregister()
