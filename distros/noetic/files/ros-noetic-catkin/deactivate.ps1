# ros-noetic-catkin: run on environment deactivation in PowerShell (bld_catkin.bat copies
# it to etc/conda); the counterpart of deactivate.bat.
if ($null -eq ${env:CONDA_PREFIX}) { Exit }

foreach ($name in 'ROS_OS_OVERRIDE', 'ROS_DISTRO', 'ROS_ETC_DIR', 'ROS_PACKAGE_PATH',
                  'ROS_PYTHON_VERSION', 'ROS_VERSION', 'PYTHONHOME', 'PYTHONPATH',
                  'CMAKE_PREFIX_PATH', 'AMENT_PREFIX_PATH', 'COLCON_PREFIX_PATH',
                  'QT_PLUGIN_PATH', 'ROS_LOCALHOST_ONLY', 'AMENT_PYTHON_EXECUTABLE') {
    Remove-Item -Path "env:$name" -ErrorAction SilentlyContinue
}
