import bpy
from bpy.types import Operator, Panel, UIList, PropertyGroup
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty
from bpy.props import CollectionProperty, PointerProperty

import re
import math
from mathutils import Matrix, Vector, Euler, Quaternion

from . import tgor_util


####################################################################################################
############################################# LIST UI ##############################################
####################################################################################################

class TGOR_UL_ActionsList(bpy.types.UIList):

	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
		
		split = layout.split(factor=0.15)
		sub = split.split()
		
		# If this element is current selected object's action
		if bpy.context.window_manager.tgor_character_settings.selObjAction == item.name:
			sub.label(icon="ACTION")
			split.alert = True
		else:
			sub.label()
		
		# if this element is current character's action
		if bpy.context.window_manager.tgor_character_settings.curCharAction == item.name:
			sub.label(icon="POSE_HLT")
			split.alert = True
		
		# if this element doensn't have a fake user (will be deleted after restart warning)
		if not item.use_fake_user:
			sub.label(icon="LIBRARY_DATA_BROKEN")
		
		# the text field/name property
		row = split.row()
		row.prop(item, "name", text="", emboss=False, translate=False)
		op = row.operator("object.tgor_assign_to_character", text="", icon='NLA_PUSHDOWN')
		op.action = item.name
	
	
	def invoke(self, context, event):
		pass   


####################################################################################################
############################################# DATA #################################################
####################################################################################################

# --------------------------------------------
# Character reference handler
class CharacterReferenceHandler():

	warning = False
	error = True
	statusMsg = ""
	
	characterScene = None
	deformRig = None
	controlRig = None
	animationData = None
	action = None
	meshFolder = ""
	animFolder = ""
	
	
	def __init__(self, context):
		scene = context.scene
		data = bpy.data
		self.warning = False	
		self.error = False
		self.statusMsg = ""
		
		# Get what is the selected name in the UI list
		selectedName = scene.tgor_character_selection.characters_selection
		
		# Get the property collection of the character
		selectedCharacter = scene.tgor_character_selection.characters.get(selectedName)
	
		# Make sure character is selected, else stop
		if not selectedCharacter:
			self.warning = True	
			self.error = True	
			self.statusMsg = "Error: No character selected. "
			return
		
		# Get/set the export path variables of the selected character
		self.meshFolder = selectedCharacter.meshFolder
		self.animFolder = selectedCharacter.animFolder
		
		
		# Get scene that the character objects refer to
		if selectedCharacter.scene:
			self.characterScene = data.scenes.get(selectedCharacter.scene)
		
		# Make sure that scene exists, else stop
		if not self.characterScene:
			self.warning = True	
			self.error = True
			self.statusMsg = "Error: No scene selected. "
			return
		

		# Get deform rig of the character	
		if selectedCharacter.deform:
			self.deformRig = self.characterScene.objects.get(selectedCharacter.deform)
			
		# Make sure deform rig exists, else continue but with a warning
		if not self.deformRig:
			self.warning = True	
			self.error = False
			self.statusMsg = "Warning: No deform rig (can't export). "
			#return	
		

		# Get control rig object reference
		if selectedCharacter.control:
			self.controlRig = self.characterScene.objects.get(selectedCharacter.control)
		
		# Make sure character has a control rig, else stop
		if not self.controlRig:
			self.warning = True	
			self.error = True
			self.statusMsg = self.statusMsg+"Error: No control rig. "
			return
		

		# Animation data object reference
		self.animationData = self.controlRig.animation_data 
		
		# Check if control rig has animation data, if not, create it
		if not self.animationData:
			self.controlRig.animation_data_create()
			self.animationData = self.controlRig.animation_data
			
		# Check again, if there is still no animation data then error out
		if not self.animationData:	
			self.warning = True	
			self.error = True
			self.statusMsg = self.statusMsg+"Error: No animation data. "
			return
		

		# Get the action of the character
		self.action = self.controlRig.animation_data.action
		


####################################################################################################
############################################# GROUPS ###############################################
####################################################################################################

