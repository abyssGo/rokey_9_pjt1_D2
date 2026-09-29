cmake_minimum_required(VERSION 3.8)
project(cobot_msgs)

# 메시지 정의만 담는 패키지다. 기능 함수의 약속(인자·반환·코드)은 cobot_api 에 있다.
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)   # FlowState/FlowEvent/WeighLive 의 stamp

# IRD v3.0 (구조 변경: 기능 사이 호출은 서비스가 아니라 파이썬 함수 → srv 12개 삭제, 함수 약속은 cobot_api 패키지)
# 정본은 이 패키지의 msg/ (IRD §7)
rosidl_generate_interfaces(${PROJECT_NAME}
  # --- msg 3 (flow_node → HMI) ---
  "msg/FlowState.msg"
  "msg/FlowEvent.msg"
  "msg/WeighLive.msg"
  DEPENDENCIES builtin_interfaces
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()
