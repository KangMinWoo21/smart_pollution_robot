#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import RPi.GPIO as GPIO
from std_msgs.msg import Bool


class RelayControlNode(Node):
    RELAY_PIN = 12

    def __init__(self):
        super().__init__("relay_control_node")
        self.create_subscription(Bool, "/hardware/relay", self.relay_callback, 10)
        self.gpio_ready = False

        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(self.RELAY_PIN, GPIO.OUT)
            GPIO.output(self.RELAY_PIN, GPIO.LOW)
            self.gpio_ready = True
            self.get_logger().info(
                f"Relay control ready on physical pin {self.RELAY_PIN}."
            )
        except Exception as exc:
            self.get_logger().error(f"GPIO setup failed: {exc}")

    def relay_callback(self, msg):
        if not self.gpio_ready:
            self.get_logger().warn("Ignoring relay command because GPIO is not ready.")
            return

        if msg.data:
            GPIO.output(self.RELAY_PIN, GPIO.HIGH)
            self.get_logger().info("Relay ON")
        else:
            GPIO.output(self.RELAY_PIN, GPIO.LOW)
            self.get_logger().info("Relay OFF")


def main(args=None):
    rclpy.init(args=args)
    node = RelayControlNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.gpio_ready:
            GPIO.cleanup()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
