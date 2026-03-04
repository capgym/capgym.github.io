# Code block 0
import numpy as np

def solve():
    # 1. Get observation
    print("Getting observation...")
    obs = get_observation()
    rgb = obs["robot0_robotview"]["images"]["rgb"]
    depth = obs["robot0_robotview"]["images"]["depth"]
    intrinsics = obs["robot0_robotview"]["intrinsics"]
    cam_pose = obs["robot0_robotview"]["pose_mat"]

    # 2. Segment handles
    # Arm 0 target: Green handle
    # Arm 1 target: Blue handle
    print("Segmenting handles...")
    green_results = segment_sam3_text_prompt(rgb, "green handle")
    blue_results = segment_sam3_text_prompt(rgb, "blue handle")

    if not green_results:
        print("Could not find green handle for Arm 0.")
        return
    if not blue_results:
        print("Could not find blue handle for Arm 1.")
        return

    # Select the highest confidence masks
    green_mask = max(green_results, key=lambda x: x["score"])["mask"]
    blue_mask = max(blue_results, key=lambda x: x["score"])["mask"]

    # 3. Plan grasps for each handle
    print("Planning grasps...")
    
    # Helper to find a sideways grasp
    def find_sideways_grasp(mask, name):
        # Generate grasp candidates in camera frame
        grasps_cam, scores = plan_grasp(depth, intrinsics, mask)
        
        best_grasp_world = None
        best_score = -float('inf')

        for i, grasp_cam in enumerate(grasps_cam):
            # Convert to world frame
            grasp_world = cam_pose @ grasp_cam
            
            # Extract rotation matrix
            R = grasp_world[:3, :3]
            
            # The gripper y-axis is the second column (index 1)
            # We want y-axis aligned with world z-axis (0, 0, 1) or (0, 0, -1)
            y_axis = R[:, 1]
            vertical_alignment = abs(np.dot(y_axis, np.array([0, 0, 1])))
            
            # The gripper z-axis (approach) should be somewhat horizontal for a side grasp
            z_axis = R[:, 2]
            horizontal_approach = abs(np.dot(z_axis, np.array([0, 0, 1]))) < 0.3

            # Check criteria: High vertical alignment of Y-axis, low vertical component of approach
            if vertical_alignment > 0.8 and horizontal_approach:
                if scores[i] > best_score:
                    best_score = scores[i]
                    best_grasp_world = grasp_world
        
        if best_grasp_world is None:
            print(f"No suitable sideways grasp found for {name}. Using best available score regardless of orientation.")
            best_idx = np.argmax(scores)
            best_grasp_world = cam_pose @ grasps_cam[best_idx]

        return best_grasp_world

    grasp_pose_0 = find_sideways_grasp(green_mask, "green handle (Arm 0)")
    grasp_pose_1 = find_sideways_grasp(blue_mask, "blue handle (Arm 1)")

    # 4. Prepare execution poses
    # Extract position and quaternion for both
    pos0, quat0 = decompose_transform(grasp_pose_0)
    pos1, quat1 = decompose_transform(grasp_pose_1)

    # Calculate pre-grasp poses (back off 10cm along the approach vector, which is Z-axis of grasp frame)
    approach_vec0 = grasp_pose_0[:3, 2]
    approach_vec1 = grasp_pose_1[:3, 2]
    
    pre_pos0 = pos0 - approach_vec0 * 0.10
    pre_pos1 = pos1 - approach_vec1 * 0.10

    # Calculate lift poses (move up 20cm in world Z)
    lift_pos0 = pos0 + np.array([0, 0, 0.20])
    lift_pos1 = pos1 + np.array([0, 0, 0.20])

    # 5. Execute Motion
    print("Opening grippers...")
    open_gripper_arm0()
    open_gripper_arm1()

    # Move to pre-grasp
    print("Moving to pre-grasp...")
    q_pre0 = solve_ik_arm0(pre_pos0, quat0)
    q_pre1 = solve_ik_arm1(pre_pos1, quat1)
    move_to_joints_both(q_pre0, q_pre1)

    # Move to grasp
    print("Moving to grasp...")
    q_grasp0 = solve_ik_arm0(pos0, quat0)
    q_grasp1 = solve_ik_arm1(pos1, quat1)
    move_to_joints_both(q_grasp0, q_grasp1)

    # Close grippers
    print("Closing grippers...")
    close_gripper_arm0()
    close_gripper_arm1()

    # Lift
    print("Lifting pot...")
    q_lift0 = solve_ik_arm0(lift_pos0, quat0)
    q_lift1 = solve_ik_arm1(lift_pos1, quat1)
    move_to_joints_both(q_lift0, q_lift1)

    print("Task complete.")

solve()

# Code block 1
import numpy as np

