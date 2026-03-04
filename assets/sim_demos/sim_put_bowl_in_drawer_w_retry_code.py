# Code block 0
import numpy as np

# 1. Inspect the scene
obs = get_observation()
agentview = obs["agentview"]
rgb = agentview["images"]["rgb"]
depth = agentview["images"]["depth"]
intrinsics = agentview["intrinsics"]
extrinsics = agentview["pose_mat"]

# 2. Open the drawer
# We need to find the drawer handle first.
handle_text_prompt = "handle of the top drawer"
handle_masks = segment_sam3_text_prompt(rgb, handle_text_prompt)

# Pick the highest confidence mask
if not handle_masks:
    print("Could not find handle.")
    # Fallback or error handling would go here, but for this snippet we assume success
else:
    best_handle = max(handle_masks, key=lambda x: x["score"])
    handle_mask = best_handle["mask"]
    
    # Calculate the grasp pose for the handle using Contact-GraspNet
    # Note: Contact-GraspNet is usually better for objects, but handles can be tricky.
    # Alternatively, we can calculate the centroid and normal manually, but let's try the grasp planner first.
    grasp_poses_cam, grasp_scores = plan_grasp(depth, intrinsics, handle_mask)
    
    # Filter for a grasp that is approachable (e.g., horizontal approach for a drawer handle)
    # The drawer handle is on the front face, so we generally want the z-axis of the gripper to align with world -Y or -X depending on setup.
    # Given the description "handle... positioned on the right face of the cabinet", we likely want to pull along +Y or +X.
    # Let's select a valid grasp. For simplicity in this script, we take the highest scoring one and assume the planner found a valid handle grasp.
    
    if len(grasp_scores) > 0:
        # Convert grasps to world frame to select the best one
        best_idx = np.argmax(grasp_scores)
        best_grasp_cam = grasp_poses_cam[best_idx]
        best_grasp_world = extrinsics @ best_grasp_cam
        
        # Decompose grasp
        grasp_pos, grasp_quat = decompose_transform(best_grasp_world)
        
        # Calculate pre-grasp (approach) position (e.g., 10cm back along the gripper's z-axis)
        # The gripper Z-axis is the approach vector.
        approach_vec = best_grasp_world[:3, 2] 
        pre_grasp_pos = grasp_pos - approach_vec * 0.10
        
        # Execute Opening Sequence
        open_gripper()
        
        # Move to pre-grasp
        joints_pre = solve_ik(pre_grasp_pos, grasp_quat)
        move_to_joints(joints_pre)
        
        # Move to grasp
        joints_grasp = solve_ik(grasp_pos, grasp_quat)
        move_to_joints(joints_grasp)
        
        close_gripper()
        
        # Pull the drawer open. 
        # Based on "handle... positioned on the right face of the cabinet (from the camera's perspective, facing positive Y)",
        # we likely need to pull in the direction of the handle's normal or simply outwards.
        # Assuming the drawer opens along the world X axis (forward/backward relative to robot base) or Y axis (left/right).
        # Usually, drawers open along one axis. Let's infer the pull direction from the grasp orientation or just use a heuristic.
        # If the handle is on the "right face" (positive Y in image, which maps to world frame), it suggests pulling towards Positive Y (World).
        # Let's calculate a pull vector.
        pull_distance = 0.25 # 25 cm
        # The prompt says "In image space the right is world frame positive Y". If the drawer is on the left, pulling it "open" usually means pulling it towards the workspace center (Positive Y).
        pull_target_pos = grasp_pos + np.array([0, pull_distance, 0]) 
        
        joints_pull = solve_ik(pull_target_pos, grasp_quat)
        move_to_joints(joints_pull)
        
        open_gripper()
        
        # Retreat slightly to clear the handle
        retreat_pos = pull_target_pos + np.array([0, -0.05, 0.1]) # back and up
        joints_retreat = solve_ik(retreat_pos, grasp_quat)
        move_to_joints(joints_retreat)
        
    else:
        print("No grasps found for handle.")

# 3. Pick and Place the Bowl
# Refresh observation to get updated scene (though static objects haven't moved much, the robot has)
obs = get_observation()
agentview = obs["agentview"]
rgb = agentview["images"]["rgb"]
depth = agentview["images"]["depth"]

bowl_text_prompt = "silver bowl"
bowl_masks = segment_sam3_text_prompt(rgb, bowl_text_prompt)