# ------------------------------------------------------------------
# Character collection properties
# (each of the characters we create and specify have this data in them)
class TGORCharactersProperty(PropertyGroup):
	
	scene: StringProperty(
            name="Scene", 
            description="Scene name where the character resides"
        )

	deform: StringProperty(
            name="Deform Rig", 
            description="Deformation Armature Object. Final animations are baked to this and then exported."
        )

	control: StringProperty(
            name="Control Rig", 
            description="Control Armature Object where animations are created. Actions are applied to this."
        )
	
	meshFolder: StringProperty(
            name="Skel Mesh export folder",
            subtype='DIR_PATH',
            default=""
        )
	
	animFolder: StringProperty(
            name="Animation export folder",
            subtype='DIR_PATH',
            default=""
        )

class TGORCharacterSelectionProperty(PropertyGroup):

	# Currently selected action in the UI
	action_selection: IntProperty(
			name="Selected action", 
			description="Selected action"
		)

	# Collection of character properties, inside of each we have more variables and settings
	characters: CollectionProperty(type=TGORCharactersProperty)

	# Currently selected character name
	characters_selection: StringProperty(
			name="Character", 
			description="Currently selected character", 
			default=""
		)


class TGORArmaturesProperty(PropertyGroup):

	object: StringProperty(
            name="Object", 
            description="name of the object"
        )

class TGORCharacterSettingsProperty(PropertyGroup):

	# Name/rename field for the new character dialogue
	character_name: StringProperty(
			name="Name", 
			description="Name for new character set", 
			default="Character"
		)

	# Cached list of all armatures in a scene
	armatureCollection: CollectionProperty(type=TGORArmaturesProperty)
	
	# Cached name of the current character's action													
	curCharAction: StringProperty(
			name="Action",
			description="Current name of character's action",
			default=""
		)

	# Cached name of the selected object's action													
	selObjAction: StringProperty(
			name="Action",
			description="Current name of selected object's action",
			default=""
		)


# Update scene frame range when the action property changes
def rangeUpdateCallback(self, context):
	
	charRefHndlr = CharacterReferenceHandler(context)
	action = charRefHndlr.animationData.action
	if action:
		context.scene.frame_start = action.tgor_action_range.startFrame
		context.scene.frame_end = action.tgor_action_range.endFrame
	return None
		
class TGORActionRangeProperty(PropertyGroup):

	# Starting frame of animation
	startFrame: IntProperty(
			name="Start", 
			description="Start",
			update = rangeUpdateCallback
		)
		
	# Ending frame of animation
	endFrame: IntProperty(
			name="End", 
			description="End",
			update = rangeUpdateCallback
		)

####################################################################################################
############################################# OPERATORS ############################################
####################################################################################################

# ------------------------------------------------------------------
# Select character
class TGOR_OT_SelectCharacter(Operator):
	bl_label = "Select character"
	bl_idname = "object.tgor_select_character"
	bl_description = "Select active character's control rig, if there is no control rig, the deformation rig will be selected."
	
	def execute(self, context):
			
		# create a class that houses useful and repetitive character references
		charRefHndlr = CharacterReferenceHandler(context)
		
		# first exit of pose mode to not run into a bug where object stays in edit mode and the pose bones of another object are selected somehow\t
		tgor_util.exitPoseMode(context)
		
		# if the control rig exists
		if charRefHndlr.controlRig:
			
            # deselect all 
			for ob in bpy.data.objects:
				ob.select_set(False)
			
            # set control rig active
			context.view_layer.objects.active = charRefHndlr.controlRig

			# select the control rig
			charRefHndlr.controlRig.select_set(True)

			# set the pose mode
			if context.object in context.visible_objects:
				bpy.ops.object.mode_set(mode='POSE')
			
			
		# if control rig isnt here, maybe deform rig exists?
		elif charRefHndlr.deformRig:
			for ob in context.selected_objects:
				ob.select_set(False)

			context.view_layer.objects.active = charRefHndlr.deformRig
			charRefHndlr.deformRig.select_set(True)

			rangeUpdateCallback(None, context)

		else: 
			self.report({'ERROR'}, "Nothing to select.")
			

		return {'FINISHED'}


