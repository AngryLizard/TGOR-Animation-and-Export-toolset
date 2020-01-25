import bpy

#-----------------------------------
# Exits the pose mode and puts blender in the object mode, contexts with the scripts are made to work with
def exitPoseMode(context):	
	if context.object:
		if context.object in context.visible_objects:
			bpy.ops.object.mode_set(mode='OBJECT')


# Make the string valid with windows file name limitiations (english characters only)
def makeValidFilename(filename):
	characters = '-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
	return ''.join(c if c in characters else "_" for c in filename)
	
#-----------------------------------
# Checks if object can be exported as skeletal mesh
# Used in UI and export operator
def exportableMesh(deformRig, ob):
	# Check if the object is a child of deformRig object
	if ob.parent == deformRig:
		# Check if mesh has an armature modifier 
		for mod in ob.modifiers:
			if mod.type == 'ARMATURE':
				# Check if that armature modifier has the deform rig as its target object
				if mod.object == deformRig:
					return True
									
	return False

	# Check the object name if it doesn't have _LOD# or _LO# as suffix (for potential LOD export in the future)
	# if not ob.name.endswith(("_LOD", "_LO"), 0 , len(ob.name)-1):
	
