# Code block 0
import numpy as np

# 1. Get the current observation
obs = get_observation()
rgb = obs["robot0_robotview"]["images"]["rgb"]
depth = obs["robot0_robotview"]["images"]["depth"]
intrinsics = obs["robot0_robotview"]["intrinsics"]
extrinsics = obs["robot0_robotview"]["pose_mat"]

# 2. Segment the "brown spill" to find its location
# Using SAM3 to find the mask of the spill.
sam_results = segment_sam3_text_prompt(rgb, "brown spill")

if not sam_results:
    print("Could not find 'brown spill' in the image.")
else:
    # Select the result with the highest score
    best_result = max(sam_results, key=lambda x: x["score"])
    mask = best_result["mask"]

    # 3. Convert mask pixels to 3D world points
    # We use the depth map and camera parameters to project the mask into 3D space.
    # Note: Depth images are (H, W, 1), mask is (H, W).
    if depth.ndim == 3:
        depth = depth.squeeze(-1)
        
    spill_points = mask_to_world_points(mask, depth, intrinsics, extrinsics)

    if spill_points.shape[0] == 0:
        print("No valid depth points found for the spill mask.")
    else:
        # 4. Determine the bounding box of the spill in world coordinates
        # We only care about x and y for the bounds, since z is fixed to 0.0 per instructions.
        min_x = np.min(spill_points[:, 0])
        max_x = np.max(spill_points[:, 0])
        min_y = np.min(spill_points[:, 1])
        max_y = np.max(spill_points[:, 1])
        
        print(f"Spill bounds: X[{min_x:.3f}, {max_x:.3f}], Y[{min_y:.3f}, {max_y:.3f}]")

        # 5. Plan the wiping trajectory
        # We will create a zig-zag pattern or a simple sweep. 
        # Given the instruction to avoid large motions and the irregular shape, 
        # a simple raster scan over the bounding box at z=0.0 is a robust approach.
        
        # Define safety height and wipe height
        z_wipe = 0.0
        z_safe = 0.15
        
        # Fixed orientation: downward facing (0,0,1,0 wxyz)
        # Note: The API doc says (0,0,1,0 wxyz), but typically downward for Franka 
        # is often a rotation of 180 deg around X or Y from base. 
        # However, we must follow the specific instruction: "use a downward-facing orientation (0,0,1,0 wxyz)"
        wipe_quat = np.array([0.0, 1.0, 0.0, 0.0]) # w, x, y, z. Wait, prompt said 0,0,1,0 wxyz.
        # Let's strictly follow the prompt's explicit value.
        wipe_quat = np.array([0.0, 0.0, 1.0, 0.0]) 

        # Create waypoints
        # We'll do a simple scan along Y, moving in X steps.
        # Padding the bounds slightly to ensure coverage
        padding = 0.02
        start_x = min_x - padding
        end_x = max_x + padding
        start_y = min_y - padding
        end_y = max_y + padding
        
        # Step size for the raster
        step_x = 0.05 
        
        waypoints = []
        
        # 1. Move to safe height above start
        waypoints.append(np.array([start_x, start_y, z_safe]))
        
        # 2. Move down to start wiping
        waypoints.append(np.array([start_x, start_y, z_wipe]))
        
        # 3. Raster pattern
        current_x = start_x
        direction = 1 # 1 for increasing Y, -1 for decreasing Y
        
        while current_x <= end_x:
            # Current strip Y bounds
            y_target = end_y if direction == 1 else start_y
            
            # Wipe along Y
            waypoints.append(np.array([current_x, y_target, z_wipe]))
            
            # Move slightly in X for next strip
            next_x = min(current_x + step_x, end_x)
            if next_x != current_x:
                waypoints.append(np.array([next_x, y_target, z_wipe]))
            
            current_x = next_x
            direction *= -1
            
            # Break if we've reached the end X and finished the Y stroke
            if current_x >= end_x:
                # One final stroke to ensure we cover the edge
                y_final = end_y if direction == 1 else start_y
                waypoints.append(np.array([current_x, y_final, z_wipe]))
                break

        # 4. Lift up
        waypoints.append(np.array([waypoints[-1][0], waypoints[-1][1], z_safe]))

        # 6. Execute the trajectory
        print(f"Executing wiping motion with {len(waypoints)} waypoints...")
        
        for i, wp in enumerate(waypoints):
            # Interpolate between waypoints for smoother motion if distance is large?
            # The instruction says "Avoid large wiping motions".
            # The raster scan has relatively small steps.
            # We'll rely on the movement function. 
            
            # Solve IK
            joints = solve_ik(wp, wipe_quat)
            
            # Move
            move_to_joints(joints)
            
        print("Wiping complete.")