# ------------------------------------------------------------------
# Assign action to character
class TGOR_OT_AssignToCharacter(Operator):
	bl_label = "Assign action to character Operator"
	bl_idname = "object.tgor_assign_to_character"
	bl_description = "Assigns an action to a character"
	
	action: StringProperty(default="")
	
	def execute(self, context):
		
		# create a class that houses userful and repetetive character references
		charRefHndlr = CharacterReferenceHandler(context)
		
		# check if there is no errors in character setup
		if not charRefHndlr.error:
			# get animation data reference from ref handler
			ad = charRefHndlr.animationData			
		else:
			# If character isn't set up get anim data from selection
			ad = context.object.animation_data
			
			# if object doesnt have animation data, create it then
			if not ad:
				context.object.animation_data_create()
				ad = context.object.animation_data
				
			#check for animation data again, if it still doesn't exist then terminate.
			if not ad:
				self.report({'ERROR'}, "Animation data can't be created for this object")
				return {'FINISHED'}
		
		# If the action is supplied as operator property, get the reference to it	
		action = bpy.data.actions.get(self.action)
		
		# Check if action reference is valid
		# If its not supplied, find what is currently selected in the UI
		if not action:
			# Get integer of the selected in the UI action
			selectedAction = context.scene.tgor_character_selection.action_selection
			
			# Check if action index refers to an actual action in the scene
			if not selectedAction < len(bpy.data.actions):
				self.report({'ERROR'}, "Selected in the UI action index refers to an invalid action in the scene")
				return {'FINISHED'}
		
			# Get action data object reference from list selection
			action = bpy.data.actions[selectedAction]
			
			
		# Just in case, check again if action reference is valid
		if not action:
			self.report({'ERROR'}, "Selected action refers to None. Try re-selecting some action!")
			return {'FINISHED'}
		
		# Actually do the work and finally assign the action to the deform rig object! woo
		ad.action = action
		
		# Make a fake user so it doesn get deleted later!
		ad.action.use_fake_user = True

		rangeUpdateCallback(None, context)
		
		return {'FINISHED'}

# ------------------------------------------------------------------
# Remove character
class TGOR_OT_CharacterRemoveOperator(Operator):
	bl_label = "Remove character"
	bl_idname = "scene.tgor_character_remove_operator"
	bl_description = "Removes selected character"
	
	def check(self, context):
		return True
	
	# Draw UI function
	def draw(self, context):
		layout = self.layout
		
		# Get current character name to display it in the label
		selectedName = context.scene.tgor_character_selection.characters_selection
		
		row = layout.row()
		
		# Check if a character is selected
		if not selectedName:
			row.label(text="NO CHARACTER SELECTED!", icon="CANCEL")
			row.label(text="", icon="CANCEL")
		else:
			row.label(text='Remove character "'+selectedName+'" ?', icon="ERROR")
	

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		
		# Get current character name
		selectedName = context.scene.tgor_character_selection.characters_selection
		sceneCharacters = context.scene.tgor_character_selection.characters
		
		# Check if not empty
		if not selectedName:
			self.report({'ERROR_INVALID_INPUT'}, "No selected character")
			return {'FINISHED'}	
		
		# Get selected character property
		selectedCharacterIndex = sceneCharacters.find(selectedName)
	
		# Check if not empty
		if selectedCharacterIndex == -1 :
			self.report({'ERROR_INVALID_INPUT'}, "Can't find a character with name "+selectedName)
			return {'FINISHED'}			
		
		# Remove array member by index
		sceneCharacters.remove(selectedCharacterIndex)
		
		# Set (move) the currently selected character to the last in the array or set empty	
		if len(sceneCharacters) > 0:
			context.scene.tgor_character_selection.characters_selection = sceneCharacters[-1].name
		else:
			context.scene.tgor_character_selection.characters_selection = ''
		
		return {'FINISHED'}
	
# ------------------------------------------------------------------
# Add character
class TGOR_OT_CharacterAddOperator(Operator):
	bl_label = "Add new character"
	bl_idname = "scene.tgor_character_add_operator"
	bl_description = "Add a new character"
	
	def check(self, context):
		return True
	
	def draw(self, context):
		row = self.layout.row()
		row.prop(context.window_manager.tgor_character_settings, "character_name")
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def execute(self, context):

		#get new character name
		name = context.window_manager.tgor_character_settings.character_name

		# Check if empty
		if not name:
			self.report({'ERROR_INVALID_INPUT'}, "No name provided")
		else:
			# Check if already in use
			if not context.scene.tgor_character_selection.characters.get(name) is None:
				self.report({'ERROR_INVALID_INPUT'}, "Name already in use")
			else:
				context.scene.tgor_character_selection.characters.add()
				context.scene.tgor_character_selection.characters[-1].name = name
				context.scene.tgor_character_selection.characters[-1].scene = context.scene.name
				context.scene.tgor_character_selection.characters_selection = name
		return {'FINISHED'}

