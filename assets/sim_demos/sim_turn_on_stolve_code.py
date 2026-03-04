# Code block 0
import numpy as np

# 1. Get the current observation from the environment
obs = get_observation()
rgb = obs["agentview"]["images"]["rgb"]
depth = obs["agentview"]["images"]["depth"]
intrinsics = obs["agentview"]["intrinsics"]
cam_extrinsics = obs["agentview"]["pose_mat"]

# 2. Segment the stove control knob
# The prompt is derived from the description: "Stove Control Knob... black, vertical handle-like object"
seg_results = segment_sam3_text_prompt(rgb, "black stove control knob handle")

# If the specific prompt fails, try a more generic one, though the first should work given the description.
if not seg_results:
    seg_results = segment_sam3_text_prompt(rgb, "black handle")

# Select the mask with the highest confidence score
target_mask_dict = max(seg_results, key=lambda x: x["score"])
target_mask = target_mask_dict["mask"]

# 3. Plan grasp poses on the segmented mask
# Note: plan_grasp returns poses in the Camera Frame
grasp_poses_cam, grasp_scores = plan_grasp(depth, intrinsics, target_mask)

if len(grasp_poses_cam) > 0:
    # 4. Transform grasp poses to World Frame
    grasp_poses_world = []
    for g_cam in grasp_poses_cam:
        grasp_poses_world.append(cam_extrinsics @ g_cam)
    grasp_poses_world = np.array(grasp_poses_world)

    # Select the best grasp based on the score
    best_idx = np.argmax(grasp_scores)
    best_grasp_world = grasp_poses_world[best_idx]

    # 5. Define Approach and Action
    # Calculate a pre-grasp position 10cm away along the gripper's negative Z-axis (approach direction)
    # The gripper Z-axis is the third column of the rotation matrix
    approach_vector = best_grasp_world[:3, 2]
    approach_vector = normalize_vector(approach_vector)
    pre_grasp_pos = best_grasp_world[:3, 3] - (approach_vector * 0.10)

    # Open gripper before approaching
    open_gripper()

    # Move to Pre-grasp
    pre_grasp_pose = best_grasp_world.copy()
    pre_grasp_pose[:3, 3] = pre_grasp_pos
    pos_pre, quat_pre = decompose_transform(pre_grasp_pose)
    joints_pre = solve_ik(pos_pre, quat_pre)
    move_to_joints(joints_pre)

    # Move to Grasp
    pos_grasp, quat_grasp = decompose_transform(best_grasp_world)
    joints_grasp = solve_ik(pos_grasp, quat_grasp)
    move_to_joints(joints_grasp)

    # Close gripper to grab the knob
    close_gripper()

    # 6. Manipulate (Turn the Knob)
    # To turn the stove on, we rotate the knob. Assuming a rotation around the World Z-axis (vertical)
    # is appropriate for a stove knob on a table surface. We rotate 90 degrees (pi/2).
    rotation_angle = np.pi / 2
    c, s = np.cos(rotation_angle), np.sin(rotation_angle)
    # Rotation matrix for Z-axis rotation
    R_z = np.array([
        [c, -s, 0],
        [s, c, 0],
        [0, 0, 1]
    ])
    
    # Calculate the new rotation: R_new = R_z_world * R_current
    current_rot = best_grasp_world[:3, :3]
    new_rot = R_z @ current_rot
    
    turn_pose_world = best_grasp_world.copy()
    turn_pose_world[:3, :3] = new_rot
    
    # Execute the turn
    pos_turn, quat_turn = decompose_transform(turn_pose_world)
    joints_turn = solve_ik(pos_turn, quat_turn)
    move_to_joints(joints_turn)

    # 7. Release and Retreat
    open_gripper()
    
    # Retreat backwards
    retreat_pos = pos_turn - (approach_vector * 0.10)
    joints_retreat = solve_ik(retreat_pos, quat_turn)
    move_to_joints(joints_retreat)
else:
    print("Could not find a valid grasp for the stove knob.")