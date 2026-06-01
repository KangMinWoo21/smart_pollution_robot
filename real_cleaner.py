import os
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Bool, String
from geometry_msgs.msg import TwistStamped

class AutonomousPurifier(Node):
    def __init__(self):
        super().__init__('autonomous_purifier')
        
        self.DEFAULT_POLLUTION_THRESHOLD = 100
        self.POLLUTION_THRESHOLD = self.DEFAULT_POLLUTION_THRESHOLD
        self.CLEAN_THRESHOLD = 45
        self.OUTDOOR_STALE_SECONDS = float(os.environ.get("OUTDOOR_AIR_STALE_SECONDS", "1800"))
        
        self.current_pm = 0
        self.outdoor_pm25 = None
        self.outdoor_pm25_updated_at = 0.0
        self.is_purifying = False
        self.current_mode = 'manual' # 기본은 수동 모드
        
        # 구독 및 발행 설정
        self.create_subscription(Int32, '/pms7003/pm25', self.sensor_callback, 10)
        self.create_subscription(String, '/robot_mode', self.mode_callback, 10)
        self.create_subscription(Int32, '/air_quality/outdoor_pm25', self.outdoor_pm25_callback, 10)
        self.cmd_pub = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        self.relay_pub = self.create_publisher(Bool, '/hardware/relay', 10)
        self.threshold_pub = self.create_publisher(Int32, '/air_quality/adaptive_threshold', 10)
        
        # 0.5초마다 주행 상태를 제어하는 타이머
        self.timer = self.create_timer(0.5, self.behavior_loop)
        
        self.get_logger().info("🤖 실전 관제용 두뇌 가동! 순간 브레이크 로직이 적용되었습니다.")

    def mode_callback(self, msg):
        """아이패드에서 수동/자동 버튼을 누를 때 실행되는 함수"""
        new_mode = msg.data
        
        # 🎯 [핵심 수정] 자동 모드에서 수동 모드로 변하는 '그 순간' 딱 한 번 브레이크를 밟습니다.
        # 이렇게 하면 기존의 자동 회전 명령이 완전히 지워져 로봇이 즉시 자리에 멈춥니다.
        if self.current_mode == 'auto' and new_mode == 'manual':
            self.get_logger().warn("🛑 자동 모드 즉시 해제 -> 잔여 주행 명령 초기화 (브레이크)")
            self.stop_robot()
            
        self.current_mode = new_mode
        self.get_logger().info(f"🔄 모드 변경됨: {self.current_mode.upper()} 모드")

    def outdoor_pm25_callback(self, msg):
        self.outdoor_pm25 = int(msg.data)
        self.outdoor_pm25_updated_at = time.monotonic()
        self.update_adaptive_threshold()

    def calculate_adaptive_threshold(self):
        if self.outdoor_pm25 is None:
            return self.DEFAULT_POLLUTION_THRESHOLD

        age = time.monotonic() - self.outdoor_pm25_updated_at
        if age > self.OUTDOOR_STALE_SECONDS:
            return self.DEFAULT_POLLUTION_THRESHOLD

        if self.outdoor_pm25 > 75:
            return 70
        if self.outdoor_pm25 >= 36:
            return 85
        return self.DEFAULT_POLLUTION_THRESHOLD

    def update_adaptive_threshold(self):
        self.POLLUTION_THRESHOLD = self.calculate_adaptive_threshold()
        msg = Int32()
        msg.data = int(self.POLLUTION_THRESHOLD)
        self.threshold_pub.publish(msg)

    def sensor_callback(self, msg):
        self.current_pm = msg.data
        
        # 오염원 감지
        if self.current_pm >= self.POLLUTION_THRESHOLD and not self.is_purifying:
            self.get_logger().warn(
                f"🚨 오염 감지! PM2.5={self.current_pm}, threshold={self.POLLUTION_THRESHOLD}. 정화를 시작합니다."
            )
            self.is_purifying = True
            self.turn_on_fan()

        # 정화 완료
        elif self.current_pm <= self.CLEAN_THRESHOLD and self.is_purifying:
            self.get_logger().info(f"✨ 정화 완료! ({self.current_pm}) 팬을 끕니다.")
            self.is_purifying = False
            self.turn_off_fan()

    def behavior_loop(self):
        """로봇의 주행 상태 제어 루프"""
        self.update_adaptive_threshold()

        # 정화 중일 때는 무조건 정지
        if self.is_purifying:
            self.stop_robot()
            return
            
        # 자동 모드일 때만 0.5초마다 지속적으로 회전 명령을 쏨
        if self.current_mode == 'auto':
            explore_msg = TwistStamped()
            explore_msg.header.stamp = self.get_clock().now().to_msg()
            explore_msg.twist.angular.z = 0.3
            self.cmd_pub.publish(explore_msg)
            
        # 수동 모드일 때는 주행 명령을 아예 쏘지 않음 (아이패드 조이스틱과 충돌 방지)
        elif self.current_mode == 'manual':
            pass

    def stop_robot(self):
        """로봇에게 즉시 속도 0을 보내 완전히 멈추게 하는 함수"""
        stop_msg = TwistStamped()
        stop_msg.header.stamp = self.get_clock().now().to_msg()
        stop_msg.twist.linear.x = 0.0
        stop_msg.twist.angular.z = 0.0
        self.cmd_pub.publish(stop_msg)

    def turn_on_fan(self):
        msg = Bool()
        msg.data = True
        self.relay_pub.publish(msg)

    def turn_off_fan(self):
        msg = Bool()
        msg.data = False
        self.relay_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = AutonomousPurifier()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.turn_off_fan()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
