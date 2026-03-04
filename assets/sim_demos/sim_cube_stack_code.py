# Code block 0
import numpy as np

def main():
    # 1. Get Initial Observation
    obs = get_observation()
    robot_view = obs["robot0_robotview"]
    rgb = robot_view["images"]["rgb"]
    depth = robot_view["images"]["depth"]
    intrinsics = robot_view["intrinsics"]
    extrinsics = robot_view["pose_mat"]

    # 2. Segment the Objects (Red Cube and Green Cube)
    # We use SAM3 with text prompts to find both objects.
    red_cube_results = segment_sam3_text_prompt(rgb, "red cube")
    green_cube_results = segment_sam3_text_prompt(rgb, "green cube")

    if not red_cube_results:
        print("Could not find red cube.")
        return
    if not green_cube_results:
        print("Could not find green cube.")
        return

    # Select the highest confidence result for each
    red_cube_mask = max(red_cube_results, key=lambda x: x["score"])["mask"]
    green_cube_mask = max(green_cube_results, key=lambda x: x["score"])["mask"]

    # 3. Plan Grasp for the Red Cube
    # We use plan_grasp to get candidate poses in camera frame.
    # Note: depth may need squeezing if shape is (H, W, 1)
    depth_squeeze = depth if depth.ndim == 2 else depth[:, :, 0]
    
    grasp_poses_cam, grasp_scores = plan_grasp(
        depth=depth_squeeze,
        intrinsics=intrinsics,
        segmentation=red_cube_mask
    )

    if len(grasp_poses_cam) == 0:
        print("No valid grasps found for red cube.")
        return

    # Filter for a top-down grasp to ensure stability
    best_grasp_world, best_score = select_top_down_grasp(
        grasps=grasp_poses_cam,
        scores=grasp_scores,
        cam_to_world=extrinsics,
        vertical_threshold=0.8
    )

    # If top-down fails, fall back to the highest scoring grasp regardless of orientation
    if best_grasp_world is None:
        best_idx = np.argmax(grasp_scores)
        best_pose_cam = grasp_poses_cam[best_idx]
        best_grasp_world = extrinsics @ best_pose_cam

    # 4. Execute Pick
    # Extract position and orientation for the grasp
    grasp_pos, grasp_quat = decompose_transform(best_grasp_world)

    # Define a pre-grasp position (e.g., 10cm above the object)
    pre_grasp_pos = grasp_pos.copy()
    pre_grasp_pos[2] += 0.10

    # Move to Pre-grasp
    joints_pre = solve_ik(pre_grasp_pos, grasp_quat)
    move_to_joints(joints_pre)

    # Open gripper to ensure we can accept the object
    open_gripper()

    # Move to Grasp
    joints_grasp = solve_ik(grasp_pos, grasp_quat)
    move_to_joints(joints_grasp)

    # Close gripper
    close_gripper()

    # Lift up (Post-grasp)
    move_to_joints(joints_pre)

    # 5. Determine Place Position (On top of Green Cube)
    # Convert green cube mask to 3D points in world frame
    green_points = mask_to_world_points(green_cube_mask, depth_squeeze, intrinsics, extrinsics)
    
    if green_points.shape[0] == 0:
        print("No depth data available for green cube.")
        return

    # Get oriented bounding box of the green cube to find its top center
    green_bbox = get_oriented_bounding_box_from_3d_points(green_points)
    green_center = green_bbox["center"]
    green_extent = green_bbox["extent"]
    
    # We want to place on top. We assume the 'extent' roughly aligns with axes or we just add height.
    # A safe heuristic is to take the highest Z point in the cloud or center + half height.
    # Let's use the max Z of the points to find the top surface, then center X, Y.
    # However, bbox center + Z offset is usually cleaner if extent is reliable.
    # Let's assume the Z-axis of the bbox extent corresponds to height or just use the world Z.
    # We will simply add a safe offset to the center. Since these are cubes, usually around 5-7cm tall.
    # Let's target slightly above the center Z.
    
    target_place_pos = green_center.copy()
    # The green cube is on the table. The center is roughly at half-height. 
    # We want to stack the red cube (held) on top. 
    # Target Z should be: Green_Center_Z + Green_Half_Height + Red_Half_Height + Buffer.
    # Approximating roughly:
    target_place_pos[2] = np.max(green_points[:, 2]) + 0.05 # Place 5cm above the highest point of green cube

    # Keep the same orientation as the grasp (holding the cube flat)
    place_quat = grasp_quat

    # Define Pre-place position (higher up)
    pre_place_pos = target_place_pos.copy()
    pre_place_pos[2] += 0.10

    # 6. Execute Place
    # Move to Pre-place
    joints_pre_place = solve_ik(pre_place_pos, place_quat)
    move_to_joints(joints_pre_place)

    # Move to Place
    joints_place = solve_ik(target_place_pos, place_quat)
    move_to_joints(joints_place)

    # Open gripper to release
    open_gripper()

    # Move back up (Post-place)
    move_to_joints(joints_pre_place)

