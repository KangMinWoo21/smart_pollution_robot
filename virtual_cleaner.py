import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import Bool, String
from visualization_msgs.msg import Marker, MarkerArray
import time
import threading
import random

class VirtualCleaner(Node):
    def __init__(self):
        super().__init__('virtual_cleaner')
        
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.relay_pub = self.create_publisher(Bool, '/hardware/relay', 10)
        self.marker_pub = self.create_publisher(MarkerArray, '/pollution_markers', 10)
        
        # [신규 추가] 아이패드에서 보내는 모드 제어 신호 구독
        self.mode_sub = self.create_subscription(String, '/robot_mode', self.mode_callback, 10)
        
        self.MAP_X_MIN = -8.9
        self.MAP_X_MAX =  0.7
        self.MAP_Y_MIN = -0.1
        self.MAP_Y_MAX =  4.8
        
        self.virtual_spots = []
        self.generate_random_spots(3)
        
        self.goal_done_event = threading.Event()
        self.marker_timer = self.create_timer(0.5, self.publish_markers) 
        self.sequence_started = False
        
        self.get_logger().info("📡 시스템 대기 중... 아이패드에서 '자동 정화' 버튼을 눌러주세요.")

    # [신규 추가] 아이패드 버튼 클릭 시 호출되는 콜백 함수
    def mode_callback(self, msg):
        if msg.data == 'auto':
            if not self.sequence_started:
                self.get_logger().info("📱 아이패드 명령 수신: '자동 정화' 시퀀스를 가동합니다!")
                self.start_sequence()
        elif msg.data == 'manual':
            self.get_logger().info("📱 아이패드 명령 수신: '수동 조종' (현재 주행 목표가 있다면 완료 후 대기합니다.)")

    def generate_random_spots(self, count):
        for _ in range(count):
            self.virtual_spots.append({
                "x": random.uniform(self.MAP_X_MIN, self.MAP_X_MAX),
                "y": random.uniform(self.MAP_Y_MIN, self.MAP_Y_MAX),
                "AQ": random.uniform(50.0, 90.0),
                "cleaned": False
            })

    def publish_markers(self):
        marker_array = MarkerArray()
        for i, spot in enumerate(self.virtual_spots):
            marker = Marker()
            marker.header.frame_id = 'map'
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = 'pollution_zones'
            marker.id = i
            marker.type = Marker.CYLINDER
            marker.action = Marker.ADD
            
            marker.pose.position.x = spot["x"]
            marker.pose.position.y = spot["y"]
            marker.pose.position.z = 0.05
            marker.pose.orientation.w = 1.0
            
            marker.scale.x = 0.6 
            marker.scale.y = 0.6
            marker.scale.z = 0.1
            
            marker.color.a = 0.6
            if spot["cleaned"]:
                marker.color.r, marker.color.g, marker.color.b = 0.0, 1.0, 0.0
            elif spot["AQ"] > 60.0:
                marker.color.r, marker.color.g, marker.color.b = 1.0, 0.0, 0.0
            else:
                marker.color.r, marker.color.g, marker.color.b = 1.0, 1.0, 0.0
                
            marker_array.markers.append(marker)
        self.marker_pub.publish(marker_array)

    def send_goal(self, x, y):
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(x)
        goal_msg.pose.pose.position.y = float(y)
        goal_msg.pose.pose.orientation.w = 1.0

        self.nav_client.wait_for_server()
        self.goal_done_event.clear()
        
        send_goal_future = self.nav_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('⚠️ 경로 생성 실패.')
            self.goal_done_event.set()
            return

        self.get_logger().info('주행 시작...')
        get_result_future = goal_handle.get_result_async()
        get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        self.get_logger().info('🏁 주행 완료! (바퀴 완전 정지)')
        self.goal_done_event.set()

    def run_sequence(self):
        while rclpy.ok():
            for spot in self.virtual_spots:
                if not spot["cleaned"] and spot["AQ"] > 35.0:
                    self.get_logger().info(f"🚨 타겟 이동 [X: {spot['x']:.2f}, Y: {spot['y']:.2f}]")
                    self.send_goal(spot["x"], spot["y"])
                    
                    self.goal_done_event.wait() # 물리적 도착 대기
                    
                    time.sleep(1)
                    self.get_logger().info("🔥 블로우팬 가동!")
                    self.relay_pub.publish(Bool(data=True))
                    
                    time.sleep(5) 
                    
                    self.get_logger().info("🍃 정화 완료 -> 팬 중지!")
                    self.relay_pub.publish(Bool(data=False))
                    spot["cleaned"] = True
                    spot["AQ"] = 20.0
                    time.sleep(1)
            
            if all(spot["cleaned"] for spot in self.virtual_spots):
                self.get_logger().info("🔄 모든 구역 정화 완료. 맵에 오염원을 재배치합니다.")
                self.virtual_spots.clear()
                self.generate_random_spots(3)
                time.sleep(1)

    def start_sequence(self):
        if not self.sequence_started:
            self.sequence_started = True
            threading.Thread(target=self.run_sequence, daemon=True).start()

def main(args=None):
    rclpy.init(args=args)
    node = VirtualCleaner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
