# Code block 0
import numpy as np

def get_best_mask(masks):
    if not masks:
        return None
    return max(masks, key=lambda x: x["score"])

def get_object_metrics(mask, depth, intrinsics, extrinsics):
    """Returns center (x,y,z), top_z, bottom_z for a given object mask."""
    points = mask_to_world_points(mask, depth, intrinsics, extrinsics)
    if points.shape[0] == 0:
        return None, None, None
    
    # Get Oriented Bounding Box
    bbox = get_oriented_bounding_box_from_3d_points(points)
    center = bbox["center"]
    
    # Calculate robust top and bottom Z from points
    zs = points[:, 2]
    top_z = np.percentile(zs, 98) # Use 98th percentile to filter outliers
    bottom_z = np.percentile(zs, 2) # Use 2nd percentile
    
    return center, top_z, bottom_z

def execute_pose_move(pose_matrix):
    """Moves robot to the specified 4x4 pose matrix."""
    pos, quat = decompose_transform(pose_matrix)
    joints = solve_ik(pos, quat)
    move_to_joints(joints)

def pick_and_place(obj_mask, target_center, target_top_z, depth, intrinsics, cam_pose):
    """
    Picks object defined by obj_mask and places it on target defined by target_center and target_top_z.
    """
    # 1. Analyze Object to be picked
    obj_center, obj_top, obj_bottom = get_object_metrics(obj_mask, depth, intrinsics, cam_pose)
    if obj_center is None:
        return

    # 2. Plan Grasp
    seg_map = obj_mask.astype(np.int32)
    # Note: plan_grasp returns poses in Camera Frame
    grasp_poses_cam, grasp_scores = plan_grasp(depth, intrinsics, seg_map)
    
    # Transform to World Frame
    grasps_world = []
    for g in grasp_poses_cam:
        grasps_world.append(transform_points(g, cam_pose) if g.shape == (3,) else cam_pose @ g) # Handle 4x4 matmul
    grasps_world = np.array(grasps_world)

    # Select best top-down grasp
    best_grasp, _ = select_top_down_grasp(grasps_world, grasp_scores, cam_pose)
    
    if best_grasp is None:
        print("No valid grasp found.")
        return

    # Calculate offset from TCP to bottom of object
    # TCP Z at grasp - Object Bottom Z
    grasp_z = best_grasp[2, 3]
    tcp_to_bottom_offset = grasp_z - obj_bottom

    # 3. Execute Pick
    # Move to Pre-Grasp (Safety Hover)
    pre_grasp = best_grasp.copy()
    pre_grasp[2, 3] += 0.15
    execute_pose_move(pre_grasp)

    # Move to Grasp
    execute_pose_move(best_grasp)
    close_gripper()

    # Lift Up
    lift_pose = best_grasp.copy()
    lift_pose[2, 3] += 0.25
    execute_pose_move(lift_pose)

    # 4. Execute Place
    # Calculate Place Pose
    place_pose = best_grasp.copy()
    place_pose[0, 3] = target_center[0]
    place_pose[1, 3] = target_center[1]
    # Target Z for TCP = Target Surface Z + Offset + Padding
    place_pose[2, 3] = target_top_z + tcp_to_bottom_offset + 0.015 

    # Move to Pre-Place (Safety Hover)
    pre_place = place_pose.copy()
    pre_place[2, 3] += 0.15
    execute_pose_move(pre_place)

    # Move to Place
    execute_pose_move(place_pose)
    open_gripper()

    # Move to Post-Place (Lift Up)
    execute_pose_move(pre_place)


# --- Main Execution ---

# 1. Reset
open_gripper()

# 2. Perception & Strategy: Stack Blue Cube on Yellow Cube
obs = get_observation()
rgb = obs["robot0_robotview"]["images"]["rgb"]
depth = obs["robot0_robotview"]["images"]["depth"]
intrinsics = obs["robot0_robotview"]["intrinsics"]
cam_pose = obs["robot0_robotview"]["pose_mat"]

# Find Yellow Cube (Base)
masks_yellow = segment_sam3_text_prompt(rgb, "yellow cube")
yellow_data = get_best_mask(masks_yellow)
yellow_center, yellow_top, _ = get_object_metrics(yellow_data["mask"], depth, intrinsics, cam_pose)