if __name__ == "__main__":
    main()

# Code block 1
import numpy as np

def main():
    # 1. Get Observation
    obs = get_observation()
    robot_view = obs["robot0_robotview"]
    rgb = robot_view["images"]["rgb"]
    depth = robot_view["images"]["depth"]
    intrinsics = robot_view["intrinsics"]
    extrinsics = robot_view["pose_mat"]

    # 2. Locate Objects
    # We need to find the red cube to pick and the green cube to place on.
    red_cube_data = segment_sam3_text_prompt(rgb, "red cube")
    green_cube_data = segment_sam3_text_prompt(rgb, "green cube")

    if not red_cube_data:
        print("No red cube found.")
        return
    if not green_cube_data:
        print("No green cube found.")
        return

    # Take the most confident detection
    red_mask = max(red_cube_data, key=lambda x: x["score"])["mask"]
    green_mask = max(green_cube_data, key=lambda x: x["score"])["mask"]

    # 3. Plan Grasp for Red Cube
    # Ensure depth is (H, W)
    depth_squeeze = depth if depth.ndim == 2 else depth[:, :, 0]
    
    grasp_poses_cam, grasp_scores = plan_grasp(
        depth=depth_squeeze,
        intrinsics=intrinsics,
        segmentation=red_mask
    )

    if len(grasp_poses_cam) == 0:
        print("No grasps found.")
        return

    # Select best top-down grasp
    best_grasp_world, best_score = select_top_down_grasp(
        grasps=grasp_poses_cam,
        scores=grasp_scores,
        cam_to_world=extrinsics,
        vertical_threshold=0.9  # stricter threshold for better alignment
    )

    # Fallback to any grasp if top-down fails
    if best_grasp_world is None:
        best_idx = np.argmax(grasp_scores)
        best_grasp_world = extrinsics @ grasp_poses_cam[best_idx]

    # 4. Execute Pick
    pick_pos, pick_quat = decompose_transform(best_grasp_world)
    
    # Heuristic: Sometimes grasp poses are right on the surface. 
    # Let's trust the planner but ensure our pre-grasp is well aligned.
    
    # Pre-grasp: 10cm above
    pre_pick_pos = pick_pos.copy()
    pre_pick_pos[2] += 0.10

    # Move to Pre-pick
    move_to_joints(solve_ik(pre_pick_pos, pick_quat))
    
    # Ensure gripper is open
    open_gripper()
    
    # Move to Pick
    move_to_joints(solve_ik(pick_pos, pick_quat))
    
    # Close Gripper
    close_gripper()
    
    # Lift (Post-pick)
    # Go high enough to clear other objects
    lift_pos = pick_pos.copy()
    lift_pos[2] += 0.15 
    move_to_joints(solve_ik(lift_pos, pick_quat))

    # 5. Determine Place Location
    # We need the world coordinates of the green cube.
    # Note: If the green cube was occluded during the pick, we rely on the initial mask/depth.
    # We use the initial observation data which is still valid for the static green cube.
    green_pts = mask_to_world_points(green_mask, depth_squeeze, intrinsics, extrinsics)
    
    if len(green_pts) == 0:
        print("No 3D points for green cube.")
        return

    # Get bounding box to find the top
    green_bbox = get_oriented_bounding_box_from_3d_points(green_pts)
    green_center = green_bbox["center"]
    
    # Calculate target place position
    # We want to place on the top surface.
    # Using the max Z of the points is a robust heuristic for "top".
    max_z = np.max(green_pts[:, 2])
    
    target_place_pos = green_center.copy()
    target_place_pos[2] = max_z + 0.05  # Place 5cm above the top surface to account for red cube height/padding
    
    # Pre-place position
    pre_place_pos = target_place_pos.copy()
    pre_place_pos[2] += 0.10

    # 6. Execute Place
    # Move to Pre-place
    move_to_joints(solve_ik(pre_place_pos, pick_quat))
    
    # Move to Place
    move_to_joints(solve_ik(target_place_pos, pick_quat))
    
    # Open Gripper
    open_gripper()
    
    # Lift (Post-place)
    move_to_joints(solve_ik(pre_place_pos, pick_quat))

if __name__ == "__main__":
    main()