if bowl_masks:
    best_bowl = max(bowl_masks, key=lambda x: x["score"])
    bowl_mask = best_bowl["mask"]
    
    # Plan grasp for bowl
    # We use a top-down constraint for bowls to avoid hitting the rim from the side
    grasp_poses_cam, grasp_scores = plan_grasp(depth, intrinsics, bowl_mask)
    
    best_bowl_grasp_world, _ = select_top_down_grasp(grasp_poses_cam, grasp_scores, extrinsics)
    
    if best_bowl_grasp_world is not None:
        bowl_pos, bowl_quat = decompose_transform(best_bowl_grasp_world)
        
        # Pre-grasp for bowl (15cm above)
        pre_bowl_pos = bowl_pos + np.array([0, 0, 0.15])
        
        open_gripper()
        
        # Move to pre-grasp
        joints_pre_bowl = solve_ik(pre_bowl_pos, bowl_quat)
        move_to_joints(joints_pre_bowl)
        
        # Move to grasp
        joints_grasp_bowl = solve_ik(bowl_pos, bowl_quat)
        move_to_joints(joints_grasp_bowl)
        
        close_gripper()
        
        # Lift bowl
        lift_pos = bowl_pos + np.array([0, 0, 0.20])
        joints_lift = solve_ik(lift_pos, bowl_quat)
        move_to_joints(joints_lift)
        
        # 4. Place in Drawer
        # We need the 3D location of the open drawer.
        # We can re-segment the "inside of the drawer" or just use the coordinate where we pulled the handle to.
        # The handle was pulled to `pull_target_pos`. The drawer center is likely offset from the handle.
        # Let's estimate the drawer center based on the handle position.
        # If handle is at pull_target_pos, the drawer volume is likely 'behind' the handle (negative Y relative to handle face) 
        # and 'down' relative to handle? Or just aligned.
        # Let's try to detect the "open drawer" visual area for robustness, or use heuristic offset.
        
        # Heuristic: The bowl should be placed slightly 'behind' the handle (World X direction? or negative Y?)
        # If we pulled along +Y, the drawer extends from `pull_target_pos` back towards -Y.
        # Wait, if we pulled +Y, the handle is at the most +Y point. The box is behind it (Negative Y).
        # We want to drop it roughly 10-15cm "inside" (Negative Y direction from handle) and slightly down?
        # Safe bet: Go to handle position + vertical offset, then move 'into' the drawer.
        
        # Using the `pull_target_pos` (handle final location):
        # Target place position: Same X and Z as handle, but moved -0.15m in Y (inside the drawer length) 
        # and maybe slightly down if the handle is high, but handles are usually centered vertically on drawer face.
        # Let's keep Z similar to avoid collision with drawer bottom, drop it from a bit of height.
        
        drop_location = pull_target_pos + np.array([0, -0.15, 0.05]) # 15cm into the drawer, 5cm above handle level
        
        # Move to above drop location
        pre_drop_pos = drop_location + np.array([0, 0, 0.15])
        joints_pre_drop = solve_ik(pre_drop_pos, bowl_quat)
        move_to_joints(joints_pre_drop)
        
        # Lower slightly
        joints_drop = solve_ik(drop_location, bowl_quat)
        move_to_joints(joints_drop)
        
        open_gripper()
        
        # Retreat up
        joints_retreat_post = solve_ik(pre_drop_pos, bowl_quat)
        move_to_joints(joints_retreat_post)
        
    else:
        print("No valid top-down grasp found for bowl.")
else:
    print("Bowl not found.")

# Code block 1
import numpy as np

# 1. Inspect the scene to find the handle again (since it moved)
obs = get_observation()
agentview = obs["agentview"]
rgb = agentview["images"]["rgb"]
depth = agentview["images"]["depth"]
intrinsics = agentview["intrinsics"]
extrinsics = agentview["pose_mat"]

# 2. Open the drawer fully
handle_text_prompt = "handle of the top drawer"
handle_masks = segment_sam3_text_prompt(rgb, handle_text_prompt)

