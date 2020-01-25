
import bpy
from bpy.types import Operator, Panel, UIList, PropertyGroup
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty
from bpy.props import CollectionProperty, PointerProperty

import re
import os
import math
from mathutils import Matrix, Vector, Euler, Quaternion

from . import sl_const
from . import sl_animexport
from . import tgor_character
from . import tgor_util

####################################################################################################
############################################# LIST UI ##############################################
####################################################################################################

class SL_UL_BonesList(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        #split = layout.split(0.15)
                    
        # the text field/name property
        main = layout.column()
        main.label(text="%s"%(item.name))
        
        box = main.box()
        col = box.column()

        row = col.row()
        row.prop(item, "location", text="")
        row.prop(item, "rotation", text="")

        row = col.row()
        row.prop(item, "override")
        if item.override:
            row.prop(item, "priority")

        main.separator()
    
    def invoke(self, context, event):
        pass

####################################################################################################
############################################# GROUPS ###############################################
####################################################################################################

class SLAnimationBones(PropertyGroup):
    
    name: StringProperty(
            name="Bone", 
            description="Bone name"
        )

    override: BoolProperty(
            name="Override", 
            description="Whether to override bone priority",
            default=False
        )

    priority: IntProperty(
            name="Priority", 
            description="Bone priority override",
            default=2,
            min=2
        )

    location: EnumProperty(
            name="Location", 
            description="When to export location",
            items=[('NEVER', "Never Location", "Never export"),
                ('DEFAULT', "Default Location", "Export if different"),
                ('ALWAYS', "Always  Location", "Always export")],
            default='DEFAULT'
        )

    rotation: EnumProperty(
            name="Rotation", 
            description="When to export rotation",
            items=[('NEVER', "Never Rotation", "Never export"),
                ('DEFAULT', "Default Rotation", "Export if different"),
                ('ALWAYS', "Always Rotation", "Always export")],
            default='DEFAULT'
        )

class SLAnimationExportProperties(PropertyGroup):

    loop: BoolProperty(
            name = "Loop",
            description = "Whether this animation loops",
            default = False
        )

    custom_loop: BoolProperty(
            name = "Custom Loop",
            description = "Whether to use custom loop ranges",
            default = False
        )

    loop_in: IntProperty(
            name = "In",
            description = "Frame when loop starts",
            default = 0,
            min = 0
        )

    loop_out: IntProperty(
            name = "Out",
            description = "Frame when loop ends",
            default = 0,
            min = 0
        )

    ease_in: FloatProperty(
            name = "Ease In",
            description = "Time in seconds to ease in",
            default = 0.5,
            min = 0.0
        )

    ease_out: FloatProperty(
            name = "Ease Out",
            description = "Time in seconds to ease out",
            default = 0.5,
            min = 0.0
        )

    custom_range: BoolProperty(
            name = "Custom Range",
            description = "Whether we use a custom frame range for animation export",
            default = False
        )

    custom_start: IntProperty(
            name = "Start",
            description = "Custom start frame for animation",
            default = 0,
            min = 0
        )

    custom_end: IntProperty(
            name = "End",
            description = "Custom end frame for animation",
            default = 0,
            min = 0
        )

    priority: IntProperty(
            name = "Base Priority",
            description = "Base Priority of all bones",
            default = 2,
            min = 0
        )

    optimisation: BoolProperty(
            name = "Optimisation",
            description = "Whether optimisation is turned on",
            default = True
        )

    threshold: FloatProperty(
            name = "Threshold",
            description = "Threshold for ssd on transform matrix for which a bone is exported",
            default = 0.0001,
            min = 0.0
        )

    file_path: StringProperty(
            name = "Output",
            description = "Path to output file",
            default = "export.anim",
            subtype = "FILE_PATH"
        )

    log_path: StringProperty(
            name = "Output Log",
            description = "Path to output log file",
            default = "out.log",
            subtype = "FILE_PATH"
        )

class SLAnimationImportProperties(PropertyGroup):

    file_path: StringProperty(
            name = "Input",
            description = "Path to input file",
            default = "input.anim",
            subtype = "FILE_PATH"
        )

    log_path: StringProperty(
            name = "Input Log",
            description = "Path to input log file",
            default = "in.log",
            subtype = "FILE_PATH"
        )

class SLBoneProperty(PropertyGroup):

	object: StringProperty(
            name="Object", 
            description="name of the object"
        )

class SLAnimationBoneProperties(PropertyGroup):

    bones: CollectionProperty(type=SLAnimationBones)

    active_bone: IntProperty(
            name = "Active Bone",
            description = "Currently active bone",
            default = 0,
            min = 0
        )

    bone: StringProperty(
            name="Export Mesh",
            description="Mesh to export."
        )

class SLAnimationUIProperties(PropertyGroup):

    hasProperties: BoolProperty(
            name="Customise Properties", 
            description="Whether to display properties",
            default=False
        )

    hasBones: BoolProperty(
            name="Customise Bones", 
            description="Whether to display bones",
            default=False
        )
    
    boneCollection: CollectionProperty(type=SLBoneProperty)

####################################################################################################
############################################# OPERATORS ############################################
####################################################################################################

class SL_OT_AnimationExport(Operator):
    bl_idname = "object.sl_animation_export"
    bl_label = "SL AnimationExport"
    bl_description = ("Export animation")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        if context.active_object.type != "ARMATURE":
            
            self.report({'INFO'}, "Active object isn't an armature!")
            return {'CANCELLED'}

        # Make sure only the armature is selected
        for selected in context.selected_objects:
            if selected != context.active_object:
                selected.select_set(False)

        ############################################################

        
        selectedAction = context.scene.tgor_character_selection.action_selection
        if selectedAction < len(bpy.data.actions):
            action = bpy.data.actions[selectedAction]
            if not action:
                self.report({'INFO'}, "No action selected!")
                return {'CANCELLED'}
            
            # Determine start and end frame
            frame_start = action.tgor_action_range.startFrame
            frame_end = action.tgor_action_range.endFrame

            if action.sl_animation_export.custom_range:
                frame_start = action.sl_animation_export.custom_start
                frame_end = action.sl_animation_export.custom_end
            
            # Generate data structure for all joints involved
            totalFrames = frame_end - frame_start + 1
            totalDuration = float(frame_end - frame_start) / context.scene.render.fps
            joints = [bone.name for bone in context.active_object.pose.bones if bone.name in sl_const.validBones]

            # Compute relative pose transforms
            bones = {}
            for joint in joints:
                
                bone = {}

                # Settings from UI
                settings = action.sl_animation_bones.get(joint)
                if not settings or context.window_manager.sl_animation_properties.hasBones:
                    settings = action.sl_animation_default_bone

                bone['loc_always'] = (settings.location == 'ALWAYS')
                bone['loc_never'] = (settings.location == 'NEVER')
                bone['rot_always'] = (settings.rotation == 'ALWAYS')
                bone['rot_never'] = (settings.rotation == 'NEVER')
                bone['priority'] = settings.priority if settings.override else action.sl_animation_export.priority
                    
                # Only continue if bone has any keys
                if not bone['loc_never'] or not bone['rot_never']:

                    bone['locations'] = []
                    bone['rotations'] = []

                    # Get initial pose local transform
                    dataBone = context.active_object.data.bones[joint]
                    dataChild = dataBone.matrix_local

                    # Get initial pose parent transform (assume origin if root)
                    if dataBone.parent:
                        dataParent = dataBone.parent.matrix_local
                        bone['offset'] = dataChild.to_translation() - dataParent.to_translation()
                    else:
                        dataParent = Matrix()
                        bone['offset'] = Vector((0,0,0))

                    # Transforms
                    bone['transform'] = dataChild.inverted() @ dataParent # (PT^-1 * T)^-1 = T1^-1 * PT
                    bone['basis'] = dataChild.to_3x3().to_4x4() # Rotation (and scale) only
                    
                    bones[joint] = bone

            # Render all frames
            oldFrame = context.scene.frame_current
            for frame in range(0, totalFrames):
                
                context.scene.frame_set(frame_start + frame)
                for name, bone in bones.items():

                    # Get current pose and pose parent transform
                    poseBone = context.active_object.pose.bones[name]
                    poseChild = poseBone.matrix
                    poseParent = poseBone.parent.matrix if poseBone.parent else Matrix()
                    poseTransform = poseParent.inverted() @ poseChild

                    # Transform in bone space
                    B = bone['basis']
                    T = bone['transform'] @ poseTransform
                    matrix = B @ T @ B.transposed() # Without scaling B^-1 = B^T

                    # poseTransform:        from "pose" to "pose parent" space
                    # bone['transform']:    from "data parent" to "data" space
                    # => T:                 from "pose" to "data" space

                    # B:                    from "data" to "global" space
                    # B':                   from "global" to "data" space
                    # => B * T * B':        from "global" to "global" space

                    # matrix: Difference between "pose" and "data" in global space

                    # Compute translation
                    loc = matrix.to_translation() + bone['offset']
                    bone['locations'].append((frame, loc))
                    
                    # Compute rotation
                    quat = (sl_const.leftRot @ matrix @ sl_const.rightRot).to_quaternion()
                    bone['rotations'].append((frame, quat))

            context.scene.frame_set(oldFrame)

            # Optimise elements by removing linear curve elements
            def optimise(elements, force, ref):
                
                # Assume nothing changes from the start
                output = [(-2, ref), (-1, ref)]
                for frm, emt in elements:
                    anch_frm, anch_emt = output[-2]
                    last_frm, last_emt = output[-1]

                    # Only add new location if there is no curve
                    ratio = float((frm - last_frm)) / (frm - anch_frm)
                    curve = (emt - last_emt) - (emt - anch_emt) * ratio
                    if curve.magnitude < action.sl_animation_export.threshold:
                        output[-1] = (frm, emt)
                    else:
                        output += [(frm, emt)]
                
                # Filter virtual location list
                elements = [(frm, emt) for frm, emt in output if frm >= 0]

                # Insert copy of first element if there is none
                frm, emt = elements[0]
                if frm != 0:
                    elements = [(0, emt)] + elements
                # TODO: Could remove last entry if the last two are equal

                # Don't export anything if there is no difference to initial pose (or if forced)
                ssd = max([(emt-ref).magnitude for frm,emt in elements])
                return elements if ssd > action.sl_animation_export.threshold or force else []

            if action.sl_animation_export.optimisation:
                # Optimize frames and filter according to always/never lists
                for name, bone in bones.items():

                    bone['locations'] = [] if bone['loc_never'] else optimise(bone['locations'], bone['loc_always'], bone['offset'])
                    bone['rotations'] = [] if bone['rot_never'] else optimise(bone['rotations'], bone['rot_always'], Quaternion((1,0,0,0)))
            else:
                # Remove blacklisted bones
                for name, bone in bones.items():

                    bone['locations'] = [] if bone['loc_never'] else bone['locations']
                    bone['rotations'] = [] if bone['rot_never'] else bone['rotations']

            ############################################################

            #filePath = action.sl_animation_export.file_path
            selectedName = context.scene.tgor_character_selection.characters_selection
            charRefHndlr = tgor_character.CharacterReferenceHandler(context)
            if not charRefHndlr.animFolder:
                self.report({'ERROR'}, "Character doesn't have animation export path defined.")
                return {'CANCELLED'}
            
            # Check path as absolute path TODO: Relative paths https://docs.blender.org/api/blender_python_api_2_77_0/bpy.path.html
            if not os.path.isdir(bpy.path.abspath(charRefHndlr.animFolder)):
                self.report({'ERROR'}, "Path '" + charRefHndlr.animFolder + "' doesn't point to an existing directory (has to be absolute path).")
                return {'CANCELLED'}
            
            # getting the full fbx export file path
            includeCharacterName = context.window_manager.tgor_action_settings.exportAnimCharacterName
            filename = tgor_util.makeValidFilename(selectedName+"_"+action.name if includeCharacterName else action.name)+".anim"
            filePath = bpy.path.abspath(os.path.join( charRefHndlr.animFolder, filename))

            logname = tgor_util.makeValidFilename(selectedName+"_"+action.name if includeCharacterName else action.name)+".log"
            logPath = bpy.path.abspath(os.path.join( charRefHndlr.animFolder, logname))
            


            anim = sl_animexport.Anim(None, False)
            anim.constraints = sl_animexport.Constraints()
            anim.constraints.num_constraints = 0
            anim.constraints.constraints = []
            anim.joints = []

            # Not used
            anim.emote_name = "(None)"
            anim.hand_pose = 0

            # Versioning
            anim.version = 1
            anim.sub_version = 0

            # Loop
            anim.loop = action.sl_animation_export.loop

            if action.sl_animation_export.custom_loop:

                inFrame = action.sl_animation_export.loop_in - frame_start
                loop_in = min(max(inFrame, 0), totalFrames - 1)
                anim.loop_in_point = float(loop_in) / context.scene.render.fps

                outFrame = action.sl_animation_export.loop_out - frame_start
                loop_out = min(max(outFrame, inFrame), totalFrames - 1)
                anim.loop_out_point = float(loop_out) / context.scene.render.fps

            else:

                anim.loop_in_point = 0.0
                anim.loop_out_point = totalDuration


            # Easing (clamp if not looping)
            ease_in = action.sl_animation_export.ease_in
            anim.ease_in_duration = ease_in if anim.loop else min(max(ease_in, 0.0), totalDuration)
            ease_out = action.sl_animation_export.ease_out
            anim.ease_out_duration = ease_out if anim.loop else min(max(ease_out, 0.0), totalDuration - ease_in)

            # Misc
            anim.base_priority = action.sl_animation_export.priority
            anim.duration = totalDuration

            # Add joints and data to anim
            for name, bone in bones.items():
                bone = bones[name]
                locs = bone['locations']
                rots = bone['rotations']

                # Only add joint if there are any curves
                if locs or rots:

                    anim.add_joint(name, bone['priority'])

                    locs = [(frm, sl_const.leftRot @ loc) for frm,loc in locs] # Rotate for SL
                    locs = [(frm, (loc.x, loc.y, loc.z)) for frm,loc in locs]
                    anim.add_time_pos([name], locs, totalFrames)

                    rots = [(frm, rot.normalized()) for frm,rot in rots] # Normalise rotation
                    rots = [(frm, (rot.x, rot.y, rot.z)) for frm,rot in rots]
                    anim.add_time_rot([name], rots, totalFrames)
            
            # Write anim to file
            anim.write(filePath)
            anim.dump(logPath)

        self.report({'INFO'}, "Exported to @ %s" % (filePath))
        return {'FINISHED'}


class SL_OT_AnimationImport(Operator):
    bl_idname = "object.sl_animation_import"
    bl_label = "SL AnimationImport"
    bl_description = ("Import animation")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        ############################################################
        filePath = bpy.context.scene.sl_animation_import.file_path

        logPath = bpy.context.scene.sl_animation_import.log_path
        anim = sl_animexport.Anim(filePath, False)
        anim.dump(logPath)

        self.report({'INFO'}, "Imported to @ %s" % (logPath))
        return {'FINISHED'}

class SL_OT_AnimationAddBone(Operator):
    bl_idname = "object.sl_animation_add_bone"
    bl_label = "SL Add Bone"
    bl_description = ("Adds a bone to current animation's bone list")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        selectedAction = context.scene.tgor_character_selection.action_selection
        if selectedAction < len(bpy.data.actions):
            action = bpy.data.actions[selectedAction]
            if not action:
                self.report({'INFO'}, "No action selected!")
                return {'CANCELLED'}

            bone = action.sl_animation_bones.bone
            
            if action.sl_animation_bones.bones.find(bone) == -1:

                action.sl_animation_bones.bones.add()
                action.sl_animation_bones.bones[-1].name = bone
                action.sl_animation_bones.active_bone = action.sl_animation_bones.bones.find(bone)

        return {'FINISHED'}


class SL_OT_AnimationAddSelectedBones(Operator):
    bl_idname = "object.sl_animation_add_bones"
    bl_label = "SL Add Bones"
    bl_description = ("Adds selected bones to current animation's bone list")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        selectedAction = context.scene.tgor_character_selection.action_selection
        if selectedAction < len(bpy.data.actions):
            action = bpy.data.actions[selectedAction]
            if not action:
                self.report({'INFO'}, "No action selected!")
                return {'CANCELLED'}
        
            for bone in (context.selected_pose_bones if context.selected_pose_bones else []) + (context.selected_bones if context.selected_bones else []):
                if action.sl_animation_bones.bones.find(bone.name) == -1 and bone.name in sl_const.validBones:

                    action.sl_animation_bones.bones.add()
                    action.sl_animation_bones.bones[-1].name = bone.name
                    action.sl_animation_bones.bones[-1].override = action.sl_animation_default_bone.override
                    action.sl_animation_bones.bones[-1].priority = action.sl_animation_default_bone.priority
                    action.sl_animation_bones.bones[-1].location = action.sl_animation_default_bone.location
                    action.sl_animation_bones.bones[-1].rotation = action.sl_animation_default_bone.rotation
                    action.sl_animation_bones.active_bone = action.sl_animation_bones.bones.find(bone.name)

        return {'FINISHED'}

class SL_OT_AnimationRemoveBone(Operator):
    bl_idname = "object.sl_animation_remove_bone"
    bl_label = "SL Remove Bone"
    bl_description = ("Removes a bone from current animation's bone list")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        selectedAction = context.scene.tgor_character_selection.action_selection
        if selectedAction < len(bpy.data.actions):
            action = bpy.data.actions[selectedAction]
            if not action:
                self.report({'INFO'}, "No action selected!")
                return {'CANCELLED'}

            if action.sl_animation_bones.active_bone >= 0:

                action.sl_animation_bones.bones.remove(action.sl_animation_bones.active_bone)
                action.sl_animation_bones.active_bone = -1
        return {'FINISHED'}


####################################################################################################
############################################# REGISTER #############################################
####################################################################################################

classes = (
    SL_UL_BonesList,

    SL_OT_AnimationExport,
    SL_OT_AnimationImport,
    SL_OT_AnimationAddBone,
    SL_OT_AnimationAddSelectedBones,
    SL_OT_AnimationRemoveBone,

    SLAnimationExportProperties,
    SLAnimationImportProperties,
    SLAnimationBones,
    SLBoneProperty,
    SLAnimationBoneProperties,
    SLAnimationUIProperties,
)

def register():
    from bpy.utils import register_class
    for c in classes:
        register_class(c)

    bpy.types.Action.sl_animation_export = PointerProperty(type=SLAnimationExportProperties)
    bpy.types.Action.sl_animation_import = PointerProperty(type=SLAnimationImportProperties)
    bpy.types.Action.sl_animation_default_bone = PointerProperty(type=SLAnimationBones)
    bpy.types.Action.sl_animation_bones = PointerProperty(type=SLAnimationBoneProperties)
    
    bpy.types.WindowManager.sl_animation_properties = PointerProperty(type=SLAnimationUIProperties)

def unregister():

    del bpy.types.Action.sl_animation_export
    del bpy.types.Action.sl_animation_import
    del bpy.types.Action.sl_animation_default_bone
    del bpy.types.Action.sl_animation_bones

    del bpy.types.WindowManager.sl_animation_properties

    from bpy.utils import unregister_class
    for c in reversed(classes):
        unregister_class(c)
