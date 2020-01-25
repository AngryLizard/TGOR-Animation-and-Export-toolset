
import bpy
from mathutils import Vector, Quaternion
from bpy.props import IntProperty, StringProperty, EnumProperty, FloatProperty, CollectionProperty, PointerProperty, BoolProperty
from bpy.types import PropertyGroup, Operator, Panel

modeItems = [
    ("FKTOIK", "FK to IK", "", 1),
    ("IKTOFK", "IK to FK", "", 2),
    ("ANY", "Any", "", 3)
    ]


#----------------------------------------------------------------
#
class TGOR_PT_Properties(Panel):
	"""Adds new buttons to Properties of selected bones when applicable for TGOR rig""" 
	bl_label = "TGOR IK/FK"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Item'

#	Creates transform operator button
	def drawTransformOperator(self, row, text, mode, bone, space):
		op = row.operator("scene.action_rig_transform_space", text=text, icon='NLA_PUSHDOWN')
		op.mode = mode
		op.bone = bone
		op.space = space

# 	Draw the menu elements
	def draw(self, context):
	
		
		layout = self.layout
		
		if context.object and context.object.type == 'ARMATURE' and context.object.data.bones.active:
			bone = context.object.data.bones.active.name 			
			
			if 'Transform Space' in context.object.pose.bones[bone]:
				row = layout.row()
				col = layout.column()
				box = col.box()
				box.label(text="Transform Space")
				row = box.row(align=True)
				self.drawTransformOperator(row, "Parent", 	0, bone, 0.0)
				self.drawTransformOperator(row, "Control", 	0, bone, 1.0)
				self.drawTransformOperator(row, "World", 	0, bone, 2.0)
				self.drawTransformOperator(row, "Parent", 	0, bone, 3.0)
				
			if 'Location Space' in context.object.pose.bones[bone]:
				row = layout.row()
				col = layout.column()
				box = col.box()
				box.label(text="Location Space")
				row = box.row(align=True)
				self.drawTransformOperator(row, "Parent", 	1, bone, 0.0)
				self.drawTransformOperator(row, "Control",  1, bone, 1.0)
				self.drawTransformOperator(row, "World", 	1, bone, 2.0)
				self.drawTransformOperator(row, "Parent", 	1, bone, 3.0)
				
			if 'Rotation Space' in context.object.pose.bones[bone]:
				row = layout.row()
				col = layout.column()
				box = col.box()
				box.label(text="Rotation Space")
				row = box.row(align=True)
				self.drawTransformOperator(row, "Parent", 	2, bone, 0.0)
				self.drawTransformOperator(row, "Control",  2, bone, 1.0)
				self.drawTransformOperator(row, "World", 	2, bone, 2.0)
				self.drawTransformOperator(row, "Parent", 	2, bone, 3.0)				
			
			collections = context.scene.kinematicBoneCollection
			
			# Find collection selected bone is in
			selected = context.object.data.bones.active.name
			collection = findMatchingCollection(context, "ANY", selected)
			if collection :
				
				if collection.property in context.object.pose.bones:
					
					# Display configured properties
					bone = context.object.pose.bones[collection.property]
					column = layout.column(align=True)
					column.prop(bone, '["%s"]' % collection.primary)
					column.prop(bone, '["%s"]' % collection.secondary)
				
				# Copy transfor operator with mode switch
				row = layout.row()
				if collection.mode == "ANY" or collection.mode == "IKTOFK":
					row.operator(TGOR_OT_ActionIKToFKOperator.bl_idname, icon='COPY_ID')
				if collection.mode == "ANY" or collection.mode == "FKTOIK":
					row.operator(TGOR_OT_ActionFKToIKOperator.bl_idname, icon='COPY_ID')
			
			
			# Switch menu on or off
			layout.separator()
			layout.prop(context.window_manager, "kinematicBoneEnabled")
			if context.window_manager.kinematicBoneEnabled:
								
				row = layout.row()
				column = row.column()
				
				# Display list of collections with Add and Remove buttons
				sub = column.row(align=True)
				sub.template_list("UI_UL_list", "bone_collections", collections, "collections", collections, "active")
				
				sub = column.row(align=True)
				sub.operator(TGOR_OT_ActionAddCollectionOperator.bl_idname, text="", icon='ZOOM_IN')
				sub.operator(TGOR_OT_ActionRemoveCollectionOperator.bl_idname, text="", icon='ZOOM_OUT')			
				
				# Display collection properties if one is selected
				if collections.active in range(0,len(collections.collections)):
					collection = collections.collections[collections.active]
					
					sub.prop(collection, "mode", text="")
					sub = column.row(align=True)
					sub.prop(collection, "primary", text="")
					sub = column.row(align=True)
					sub.prop(collection, "secondary", text="")
					sub = column.row(align=True)
					sub.prop_search(collection, "property", context.object.data, "bones", text="")
					
					# Display list of associated bones with Add and Remove buttons
					column = row.column()
					sub = column.row(align=True)
					sub.template_list("UI_UL_list", "collection_bones", collection, "bones", collection, "active")
					
					sub = column.row(align=True)
					sub.operator(TGOR_OT_ActionAddBoneOperator.bl_idname, text="", icon='ZOOM_IN')
					sub.operator(TGOR_OT_ActionRemoveBoneOperator.bl_idname, text="", icon='ZOOM_OUT')
					
					# Display bone properties if one is selected
					if collection.active in range(0,len(collection.bones)):
						bone = collection.bones[collection.active]
						sub.prop_search(bone, "source", context.object.data, "bones", text="")
						sub.operator(TGOR_OT_ActionSourceSelectionOperator.bl_idname, text="", icon='UV_SYNC_SELECT')
						sub.prop_search(bone, "target", context.object.data, "bones", text="")
						sub.operator(TGOR_OT_ActionTargetSelectionOperator.bl_idname, text="", icon='UV_SYNC_SELECT')