# ------------------------------------------------------------------
# Character settings
class TGOR_OT_CharacterSettingsOperator(Operator):
	bl_label = "Character settings"
	bl_idname = "scene.tgor_character_settings_operator"
	bl_description = "Set up the settings for the selected character"

	def check(self, context):
		return True
	
	def draw(self, context):
		
		# Get selected character
		selectedName = context.scene.tgor_character_selection.characters_selection
		selectedCharacter = context.scene.tgor_character_selection.characters.get(selectedName)
				
		# The UI is very different depending if we have character selected or not
		if selectedCharacter: 	 
		
			# get the scene character belongs to!
			# so later we can use bpy.data.scenes['Scene'].objects[]...
			
			row = self.layout.row()
			row.prop_search(selectedCharacter, "scene", bpy.data, "scenes", icon="SCENE_DATA")
			
			# Get the scene of the specified name
			characterScene = bpy.data.scenes.get(selectedCharacter.scene)
			
			# If we have character selected
			if characterScene:  
				
				self.layout.separator()	
			
				# --------------------------------------------------------
				# Create/refresh list of objects of ARMATURE type
				
				# Get list declared in windows manager and clear leftover junk in it first
				objCache = context.window_manager.tgor_character_settings.armatureCollection
				objCache.clear()
				
				# Find all scene objects of Armature type and add them to the cache list
				for ob in characterScene.objects:
					if ob.type == 'ARMATURE':
						objCache.add()
						collectionMember = objCache[-1]
						collectionMember.name = ob.name
						collectionMember.object = ob.name
						
				# --------------------------------------------------------
		
				row = self.layout.row()
				row.prop_search(selectedCharacter, "deform", context.window_manager.tgor_character_settings, "armatureCollection", icon="OUTLINER_OB_ARMATURE")
				row = self.layout.row()
				row.prop_search(selectedCharacter, "control", context.window_manager.tgor_character_settings, "armatureCollection", icon="OUTLINER_OB_ARMATURE")
		
			# If no scene is selected
			else:
				row = self.layout.row()
				row.label(text="Select a scene first!", icon="CANCEL")
				row.label(text="", icon="CANCEL")
			
			# ---------------------------
			# File paths 
			self.layout.separator()
			col = self.layout.column()	
			col.label(text="Export folders:")
			col.prop(selectedCharacter, "meshFolder", text="Skel. Meshes")
			col.prop(selectedCharacter, "animFolder", text="Animations")
			
			
		# If no character is selected:	
		else:
			row = self.layout.row()
			row.label(text="NO CHARACTER SELECTED!", icon="CANCEL")
			row.label(text="", icon="CANCEL")

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def execute(self, context):
		return {'FINISHED'}

# ------------------------------------------------------------------
# Set frame range 
class TGOR_OT_SetFrameRange(Operator):
	bl_label = "Set frame range by action"
	bl_idname = "object.tgor_set_character_action_scene_range"
	bl_description = "Sets scene range depending on the object's action range"
	
	def execute(self, context):

		# create a class that houses userful and repetetive character references
		charRefHndlr = CharacterReferenceHandler(context)
		
		# if out refernce handler works properly, aka character is setup appropriately
		if not charRefHndlr.error:

			# get animation data reference from ref handler
			ad = charRefHndlr.animationData

		# If there is no proper character, set the range according to selected object's action
		else:
			ad = context.object.animation_data
			
			
			
		# Check if object has animation data, if not then' stop. 
		# We have no use of it if there is no action anyway
		if not ad:
			self.report({'WARNING'}, "There is no animation data and no action, can't get the keyframe range from nothing.")
			return {'FINISHED'}
		
		# get the action, terminate if there is no action
		action = ad.action
		if not action:
			self.report({'WARNING'}, "There is no action, can't get the keyframe range from nothing.")
			return {'FINISHED'}
		
		# get the last position from vec2 of scene's keyframe range
		startframe = int(action.frame_range[0])
		lastframe = int(action.frame_range[1])
				
		# if it has fcurves in it
		if action.fcurves:
			if len(action.fcurves) > 0 :
				action.tgor_action_range.startFrame = startframe # 
				action.tgor_action_range.endFrame = lastframe # get the last keyframe position and set the scene's end frame to it
		else:
			self.report({'WARNING'}, "The control rig's action doesn't have keyframes")
			return {'FINISHED'}
		
		return {'FINISHED'}



