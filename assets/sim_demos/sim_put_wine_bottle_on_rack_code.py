# Code block 0
import numpy as np

def main():
    # 1. Perception: Get current state
    obs = get_observation()
    rgb = obs["agentview"]["images"]["rgb"]
    depth = obs["agentview"]["images"]["depth"]
    intrinsics = obs["agentview"]["intrinsics"]
    extrinsics = obs["agentview"]["pose_mat"]

    # 2. Identify Objects: Bottle and Rack
    # Segment the wine bottle
    bottle_results = segment_sam3_text_prompt(rgb, "wine bottle")
    if not bottle_results:
        print("Error: Could not find wine bottle.")
        return
    # Pick the mask with the highest confidence score
    bottle_data = max(bottle_results, key=lambda x: x["score"])
    bottle_mask = bottle_data["mask"]

    # Segment the rack
    rack_results = segment_sam3_text_prompt(rgb, "wooden wine rack")
    if not rack_results:
        # Fallback to simpler prompt
        rack_results = segment_sam3_text_prompt(rgb, "rack")
    
    if not rack_results:
        print("Error: Could not find rack.")
        return
        
    rack_data = max(rack_results, key=lambda x: x["score"])
    rack_mask = rack_data["mask"]

    # 3. Grasp Planning
    # Create an integer segmentation map for the grasp planner (bottle = 1)
    seg_map = np.zeros(depth.shape, dtype=np.int32)
    seg_map[bottle_mask] = 1

    # Plan grasps. grasp_poses_cam are in camera frame.
    grasp_poses_cam, grasp_scores = plan_grasp(depth, intrinsics, seg_map)
    
    if len(grasp_scores) == 0:
        print("Error: No valid grasps found.")
        return

    # Prefer a top-down grasp for the upright bottle
    best_grasp_world, best_score = select_top_down_grasp(
        grasp_poses_cam, grasp_scores, extrinsics, vertical_threshold=0.8
    )

    # If top-down fails, use the highest scoring grasp regardless of orientation
    if best_grasp_world is None:
        print("Warning: No top-down grasp found. Using best available.")
        # Transform all to world frame manually
        grasp_poses_world = np.matmul(extrinsics, grasp_poses_cam)
        best_idx = np.argmax(grasp_scores)
        best_grasp_world = grasp_poses_world[best_idx]

    # Decompose the target grasp into position and orientation
    grasp_pos, grasp_quat = decompose_transform(best_grasp_world)
    
    # 4. Execute Grasp
    open_gripper()
    
    # Calculate pre-grasp position: back off 10cm along the gripper's Z-axis (approach vector)
    grasp_rot = best_grasp_world[:3, :3]
    approach_vec = grasp_rot[:, 2] 
    pre_grasp_pos = grasp_pos - (approach_vec * 0.10)

    # Move to pre-grasp
    joints_pre = solve_ik(pre_grasp_pos, grasp_quat)
    move_to_joints(joints_pre)
    
    # Move to grasp
    joints_grasp = solve_ik(grasp_pos, grasp_quat)
    move_to_joints(joints_grasp)
    
    close_gripper()
    
    # Lift the bottle vertically (World +Z) to clear table/obstacles
    lift_height = 0.25 # 25cm lift
    lift_pos = grasp_pos + np.array([0.0, 0.0, lift_height])
    joints_lift = solve_ik(lift_pos, grasp_quat)
    move_to_joints(joints_lift)

    # 5. Place Planning
    # Convert rack mask to 3D world points to understand its geometry
    rack_points_world = mask_to_world_points(rack_mask, depth, intrinsics, extrinsics)
    
    # We will aim for the center of the rack's occupied space
    rack_bbox = get_oriented_bounding_box_from_3d_points(rack_points_world)
    rack_center = rack_bbox["center"]
    
    # To avoid collision, we place it slightly above the highest point of the rack
    rack_max_z = np.max(rack_points_world[:, 2])
    
    # Target place position: Center X/Y, Max Z + buffer
    place_pos = rack_center.copy()
    place_pos[2] = rack_max_z + 0.10 # 10cm clearance above the rack's structure

    # 6. Execute Place
    # Move to a "hover" position above the rack first
    # Ensure the hover height is safe (higher of current lift or target place + margin)
    safe_z = max(lift_pos[2], place_pos[2] + 0.1)
    hover_pos = place_pos.copy()
    hover_pos[2] = safe_z
    
    # We maintain the grasp orientation during transfer
    joints_hover = solve_ik(hover_pos, grasp_quat)
    move_to_joints(joints_hover)
    
    # Lower to the rack
    joints_place = solve_ik(place_pos, grasp_quat)
    move_to_joints(joints_place)
    
    # Release object
    open_gripper()
    
    # Retreat (move up to clear the object)
    retreat_pos = place_pos + np.array([0.0, 0.0, 0.15])
    joints_retreat = solve_ik(retreat_pos, grasp_quat)
    move_to_joints(joints_retreat)

main()