def copyBoneTransform(context, source, target):
		
	# Store old values for later retreival in case of locked values
	oldLocation = source.location.copy()
	oldScale = source.scale.copy()
	oldRotation = source.rotation_euler.copy()
	
	if target:
		# Get world space
		location = target.matrix @ Vector([0,0,0])
		rotation = target.matrix.to_3x3()
			
		# Compute location and rotation in bone local space
		parent =  source.matrix_basis @ source.matrix.inverted_safe()
		
		# Set rotation matrix
		matrix = (parent.to_3x3() @ rotation).to_4x4()
		
		# Set location part of matrix
		local = (parent @ location)
		matrix[0][3] = local[0]
		matrix[1][3] = local[1]
		matrix[2][3] = local[2]
		
		source.matrix_basis = matrix
	else:
		# Set all values to 0
		source.matrix_basis.zero()
		
	# Update transforms
	context.view_layer.update()
    		
	# Reset locked
	for i in range(0, 3):
		if source.lock_location[i]: 
			source.location[i] = oldLocation[i]
		if source.lock_scale[i]: 
			source.scale[i] = oldScale[i]
		if source.lock_rotation[i]: 
			source.rotation_euler[i] = oldRotation[i]
    
    
# Copies transforms of all bones featured in collection
def copyBoneTransforms(context, collection):
	
	bones = []
	
	# Apply to all connections
	for connection in collection.bones:
		
		# Get source bone
		if connection.source in context.object.pose.bones:
			source = context.object.pose.bones[connection.source]
			
			# Get target bone
			if connection.target in context.object.pose.bones:
				target = context.object.pose.bones[connection.target]
				
				# Apply transform
				bones.append((source, target))
			else:
				bones.append((source, None))
	
	# Sort by depth inside target hierarchy
	bones.sort(key=lambda x: len(x[0].parent_recursive))
	for tuple in bones:
		
		# Copy transforms
		copyBoneTransform(context, tuple[0], tuple[1])

# Finds collection with the right mode featuring selected bone
def findMatchingCollection(context, mode, selected):
	
	# Get collections
	collections = context.scene.kinematicBoneCollection
			
	# Get all collections with the right mode
	for collection in collections.collections:
		if collection.mode == mode or collection.mode == "ANY" or mode == "ANY":
			
			# Find all connections that feature this bone
			for connection in collection.bones:
				
				if selected == connection.source or selected == connection.target:
					return collection
	return None
	
# ------------------------------------------------------------------
# Match transform from FK to IK
class TGOR_OT_ActionFKToIKOperator(bpy.types.Operator):
	bl_label = "Copy FK to IK transform"
	bl_idname = "scene.action_fk_to_ik_space"
	bl_description = "Copy FK to IK transform"
		
	
	def execute(self, context):
		
		if context.object and context.object.type == 'ARMATURE' and context.object.mode == 'POSE' and context.object.data.bones.active:
			selected = context.object.data.bones.active.name
			
			# Copy transforms of all bones featured in the same collection
			collection = findMatchingCollection(context, "FKTOIK", selected)
			
			if collection:
				copyBoneTransforms(context, collection)
		
		return {'FINISHED'}
	
