# config.py
import os

BASE_DIR = r"E:/My_Gap_Year/onsite/carla_manual_control/carla_manual_control"
# 只需要更换这里为你的根目录即可使用


class DataConfig:
    seq_len = 1
    img_seq_len = 1
    lidar_seq_len = 1
    pred_len = 4
    scale = 1
    img_resolution = (160, 704)
    img_width = 320
    lidar_resolution_width = 256
    lidar_resolution_height = 256
    pixels_per_meter = 8.0
    lidar_pos = [1.3, 0.0, 2.5]
    lidar_rot = [0.0, 0.0, -90.0]

    camera_pos = [1.3, 0.0, 2.3]
    camera_width = 960
    camera_height = 480
    camera_fov = 120
    camera_rot_0 = [0.0, 0.0, 0.0]
    camera_rot_1 = [0.0, 0.0, -60.0]
    camera_rot_2 = [0.0, 0.0, 60.0]

    bev_resolution_width = 160
    bev_resolution_height = 160
    use_target_point_image = False
    gru_concat_target_point = True
    augment = True
    inv_augment_prob = 0.1
    aug_max_rotation = 20
    debug = False
    sync_batch_norm = False
    train_debug_save_freq = 50
    bb_confidence_threshold = 0.3


CONFIG_DATA = {
    "Town01": {"map_size": 3987, "px_per_m_x": 8.00, "x_offset": 417.0, "px_per_m_y": 8.00, "y_offset": 417.0,
               "x_negative": True},
    "Town02": {"map_size": 2409, "px_per_m_x": 8.00, "x_offset": 461.0, "px_per_m_y": 8.00, "y_offset": -442.0,
               "x_negative": True},
    "Town03": {"map_size": 4135, "px_per_m_x": 8.00, "x_offset": 1591, "px_per_m_y": 8.00, "y_offset": 2073,
               "x_negative": True},
    "Town04": {"map_size": 8235, "px_per_m_x": 8.00, "x_offset": 4520, "px_per_m_y": 8.00, "y_offset": 3569,
               "x_negative": True},
    "Town05": {"map_size": 4696, "px_per_m_x": 8.00, "x_offset": 2608.0, "px_per_m_y": 8.00, "y_offset": 2062.0,
               "x_negative": True},
    "Town06": {"map_size": 9149, "px_per_m_x": 8.00, "x_offset": 3364, "px_per_m_y": 8.00, "y_offset": 1618,
               "x_negative": True},
    "Town07": {"map_size": 3785, "px_per_m_x": 8.00, "x_offset": 2038, "px_per_m_y": 8.00, "y_offset": 2395,
               "x_negative": True},
    "Town10HD": {"map_size": 2596, "px_per_m_x": 8.00, "x_offset": 1318, "px_per_m_y": 8.00, "y_offset": 948,
                 "x_negative": True}
}

ROOT_SAVE_DIR = "data"
DEFAULT_SCENARIO = "Scenario1"
DEFAULT_ROUTE = "Route001"
ROUTE_IMAGE_DIR = os.path.join(BASE_DIR, "Route")
FIXED_MAP_FOLDER = os.path.join(BASE_DIR, "png_of_maps")
PARAM_FILE_PATH = os.path.join(BASE_DIR, "temporary", "carla_spawn_params.json")
NAV_POINTS_FILE_PATH = os.path.join(BASE_DIR, "temporary", "navigation_points.json")
SAVE_ROUTE_FOLDER = os.path.join(BASE_DIR, "Route")
SCENARIO_FOLDER = os.path.join(BASE_DIR, "data", "Scenario1")
config_path = os.path.join(BASE_DIR, "config.py")
