"""RoboStack smoke test of ROS 1 itself: roscore starts, a message published with rostopic
arrives (rospy, Python), and rosbag records and reads it (C++ tools: on macOS they load
librospack, see ros-noetic-rospack.patch)."""
import os
import subprocess
import sys
import tempfile
import time

env = dict(os.environ, ROS_MASTER_URI="http://localhost:11399", ROS_HOSTNAME="localhost")
work = tempfile.mkdtemp()
procs = []


def start(*cmd):
    p = subprocess.Popen(cmd, env=env, cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    procs.append(p)
    return p


def stop():
    for p in procs:
        if p.poll() is None:
            p.terminate()
    time.sleep(2)
    for p in procs:
        if p.poll() is None:
            p.kill()
        p.wait()


try:
    start("roscore", "-p", "11399")
    for _ in range(60):
        if subprocess.run(["rostopic", "list"], env=env, capture_output=True).returncode == 0:
            break
        time.sleep(1)
    else:
        sys.exit("roscore did not come up")
    start("rostopic", "pub", "-r", "5", "/chatter", "std_msgs/String", "data: robostack")
    echo = subprocess.run(["rostopic", "echo", "-n", "1", "/chatter"], env=env, capture_output=True,
                          text=True, timeout=60)
    if "robostack" not in echo.stdout:
        sys.exit("rostopic echo: " + echo.stdout + echo.stderr)
    subprocess.run(["rosbag", "record", "-O", "test.bag", "--duration=3", "/chatter"], env=env, cwd=work,
                   capture_output=True, timeout=60, check=True)
    info = subprocess.run(["rosbag", "info", "test.bag"], env=env, cwd=work, capture_output=True, text=True,
                          timeout=60, check=True)
    if "std_msgs/String" not in info.stdout:
        sys.exit("rosbag info: " + info.stdout)
    print("roscore, rostopic and rosbag work")
finally:
    stop()
