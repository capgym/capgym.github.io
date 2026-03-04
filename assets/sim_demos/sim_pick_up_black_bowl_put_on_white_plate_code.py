# Code block 0
import numpy as np

# 1. Get Observation
obs = get_observation()
agentview = obs["agentview"]
rgb = agentview["images"]["rgb"]
depth = agentview["images"]["depth"]
intrinsics = agentview["intrinsics"]
extrinsics = agentview["pose_mat"]

# 2. Identify the Target Bowl ("akita black bowl between the plate and the ramekin")
# Since there are multiple bowls, we use a specific descriptive prompt for Molmo or SAM3.
# Molmo is good at spatial reasoning from text.
bowl_point_query = point_prompt_molmo(rgb, "akita black bowl between the plate and the ramekin")
bowl_point = bowl_point_query.get("akita black bowl between the plate and the ramekin")

if bowl_point is None or bowl_point[0] is None:
    # Fallback: try identifying all bowls and the plate/ramekin to do geometric filtering,
    # but let's try a simpler specific segmentation prompt first if Molmo fails.
    # We will assume Molmo works for this reasoning task as it is designed for it.
    print("Molmo failed to find the specific bowl. Trying SAM3 with broader prompt.")
    # This path is a backup and might require more logic, but for this script we assume success or restart.
    exit(1)

# Segment the bowl using the point prompt from Molmo to get a precise mask
bowl_sam_results = segment_sam3_point_prompt(rgb, point_coords=bowl_point)
# Select the result with the highest score
best_bowl_result = max(bowl_sam_results, key=lambda x: x["score"])
bowl_mask = best_bowl_result["mask"]

# 3. Identify the Destination Plate
plate_sam_results = segment_sam3_text_prompt(rgb, "white plate with red rings")
if not plate_sam_results:
    print("Could not find the plate.")
    exit(1)
best_plate_result = max(plate_sam_results, key=lambda x: x["score"])
plate_mask = best_plate_result["mask"]

# 4. Plan Grasp for the Bowl
grasp_poses_cam, grasp_scores = plan_grasp(depth, intrinsics, bowl_mask)

if len(grasp_scores) == 0:
    print("No valid grasps found.")
    exit(1)

# Select the best top-down grasp to avoid collisions and weird angles
grasp_world_matrix, grasp_score = select_top_down_grasp(
    grasp_poses_cam, grasp_scores, extrinsics, vertical_threshold=0.8
)

if grasp_world_matrix is None:
    # If no strict top-down grasp, pick the highest scoring one and transform it
    best_idx = np.argmax(grasp_scores)
    best_pose_cam = grasp_poses_cam[best_idx]
    grasp_world_matrix = extrinsics @ best_pose_cam

# Decompose grasp pose
grasp_pos, grasp_quat = decompose_transform(grasp_world_matrix)

# 5. Determine Placement Position
# We want to place it on the plate. Let's find the center of the plate in world coordinates.
plate_world_points = mask_to_world_points(plate_mask, depth, intrinsics, extrinsics)
if len(plate_world_points) == 0:
    print("No valid depth for plate.")
    exit(1)
    
# Get center of the plate points
# We can use an oriented bounding box or just the mean. The mean is safer for a flat object like a plate.
plate_center = np.mean(plate_world_points, axis=0)
place_pos = plate_center.copy()
place_pos[2] += 0.05  # Place slightly above the plate surface to avoid smashing

# 6. Execute Pick
# Pre-grasp position (10cm above grasp)
pre_grasp_pos = grasp_pos.copy()
pre_grasp_pos[2] += 0.10

# Move to pre-grasp
joints_pre = solve_ik(pre_grasp_pos, grasp_quat)
move_to_joints(joints_pre)

# Move to grasp
open_gripper()
joints_grasp = solve_ik(grasp_pos, grasp_quat)
move_to_joints(joints_grasp)
close_gripper()

# Lift up
move_to_joints(joints_pre)

# 7. Execute Place
# Pre-place position (above the plate center)
pre_place_pos = place_pos.copy()
pre_place_pos[2] += 0.15 

# We can keep the same orientation as the grasp, or force a top-down orientation.
# Keeping grasp orientation is usually safer unless the object needs reorienting.
place_quat = grasp_quat 

joints_pre_place = solve_ik(pre_place_pos, place_quat)
move_to_joints(joints_pre_place)

# Move down to place
joints_place = solve_ik(place_pos, place_quat)
move_to_joints(joints_place)

# Release
open_gripper()

# Move back up
move_to_joints(joints_pre_place)