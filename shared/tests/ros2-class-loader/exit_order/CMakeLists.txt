cmake_minimum_required(VERSION 3.20)
project(class_loader_exit_order CXX)

set(CMAKE_CXX_STANDARD 17)
find_package(class_loader REQUIRED)

add_library(exit_order_plugin SHARED plugin.cpp)
target_link_libraries(exit_order_plugin class_loader::class_loader)

add_executable(exit_order main.cpp)
target_link_libraries(exit_order class_loader::class_loader)
target_compile_definitions(exit_order PRIVATE
  PLUGIN_PATH="$<TARGET_FILE:exit_order_plugin>")
add_dependencies(exit_order exit_order_plugin)
