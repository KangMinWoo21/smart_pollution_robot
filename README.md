 ## 통합 실행

  시연과 테스트는 노트북에서 아래 명령 하나로 시작한다.

  ```bash
  ./run_demo.sh

  run_demo.sh는 항상 Raspberry Pi 쪽과 노트북 쪽을 함께 실행한다.

  Raspberry Pi 쪽에서 실행되는 것:

  - TurtleBot3 bringup
  - LDS /scan
  - odometry /odom
  - PMS7003 미세먼지 센서
  - relay / blower fan 제어
  - /dev/ttyS0 사용 전 serial-getty@ttyS0 정지

  노트북 쪽에서 실행되는 것:

  - Zenoh router
  - Nav2
  - rosbridge
  - web UI
  - map publisher
  - robot pose publisher
  - 외부 미세먼지 API node
  - real_cleaner.py

  통합 실행 후 확인할 기본 포트:

  - web: http://127.0.0.1:8000/
  - rosbridge: 9090
  - Zenoh: 7447

  기본 확인 토픽:

  ros2 topic list | grep -E '/scan|/odom|/pms7003/pm25|/hardware/relay|/air_quality/outdoor_pm25|/air_quality/adaptive_threshold'

  2D Pose Estimate가 잡히려면 /scan, /odom, TF가 먼저 살아 있어야 한다. 특히 odom -> base_footprint가 없으면 Raspberry Pi bringup이 제대로 실행되지 않
  은 상태다.

  ## 시연 설정

  시연장 자동 순찰 waypoint:

  3.07,4.98,-1.59
  3.00,1.25,0.05
  5.62,1.63,1.47
  7.50,5.19,-2.90
  5.42,4.68,3.01

  주방 집중 모드 waypoint:

  7.50,5.19,-2.90

  주방 집중이 정상 작동하면 real_cleaner.py 로그에 아래와 비슷하게 출력된다.

  집중 순찰 구역 변경: kitchen, 후보 1개

  현재 팬 ON 기준:

  기본 실내 PM2.5 기준: 50
  가습기 의심 기준: PM2.5 35 초과
  외부 미세먼지 나쁨: 48
  외부 미세먼지 매우 나쁨: 45

  외부 미세먼지는 창문이 닫힌 시연 환경을 기준으로 실내 기준을 소폭만 낮춘다.

  ## 외부 미세먼지 API

  사용 API:

  endpoint: http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty
  stationName: 복대동
  dataTerm: DAILY
  pageNo: 1
  numOfRows: 1
  returnType: json
  ver: 1.3
  json path: response.body.items.0.pm25Value

  외부 PM2.5 값은 /air_quality/outdoor_pm25로 publish되고 웹 UI에 표시된다.

  확인 명령:

  ros2 topic echo /air_quality/outdoor_pm25 --once

  ## 맵과 장애물 회피 설정

  run_demo.sh는 기본으로 원래 매핑한 linetrace_map.yaml을 사용한다. linetrace_map_dynamic.yaml은 가운데 장애물을 너무 많이 지워 Nav2가 실제 장애물 방향으로 경로를 만들 수 있으므로 기본값으로 쓰지 않는다.

  현재 Nav2는 demo_nav2_params.yaml을 사용한다. 이 파일은 정적 맵의 테두리와 기존 구조물은 유지하면서, local/global costmap의 scan obstacle_layer로 실제 LiDAR 장애물을 반영한다. 즉 가운데 배치가 약간 바뀐 경우에는 맵을 지우는 방식이 아니라 센서 기반 costmap으로 회피한다.

  장애물 근처에서 바로 멈추는 경우 확인 순서:

  - RViz에서 local_costmap과 global_costmap이 실제 장애물을 과하게 크게 표시하는지 확인
  - demo_nav2_params.yaml의 inflation_radius는 0.30m 기준이다. 너무 좁게 지나가면 0.35로 올리고, 너무 멀리서 멈추면 0.25로 낮춘다.
  - movement_time_allowance는 20초로 늘려 좁은 곳에서 바로 stuck 판정이 나지 않게 했다.
  - 정적 맵에 없는 새 장애물은 LiDAR로 회피하지만, 통로 전체를 막으면 우회 경로가 없어서 정지하는 것이 정상이다.

  ## 자주 나는 오류와 해결

  ### 웹이 안 뜸

  원인:

  - web server가 죽었거나 8000 포트가 열려 있지 않음
  - rosbridge가 죽어서 화면 데이터가 갱신되지 않음

  확인:

  curl -I http://127.0.0.1:8000/
  curl -I http://127.0.0.1:9090/

  해결:

  ./run_demo.sh

  또는 노트북 쪽만 재시작:

  USE_ZENOH=1 ./start_laptop.sh

  ### 2D Pose Estimate가 안 잡힘

  원인:

  - Raspberry Pi bringup이 죽음
  - /scan publisher 없음
  - /odom publisher 없음
  - odom -> base_footprint TF 없음
  - AMCL/Nav2는 떠 있지만 로봇 센서 데이터가 안 들어옴

  확인:

  ros2 topic info /scan
  ros2 topic info /odom
  ros2 run tf2_ros tf2_echo odom base_footprint

  해결:

  ./run_demo.sh

  또는 Pi 쪽만 재시작:

  ssh -t a@172.20.10.2 'cd /home/a/pollution_robot && USE_ZENOH=1 ZENOH_ROUTER_ENDPOINT=tcp/172.20.10.5:7447 PMS_PORT=/dev/ttyS0 ./
  start_raspberry_pi.sh'

  ### 주방 집중 모드가 전체 순찰처럼 보임

  원인:

  - 오래된 real_cleaner.py 프로세스가 살아 있음
  - 주방 bounds가 시연장 좌표와 맞지 않음
  - /target_zone이 kitchen으로 publish되지 않음

  확인:

  ros2 topic echo /target_zone --once

  정상 로그:

  집중 순찰 구역 변경: kitchen, 후보 1개

  해결:

  USE_ZENOH=1 ./start_laptop.sh

  ### PMS7003 센서가 안 뜸

  원인:

  - /dev/ttyS0를 serial-getty가 잡고 있음
  - Pi 쪽 PMS node가 죽음
  - Zenoh 연결이 안 됨

  확인:

  ros2 topic echo /pms7003/pm25 --once

  해결:

  ssh -t a@172.20.10.2 'sudo systemctl stop serial-getty@ttyS0.service'
  ssh -t a@172.20.10.2 'cd /home/a/pollution_robot && PMS_PORT=/dev/ttyS0 ./start_raspberry_pi.sh'

  ### 팬이 안 켜짐

  원인:

  - /hardware/relay node가 죽음
  - adaptive threshold보다 PM2.5가 낮음
  - Pi 쪽 relay 권한 문제

  확인:

  ros2 topic echo /air_quality/adaptive_threshold --once
  ros2 topic echo /hardware/relay --once

  수동 확인:

  ros2 topic pub --once /hardware/relay std_msgs/msg/Bool "{data: true}"

  ### 외부 미세먼지가 고정값으로 보임

  원인:

  - OUTDOOR_AIR_MODE=mock 상태
  - API key 또는 JSON path 오류
  - 공공데이터 API 응답 지연

  확인:

  ros2 topic echo /air_quality/outdoor_pm25 --once

  해결:

  OUTDOOR_AIR_MODE=api USE_ZENOH=1 ./start_laptop.sh

  ### Nav2 timeout

  원인:

  - map, AMCL, controller lifecycle node가 inactive
  - 초기 위치가 안 잡힘
  - /scan, /odom, TF가 없음
  - Zenoh discovery 지연

  확인:

  ros2 lifecycle get /controller_server
  ros2 lifecycle get /planner_server
  ros2 topic info /scan
  ros2 topic info /odom

  해결:

  ./run_demo.sh

  그 후 RViz에서 2D Pose Estimate를 다시 찍는다.

  ### bwrap 또는 sandbox timeout

  개발 중 아래 오류가 날 수 있다.

  bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted

  원인:

  - Codex 실행 sandbox가 네트워크 namespace를 만들지 못함
  - 긴 heredoc, 긴 파일쓰기, 긴 Perl 치환 명령이 자동 승인 검토에서 timeout됨

  해결:

  - 긴 파일쓰기는 한 번에 하지 말고 짧은 명령으로 나눠 실행
  - 큰 README 수정은 직접 붙여넣는 방식이 더 빠름
  - 실제 로봇 실행 명령은 일반 터미널에서 직접 실행하면 sandbox 영향을 받지 않음

