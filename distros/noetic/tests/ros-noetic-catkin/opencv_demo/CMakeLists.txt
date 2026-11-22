# RoboStack's catkin maps OpenCV requests as ROS 1 packages write them to OpenCV 5
# (ros-noetic-catkin.patch): the version 4 is dropped, calib3d becomes calib, geometry and
# stereo, features2d becomes features, and imgproc also brings geometry.
cmake_minimum_required(VERSION 3.5)
project(opencv_demo CXX)
find_package(catkin REQUIRED)
find_package(OpenCV 4 REQUIRED COMPONENTS core imgproc calib3d features2d)
catkin_package()
include_directories(${OpenCV_INCLUDE_DIRS})
add_executable(opencv_demo main.cpp)
target_link_libraries(opencv_demo ${OpenCV_LIBS})
# catkin_package() sends executables to devel/lib/<project>; keep it where the test runs it
set_target_properties(opencv_demo PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
