#!/usr/bin/env python3
import json
import os
import urllib.request



def extract_json_path(payload, path):
    value = payload
    for key in path.split("."):
        if isinstance(value, list):
            if not key.isdigit():
                return None
            index = int(key)
            if index >= len(value):
                return None
            value = value[index]
        elif isinstance(value, dict):
            if key not in value:
                return None
            value = value[key]
        else:
            return None

    if value in (None, "", "-"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Int32


class OutdoorAirQualityNode(Node):
    def __init__(self):
        super().__init__("outdoor_air_quality_node")
        qos = QoSProfile(depth=1)
        qos.reliability = ReliabilityPolicy.RELIABLE
        qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        self.publisher = self.create_publisher(Int32, "/air_quality/outdoor_pm25", qos)
        self.mode = os.environ.get("OUTDOOR_AIR_MODE", "mock").strip().lower()
        self.mock_value = int(os.environ.get("OUTDOOR_PM25_MOCK", "62"))
        self.api_url = os.environ.get("OUTDOOR_AIR_API_URL", "").strip()
        self.api_json_path = os.environ.get("OUTDOOR_AIR_API_JSON_PATH", "pm25").strip()
        interval = float(os.environ.get("OUTDOOR_AIR_INTERVAL_SECONDS", "10"))
        self.timer = self.create_timer(interval, self.publish_reading)
        self.get_logger().info(f"Outdoor air quality node started in {self.mode} mode.")
        self.publish_reading()

    def publish_reading(self):
        value = self.mock_value if self.mode == "mock" else self.fetch_api_value()
        if value is None:
            self.get_logger().warn("Outdoor PM2.5 API unavailable; publishing fallback mock value.")
            value = self.mock_value

        msg = Int32()
        msg.data = int(value)
        self.publisher.publish(msg)
        self.get_logger().info(f"Outdoor PM2.5: {msg.data}")

    def fetch_api_value(self):
        if not self.api_url:
            self.get_logger().warn("OUTDOOR_AIR_API_URL is empty.")
            return None

        try:
            with urllib.request.urlopen(self.api_url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return extract_json_path(payload, self.api_json_path)
        except Exception as exc:
            self.get_logger().warn(f"Outdoor air API fetch failed: {exc}")
            return None


def main(args=None):
    rclpy.init(args=args)
    node = OutdoorAirQualityNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
