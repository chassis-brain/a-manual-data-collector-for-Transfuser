# 一个用于手动控制的Transfuser数据采集工具
代码基于carla中manual_control.py实现手动控制，添加地图标点自定义出生点、方向、高度、npc设置以及导航点的手动选择
用于丰富transfuser数据集，方便构造多种长尾场景
用法：
a.将config.py的base路径改为您的根目录文件夹地址
b.先运行point文件，用于设定上述手动选择；

     地图坐标工具使用说明
     1. 鼠标滚轮 → 缩放，右键拖拽 → 平移
     2. 左键点击：阶段1选出生点（红），阶段2选朝向点（蓝），阶段3选导航点（绿）
     3. 键盘：Enter撤销导航点，Tab结束保存，q退出
     4. 出生参数保存：{PARAM_FILE_PATH}
     5. 导航点保存：{NAV_POINTS_FILE_PATH}
     6. 路线图保存：{SAVE_ROUTE_FOLDER}/TownName/Routexxx.png
     7. 编号依据：{SCENARIO_FOLDER}/TownName/Routexxx 文件夹

c.再运行main文件，r键开始采集，其余键设置与原生代码相同

    W            : throttle
    S            : brake
    A/D          : steer left/right
    Q            : toggle reverse
    Space        : hand-brake
    P            : toggle autopilot
    M            : toggle manual transmission
    ,/.          : gear up/down
    CTRL + W     : toggle constant velocity mode at 60 km/h
    L            : toggle next light type
    SHIFT + L    : toggle high beam
    Z/X          : toggle right/left blinker
    I            : toggle interior light
    TAB          : change sensor position
    ` or N       : next sensor
    [1-9]        : change to sensor [1-9]
    G            : toggle radar visualization
    C            : change weather (Shift+C reverse)
    Backspace    : change vehicle
    O            : open/close all doors of vehicle
    T            : toggle vehicle's telemetry
    V            : Select next map layer (Shift+V reverse)
    B            : Load current selected map layer (Shift+B to unload)
    R            : toggle recording images to disk
    CTRL + R     : toggle recording of simulation (replacing any previous)
    CTRL + P     : start replaying last recorded simulation
    CTRL + +     : increments the start time of the replay by 1 second (+SHIFT = 10 seconds)
    CTRL + -     : decrements the start time of the replay by 1 second (+SHIFT = 10 seconds)
    F1           : toggle HUD
    H/?          : toggle help
    ESC          : quit 

如果想改造成其他模型适用的数据集，只需要修改sensor_manager.py文件