# Code block 0
import numpy as np
from scipy.spatial.transform import Rotation as R

# 1. Initialize robot
open_gripper()

# 2. Get the grasp pose for the nut's handle
# Using the specific query 'extruded handle of the brown square nut' as suggested
nut_handle_pos, nut_handle_quat = sample_grasp_pose('extruded handle of the brown square nut')

# 3. Approach and grasp the nut
# Use a z_approach to come down vertically onto the handle
goto_pose(nut_handle_pos, nut_handle_quat, z_approach=0.1)
close_gripper()

# 4. Lift the nut up to avoid collisions during transport
# We move up by 15cm from the current grasp position
lift_pos = nut_handle_pos + np.array([0, 0, 0.15])
goto_pose(lift_pos, nut_handle_quat)

# 5. Determine the relative transform between the grasp point (handle) and the insertion point (center of hole)
# The insertion needs to align the nut's hole with the block's peg.
# The robot is holding the handle, not the center of the nut.
# We need to find where the center of the nut is relative to the handle, so we can apply that offset to the target.

# Get the position of the nut's center (the hole)
nut_center_pos, _ = get_object_pose('white hollow center of the brown square nut')

# Calculate the vector from the handle (grasp point) to the nut's center (insertion point)
# This vector represents "where the center is relative to the gripper" in world frame *at the moment of grasping*
# Since we haven't rotated the gripper significantly in Z yet, this world-frame offset is a reasonable approximation for translation.
# Ideally, we would do this in the gripper frame, but without `get_ee_pose`, we rely on the stable grasp orientation.
handle_to_center_offset = nut_center_pos - nut_handle_pos

# 6. Get the target pose (the block/peg)
# We want to place the `white hollow center` onto the `brown square block`.
block_pos, _ = get_object_pose('brown square block')

# 7. Calculate the target placement pose for the robot gripper
# We want the `nut_center` to be at `block_pos`.
# Therefore, the gripper (holding the handle) must be at `block_pos - handle_to_center_offset`.
# Wait, let's check vector math:
# Target Nut Center = Block Position
# Gripper Target = Target Nut Center - (Nut Center - Handle Position)  <-- This subtracts the offset
# Gripper Target = Block Position - (Nut Center Position - Handle Position)
# Gripper Target = Block Position + (Handle Position - Nut Center Position)
gripper_target_pos = block_pos + (nut_handle_pos - nut_center_pos)

# 8. Move to the target position
# We use the same grasp orientation (`nut_handle_quat`) to maintain the relative alignment.
# We add a z_approach to align carefully before inserting.
goto_pose(gripper_target_pos, nut_handle_quat, z_approach=0.1)

# 9. Release the object
open_gripper()

# 10. Retreat to safe position
goto_home_joint_position()

# Code block 1
import numpy as np
from scipy.spatial.transform import Rotation as R

# 1. Initialize
open_gripper()

# 2. Perception and Planning BEFORE moving anything
# We need the relationship between the handle (where we grasp) and the hole (where we insert).
# Both must be queried while the object is static on the table to get a valid relative transform.

# Get the grasp pose for the handle
nut_handle_pos, nut_handle_quat = sample_grasp_pose('extruded handle of the brown square nut')

# Get the position of the nut's center hole
nut_center_pos, _ = get_object_pose('white hollow center of the brown square nut')

# Get the target position (the block we want to insert onto)
block_pos, _ = get_object_pose('brown square block')

# Calculate the offset: vector from the Nut Center -> Handle
# This vector tells us: "To put the center at X, the gripper must be at X + offset"
center_to_handle_offset = nut_handle_pos - nut_center_pos

# Calculate the target gripper position for insertion
# We want the nut center to end up at block_pos.
# So the gripper needs to be at block_pos + center_to_handle_offset.
gripper_target_pos = block_pos + center_to_handle_offset

# 3. Execute Pick
# Approach and grasp the nut by the handle
goto_pose(nut_handle_pos, nut_handle_quat, z_approach=0.1)
close_gripper()

# 4. Lift
# Lift up to clear the table/obstacles
lift_pos = nut_handle_pos + np.array([0, 0, 0.2])
goto_pose(lift_pos, nut_handle_quat)

# 5. Execute Place
# Move to the calculated target position.
# We use the same quaternion as the grasp to maintain the relative orientation.
# We use a z_approach to align vertically above the peg before sliding down.
goto_pose(gripper_target_pos, nut_handle_quat, z_approach=0.1)

# 6. Release and Retreat
open_gripper()

# Move up slightly to clear the peg before going home
retreat_pos = gripper_target_pos + np.array([0, 0, 0.1])
goto_pose(retreat_pos, nut_handle_quat)

goto_home_joint_position()