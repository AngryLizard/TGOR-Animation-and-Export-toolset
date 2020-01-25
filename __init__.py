
bl_info = {
    "name": "Second Life Exporter",
    "author": "Salireths, Hopfel",
    "version": (0, 0, 0),
    "blender": (2, 80, 0),
    "location": "Properties > Modifiers",
    "description": "Exporting a rig for SL",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export"
    }

'''
A word of warning: the SL and UE export scripts were separate and written by different people.
Due to merging the two the code structure has in some places become quite incoherent with a lot 
of data coupling between modules and duplicate code.

There are two panels, one is in this file tying all exports together and one is the character panel in tgor_character.
sl_animation/sl_mesh handles exporting for animations and meshes for second life, tgor_export handles exporting to fbx for Unreal Engine 4.

Good luck!
'''

import bpy

from bpy.types import Operator, Panel, UIList, PropertyGroup
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty
from bpy.props import CollectionProperty, PointerProperty

from . import sl_mesh
from . import sl_const
from . import sl_animation
from . import tgor_export
from . import tgor_character
from . import tgor_util
from . import tgor_transform

####################################################################################################
############################################# PANEL ################################################
####################################################################################################

class TGOR_PT_GameAnimExport(Panel):
	"""Export group""" 
	bl_idname = "TGOR_PT_GameAnimExport"
	bl_label = "Export"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tool'

	#bl_space_type = 'PROPERTIES'
	#bl_region_type = 'NAVIGATION_BAR'
    #bl_label = "Navigation Bar"
	#bl_options = {'HIDE_HEADER'}

	#bl_category = "Character"