def normalize_vector(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm

def solve():
    print("Getting observation...")
    obs = get_observation()
    rgb = obs["robot0_robotview"]["images"]["rgb"]
    depth = obs["robot0_robotview"]["images"]["depth"]
    intrinsics = obs["robot0_robotview"]["intrinsics"]
    cam_pose = obs["robot0_robotview"]["pose_mat"]

    print("Segmenting objects...")
    # Segment handles and pot
    green_res = segment_sam3_text_prompt(rgb, "green handle")
    blue_res = segment_sam3_text_prompt(rgb, "blue handle")
    
    if not green_res:
        print("Green handle not found.")
        return
    if not blue_res:
        print("Blue handle not found.")
        return
    
    green_mask = max(green_res, key=lambda x: x["score"])["mask"]
    blue_mask = max(blue_res, key=lambda x: x["score"])["mask"]
    
    # Get point clouds for handles
    pts_green = mask_to_world_points(green_mask, depth, intrinsics, cam_pose)
    pts_blue = mask_to_world_points(blue_mask, depth, intrinsics, cam_pose)
    
    if len(pts_green) == 0 or len(pts_blue) == 0:
        print("Point clouds for handles are empty.")
        return

    # Calculate centroids
    center_green = np.mean(pts_green, axis=0)
    center_blue = np.mean(pts_blue, axis=0)
    
    # Estimate pot center as midpoint between handles (robust to pot occlusion)
    center_pot = (center_green + center_blue) / 2.0
    
    print(f"Green Handle Center: {center_green}")
    print(f"Blue Handle Center: {center_blue}")
    print(f"Estimated Pot Center: {center_pot}")

    # Define Grasp Orientation
    # Strategy: Side grasp. 
    # Gripper Z (approach) points from handle towards pot center (horizontally).
    # Gripper Y (fingers) aligned with World Z.
    
    def get_grasp_pose(handle_center, target_center):
        # Vector from handle to center
        approach_vec = target_center - handle_center
        approach_vec[2] = 0  # Force horizontal approach
        
        z_axis = normalize_vector(approach_vec) # Approach
        y_axis = np.array([0, 0, 1])            # Finger axis (World Z)
        x_axis = np.cross(y_axis, z_axis)       # Right
        
        # Re-orthogonalize Y
        y_axis = np.cross(z_axis, x_axis)
        
        R = np.column_stack((x_axis, y_axis, z_axis))
        quat = rotation_matrix_to_quaternion(R)
        return handle_center, quat, z_axis

    pos0, quat0, approach0 = get_grasp_pose(center_green, center_pot)
    pos1, quat1, approach1 = get_grasp_pose(center_blue, center_pot)

    # Offsets
    # Pre-grasp: back off 15cm
    pre_pos0 = pos0 - approach0 * 0.15
    pre_pos1 = pos1 - approach1 * 0.15
    
    # Grasp position adjustment? 
    # The centroid is on the surface. We might want to penetrate slightly?
    # Or rely on the gripper fingers closing. 
    # Let's add a tiny forward push (2cm) to ensure contact, assuming centroid is surface.
    grasp_pos0 = pos0 + approach0 * 0.02
    grasp_pos1 = pos1 + approach1 * 0.02

    # Lift
    lift_height = 0.20
    lift_pos0 = grasp_pos0 + np.array([0, 0, lift_height])
    lift_pos1 = grasp_pos1 + np.array([0, 0, lift_height])

    # Execute
    print("Opening grippers...")
    open_gripper_arm0()
    open_gripper_arm1()
    
    print("Moving to pre-grasp...")
    q_pre0 = solve_ik_arm0(pre_pos0, quat0)
    q_pre1 = solve_ik_arm1(pre_pos1, quat1)
    move_to_joints_both(q_pre0, q_pre1)
    
    print("Moving to grasp...")
    q_grasp0 = solve_ik_arm0(grasp_pos0, quat0)
    q_grasp1 = solve_ik_arm1(grasp_pos1, quat1)
    move_to_joints_both(q_grasp0, q_grasp1)
    
    print("Closing grippers...")
    close_gripper_arm0()
    close_gripper_arm1()
    
    print("Lifting...")
    q_lift0 = solve_ik_arm0(lift_pos0, quat0)
    q_lift1 = solve_ik_arm1(lift_pos1, quat1)
    move_to_joints_both(q_lift0, q_lift1)
    
    print("Done.")

solve()

# Code block 2
import numpy as np

def normalize_vector(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm

def solve():
    print("Getting observation...")
    obs = get_observation()
    rgb = obs["robot0_robotview"]["images"]["rgb"]
    depth = obs["robot0_robotview"]["images"]["depth"]
    intrinsics = obs["robot0_robotview"]["intrinsics"]
    cam_pose = obs["robot0_robotview"]["pose_mat"]

    print("Segmenting objects...")
    # Segment handles and pot
    green_res = segment_sam3_text_prompt(rgb, "green handle")
    blue_res = segment_sam3_text_prompt(rgb, "blue handle")
    
    if not green_res:
        print("Green handle not found.")
        return
    if not blue_res:
        print("Blue handle not found.")
        return
    
    green_mask = max(green_res, key=lambda x: x["score"])["mask"]
    blue_mask = max(blue_res, key=lambda x: x["score"])["mask"]
    
    # Robust point cloud generation manually
    # 1. Convert depth to point cloud in camera frame
    # depth_to_point_cloud returns (H, W, 3)
    pcd_cam = depth_to_point_cloud(depth, intrinsics)
    
    # 2. Flatten for easier processing
    H, W, _ = pcd_cam.shape
    pcd_cam_flat = pcd_cam.reshape(-1, 3)
    
    # 3. Transform to world frame
    # Homogeneous coordinates
    ones = np.ones((pcd_cam_flat.shape[0], 1))
    pcd_cam_homo = np.hstack([pcd_cam_flat, ones])
    pcd_world_homo = (cam_pose @ pcd_cam_homo.T).T
    pcd_world = pcd_world_homo[:, :3]
    
    # 4. Filter by masks
    green_mask_flat = green_mask.flatten() > 0
    blue_mask_flat = blue_mask.flatten() > 0
    
    pts_green = pcd_world[green_mask_flat]
    pts_blue = pcd_world[blue_mask_flat]
    
    # Filter out potential zero points or noise (often depth=0 results in origin)
    # Valid points usually have z > 0 (table height) or near table.
    # Assuming table is at z=0, valid points are z >= 0.
    pts_green = pts_green[pts_green[:, 2] > 0.01]
    pts_blue = pts_blue[pts_blue[:, 2] > 0.01]

    if len(pts_green) == 0 or len(pts_blue) == 0:
        print("Point clouds for handles are empty after filtering.")
        return

    # Calculate centroids
    center_green = np.mean(pts_green, axis=0)
    center_blue = np.mean(pts_blue, axis=0)
    
    # Estimate pot center as midpoint between handles
    center_pot = (center_green + center_blue) / 2.0
    
    print(f"Green Handle Center: {center_green}")
    print(f"Blue Handle Center: {center_blue}")
    print(f"Estimated Pot Center: {center_pot}")

    # Define Grasp Orientation
    # Strategy: Side grasp. 
    # Gripper Z (approach) points from handle towards pot center (horizontally).
    # Gripper Y (fingers) aligned with World Z.
    
    def get_grasp_pose(handle_center, target_center):
        # Vector from handle to center
        approach_vec = target_center - handle_center
        approach_vec[2] = 0  # Force horizontal approach
        
        z_axis = normalize_vector(approach_vec) # Approach
        y_axis = np.array([0, 0, 1])            # Finger axis (World Z)
        x_axis = np.cross(y_axis, z_axis)       # Right
        
        # Re-orthogonalize Y
        y_axis = np.cross(z_axis, x_axis)
        
        R = np.column_stack((x_axis, y_axis, z_axis))
        quat = rotation_matrix_to_quaternion(R)
        return handle_center, quat, z_axis

    pos0, quat0, approach0 = get_grasp_pose(center_green, center_pot)
    pos1, quat1, approach1 = get_grasp_pose(center_blue, center_pot)

    # Offsets
    # Pre-grasp: back off 15cm
    pre_pos0 = pos0 - approach0 * 0.15
    pre_pos1 = pos1 - approach1 * 0.15
    
    # Grasp position adjustment
    # Add a tiny forward push (2cm) to ensure contact inside the handle loop or against it
    grasp_pos0 = pos0 + approach0 * 0.02
    grasp_pos1 = pos1 + approach1 * 0.02

    # Lift
    lift_height = 0.20
    lift_pos0 = grasp_pos0 + np.array([0, 0, lift_height])
    lift_pos1 = grasp_pos1 + np.array([0, 0, lift_height])

    # Execute
    print("Opening grippers...")
    open_gripper_arm0()
    open_gripper_arm1()
    
    # Move arms to a safe intermediate high position first to avoid collision
    # safe_pos0 = pre_pos0 + np.array([0, 0, 0.2])
    # safe_pos1 = pre_pos1 + np.array([0, 0, 0.2])
    # q_safe0 = solve_ik_arm0(safe_pos0, quat0)
    # q_safe1 = solve_ik_arm1(safe_pos1, quat1)
    # move_to_joints_both(q_safe0, q_safe1)

    print("Moving to pre-grasp...")
    q_pre0 = solve_ik_arm0(pre_pos0, quat0)
    q_pre1 = solve_ik_arm1(pre_pos1, quat1)
    move_to_joints_both(q_pre0, q_pre1)
    
    print("Moving to grasp...")
    q_grasp0 = solve_ik_arm0(grasp_pos0, quat0)
    q_grasp1 = solve_ik_arm1(grasp_pos1, quat1)
    move_to_joints_both(q_grasp0, q_grasp1)
    
    print("Closing grippers...")
    close_gripper_arm0()
    close_gripper_arm1()
    
    print("Lifting...")
    q_lift0 = solve_ik_arm0(lift_pos0, quat0)
    q_lift1 = solve_ik_arm1(lift_pos1, quat1)
    move_to_joints_both(q_lift0, q_lift1)
    
    print("Done.")

solve()