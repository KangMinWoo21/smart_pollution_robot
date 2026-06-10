#!/usr/bin/env python3
import os
import threading
import time

import rclpy
from rclpy.node import Node
import serial
from std_msgs.msg import Int32


class PMSSensorNode(Node):
    def __init__(self):
        super().__init__("pms_sensor_node")
        self.pm25_publisher = self.create_publisher(Int32, "/pms7003/pm25", 10)
        self.ser = None

        port = os.environ.get("PMS_PORT", "/dev/serial0")
        try:
            self.ser = serial.Serial(port, baudrate=9600, timeout=1)
            self.get_logger().info(
                f"PMS7003 connected on {port}; starting reader thread."
            )
            self.thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.thread.start()
        except Exception as exc:
            self.get_logger().error(f"Failed to connect PMS7003 on {port}: {exc}")

    def read_serial_data(self):
        while rclpy.ok():
            if self.ser and self.ser.is_open:
                try:
                    if self.ser.read(1) == b"\x42" and self.ser.read(1) == b"\x4d":
                        data = self.ser.read(30)
                        if len(data) == 30:
                            pm25 = data[10] * 256 + data[11]
                            msg = Int32()
                            msg.data = pm25
                            self.pm25_publisher.publish(msg)
                            self.get_logger().info(f"PM2.5: {pm25} ug/m3")
                except Exception as exc:
                    self.get_logger().warn(f"PMS7003 read error: {exc}")
            time.sleep(0.01)

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()


def main(args=None):
    rclpy.init(args=args)
    node = PMSSensorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