# ------------------------------------------------------------------
# Match transform from IK to FK
class TGOR_OT_ActionIKToFKOperator(bpy.types.Operator):
	bl_label = "Copy IK to FK transform"
	bl_idname = "scene.action_ik_to_fk_space"
	bl_description = "Copy IK to FK transform"
		
	def execute(self, context):
		
		if context.object and context.object.type == 'ARMATURE' and context.object.mode == 'POSE' and context.object.data.bones.active:
			selected = context.object.data.bones.active.name
			
			# Copy transforms of all bones featured in the same collection
			collection = findMatchingCollection(context, "IKTOFK", selected)
			
			if collection:
				copyBoneTransforms(context, collection)
		
		return {'FINISHED'}

# ------------------------------------------------------------------
# Add bone collection
class TGOR_OT_ActionAddCollectionOperator(bpy.types.Operator):
	bl_label = "Add Collection"
	bl_idname = "scene.action_add_collection"
	bl_description = "Add bone collection"
	
	def execute(self, context):
			
		collections = context.scene.kinematicBoneCollection
		collections.active = len(collections.collections)
		collection = collections.collections.add()
		collection.name = "new"
		if not collection.name:
			collection.name = "BoneCollection"
		
		return {'FINISHED'}
	
# ------------------------------------------------------------------
# Remove bone collection
class TGOR_OT_ActionRemoveCollectionOperator(bpy.types.Operator):
	bl_label = "Remove Collection"
	bl_idname = "scene.action_remove_collection"
	bl_description = "Remove bone collection"
	
	def execute(self, context):
			
		collections = context.scene.kinematicBoneCollection
		
		if collections.active in range(0,len(collections.collections)):
			collections.collections.remove(collections.active)
			collections.active = -1
		
		return {'FINISHED'}

# ------------------------------------------------------------------
# Source select bone
class TGOR_OT_ActionSourceSelectionOperator(bpy.types.Operator):
	bl_label = "Source Select Bone"
	bl_idname = "scene.source_select_bone"
	bl_description = "Source select bone"
	
	def execute(self, context):
		
		if context.object and context.object.type == 'ARMATURE' and context.object.data.bones.active:
			collections = context.scene.kinematicBoneCollection
			
			if collections.active in range(0,len(collections.collections)) :
				collection = collections.collections[collections.active]

				if collection.active in range(0,len(collection.bones)) :
					bone = collection.bones[collection.active]
					
					bone.source = context.object.data.bones.active.name
				
		return {'FINISHED'}

# ------------------------------------------------------------------
# Target select bone
class TGOR_OT_ActionTargetSelectionOperator(bpy.types.Operator):
	bl_label = "Target Select Bone"
	bl_idname = "scene.target_select_bone"
	bl_description = "Target select bone"
	
	def execute(self, context):
		
		if context.object and context.object.type == 'ARMATURE' and context.object.data.bones.active:
			collections = context.scene.kinematicBoneCollection
			
			if collections.active in range(0,len(collections.collections)) :
				collection = collections.collections[collections.active]

				if collection.active in range(0,len(collection.bones)) :
					bone = collection.bones[collection.active]
					bone.target = context.object.data.bones.active.name
				
		return {'FINISHED'}

# ------------------------------------------------------------------
# Add bone
class TGOR_OT_ActionAddBoneOperator(Operator):
	bl_label = "Add Bone"
	bl_idname = "scene.action_add_bone"
	bl_description = "Add bone"
	
	def execute(self, context):
		
		collections = context.scene.kinematicBoneCollection
		
		if collections.active in range(0,len(collections.collections)) :
			collection = collections.collections[collections.active]

			collection.active = len(collection.bones)
			bone = collection.bones.add()
			bone.name = "new"
		
		return {'FINISHED'}
	
# ------------------------------------------------------------------
# Remove bone
class TGOR_OT_ActionRemoveBoneOperator(Operator):
	bl_label = "Remove Bone"
	bl_idname = "scene.action_remove_bone"
	bl_description = "Remove bone"
	
	def execute(self, context):
		
		collections = context.scene.kinematicBoneCollection
		
		if collections.active in range(0,len(collections.collections)) :
			collection = collections.collections[collections.active]
			
			if collection.active in range(0,len(collection.bones)) :
				collection.bones.remove(collection.active)
				collection.active = collection.active - 1
				
		return {'FINISHED'}
	