# Find Blue Cube (Object 1)
masks_blue = segment_sam3_text_prompt(rgb, "blue cube")
blue_data = get_best_mask(masks_blue)

if yellow_center is not None and blue_data is not None:
    # Execute Step 1: Blue -> Yellow
    pick_and_place(blue_data["mask"], yellow_center, yellow_top, depth, intrinsics, cam_pose)


# 3. Perception & Strategy: Stack Ball on Blue Cube
# Re-observe because the blue cube has moved
obs = get_observation()
rgb = obs["robot0_robotview"]["images"]["rgb"]
depth = obs["robot0_robotview"]["images"]["depth"]
intrinsics = obs["robot0_robotview"]["intrinsics"]
cam_pose = obs["robot0_robotview"]["pose_mat"]

# Find Blue Cube again (New Base)
masks_blue_new = segment_sam3_text_prompt(rgb, "blue cube")
blue_data_new = get_best_mask(masks_blue_new)
blue_center_new, blue_top_new, _ = get_object_metrics(blue_data_new["mask"], depth, intrinsics, cam_pose)

# Find Tennis Ball (Object 2)
masks_ball = segment_sam3_text_prompt(rgb, "yellow tennis ball")
ball_data = get_best_mask(masks_ball)

if blue_center_new is not None and ball_data is not None:
    # Execute Step 2: Ball -> Blue
    pick_and_place(ball_data["mask"], blue_center_new, blue_top_new, depth, intrinsics, cam_pose)

# Code block 1
import numpy as np

def get_best_mask(masks):
    if not masks:
        return None
    return max(masks, key=lambda x: x["score"])

def get_object_metrics(mask, depth, intrinsics, extrinsics):
    """Returns center (x,y,z), top_z, bottom_z for a given object mask."""
    points = mask_to_world_points(mask, depth, intrinsics, extrinsics)
    if points.shape[0] == 0:
        return None, None, None
    
    # Get Oriented Bounding Box
    bbox = get_oriented_bounding_box_from_3d_points(points)
    center = bbox["center"]
    
    # Calculate robust top and bottom Z from points
    zs = points[:, 2]
    if len(zs) == 0:
        return None, None, None
        
    top_z = np.percentile(zs, 98) # Use 98th percentile to filter outliers
    bottom_z = np.percentile(zs, 2) # Use 2nd percentile
    
    return center, top_z, bottom_z

def execute_pose_move(pose_matrix):
    """Moves robot to the specified 4x4 pose matrix."""
    pos, quat = decompose_transform(pose_matrix)
    joints = solve_ik(pos, quat)
    move_to_joints(joints)