####################################################################################################
############################################# PANEL ################################################
####################################################################################################


class TGOR_PT_GameAnimCharacters(Panel):
	"""TGOR tab for the toolbar in the 3D Viewport, character group""" 
	bl_idname = "TGOR_PT_GameAnimCharacters"
	bl_label = "Character"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tool'

# 	Draw the menu elements
	def draw(self, context):
		selectedName = context.scene.tgor_character_selection.characters_selection
		selectedCharacter = context.scene.tgor_character_selection.characters.get(selectedName)
		
		# Create a class that houses userful and repetetive character references
		charRefHndlr = CharacterReferenceHandler(context)
		
		# -------- 
		# Cache names so they can be used in the lists, curCharAction selObjAction
		
		# Cache current character's action name, none if no character/no action
		if charRefHndlr.action:
			context.window_manager.tgor_character_settings.curCharAction = charRefHndlr.action.name
		else:
			context.window_manager.tgor_character_settings.curCharAction = ""
		
		# Cache name of the currently selected object's action
		if context.object:
			if context.object.animation_data:
				if context.object.animation_data.action:
					context.window_manager.tgor_character_settings.selObjAction = context.object.animation_data.action.name
				else:
					context.window_manager.tgor_character_settings.selObjAction = ""
			else:
				context.window_manager.tgor_character_settings.selObjAction = ""
		else:
			context.window_manager.tgor_character_settings.selObjAction = ""

		# -------- 
		# The character controls box

		col = self.layout.column(align=True)

		row = col.row(align=True)
		row.label(text="Selected character:")

		row = col.row(align=True)
		row.prop_search(context.scene.tgor_character_selection, "characters_selection", context.scene.tgor_character_selection, "characters", text="", icon='POSE_HLT')
		row.operator("scene.tgor_character_add_operator", text="", icon='ZOOM_IN')
		row.operator("scene.tgor_character_remove_operator", text="", icon='ZOOM_OUT')

		row = col.row(align=True)
		row.operator("object.tgor_select_character", icon="RESTRICT_SELECT_OFF", text="Select")		
		row.operator("scene.tgor_character_settings_operator", icon="SETTINGS", text="Settings")		
	
		# --------
		# Errors and warnings
		if charRefHndlr.warning:
			row = self.layout.row()
			row.label(text=str(charRefHndlr.statusMsg), icon='ERROR')
		
		# --------
		# Action selection list
		col = self.layout.column(align=True)	

		row = col.row(align=True)
		row.template_list("TGOR_UL_ActionsList", "actionlist", bpy.data, "actions", context.scene.tgor_character_selection, "action_selection")

		row = col.row(align=True)
		if not charRefHndlr.error: 
			op = row.operator("object.tgor_assign_to_character", text="Assign to " + str(selectedCharacter.control), icon='NLA_PUSHDOWN')
			op.action = ""
			row = col.row(align=True)
			row.operator("scene.tgor_action_add_operator", text="Add", icon='ZOOM_IN')
			row.operator("scene.tgor_action_del_operator", text="Del", icon='ZOOM_OUT')
			row.operator("scene.tgor_action_copy_operator", text="Copy", icon='PASTEDOWN')
		else: 
			row.operator("object.tgor_assign_to_character", text="Assign to "+context.object.name, icon='NLA_PUSHDOWN')

		# --------
		# TemplateID, action of the selected character's control rig action
		# or of selected object if there is no character
		row = self.layout.row()
		
		if not charRefHndlr.error:
			row.template_ID(charRefHndlr.animationData, "action")
		else:
			row.label(text='Action of "'+context.object.name+"' :")
			row = self.layout.row()
			# if selected object's animation data exists, display template_id widget of its action
			if context.object.animation_data:
				row.template_ID(context.object.animation_data, "action")
			
		# --------
		# End - frame control box
		
		if charRefHndlr.action:

			row = self.layout.row()
			box = row.box()

			row = box.row(align=True)
			row.label(text="Frame range:")

			row = box.row(align=True)
			row.operator("object.tgor_set_character_action_scene_range", text="", icon='PREVIEW_RANGE')

			sub = row.row(align=True)
			sub.scale_x = 2.0
			sub.prop(charRefHndlr.action.tgor_action_range, "startFrame")
			sub.prop(charRefHndlr.action.tgor_action_range, "endFrame")
			
		# --------	
		# NLA strips warnings and cleanup
		
		nlaWarning = False
		if not charRefHndlr.error:
			# Detect if deform rig has action assigned and/or NLA tracks
			if charRefHndlr.deformRig and charRefHndlr.deformRig != charRefHndlr.controlRig:
				if charRefHndlr.deformRig.animation_data:
					if charRefHndlr.deformRig.animation_data.action or len(charRefHndlr.deformRig.animation_data.nla_tracks) > 0:
						row = self.layout.row()

						col = row.column(align=True)
						col.label(text="Warning:", icon="ERROR")
						col.label(text="Deform Rig has action/NLA tracks!")
						nlaWarning = True

			# Detect if control rig has NLA tracks assigned
			if charRefHndlr.controlRig:	
				if len(charRefHndlr.animationData.nla_tracks) > 0:
					row = self.layout.row()

					col = row.column(align=True)
					col.label(text="Warning:", icon="ERROR")
					col.label(text="Control Rig has NLA tracks!")
					nlaWarning = True
				
			# Operator to clean up and remove any NLA and action stuff that is not supposed to be handled by the script
			# displayed only if there are any problems detected
			if nlaWarning:
				row = self.layout.row()

				col = row.column(align=True)
				col.label(text="Script isn't designed to handle ")
				col.label(text="some of the NLA features used,")
				col.label(text="consider cleaning it up.")
				col.operator("object.tgor_cleanup_nla", text="Cleanup", icon='PARTICLEMODE')