# ------------------------------------------------------------------
# Copy selected action
class TGOR_OT_ActionTransformSpaceOperator(Operator):
	bl_label = "Transform Space"
	bl_idname = "scene.action_rig_transform_space"
	bl_description = "Switch between various bone transform spaces without moving the bone"
	
	# input parameter with the mesh name to export
	mode: IntProperty(default=0) #0 Transform, 1 Location, 2 Rotation
	bone: StringProperty(default="")
	space: FloatProperty(default=0.0)
	
	def execute(self, context):
	
		if self.bone in context.object.pose.bones:
			bone = context.object.pose.bones[self.bone]
			
			# Get world space (Tried to make it with one 4x4 only, didn't work. Try it I dare you.)
			location = bone.matrix @ Vector([0,0,0])
			rotation = bone.matrix.to_3x3()
			
			# Move the rig
			name = 'Location Space' if self.mode == 1 else 'Rotation Space' if self.mode == 2 else 'Transform Space'
			bone[name] = self.space
			
			# Custom properties don't update the rig, so we do it manually.
			# DO NOT DELET EVEN IF STUPID
			bone.location = bone.location
			
			# Update all matrices
			context.view_layer.update()
			
			# Compute location and rotation in bone local space
			parent =  bone.matrix_basis @ bone.matrix.inverted_safe()
			
			if self.mode != 1:
				
				# Set rotation matrix
				matrix = (parent.to_3x3() @ rotation).to_4x4()
				
				# Set location part of matrix
				if self.mode != 2: 
					local = (parent @ location)
				else:
					local = bone.location
                    
				matrix[0][3] = local[0]
				matrix[1][3] = local[1]
				matrix[2][3] = local[2]
				bone.matrix_basis = matrix
			
			elif self.mode != 2:
				
				# Set location
				bone.location = parent @ location
			
		return {'FINISHED'}


# ------------------------------------------------------------------
		
def updateBone(self, context):
	self.name = self.source + " -> " + self.target


class BoneIdentifier(PropertyGroup):
	
	# source bone
	source: StringProperty(name="Source", update=updateBone, default="")
	
	# target bone
	target: StringProperty(name="Target", update=updateBone, default="")
	
class BoneCollection(PropertyGroup):
	
	# Active bone
	active: IntProperty(name="Active", default=0)
	
	# Mode
	mode: EnumProperty(name="Selected", items=modeItems)
	
	# Primary property 
	primary: StringProperty(name="Primary", description="Primary property name to expose")
	
	# Secondary property
	secondary: StringProperty(name="Secondary", description="Secondary property name to expose")
	
	# Property bone target
	property: StringProperty(name="Property", description="Bone to display primary and secondary properties from")
	
	# Bone names
	bones: CollectionProperty(name="Bones", type=BoneIdentifier)
	
class BoneCollections(PropertyGroup):
	
	# Active collection
	active: IntProperty(name="Active", default=0)
		
	# Bone names
	collections: CollectionProperty(name="Collections", type=BoneCollection)



classes = (
	TGOR_PT_Properties,
	TGOR_OT_ActionFKToIKOperator,
	TGOR_OT_ActionIKToFKOperator,
	TGOR_OT_ActionAddCollectionOperator,
	TGOR_OT_ActionRemoveCollectionOperator,
	TGOR_OT_ActionSourceSelectionOperator,
	TGOR_OT_ActionTargetSelectionOperator,
	TGOR_OT_ActionAddBoneOperator,
	TGOR_OT_ActionRemoveBoneOperator,
    TGOR_OT_ActionTransformSpaceOperator,

    BoneIdentifier,
    BoneCollection,
    BoneCollections,
)

def register():

    from bpy.utils import register_class
    for c in classes:
        register_class(c)
	
    bpy.types.Scene.kinematicBoneCollection = PointerProperty(type=BoneCollections)
    bpy.types.WindowManager.kinematicBoneEnabled = BoolProperty(name="Settings", default=False)

def unregister():
	
	del bpy.types.Scene.kinematicBoneCollection
	del bpy.types.WindowManager.kinematicBoneEnabled

	from bpy.utils import unregister_class
	for c in reversed(classes):
		unregister_class(c)