# 	Draw the menu elements
	def draw(self, context):
		selectedName = context.scene.tgor_character_selection.characters_selection
		selectedCharacter = context.scene.tgor_character_selection.characters.get(selectedName)
		
		
		# export mode drop down enum
		col = self.layout.column()
		col.prop(context.window_manager.tgor_action_settings, "exportMode", text="Export")
		col.separator()
		
		
		# ----------------------------------------------
		# Skeletal mesh export mode ui block
		if context.window_manager.tgor_action_settings.exportMode == "UEMesh":
			if selectedCharacter:
				col = self.layout.column()
				col.prop(selectedCharacter, "meshFolder", text="Skel. Meshes")
							
				# ui box that lists all the exportable meshes of the character
				characterScene = bpy.data.scenes.get(selectedCharacter.scene)
				if characterScene:			
					deformRig = characterScene.objects.get(selectedCharacter.deform)
					if deformRig:
						box = col.box()
						sub = box.column()
						
						sl_mesh.meshlist = [(ob.name, ob.name, "") for ob in characterScene.objects if tgor_util.exportableMesh(deformRig, ob)]
						sl_mesh.meshlist.sort()
						col.prop(context.window_manager.sl_mesh_export, "meshesA", expand=True)
						col.prop(context.window_manager.sl_mesh_export, "meshesB", expand=True)
						col.prop(context.window_manager.sl_mesh_export, "meshesC", expand=True)
						col.prop(context.window_manager.sl_mesh_export, "meshesD", expand=True)
						
						sub.operator("object.tgor_export_character_skel_mesh", icon="EXPORT", text="")
			else:
				col.label(text="No character selected", icon="CANCEL")
		
		
		# ----------------------------------------------
		# Animation export mode ui block
		elif context.window_manager.tgor_action_settings.exportMode == "UEAnim":
			if selectedCharacter:
				col = self.layout.column()
				col.prop(selectedCharacter, "animFolder", text="Animations")
				box = col.box()
				sub = box.column(align=True)
				sub.operator("object.tgor_export_character_animation", icon="EXPORT", text="Export current action")
				sub.prop(context.window_manager.tgor_action_settings, "exportAnimCharacterName")
			else:
				col.label(text="No character selected", icon="CANCEL")
		
        # ----------------------------------------------
		# Skeletal mesh export mode ui block
		if context.window_manager.tgor_action_settings.exportMode == "SLMesh":
			if selectedCharacter:
							
				# ui box that lists all the exportable meshes of the character
				characterScene = bpy.data.scenes.get(selectedCharacter.scene)
				if characterScene:			
					deformRig = characterScene.objects.get(selectedCharacter.deform)
					if deformRig:

						row = self.layout.row()
						col = row.column()

						sl_mesh.meshlist = [(ob.name, ob.name, "") for ob in characterScene.objects if tgor_util.exportableMesh(deformRig, ob)]
						sl_mesh.meshlist.sort()
						col.prop(context.window_manager.sl_mesh_export, "meshesA", expand=True)
						col.prop(context.window_manager.sl_mesh_export, "meshesB", expand=True)
						col.prop(context.window_manager.sl_mesh_export, "meshesC", expand=True)
						col.prop(context.window_manager.sl_mesh_export, "meshesD", expand=True)

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
						col.prop(selectedCharacter, "meshFolder", text="Output")
						# col.prop(context.window_manager.sl_mesh_export, 'file_path')
						split = col.split(factor=0.25)
						split.prop(context.window_manager.sl_mesh_export, "patchCollada")
						split.operator("object.sl_mesh_export", icon='FILE_TICK')

			else:
				col.label(text="No character selected", icon="CANCEL")

		
		# ----------------------------------------------
		# Animation export mode ui block
		elif context.window_manager.tgor_action_settings.exportMode == "SLAnim":


			selectedAction = context.scene.tgor_character_selection.action_selection
			if selectedAction < len(bpy.data.actions):
				action = bpy.data.actions[selectedAction]
				if action:
					self.layout.label(text="Second Life export tools")

					box = self.layout.box()
					row = box.row()
					row.prop(context.window_manager.sl_animation_properties, 'hasProperties')
					if context.window_manager.sl_animation_properties.hasProperties:
					
					    row = box.row()
					    row.prop(action.sl_animation_export, 'loop')

					    row = box.row()
					    row.prop(action.sl_animation_export, 'custom_loop')
					    if action.sl_animation_export.custom_loop:
					        row.prop(action.sl_animation_export, 'loop_in')
					        row.prop(action.sl_animation_export, 'loop_out')
					    
					    row = box.row()
					    row.prop(action.sl_animation_export, 'custom_range')
					    if action.sl_animation_export.custom_range:
					        row.prop(action.sl_animation_export, 'custom_start')
					        row.prop(action.sl_animation_export, 'custom_end')
					
					    row = box.row()
					    row.prop(action.sl_animation_export, 'ease_in')
					    row.prop(action.sl_animation_export, 'ease_out')
					
					    row = box.row()
					    row.prop(action.sl_animation_export, 'priority')
					
					    row = box.row()
					    row.prop(action.sl_animation_export, 'optimisation')
					    if action.sl_animation_export.optimisation:   
					        row.prop(action.sl_animation_export, 'threshold')
					
					box = self.layout.box()
					row = box.row()
					row.prop(context.window_manager.sl_animation_properties, 'hasBones')
					if context.window_manager.sl_animation_properties.hasBones:
											
						objCache = context.window_manager.sl_animation_properties.boneCollection
						objCache.clear()
						
						characterScene = bpy.data.scenes.get(selectedCharacter.scene)
						if characterScene:			
						    deformRig = characterScene.objects.get(selectedCharacter.deform)
						    if deformRig:
						        for bone in sl_const.validBones:
						            if bone in deformRig.data.bones:
						                objCache.add()
						                collectionMember = objCache[-1]
						                collectionMember.name = bone
						                collectionMember.object = bone
						    else:
						        box.label(text="No deform rig selected", icon="CANCEL")
						
						row = box.row()
						col = row.column()
						col.prop_search(action.sl_animation_bones, "bone", context.window_manager.sl_animation_properties, "boneCollection", icon="OUTLINER_OB_ARMATURE")
						col.operator("object.sl_animation_add_bone", icon='BONE_DATA')
						
						if (context.selected_pose_bones and len(context.selected_pose_bones) > 0) or (context.selected_bones and len(context.selected_bones) > 0):
						    row = col.row()
						    row.operator("object.sl_animation_add_bones", icon='BONE_DATA')
						
						col.template_list("SL_UL_BonesList", "bonelist", action.sl_animation_bones, "bones", action.sl_animation_bones, "active_bone")
						
						if action.sl_animation_bones.active_bone >= 0:
						    col.operator("object.sl_animation_remove_bone", icon='EXPORT')
						#col.prop(action, 'sl_animation_bones')
						
					col = self.layout.column()
					sl_animation.SL_UL_BonesList.draw_item(None, context, col, None, action.sl_animation_default_bone, -1, None, None, -1)
					col.prop(selectedCharacter, "animFolder", text="Animations")
					box = col.box()
					sub = box.column(align=True)
					sub.operator("object.sl_animation_export", icon="EXPORT", text="Export current action")
					sub.prop(context.window_manager.tgor_action_settings, "exportAnimCharacterName")


					'''
					box = self.layout.box()
					row = box.row()
					col = row.column()
					col.label(text="Export/Import:")
					col.prop(action.sl_animation_export, 'file_path')
					col.prop(action.sl_animation_export, 'log_path')
					col.operator("object.sl_animation_export", icon='EXPORT')
					col.prop(action.sl_animation_import, 'file_path')
					col.prop(action.sl_animation_import, 'log_path')
					col.operator("object.sl_animation_import", icon='IMPORT')
                    '''

				else:
					col.label(text="Invalid action selection", icon="CANCEL")
			else:
				col.label(text="No action selected", icon="CANCEL")
			


classes = (
    TGOR_PT_GameAnimExport,
)


# Register
def register():

    from bpy.utils import register_class
    for c in classes:
        register_class(c)

    sl_mesh.register()
    sl_animation.register()
    tgor_export.register()
    tgor_transform.register()


def unregister():

    sl_mesh.unregister()
    sl_animation.unregister()
    tgor_export.unregister()
    tgor_transform.unregister()

    from bpy.utils import unregister_class
    for c in reversed(classes):
        unregister_class(c)

if __name__ == "__main__":
    register()