# Code block 1
import numpy as np

# 1. Get the current observation to see remaining spills
obs = get_observation()
rgb = obs["robot0_robotview"]["images"]["rgb"]
depth = obs["robot0_robotview"]["images"]["depth"]
intrinsics = obs["robot0_robotview"]["intrinsics"]
extrinsics = obs["robot0_robotview"]["pose_mat"]

# 2. Segment the "brown spill" again
# The spill is reported to be fragmented, so we should look for multiple instances
sam_results = segment_sam3_text_prompt(rgb, "brown spill")

if not sam_results:
    print("No 'brown spill' detected.")
else:
    # 3. Combine masks to cover all fragmented patches
    # We iterate through results and combine masks that have a sufficiently high confidence score.
    combined_mask = np.zeros(rgb.shape[:2], dtype=bool)
    
    # Filter by score to avoid noise, assuming the top score is a good reference
    best_score = max(r["score"] for r in sam_results)
    score_threshold = max(0.2, best_score * 0.5)
    
    count = 0
    for res in sam_results:
        if res["score"] >= score_threshold:
            combined_mask = np.logical_or(combined_mask, res["mask"])
            count += 1
    
    print(f"Combined {count} mask instances for the spill.")

    # 4. Convert mask pixels to 3D world points
    if depth.ndim == 3:
        depth = depth.squeeze(-1)
        
    spill_points = mask_to_world_points(combined_mask, depth, intrinsics, extrinsics)

    if spill_points.shape[0] < 50:
        print("Spill points count is very low; treating as clean.")
    else:
        # 5. Determine the bounding box of the remaining spill parts
        min_x = np.min(spill_points[:, 0])
        max_x = np.max(spill_points[:, 0])
        min_y = np.min(spill_points[:, 1])
        max_y = np.max(spill_points[:, 1])
        
        print(f"Remaining spill bounds: X[{min_x:.3f}, {max_x:.3f}], Y[{min_y:.3f}, {max_y:.3f}]")

        # 6. Plan a denser wiping trajectory
        z_wipe = 0.0
        z_safe = 0.15
        
        # Use the requested downward orientation
        wipe_quat = np.array([0.0, 0.0, 1.0, 0.0]) 

        # Padding
        padding = 0.03
        start_x = min_x - padding
        end_x = max_x + padding
        start_y = min_y - padding
        end_y = max_y + padding
        
        # Finer step size (3cm) for better coverage
        step_x = 0.03 
        
        waypoints = []
        
        # Safe start
        waypoints.append(np.array([start_x, start_y, z_safe]))
        waypoints.append(np.array([start_x, start_y, z_wipe]))
        
        current_x = start_x
        direction = 1 # Toggle between min_y and max_y
        
        # Raster scan
        while current_x <= end_x:
            target_y = end_y if direction == 1 else start_y
            
            # Wipe across Y
            waypoints.append(np.array([current_x, target_y, z_wipe]))
            
            # Step in X
            next_x = min(current_x + step_x, end_x)
            
            if next_x > current_x:
                # Move to next X at current Y
                waypoints.append(np.array([next_x, target_y, z_wipe]))
            
            if current_x >= end_x:
                break
                
            current_x = next_x
            direction *= -1

        # Lift up
        waypoints.append(np.array([waypoints[-1][0], waypoints[-1][1], z_safe]))

        # 7. Execute
        print(f"Executing re-wiping motion with {len(waypoints)} waypoints...")
        for wp in waypoints:
            try:
                joints = solve_ik(wp, wipe_quat)
                move_to_joints(joints)
            except Exception as e:
                print(f"IK failed for waypoint {wp}: {e}")

        print("Re-wiping complete.")

# Code block 2
import numpy as np