if handle_masks:
    best_handle = max(handle_masks, key=lambda x: x["score"])
    handle_mask = best_handle["mask"]
    
    # Plan grasp for the handle
    grasp_poses_cam, grasp_scores = plan_grasp(depth, intrinsics, handle_mask)
    
    if len(grasp_scores) > 0:
        best_idx = np.argmax(grasp_scores)
        best_grasp_cam = grasp_poses_cam[best_idx]
        best_grasp_world = extrinsics @ best_grasp_cam
        
        grasp_pos, grasp_quat = decompose_transform(best_grasp_world)
        
        # Approach vector (gripper Z)
        approach_vec = best_grasp_world[:3, 2]
        
        # Pre-grasp (approach)
        pre_grasp_pos = grasp_pos - approach_vec * 0.10
        
        open_gripper()
        move_to_joints(solve_ik(pre_grasp_pos, grasp_quat))
        move_to_joints(solve_ik(grasp_pos, grasp_quat))
        close_gripper()
        
        # Pull the drawer significantly more this time.
        # Based on previous logic, pulling towards +Y seemed correct for "right face".
        # We increase the distance to ensure it opens fully.
        pull_distance = 0.35 
        pull_target_pos = grasp_pos + np.array([0, pull_distance, 0])
        
        # Execute pull
        move_to_joints(solve_ik(pull_target_pos, grasp_quat))
        
        open_gripper()
        
        # Retreat
        retreat_pos = pull_target_pos + np.array([0, -0.1, 0.1])
        move_to_joints(solve_ik(retreat_pos, grasp_quat))
        
        # 3. Pick the Bowl
        # Refresh observation
        obs = get_observation()
        rgb = obs["agentview"]["images"]["rgb"]
        depth = obs["agentview"]["images"]["depth"]
        intrinsics = obs["agentview"]["intrinsics"]
        
        bowl_text_prompt = "silver bowl"
        bowl_masks = segment_sam3_text_prompt(rgb, bowl_text_prompt)
        
        if bowl_masks:
            best_bowl = max(bowl_masks, key=lambda x: x["score"])
            bowl_mask = best_bowl["mask"]
            
            grasp_poses_cam, grasp_scores = plan_grasp(depth, intrinsics, bowl_mask)
            best_bowl_grasp_world, _ = select_top_down_grasp(grasp_poses_cam, grasp_scores, extrinsics)
            
            if best_bowl_grasp_world is not None:
                bowl_pos, bowl_quat = decompose_transform(best_bowl_grasp_world)
                
                # Pre-grasp
                pre_bowl_pos = bowl_pos + np.array([0, 0, 0.15])
                move_to_joints(solve_ik(pre_bowl_pos, bowl_quat))
                move_to_joints(solve_ik(bowl_pos, bowl_quat))
                close_gripper()
                
                # Lift
                lift_pos = bowl_pos + np.array([0, 0, 0.25])
                move_to_joints(solve_ik(lift_pos, bowl_quat))
                
                # 4. Place in Drawer
                # Calculate drop position based on the handle's final pulled position.
                # If we pulled to `pull_target_pos` (handle center), the drawer interior is 'behind' it.
                # Assuming pull was along +Y, "behind" is -Y.
                # We drop it inside the drawer volume.
                drop_pos = pull_target_pos + np.array([0, -0.15, 0.05])
                
                # Move to pre-drop (high)
                pre_drop_pos = drop_pos + np.array([0, 0, 0.15])
                move_to_joints(solve_ik(pre_drop_pos, bowl_quat))
                
                # Move to drop
                move_to_joints(solve_ik(drop_pos, bowl_quat))
                open_gripper()
                
                # Retreat
                move_to_joints(solve_ik(pre_drop_pos, bowl_quat))
            else:
                print("No top-down grasp for bowl.")
        else:
            print("Bowl not found.")
    else:
        print("No grasp for handle found.")
else:
    print("Handle not found.")

# Code block 2
import numpy as np

# 1. Inspect the scene
# Since the drawer is already open (according to the observation), we need to find the bowl and place it into the drawer.
obs = get_observation()
agentview = obs["agentview"]
rgb = agentview["images"]["rgb"]
depth = agentview["images"]["depth"]
intrinsics = agentview["intrinsics"]
extrinsics = agentview["pose_mat"]

# 2. Locate the bowl
bowl_text_prompt = "silver bowl"
bowl_masks = segment_sam3_text_prompt(rgb, bowl_text_prompt)

if not bowl_masks:
    print("Could not find the bowl.")
