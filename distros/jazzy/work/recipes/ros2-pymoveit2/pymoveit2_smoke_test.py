#!/usr/bin/env python3
"""Smoke test for pymoveit2, without a running MoveIt.

Creates the arm and gripper interfaces for the Panda preset on one node (this loads
rclpy, the RMW and the type support of every message, service and action package
pymoveit2 uses), publishes a JointState on the same node and checks that the arm
interface receives it, then destroys everything.
"""

import sys
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from sensor_msgs.msg import JointState

from pymoveit2 import MoveIt2, MoveIt2Gripper
from pymoveit2.robots import panda

TIMEOUT_SEC = 20.0


def main() -> int:
    rclpy.init()
    node = rclpy.create_node("pymoveit2_smoke_test")
    executor = SingleThreadedExecutor()
    executor.add_node(node)

    joint_names = panda.joint_names()
    moveit2 = MoveIt2(
        node=node,
        joint_names=joint_names,
        base_link_name=panda.base_link_name(),
        end_effector_name=panda.end_effector_name(),
        group_name=panda.MOVE_GROUP_ARM,
    )
    gripper = MoveIt2Gripper(
        node=node,
        gripper_joint_names=panda.gripper_joint_names(),
        open_gripper_joint_positions=panda.OPEN_GRIPPER_JOINT_POSITIONS,
        closed_gripper_joint_positions=panda.CLOSED_GRIPPER_JOINT_POSITIONS,
        gripper_group_name=panda.MOVE_GROUP_GRIPPER,
    )

    assert moveit2.joint_names == joint_names, moveit2.joint_names
    assert moveit2.joint_state is None, "joint state before anything was published"

    # Same node, so the same DDS participant: no network discovery is involved.
    publisher = node.create_publisher(JointState, "joint_states", 1)
    msg = JointState()
    msg.name = joint_names
    msg.position = [0.1 * i for i in range(len(joint_names))]

    deadline = time.monotonic() + TIMEOUT_SEC
    while moveit2.joint_state is None and time.monotonic() < deadline:
        msg.header.stamp = node.get_clock().now().to_msg()
        publisher.publish(msg)
        executor.spin_once(timeout_sec=0.1)

    received = moveit2.joint_state
    ok = received is not None and list(received.name) == joint_names
    if ok:
        print("pymoveit2 smoke test: joint state received:", list(received.position))
    else:
        print(
            f"pymoveit2 smoke test: no joint state within {TIMEOUT_SEC} s",
            file=sys.stderr,
        )

    gripper.destroy()
    moveit2.destroy()
    executor.shutdown()
    node.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
