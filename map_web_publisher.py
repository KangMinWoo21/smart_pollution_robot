import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from nav_msgs.srv import GetMap


class MapWebPublisher(Node):
    def __init__(self):
        super().__init__('map_web_publisher')
        self.map_msg = None
        self.map_client = self.create_client(GetMap, '/map_server/map')
        self.map_pub = self.create_publisher(OccupancyGrid, '/map_web', 10)
        self.map_sub = self.create_subscription(
            OccupancyGrid, '/map', self.live_map_callback, 10
        )
        self.timer = self.create_timer(1.0, self.publish_map)
        self.request_map()

    def live_map_callback(self, msg):
        self.map_msg = msg

    def request_map(self):
        self.get_logger().info('Waiting for /map_server/map service...')
        if not self.map_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('/map_server/map service is not available.')
            return

        future = self.map_client.call_async(GetMap.Request())
        future.add_done_callback(self.map_response_callback)

    def map_response_callback(self, future):
        try:
            response = future.result()
        except Exception as exc:
            self.get_logger().error(f'Failed to get map: {exc}')
            return

        self.map_msg = response.map
        self.get_logger().info(
            f'Received map {self.map_msg.info.width}x{self.map_msg.info.height}; publishing /map_web'
        )

    def publish_map(self):
        if self.map_msg is None:
            return

        self.map_msg.header.stamp = self.get_clock().now().to_msg()
        self.map_pub.publish(self.map_msg)


def main(args=None):
    rclpy.init(args=args)
    node = MapWebPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
