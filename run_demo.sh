#!/bin/bash

# 공통 도메인 ID 설정
export ROS_DOMAIN_ID=30
export TURTLEBOT3_MODEL=waffle
export LDS_MODEL=LDS-02

# 1. 터틀봇 브링업 (로봇 쪽에도 도메인 ID 전달)
gnome-terminal --title="1. Robot Bringup" -- bash -c "ssh -t a@172.20.10.2 'export ROS_DOMAIN_ID=30 && export TURTLEBOT3_MODEL=waffle && export LDS_MODEL=LDS-02 && source /opt/ros/humble/setup.bash && ros2 launch turtlebot3_bringup robot.launch.py'; exec bash"

sleep 6

# 2. 미세먼지 센서 및 팬 제어
gnome-terminal --title="2. Dust Sensor & Fan" -- bash -c "ssh -t a@172.20.10.2 'python3 ~/smart_air_purifier.py'; exec bash"

sleep 2

# 3. SLAM 맵핑 (노트북 로컬)
gnome-terminal --title="3. SLAM Mapping" -- bash -c "export ROS_DOMAIN_ID=30 && export TURTLEBOT3_MODEL=waffle && ros2 launch turtlebot3_cartographer cartographer.launch.py; exec bash"

sleep 2

# 4. 키보드 조종기 (노트북 로컬)
gnome-terminal --title="4. Teleop Control" -- bash -c "export ROS_DOMAIN_ID=30 && export TURTLEBOT3_MODEL=waffle && ros2 run turtlebot3_teleop teleop_keyboard; exec bash"

echo "도메인 ID 30으로 모든 시스템 동기화 완료!"
