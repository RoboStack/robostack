# RoboStack's catkin compatibility for ROS 1 packages on conda-forge (ros-noetic-catkin.patch):
# a request for C++11 still builds as C++17, boost_system is found (Boost >= 1.89 has no
# such component), and find_package(Eigen3 3.3) finds Eigen 5 and sets EIGEN3_INCLUDE_DIRS.
cmake_minimum_required(VERSION 3.5)
project(compat_demo CXX)
add_compile_options(-std=c++11)
set(CMAKE_CXX_STANDARD 11)
find_package(catkin REQUIRED)
find_package(Boost REQUIRED COMPONENTS system thread)
find_package(Eigen3 3.3 REQUIRED)
if(NOT EIGEN3_INCLUDE_DIRS)
  message(FATAL_ERROR "EIGEN3_INCLUDE_DIRS is empty")
endif()
catkin_package()
include_directories(${EIGEN3_INCLUDE_DIRS} ${Boost_INCLUDE_DIRS})
add_executable(compat_demo main.cpp)
target_link_libraries(compat_demo ${Boost_LIBRARIES})
# catkin_package() sends executables to devel/lib/<project>; keep it where the test runs it
set_target_properties(compat_demo PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
