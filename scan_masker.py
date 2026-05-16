import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

class ScanMasker(Node):
    def __init__(self):
        super().__init__('scan_masker')
        self.sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        self.pub = self.create_publisher(LaserScan, '/scan_filtered', 10)
        
        # [핵심 파라미터] 라이다 중심으로부터 기둥까지의 최대 거리 (단위: 미터)
        # 0.20 = 20cm. (터틀봇 Waffle 상판 반경이 약 15cm이므로 20cm면 충분합니다)
        self.THRESHOLD_DISTANCE = 0.20 
        
        self.get_logger().info(f"🔥 Distance Masker Started: 반경 {self.THRESHOLD_DISTANCE}m 이내의 기둥 데이터를 제거합니다...")

    def scan_callback(self, msg):
        ranges = list(msg.ranges)
        
        # 360도 전체를 검사하여, 거리가 20cm 미만인 데이터는 모두 0.0(무시)으로 덮어씌움
        for i in range(len(ranges)):
            # 0.0보다 큰 유효한 데이터 중 임계값(20cm)보다 가까운 것 = 기둥
            if 0.0 < ranges[i] < self.THRESHOLD_DISTANCE:
                ranges[i] = 0.0
                
        msg.ranges = ranges
        self.pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = ScanMasker()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
