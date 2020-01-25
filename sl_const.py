
from mathutils import Matrix, Vector, Euler
import numpy as np

validBones = [
    'mSkull', 'mEyeRight', 'mEyeLeft', 'mFaceEyeAltRight', 'mFaceEyeAltLeft', 'mFaceForeheadLeft', 'mFaceForeheadRight', 'mFaceEyebrowOuterLeft', 
    'mFaceEyebrowCenterLeft', 'mFaceEyebrowInnerLeft', 'mFaceEyebrowOuterRight', 'mFaceEyebrowCenterRight', 'mFaceEyebrowInnerRight', 
    'mFaceEyeLidUpperLeft', 'mFaceEyeLidLowerLeft', 'mFaceEyeLidUpperRight', 'mFaceEyeLidLowerRight', 'mFaceEar2Left', 'mFaceEar1Left', 
    'mFaceEar2Right', 'mFaceEar1Right', 'mFaceNoseLeft', 'mFaceNoseCenter', 'mFaceNoseRight', 'mFaceCheekLowerLeft', 'mFaceCheekUpperLeft', 
    'mFaceCheekLowerRight', 'mFaceCheekUpperRight', 'mFaceChin', 'mFaceLipLowerLeft', 'mFaceLipLowerRight', 'mFaceLipLowerCenter', 'mFaceTongueTip', 
    'mFaceTongueBase', 'mFaceTeethLower', 'mFaceJaw', 'mFaceJawShaper', 'mFaceForeheadCenter', 'mFaceNoseBase', 'mFaceLipUpperLeft', 'mFaceLipUpperRight',
    'mFaceLipCornerLeft', 'mFaceLipCornerRight', 'mFaceLipUpperCenter', 'mFaceTeethUpper', 'mFaceEyecornerInnerLeft', 'mFaceEyecornerInnerRight', 
    'mFaceNoseBridge', 'mFaceRoot', 'mHead', 'HEAD', 'mNeck', 'NECK', 'mHandMiddle3Left', 'mHandMiddle2Left', 'mHandMiddle1Left', 'mHandIndex3Left', 
    'mHandIndex2Left', 'mHandIndex1Left', 'mHandRing3Left', 'mHandRing2Left', 'mHandRing1Left', 'mHandPinky3Left', 'mHandPinky2Left', 'mHandPinky1Left', 
    'mHandThumb3Left', 'mHandThumb2Left', 'mHandThumb1Left', 'mWristLeft', 'L_HAND', 'mElbowLeft', 'L_LOWER_ARM', 'mShoulderLeft', 'L_UPPER_ARM', 
    'mCollarLeft', 'L_CLAVICLE', 'mHandMiddle3Right', 'mHandMiddle2Right', 'mHandMiddle1Right', 'mHandIndex3Right', 'mHandIndex2Right', 'mHandIndex1Right', 
    'mHandRing3Right', 'mHandRing2Right', 'mHandRing1Right', 'mHandPinky3Right', 'mHandPinky2Right', 'mHandPinky1Right', 'mHandThumb3Right', 'mHandThumb2Right', 
    'mHandThumb1Right', 'mWristRight', 'R_HAND', 'mElbowRight', 'R_LOWER_ARM', 'mShoulderRight', 'R_UPPER_ARM', 'mCollarRight', 'R_CLAVICLE', 'mWing4Left', 
    'mWing4FanLeft', 'mWing3Left', 'mWing2Left', 'mWing1Left', 'mWing4Right', 'mWing4FanRight', 'mWing3Right', 'mWing2Right', 'mWing1Right', 'mWingsRoot', 
    'mChest', 'CHEST', 'LEFT_PEC', 'RIGHT_PEC', 'UPPER_BACK', 'mSpine4', 'mSpine3', 'mTorso', 'BELLY', 'LEFT_HANDLE', 'RIGHT_HANDLE', 'LOWER_BACK', 'mSpine2', 
    'mSpine1', 'mToeRight', 'mFootRight', 'mAnkleRight', 'R_FOOT', 'mKneeRight', 'R_LOWER_LEG', 'mHipRight', 'R_UPPER_LEG', 'mToeLeft', 'mFootLeft', 
    'mAnkleLeft', 'L_FOOT', 'mKneeLeft', 'L_LOWER_LEG', 'mHipLeft', 'L_UPPER_LEG', 'mTail6', 'mTail5', 'mTail4', 'mTail3', 'mTail2', 'mTail1', 'mGroin', 
    'mHindLimb4Left', 'mHindLimb3Left', 'mHindLimb2Left', 'mHindLimb1Left', 'mHindLimb4Right', 'mHindLimb3Right', 'mHindLimb2Right', 'mHindLimb1Right', 
    'mHindLimbsRoot', 'mPelvis', 'PELVIS', 'BUTT']

renameList = [
        ("!Slit_L", "mHindLimb1Left"),
        ("!Slit_R", "mHindLimb2Left"),
        ("!Slit_B", "mHindLimb3Left"),
        ("!Slit_T", "mHindLimb4Left"),
        ("!Tailhole_R", "mHindLimb1Right"),
        ("!Tailhole_L", "mHindLimb2Right"),
        ("!Tailhole_T", "mHindLimb3Right"),
        ("!Tailhole_B", "mHindLimb4Right")
    ]
    
colladaLookup = {
    'HEAD': np.array([0.11, 0.09, 0.12]), 'NECK': np.array([0.05, 0.06, 0.08]), 'L_HAND': np.array([0.05, 0.08, 0.03]), 'L_LOWER_ARM': np.array([0.04, 0.14, 0.04]), 
    'L_UPPER_ARM': np.array([0.05, 0.17, 0.05]), 'L_CLAVICLE': np.array([0.07, 0.14, 0.05]), 'R_HAND': np.array([0.05, 0.08, 0.03]), 'R_LOWER_ARM': np.array([0.04, 0.14, 0.04]), 
    'R_UPPER_ARM': np.array([0.05, 0.17, 0.05]), 'R_CLAVICLE': np.array([0.07, 0.14, 0.05]), 'CHEST': np.array([0.11, 0.15, 0.2 ]), 'LEFT_PEC': np.array([0.05, 0.05, 0.05]), 
    'RIGHT_PEC': np.array([0.05, 0.05, 0.05]), 'UPPER_BACK': np.array([0.09, 0.13, 0.15]), 'BELLY': np.array([0.09, 0.13, 0.15]), 'LEFT_HANDLE': np.array([0.05, 0.05, 0.05]), 
    'RIGHT_HANDLE': np.array([0.05, 0.05, 0.05]), 'LOWER_BACK': np.array([0.09, 0.13, 0.15]), 'R_FOOT': np.array([0.13, 0.05, 0.05]), 'R_LOWER_LEG': np.array([0.06, 0.06, 0.25]), 
    'R_UPPER_LEG': np.array([0.09, 0.09, 0.32]), 'L_FOOT': np.array([0.13, 0.05, 0.05]), 'L_LOWER_LEG': np.array([0.06, 0.06, 0.25]), 'L_UPPER_LEG': np.array([0.09, 0.09, 0.32]), 
    'PELVIS': np.array([0.12, 0.16, 0.17]), 'BUTT': np.array([0.1, 0.1, 0.1])}

rightRot = Matrix(((0.0, 1.0, 0.0, 0.0), (-1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)))
leftRot = Matrix(((0.0, -1.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)))