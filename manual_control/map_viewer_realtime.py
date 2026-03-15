import cv2
import json
import threading
import os
from config import CONFIG_DATA, FIXED_MAP_FOLDER, PARAM_FILE_PATH, NAV_POINTS_FILE_PATH

vehicle_world_x = 0.0
vehicle_world_y = 0.0
update_lock = threading.Lock()


def world2pixel(world_x, world_y, calib_params):
    px_per_m_x = calib_params["px_per_m_x"]
    x_offset = calib_params["x_offset"]
    px_per_m_y = calib_params["px_per_m_y"]
    y_offset = calib_params["y_offset"]
    x_negative = calib_params["x_negative"]
    if x_negative:
        u = world_x * px_per_m_x + x_offset
    else:
        u = -world_x * px_per_m_x + x_offset
    v = world_y * px_per_m_y + y_offset
    return int(round(u)), int(round(v))


def update_vehicle_position(x, y):
    global vehicle_world_x, vehicle_world_y
    with update_lock:
        vehicle_world_x = x
        vehicle_world_y = y


def realtime_map_viewer():
    print("启动右下角小窗口")
    with open(PARAM_FILE_PATH, 'r', encoding='utf-8') as f:
        spawn_params = json.load(f)
    map_name = spawn_params["map"]
    spawn_x = spawn_params["x"]
    spawn_y = spawn_params["y"]
    with open(NAV_POINTS_FILE_PATH, 'r', encoding='utf-8') as f:
        nav_data = json.load(f)
    targets = nav_data["targets"]
    calib = CONFIG_DATA[map_name]
    map_path = os.path.join(FIXED_MAP_FOLDER, f"{map_name}.png")
    img = cv2.imread(map_path)
    if img is None:
        print(f"地图加载失败：{map_path}")
        return
    print(f"地图加载成功：{map_name}")
    img_copy = img.copy()
    img_h, img_w = img.shape[:2]
    spawn_u, spawn_v = world2pixel(spawn_x, spawn_y, calib)
    target_pixels = [world2pixel(x, y, calib) for x, y in targets]
    WINDOW_W = 320
    WINDOW_H = 320
    ZOOM = 2.0
    CARLA_W = 1280
    trajectory = []
    cv2.namedWindow("CARLA Map", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("CARLA Map", WINDOW_W, WINDOW_H)
    cv2.moveWindow("CARLA Map", CARLA_W - WINDOW_W - 10, 720 - WINDOW_H - 70)
    while True:
        with update_lock:
            x, y = vehicle_world_x, vehicle_world_y
        u, v = world2pixel(x, y, calib)
        trajectory.append((u, v))
        if len(trajectory) > 200:
            trajectory.pop(0)
        frame = img_copy.copy()
        cv2.circle(frame, (spawn_u, spawn_v), 6, (0, 0, 255), -1)
        prev = (spawn_u, spawn_v)
        for idx, (px, py) in enumerate(target_pixels):
            cv2.line(frame, prev, (px, py), (0, 255, 0), 2)
            cv2.circle(frame, (px, py), 4, (0, 255, 0), -1)
            prev = (px, py)
        for i in range(1, len(trajectory)):
            cv2.line(frame, trajectory[i - 1], trajectory[i], (255, 0, 255), 1)
        cv2.circle(frame, (u, v), 6, (255, 0, 0), -1)
        cv2.circle(frame, (u, v), 8, (255, 255, 255), 1)
        crop_size = int(WINDOW_W / ZOOM)
        x1 = max(0, u - crop_size // 2)
        y1 = max(0, v - crop_size // 2)
        x2 = min(img_w, x1 + crop_size)
        y2 = min(img_h, y1 + crop_size)
        crop = frame[y1:y2, x1:x2]
        show = cv2.resize(crop, (WINDOW_W, WINDOW_H))
        cv2.imshow("CARLA Map", show)
        key = cv2.waitKey(200) & 0xFF
        if key == ord('q'):
            break
    cv2.destroyAllWindows()


def start_realtime_map():
    t = threading.Thread(target=realtime_map_viewer, daemon=True)
    t.start()