else:
    best_bowl = max(bowl_masks, key=lambda x: x["score"])
    bowl_mask = best_bowl["mask"]
    
    # Plan grasp for the bowl
    # We want a top-down grasp for the bowl
    grasp_poses_cam, grasp_scores = plan_grasp(depth, intrinsics, bowl_mask)
    
    best_bowl_grasp_world, best_score = select_top_down_grasp(grasp_poses_cam, grasp_scores, extrinsics)
    
    if best_bowl_grasp_world is not None:
        bowl_pos, bowl_quat = decompose_transform(best_bowl_grasp_world)
        
        # Pre-grasp (approach from above)
        pre_grasp_pos = bowl_pos + np.array([0, 0, 0.15])
        
        open_gripper()
        
        # Move to pre-grasp
        joints_pre = solve_ik(pre_grasp_pos, bowl_quat)
        move_to_joints(joints_pre)
        
        # Move to grasp
        joints_grasp = solve_ik(bowl_pos, bowl_quat)
        move_to_joints(joints_grasp)
        
        close_gripper()
        
        # Lift the bowl
        lift_height = 0.20
        lift_pos = bowl_pos + np.array([0, 0, lift_height])
        joints_lift = solve_ik(lift_pos, bowl_quat)
        move_to_joints(joints_lift)
        
        # 3. Place in the drawer
        # We need to find the open drawer to place the bowl inside.
        # Since the drawer is open, we can try to segment the "inside of the open drawer" or the handle again to get a reference.
        # Let's find the handle of the top drawer again to use as a reference point.
        # The handle should now be pulled out (towards +Y in world frame, or +X depending on setup, but typically +Y based on previous context).
        
        # Re-observe to find handle new position
        obs = get_observation()
        rgb_new = obs["agentview"]["images"]["rgb"]
        depth_new = obs["agentview"]["images"]["depth"]
        intrinsics_new = obs["agentview"]["intrinsics"]
        
        handle_text_prompt = "handle of the top drawer"
        handle_masks = segment_sam3_text_prompt(rgb_new, handle_text_prompt)
        
        drop_target_pos = None
        
        if handle_masks:
            best_handle = max(handle_masks, key=lambda x: x["score"])
            handle_mask = best_handle["mask"]
            
            # Get 3D point of the handle
            # We can pick a point from the mask and deproject it
            ys, xs = np.where(handle_mask)
            if len(ys) > 0:
                # Use the center of the mask
                y_c, x_c = int(np.mean(ys)), int(np.mean(xs))
                z_c = depth_new[y_c, x_c]
                if z_c > 0:
                    handle_pos_world = pixel_to_world_point(x_c, y_c, z_c, intrinsics_new, extrinsics)
                    
                    # Heuristic: The drawer interior is 'behind' the handle.
                    # Previous reasoning suggested pulling along Y. If handle is at Y_handle, drawer box is at Y < Y_handle.
                    # Let's place it roughly 10-15cm behind the handle in Y, and keep X similar.
                    # NOTE: "In image space the right is world frame positive Y". If the drawer is on the right side of the image, 
                    # and we pull it open, we pull towards positive Y? No, usually drawers open forward relative to the cabinet front.
                    # If the camera looks from front, and right is +Y, then cabinet front face normal is likely +X (backwards into camera is +X?? No wait).
                    # "backward into the camera is world frame positive X". So camera looks towards -X.
                    # This means the robot and table are in -X direction relative to camera? Or camera is at +X looking -X?
                    # Let's rely on relative position. 
                    # If the handle is at `handle_pos_world`, and the drawer is open, the "inside" is usually along the axis of opening.
                    # Assuming standard drawer opening, we place it slightly "in" from the handle.
                    # Let's try an offset. If handle is at (x, y, z), we place at (x, y - 0.15, z + small_offset)?
                    # If the handle is on the "right face", it implies the drawer moves along Y axis.
                    # If we pulled it open, it moved +Y (to the right in image). So inside is -Y relative to handle.
                    
                    drop_target_pos = handle_pos_world + np.array([0.0, -0.15, 0.05])
        
        if drop_target_pos is None:
            # Fallback if handle detection fails or depth is bad:
            # Use a hardcoded guess relative to the lift position or just blindly rely on previous successful pull coordinate?
            # Let's assume the bowl lift position is safe and move relative to the handle if found, 
            # otherwise we might be stuck. But since the drawer is open, handle should be visible.
            print("Could not robustly detect handle 3D position. Trying a fallback heuristic based on bowl position.")
            # This is risky, but better than crashing.
            # Assuming bowl was picked from table, maybe (0, 0, 0.2) relative to table center?
            # Let's just print error and stop if we can't find target.
            print("Cannot place bowl without target.")
        else:
            # Execute Place
            # Move to high approach position above drawer
            pre_drop_pos = drop_target_pos + np.array([0, 0, 0.15])
            
            joints_pre_drop = solve_ik(pre_drop_pos, bowl_quat)
            move_to_joints(joints_pre_drop)
            
            # Lower into drawer
            joints_drop = solve_ik(drop_target_pos, bowl_quat)
            move_to_joints(joints_drop)
            
            open_gripper()
            
            # Retreat
            joints_retreat = solve_ik(pre_drop_pos, bowl_quat)
            move_to_joints(joints_retreat)
            
    else:
        print("Could not find a valid grasp for the bowl.")