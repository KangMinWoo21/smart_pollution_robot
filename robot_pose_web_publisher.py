import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry


class RobotPoseWebPublisher(Node):
    def __init__(self):
        super().__init__('robot_pose_web_publisher')
        self.last_pose = None

        amcl_qos = QoSProfile(depth=10)
        amcl_qos.reliability = ReliabilityPolicy.RELIABLE
        amcl_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

        self.create_subscription(
            PoseWithCovarianceStamped,
            '/amcl_pose',
            self.amcl_callback,
            amcl_qos,
        )
        self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        self.pose_pub = self.create_publisher(PoseStamped, '/robot_pose_web', 10)
        self.timer = self.create_timer(0.2, self.publish_pose)
        self.get_logger().info('Publishing web robot pose on /robot_pose_web')

    def amcl_callback(self, msg):
        pose = PoseStamped()
        pose.header = msg.header
        pose.pose = msg.pose.pose
        self.last_pose = pose

    def odom_callback(self, msg):
        if self.last_pose is not None and self.last_pose.header.frame_id == 'map':
            return
        pose = PoseStamped()
        pose.header = msg.header
        pose.pose = msg.pose.pose
        self.last_pose = pose

    def publish_pose(self):
        if self.last_pose is None:
            return
        self.last_pose.header.stamp = self.get_clock().now().to_msg()
        self.pose_pub.publish(self.last_pose)


def main(args=None):
    rclpy.init(args=args)
    node = RobotPoseWebPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
