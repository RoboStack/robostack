# ros-noetic-catkin: run on environment activation (build_catkin.sh copies it to etc/conda)
# if [ -z "${CONDA_PREFIX}" ]; then
#     exit 0;
# fi

# Not sure if this is necessary on UNIX?
# export QT_PLUGIN_PATH=$CONDA_PREFIX\plugins

if [ "$CONDA_BUILD" = "1" -a "$target_platform" != "$build_platform" ]; then
    # ignore sourcing
    echo "Not activating ROS when cross-compiling";
else
    source $CONDA_PREFIX/setup.sh
fi

case "$OSTYPE" in
  darwin*)  export ROS_OS_OVERRIDE="conda:osx";;
  linux*)   export ROS_OS_OVERRIDE="conda:linux";;
esac

export ROS_ETC_DIR=$CONDA_PREFIX/etc/ros
export AMENT_PREFIX_PATH=$CONDA_PREFIX

# Looks unnecessary for UNIX
# unset PYTHONHOME=