def pick_and_place(obj_mask, target_center, target_top_z, depth, intrinsics, cam_pose):
    """
    Picks object defined by obj_mask and places it on target defined by target_center and target_top_z.
    """
    # 1. Analyze Object to be picked
    obj_center, obj_top, obj_bottom = get_object_metrics(obj_mask, depth, intrinsics, cam_pose)
    if obj_center is None:
        print("Could not calculate object metrics.")
        return

    # 2. Plan Grasp
    seg_map = obj_mask.astype(np.int32)
    # plan_grasp returns poses in CAMERA FRAME
    grasp_poses_cam, grasp_scores = plan_grasp(depth, intrinsics, seg_map)
    
    if len(grasp_poses_cam) == 0:
        print("No grasps generated by planner.")
        return

    # Select best top-down grasp. 
    # select_top_down_grasp takes grasps in CAMERA FRAME and returns the best in WORLD FRAME.
    best_grasp_world, best_score = select_top_down_grasp(grasp_poses_cam, grasp_scores, cam_pose, vertical_threshold=0.8)
    
    if best_grasp_world is None:
        print("No strictly vertical grasp found. Trying relaxed threshold.")
        best_grasp_world, best_score = select_top_down_grasp(grasp_poses_cam, grasp_scores, cam_pose, vertical_threshold=0.5)

    if best_grasp_world is None:
        print("No valid grasp found even with relaxed threshold.")
        return

    print(f"Executing grasp with score {best_score}")

    # Calculate offset from TCP to bottom of object
    # TCP Z at grasp - Object Bottom Z
    grasp_z = best_grasp_world[2, 3]
    tcp_to_bottom_offset = grasp_z - obj_bottom

    # 3. Execute Pick
    # Move to Pre-Grasp (Safety Hover)
    pre_grasp = best_grasp_world.copy()
    pre_grasp[2, 3] += 0.10
    execute_pose_move(pre_grasp)

    # Move to Grasp
    execute_pose_move(best_grasp_world)
    close_gripper()

    # Lift Up
    lift_pose = best_grasp_world.copy()
    lift_pose[2, 3] += 0.20
    execute_pose_move(lift_pose)

    # 4. Execute Place
    # Calculate Place Pose
    place_pose = best_grasp_world.copy()
    place_pose[0, 3] = target_center[0]
    place_pose[1, 3] = target_center[1]
    # Target Z for TCP = Target Surface Z + Offset + Padding
    # Adding a small padding (1cm) to ensure we don't collide hard, 
    # but close enough to drop safely.
    place_pose[2, 3] = target_top_z + tcp_to_bottom_offset + 0.015 

    # Move to Pre-Place (Safety Hover)
    pre_place = place_pose.copy()
    pre_place[2, 3] += 0.15
    execute_pose_move(pre_place)

    # Move to Place
    execute_pose_move(place_pose)
    open_gripper()

    # Move to Post-Place (Lift Up)
    execute_pose_move(pre_place)


# --- Main Execution ---

# 1. Reset
open_gripper()

# 2. Perception & Strategy: Stack Blue Cube on Yellow Cube
obs = get_observation()
rgb = obs["robot0_robotview"]["images"]["rgb"]
depth = obs["robot0_robotview"]["images"]["depth"]
intrinsics = obs["robot0_robotview"]["intrinsics"]
cam_pose = obs["robot0_robotview"]["pose_mat"]

# Find Yellow Cube (Base)
masks_yellow = segment_sam3_text_prompt(rgb, "yellow cube")
yellow_data = get_best_mask(masks_yellow)

# Find Blue Cube (Object 1)
masks_blue = segment_sam3_text_prompt(rgb, "blue cube")
blue_data = get_best_mask(masks_blue)

if yellow_data is not None and blue_data is not None:
    # Get base metrics
    yellow_center, yellow_top, _ = get_object_metrics(yellow_data["mask"], depth, intrinsics, cam_pose)
    
    if yellow_center is not None:
        print("Stacking Blue Cube on Yellow Cube...")
        pick_and_place(blue_data["mask"], yellow_center, yellow_top, depth, intrinsics, cam_pose)
    else:
        print("Could not compute metrics for Yellow Cube")
else:
    print("Could not find Blue or Yellow cube")


# 3. Perception & Strategy: Stack Ball on Blue Cube
# Re-observe because the blue cube has moved
obs = get_observation()
rgb = obs["robot0_robotview"]["images"]["rgb"]
depth = obs["robot0_robotview"]["images"]["depth"]
intrinsics = obs["robot0_robotview"]["intrinsics"]
cam_pose = obs["robot0_robotview"]["pose_mat"]

# Find Blue Cube again (New Base)
masks_blue_new = segment_sam3_text_prompt(rgb, "blue cube")
blue_data_new = get_best_mask(masks_blue_new)

# Find Tennis Ball (Object 2)
masks_ball = segment_sam3_text_prompt(rgb, "yellow tennis ball")
ball_data = get_best_mask(masks_ball)

if blue_data_new is not None and ball_data is not None:
    # Get base metrics (blue cube is now the base)
    blue_center_new, blue_top_new, _ = get_object_metrics(blue_data_new["mask"], depth, intrinsics, cam_pose)
    
    if blue_center_new is not None:
        print("Stacking Tennis Ball on Blue Cube...")
        pick_and_place(ball_data["mask"], blue_center_new, blue_top_new, depth, intrinsics, cam_pose)
    else:
        print("Could not compute metrics for Blue Cube (new base)")
else:
    print("Could not find Blue Cube or Tennis Ball for second stack")