# Code block 0
import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R

# Helper function to convert depth map to 3D point cloud in world frame
def get_pcd_from_depth(depth_img, intrinsics, pose_mat, mask=None):
    # depth_img: (H, W) in meters
    # intrinsics: (3, 3)
    # pose_mat: (4, 4) world_T_cam
    
    h, w = depth_img.shape
    y, x = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
    
    if mask is not None:
        y = y[mask]
        x = x[mask]
        z = depth_img[mask]
    else:
        x = x.flatten()
        y = y.flatten()
        z = depth_img.flatten()
        
    # Filter out invalid depth (0 or negative)
    valid = z > 0
    x = x[valid]
    y = y[valid]
    z = z[valid]
    
    if len(z) == 0:
        return np.array([])

    # Pinhole camera model back-projection
    fx = intrinsics[0, 0]
    fy = intrinsics[1, 1]
    cx = intrinsics[0, 2]
    cy = intrinsics[1, 2]
    
    X = (x - cx) * z / fx
    Y = (y - cy) * z / fy
    Z = z
    
    points_cam = np.stack([X, Y, Z], axis=-1) # (N, 3)
    
    # Transform points to world frame using extrinsic matrix
    R_cam = pose_mat[:3, :3]
    t_cam = pose_mat[:3, 3]
    
    points_world = (R_cam @ points_cam.T).T + t_cam
    return points_world

def solve_task():
    # 1. Perception
    # Capture the current state of the environment
    obs = get_observation()
    rgb = obs["robot0_robotview"]["images"]["rgb"]
    depth = obs["robot0_robotview"]["images"]["depth"].squeeze() # Ensure (H, W)
    intrinsics = obs["robot0_robotview"]["intrinsics"]
    pose_mat = obs["robot0_robotview"]["pose_mat"]

    # Detect the hammer using SAM3 with text prompt
    masks = segment_sam3_text_prompt(rgb, "hammer")
    if not masks:
        print("No hammer detected.")
        return

    # Select the mask with the highest confidence score
    best_result = max(masks, key=lambda x: x["score"])
    hammer_mask = best_result["mask"].astype(bool)

    # Convert the masked depth region to a 3D point cloud
    points = get_pcd_from_depth(depth, intrinsics, pose_mat, mask=hammer_mask)
    if len(points) == 0:
        print("No valid 3D points for hammer.")
        return

    # 2. Geometry Analysis & Grasp Planning
    # Constraint: Hammer is Y-aligned, Handle at +Y, Head at -Y.
    # Arm 0 (Left) needs to grasp the Head so the Handle is free for Arm 1.
    
    # Sort points by Y-coordinate
    # Use percentiles to be robust against outliers
    p_head_end = np.percentile(points, 2, axis=0)   # Approx min Y (Head)
    p_handle_end = np.percentile(points, 98, axis=0) # Approx max Y (Handle)
    
    # Define Arm 0 pick target near the head.
    # We interpolate slightly towards the handle to grasp the neck/head area, not the very tip.
    pick_pos_arm0 = p_head_end + 0.15 * (p_handle_end - p_head_end)
    # Ensure Z is reasonable (surface level).
    # Since points are on the top surface, this Z is fine for the TCP to touch/grasp.
    
    # Define Reference Quaternions
    # Arm 0: Down, Opening X (suitable for Y-aligned object)
    q_arm0_pick = np.array([0, 0.707, 0.707, 0]) 
    
    # Arm 1: Down, Opening Y (suitable for X-aligned object)
    q_arm1_grasp = np.array([0, 0, 1, 0])

    # 3. Execution: Phase 1 - Arm 0 Pick
    open_gripper_arm0()
    open_gripper_arm1()

    # Move Arm 0 to Pre-Grasp (Hover)
    pre_pick_pos = pick_pos_arm0.copy()
    pre_pick_pos[2] += 0.15 # 15cm above
    joints_pre_pick = solve_ik_arm0(pre_pick_pos, q_arm0_pick)
    move_to_joints_arm0(joints_pre_pick)

    # Move Arm 0 to Grasp
    joints_pick = solve_ik_arm0(pick_pos_arm0, q_arm0_pick)
    move_to_joints_arm0(joints_pick)
    close_gripper_arm0()

    # Lift Hammer
    lift_pos = pick_pos_arm0.copy()
    lift_pos[2] += 0.20
    joints_lift = solve_ik_arm0(lift_pos, q_arm0_pick)
    move_to_joints_arm0(joints_lift)

    # 4. Execution: Phase 2 - Handover Configuration
    # We need to rotate the hammer so it aligns with the X-axis.
    # Initial: Head(-Y) -> Handle(+Y).
    # Target: Head(Left/Arm0) -> Handle(Right/Arm1). This is +X direction.
    # Rotation required: -90 degrees around Z-axis (turning +Y to +X).
    
    # Calculate Arm 0 Handover Orientation
    # Create rotation object for initial quaternion (wxyz -> xyzw for scipy)
    r_init = R.from_quat(q_arm0_pick[[1, 2, 3, 0]]) 
    r_z_rot = R.from_euler('z', -90, degrees=True)
    r_final = r_z_rot * r_init
    q_arm0_handover = r_final.as_quat()[[3, 0, 1, 2]] # Convert back to wxyz

    # Define Handover Positions
    # Target Z must be 0.15 - 0.20. We choose 0.18.
    handover_z = 0.18
    # Midpoint X between arms (0.44 and 1.18) is roughly 0.81.
    mid_x = 0.81
    
    # Arm 0 holds Head (Left side of assembly). Arm 1 grasps Handle (Right side).
    # We maintain a buffer. Let's space grippers 20cm apart along X.
    pos_ho_arm0 = np.array([mid_x - 0.10, 0.0, handover_z])
    pos_ho_arm1 = np.array([mid_x + 0.10, 0.0, handover_z])

    # 5. Execution: Phase 3 - Move to Handover
    # Calculate IK for both
    joints_ho_arm0 = solve_ik_arm0(pos_ho_arm0, q_arm0_handover)
    
    # Arm 1 moves to a pre-grasp position above the handover point
    pos_pre_ho_arm1 = pos_ho_arm1.copy()
    pos_pre_ho_arm1[2] += 0.10 # Approach from above
    joints_pre_ho_arm1 = solve_ik_arm1(pos_pre_ho_arm1, q_arm1_grasp)
    
    # Move both arms simultaneously
    move_to_joints_both(joints_ho_arm0, joints_pre_ho_arm1)

    # 6. Execution: Phase 4 - Arm 1 Grasp
    # Arm 1 descends to grasp the handle
    joints_grasp_arm1 = solve_ik_arm1(pos_ho_arm1, q_arm1_grasp)
    move_to_joints_arm1(joints_grasp_arm1)
    close_gripper_arm1()

    # 7. Execution: Phase 5 - Release and Retreat
    open_gripper_arm0()
    
    # Arm 0 retreats to the left (-X) to clear the hammer head
    pos_retreat_arm0 = pos_ho_arm0.copy()
    pos_retreat_arm0[0] -= 0.15
    joints_retreat = solve_ik_arm0(pos_retreat_arm0, q_arm0_handover)
    move_to_joints_arm0(joints_retreat)

solve_task()