# 1. Get the current observation
obs = get_observation()
rgb = obs["robot0_robotview"]["images"]["rgb"]
depth = obs["robot0_robotview"]["images"]["depth"]
intrinsics = obs["robot0_robotview"]["intrinsics"]
extrinsics = obs["robot0_robotview"]["pose_mat"]

# 2. Segment the "brown spill"
sam_results = segment_sam3_text_prompt(rgb, "brown spill")

if not sam_results:
    print("No 'brown spill' detected.")
else:
    # 3. Combine masks more robustly
    combined_mask = np.zeros(rgb.shape[:2], dtype=bool)
    
    # Sort results by score descending
    sorted_results = sorted(sam_results, key=lambda x: x["score"], reverse=True)
    best_score = sorted_results[0]["score"]
    
    # Be more permissive: include anything with > 0.1 score, or at least the top one
    count = 0
    for res in sorted_results:
        if res["score"] > 0.1:
            combined_mask = np.logical_or(combined_mask, res["mask"])
            count += 1
            
    # Fallback: if nothing passed threshold but we have results, take the top one
    if count == 0 and len(sorted_results) > 0:
        print("Scores were low, using top result anyway.")
        combined_mask = sorted_results[0]["mask"]
        count = 1

    print(f"Combined {count} mask instances for the spill.")

    # 4. Convert mask pixels to 3D world points
    if depth.ndim == 3:
        depth = depth.squeeze(-1)
        
    spill_points = mask_to_world_points(combined_mask, depth, intrinsics, extrinsics)

    if spill_points.shape[0] < 10:
        print("Spill points count is very low; cannot plan wiping.")
    else:
        # 5. Determine the bounding box
        min_x = np.min(spill_points[:, 0])
        max_x = np.max(spill_points[:, 0])
        min_y = np.min(spill_points[:, 1])
        max_y = np.max(spill_points[:, 1])
        
        print(f"Spill bounds: X[{min_x:.3f}, {max_x:.3f}], Y[{min_y:.3f}, {max_y:.3f}]")

        # 6. Plan wiping trajectory
        # Fixed downward orientation (0,0,1,0 wxyz)
        wipe_quat = np.array([0.0, 0.0, 1.0, 0.0]) 

        z_wipe = 0.0
        z_safe = 0.15
        
        padding = 0.04
        start_x = min_x - padding
        end_x = max_x + padding
        start_y = min_y - padding
        end_y = max_y + padding
        
        # Step size (4cm)
        step_x = 0.04
        
        waypoints = []
        
        # Safe start
        waypoints.append(np.array([start_x, start_y, z_safe]))
        waypoints.append(np.array([start_x, start_y, z_wipe]))
        
        current_x = start_x
        direction = 1 
        
        # Raster scan loop
        while current_x <= end_x:
            target_y = end_y if direction == 1 else start_y
            
            # Interpolate long wipe motions to avoid large IK jumps
            # The API 'interpolate_segment' creates waypoints between p1 and p2
            p_start = np.array([current_x, (start_y if direction == 1 else end_y), z_wipe])
            p_end = np.array([current_x, target_y, z_wipe])
            
            # Generate intermediate points for the wipe stroke
            stroke_points = interpolate_segment(p_start, p_end, step=0.05)
            # extend list, skipping the first one if it's duplicate of last waypoint
            for pt in stroke_points:
                waypoints.append(pt)
            
            # Step in X
            next_x = min(current_x + step_x, end_x)
            
            if next_x > current_x:
                # Move to next X at current Y
                waypoints.append(np.array([next_x, target_y, z_wipe]))
            
            if current_x >= end_x:
                break
                
            current_x = next_x
            direction *= -1

        # Lift up
        waypoints.append(np.array([waypoints[-1][0], waypoints[-1][1], z_safe]))

        # 7. Execute
        print(f"Executing wiping motion with {len(waypoints)} waypoints...")
        for i, wp in enumerate(waypoints):
            try:
                joints = solve_ik(wp, wipe_quat)
                move_to_joints(joints)
            except Exception as e:
                print(f"IK failed for waypoint {i}: {e}")

        print("Wiping complete.")

# Code block 3
import numpy as np

# 1. Get current observation to find the remaining spill
obs = get_observation()
rgb = obs["robot0_robotview"]["images"]["rgb"]
depth = obs["robot0_robotview"]["images"]["depth"]
intrinsics = obs["robot0_robotview"]["intrinsics"]
extrinsics = obs["robot0_robotview"]["pose_mat"]

