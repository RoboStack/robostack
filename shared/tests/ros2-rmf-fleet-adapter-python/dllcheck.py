# Temporary diagnostic (Windows): load rmf_adapter's DLL dependencies one by one, in
# dependency order, to find the one whose initialisation fails.
import ctypes
import glob
import os

bindir = os.path.join(os.environ["PREFIX"], "Library", "bin")
os.add_dll_directory(bindir)
names = ["nlohmann_json_schema_validator", "json-schema-validator", "rmf_utils", "rmf_traffic",
         "rmf_battery", "rmf_task", "rmf_task_sequence", "rmf_websocket", "rmf_traffic_ros2",
         "rmf_task_ros2", "rmf_fleet_adapter"]
for name in names:
    for path in glob.glob(os.path.join(bindir, name + "*.dll")):
        try:
            ctypes.WinDLL(path)
            print("ok  ", os.path.basename(path), flush=True)
        except OSError as e:
            print("FAIL", os.path.basename(path), e, flush=True)
print([os.path.basename(p) for p in glob.glob(os.path.join(bindir, "*json*schema*"))])
