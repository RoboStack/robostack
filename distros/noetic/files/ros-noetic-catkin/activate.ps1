# ros-noetic-catkin: run on environment activation in PowerShell (bld_catkin.bat copies
# it to etc/conda). catkin's setup scripts are batch files only: run local_setup.bat in
# cmd.exe and take over the environment variables it sets (RoboStack/ros-noetic#21).
if ($null -eq ${env:CONDA_PREFIX}) { Exit }

# Don't do anything when we are in conda build.
if ($null -ne ${env:SYS_PREFIX}) { Exit 0 }

$Env:QT_PLUGIN_PATH = "${env:CONDA_PREFIX}\Library\plugins"

$setup = "${env:CONDA_PREFIX}\Library\local_setup.bat"
if (Test-Path $setup) {
    $before = @{}
    Get-ChildItem env: | ForEach-Object { $before[$_.Name] = $_.Value }
    cmd.exe /d /c "call `"$setup`" >nul 2>&1 && set" | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            if ($before[$Matches[1]] -cne $Matches[2]) {
                Set-Item -Path "env:$($Matches[1])" -Value $Matches[2]
            }
        }
    }
}

$Env:PYTHONHOME = ''
$Env:ROS_OS_OVERRIDE = 'conda:win64'
$Env:ROS_ETC_DIR = "${env:CONDA_PREFIX}\Library\etc\ros"
$Env:AMENT_PREFIX_PATH = "${env:CONDA_PREFIX}\Library"
$Env:AMENT_PYTHON_EXECUTABLE = "${env:CONDA_PREFIX}\python.exe"