# 2. Segment "brown spill" again
# The previous attempt missed a spot, likely because the segmentation score was low or it was a separate island.
# We will lower the threshold and try to capture all remaining brown spots.
sam_results = segment_sam3_text_prompt(rgb, "brown spill")

if not sam_results:
    print("No 'brown spill' detected.")
else:
    combined_mask = np.zeros(rgb.shape[:2], dtype=bool)
    
    # We want to be very inclusive now since we know there is a remaining spot.
    # We will take any result with a positive score, or simply the top few if scores are low.
    sorted_results = sorted(sam_results, key=lambda x: x["score"], reverse=True)
    
    # Debug prints
    for i, res in enumerate(sorted_results):
        print(f"Mask {i}: score {res['score']:.3f}, size {np.sum(res['mask'])}")

    # Combine masks. If the top score is very low, we might need to trust it anyway as per previous logic.
    # However, since there are multiple spots, we should combine all reasonable candidates.
    threshold = 0.05 # Very low threshold
    count = 0
    for res in sorted_results:
        if res["score"] > threshold:
            combined_mask = np.logical_or(combined_mask, res["mask"])
            count += 1
            
    # If still nothing, take the top one
    if count == 0 and len(sorted_results) > 0:
        combined_mask = sorted_results[0]["mask"]
        count = 1
        print("Forcing use of top result due to low scores.")

    print(f"Combined {count} mask instances for the remaining spill.")

    # 3. Convert mask to world points
    if depth.ndim == 3:
        depth = depth.squeeze(-1)
    
    spill_points = mask_to_world_points(combined_mask, depth, intrinsics, extrinsics)

    if spill_points.shape[0] < 10:
        print("Spill points count is very low; treating as clean.")
    else:
        # 4. Bounding box
        min_x = np.min(spill_points[:, 0])
        max_x = np.max(spill_points[:, 0])
        min_y = np.min(spill_points[:, 1])
        max_y = np.max(spill_points[:, 1])
        
        print(f"Remaining spill bounds: X[{min_x:.3f}, {max_x:.3f}], Y[{min_y:.3f}, {max_y:.3f}]")

        # 5. Plan wiping trajectory
        # Standard wiping parameters
        z_wipe = 0.0
        z_safe = 0.15
        wipe_quat = np.array([0.0, 0.0, 1.0, 0.0]) # Downward facing

        # Add padding to ensure we cover the edges of the spill
        padding = 0.05
        start_x = min_x - padding
        end_x = max_x + padding
        start_y = min_y - padding
        end_y = max_y + padding
        
        # Step size for raster scan
        step_x = 0.04
        
        waypoints = []
        
        # Move to safe start
        waypoints.append(np.array([start_x, start_y, z_safe]))
        waypoints.append(np.array([start_x, start_y, z_wipe]))
        
        current_x = start_x
        direction = 1
        
        while current_x <= end_x:
            target_y = end_y if direction == 1 else start_y
            
            # Use interpolate_segment to generate dense waypoints for the stroke
            p_start = np.array([current_x, (start_y if direction == 1 else end_y), z_wipe])
            p_end = np.array([current_x, target_y, z_wipe])
            
            stroke_points = interpolate_segment(p_start, p_end, step=0.05)
            # Filter stroke points to ensure they are valid numpy arrays and not empty
            for pt in stroke_points:
                waypoints.append(pt)

            # Move to next X strip
            next_x = min(current_x + step_x, end_x)
            if next_x > current_x:
                waypoints.append(np.array([next_x, target_y, z_wipe]))
            
            if current_x >= end_x:
                break
            
            current_x = next_x
            direction *= -1
            
        # Lift up at the end
        if len(waypoints) > 0:
            last_pos = waypoints[-1]
            waypoints.append(np.array([last_pos[0], last_pos[1], z_safe]))
            
        # 6. Execute
        print(f"Executing cleanup wipe with {len(waypoints)} waypoints...")
        for i, wp in enumerate(waypoints):
            try:
                joints = solve_ik(wp, wipe_quat)
                move_to_joints(joints)
            except Exception as e:
                print(f"IK failed for waypoint {i} at {wp}: {e}")
                
        print("Cleanup complete.")