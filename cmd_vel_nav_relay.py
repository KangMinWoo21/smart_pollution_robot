#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped


class CmdVelNavRelay(Node):
    def __init__(self):
        super().__init__("cmd_vel_nav_relay")
        self.publisher = self.create_publisher(TwistStamped, "/cmd_vel", 10)
        self.subscription = self.create_subscription(
            TwistStamped,
            "/cmd_vel_smoothed",
            self.relay_callback,
            10,
        )
        self.get_logger().info("Relaying /cmd_vel_smoothed to /cmd_vel for demo driving.")

    def relay_callback(self, msg):
        self.publisher.publish(msg)


def main():
    rclpy.init()
    node = CmdVelNavRelay()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
