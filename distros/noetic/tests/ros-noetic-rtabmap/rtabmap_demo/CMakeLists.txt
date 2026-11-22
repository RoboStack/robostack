# a program built against rtabmap's exported CMake config (RTABMapConfig.cmake asks for the
# OpenCV 5 components, see ros-noetic-rtabmap.patch)
cmake_minimum_required(VERSION 3.16)
project(rtabmap_demo CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(RTABMap REQUIRED)
add_executable(rtabmap_demo main.cpp)
target_link_libraries(rtabmap_demo rtabmap::core)