# ------------------------------------------------------------------
# Cleanup
class TGOR_OT_cleanupNLA(Operator):
	bl_label = "Cleanup unnecessary NLA and animation data"
	bl_idname = "object.tgor_cleanup_nla"
	bl_description = "Remove all the data that might interfere with how the script is designed to work, such as NLA tracks on control rig (only Actions are supported) and all animation data on the deform rig."
	
	def execute(self, context):
	
		# create a class that houses userful and repetetive character references
		charRefHndlr = CharacterReferenceHandler(context)
		
		# check if there is no errors in character setup
		if charRefHndlr.error:
			self.report({'ERROR'}, "Character setup is invalid, cant clean up.")
			return {'FINISHED'}
		
		# Check if deform rig has animation data and clear it (removing all NLA tracks and actions assigned to it)
		if charRefHndlr.deformRig:
			if charRefHndlr.deformRig.animation_data:
				charRefHndlr.deformRig.animation_data_clear()

		# Detect if control rig has NLA tracks assigned
		if charRefHndlr.controlRig:	
			if len(charRefHndlr.animationData.nla_tracks) > 0:
				
				# make a list of all tracks
				tracks = []
				for track in charRefHndlr.animationData.nla_tracks:
					tracks.append(track)
					
				# iterate through that list and remove all
				for t in tracks:
					charRefHndlr.animationData.nla_tracks.remove(t)
						
		return {'FINISHED'}

                
####################################################################################################
############################################# REGISTER #############################################
####################################################################################################

classes = (
	TGOR_UL_ActionsList,

    TGOR_OT_SelectCharacter,
    TGOR_OT_AssignToCharacter,
    TGOR_OT_CharacterRemoveOperator,
    TGOR_OT_CharacterAddOperator,
    TGOR_OT_CharacterSettingsOperator,
	TGOR_OT_cleanupNLA,
	TGOR_OT_SetFrameRange,

    TGOR_PT_GameAnimCharacters,

    TGORCharactersProperty,
	TGORCharacterSelectionProperty,
	TGORArmaturesProperty,
	TGORCharacterSettingsProperty,
	TGORActionRangeProperty,
)

def register():

    from bpy.utils import register_class
    for c in classes:
        register_class(c)

    bpy.types.Scene.tgor_characters = CollectionProperty(type=TGORCharactersProperty) 
    bpy.types.Scene.tgor_character_selection = PointerProperty(type=TGORCharacterSelectionProperty)
    bpy.types.WindowManager.tgor_character_settings = PointerProperty(type=TGORCharacterSettingsProperty)
    bpy.types.Action.tgor_action_range = PointerProperty(type=TGORActionRangeProperty)


def unregister():

    del bpy.types.Scene.tgor_characters
    del bpy.types.Scene.tgor_character_selection
    del bpy.types.WindowManager.tgor_character_settings
    del bpy.types.Action.tgor_action_range

    from bpy.utils import unregister_class
    for c in reversed(classes):
        unregister_class(c)
