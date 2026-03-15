import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import os
import re
import json
import math
import glob
from config import CONFIG_DATA, FIXED_MAP_FOLDER, PARAM_FILE_PATH, NAV_POINTS_FILE_PATH, SAVE_ROUTE_FOLDER, \
    SCENARIO_FOLDER

scale = 1.0
offset_x = 0
offset_y = 0
drag = False
drag_start = (0, 0)

map_img_original = None
map_img_copy = None
map_img_display = None
current_map_name = ""
current_calib_params = {}
select_phase = 1
first_point = {"pixel": (0, 0), "world": (0.0, 0.0)}
second_point = {"pixel": (0, 0), "world": (0.0, 0.0)}
navigation_points = []
theta_value = 0.0


def pixel2world(pixel_u, pixel_v, calib_params):
    px_per_m_x = calib_params["px_per_m_x"]
    x_offset = calib_params["x_offset"]
    px_per_m_y = calib_params["px_per_m_y"]
    y_offset = calib_params["y_offset"]
    x_negative = calib_params["x_negative"]
    world_x = (pixel_u - x_offset) / px_per_m_x
    if not x_negative:
        world_x = -world_x
    world_y = (pixel_v - y_offset) / px_per_m_y
    return round(world_x, 3), round(world_y, 3)


def calculate_theta_from_two_points(world_x1, world_y1, world_x2, world_y2):
    dx = world_x2 - world_x1
    dy = world_y2 - world_y1
    radian = math.atan2(dy, dx)
    theta = math.degrees(radian)
    if theta < 0:
        theta += 360.0
    return round(theta, 1)


def calculate_distance(world1, world2):
    dx = world1[0] - world2[0]
    dy = world1[1] - world2[1]
    return math.hypot(dx, dy)


def save_spawn_params(world_x, world_y, map_name, z=0.5, theta=0.0, npc_vehicles=0, npc_pedestrians=0):
    params = {
        "x": world_x, "y": world_y, "z": z, "theta": theta,
        "map": map_name, "npc_vehicles": npc_vehicles, "npc_pedestrians": npc_pedestrians
    }
    try:
        with open(PARAM_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(params, f, indent=4)
        print(f"出生参数已保存到：{PARAM_FILE_PATH}")
    except Exception as e:
        messagebox.showerror("错误", f"保存出生参数失败：{e}")


def save_navigation_points():
    global first_point, theta_value, navigation_points
    spawn_world = first_point["world"]
    targets = [p["world"] for p in navigation_points]
    data = {
        "spawn": {"x": spawn_world[0], "y": spawn_world[1], "theta": theta_value},
        "targets": targets
    }
    try:
        with open(NAV_POINTS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"导航点已保存到：{NAV_POINTS_FILE_PATH}")
        messagebox.showinfo("完成", f"导航点保存成功！共 {len(targets)} 个目标点。")
    except Exception as e:
        messagebox.showerror("错误", f"保存导航点失败：{e}")


def get_next_route_name(town_name):
    """基于 data/Scenario1/TownName/ 下的 Routexxx 文件夹确定下一个编号"""
    scenario_town_path = os.path.join(SCENARIO_FOLDER, town_name)
    if not os.path.exists(scenario_town_path):
        return "Route001"
    # 匹配 Routexxx 文件夹（不包含扩展名）
    pattern = os.path.join(scenario_town_path, "Route[0-9][0-9][0-9]")
    existing_folders = glob.glob(pattern)
    max_num = 0
    for f in existing_folders:
        folder_name = os.path.basename(f)
        # 提取最后三位数字
        num_str = folder_name[-3:]
        if num_str.isdigit():
            num = int(num_str)
            if num > max_num:
                max_num = num
    next_num = max_num + 1
    return f"Route{next_num:03d}"


def update_config_default_route(route_name):
    from config import config_path
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        replaced = False
        for line in lines:
            if line.strip().startswith("DEFAULT_ROUTE"):
                new_lines.append(f'DEFAULT_ROUTE = "{route_name}"\n')
                replaced = True
            else:
                new_lines.append(line)
        if not replaced:
            new_lines.append(f'\nDEFAULT_ROUTE = "{route_name}"\n')
        with open(config_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"config.py 已更新：DEFAULT_ROUTE = \"{route_name}\"")
    except Exception as e:
        print(f"更新 config.py 失败：{e}")


def save_route_map():
    global map_img_original, first_point, navigation_points, current_map_name
    route_name = get_next_route_name(current_map_name)
    save_img = map_img_original.copy()
    if first_point["pixel"] != (0, 0):
        u, v = first_point["pixel"]
        cv2.circle(save_img, (u, v), 6, (0, 0, 255), -1)
    points_pixel = [first_point["pixel"]]
    for p in navigation_points:
        points_pixel.append(p["pixel"])
    for i in range(len(points_pixel) - 1):
        cv2.line(save_img, points_pixel[i], points_pixel[i + 1], (0, 255, 0), 2)
    for idx, p in enumerate(navigation_points, 1):
        u, v = p["pixel"]
        cv2.circle(save_img, (u, v), 5, (0, 255, 0), -1)
        cv2.putText(save_img, f"#{idx}", (u + 8, v - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    town_folder = os.path.join(SAVE_ROUTE_FOLDER, current_map_name)
    if not os.path.exists(town_folder):
        os.makedirs(town_folder)
    filename = f"{route_name}.png"
    save_path = os.path.join(town_folder, filename)
    cv2.imwrite(save_path, save_img)
    update_config_default_route(route_name)
    print(f"\n路线图已保存：{save_path}")
    messagebox.showinfo("路线保存", f"路线图已保存：\n{current_map_name}/{filename}")


def get_height_input(world_x, world_y, theta):
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    z_input = simpledialog.askfloat("输入高度(Z轴)",
                                    f"生成位置：X={world_x}, Y={world_y}\n朝向角度：{theta}°\n车辆生成高度（米，默认0.5）：",
                                    minvalue=0.0, maxvalue=10.0, initialvalue=0.5)
    z = z_input if z_input is not None else 0.5
    root.destroy()
    return z


def get_npc_count_input():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    npc_vehicles_input = simpledialog.askinteger("NPC车辆数量", "请输入要生成的自动驾驶NPC车辆数量（默认0，最大100）：",
                                                 minvalue=0, maxvalue=100, initialvalue=0)
    npc_vehicles = npc_vehicles_input if npc_vehicles_input is not None else 0
    npc_pedestrians_input = simpledialog.askinteger("NPC行人数量",
                                                    f"NPC车辆数量已设为：{npc_vehicles}辆\n请输入要生成的NPC行人数量（默认0，最大200）：",
                                                    minvalue=0, maxvalue=200, initialvalue=0)
    npc_pedestrians = npc_pedestrians_input if npc_pedestrians_input is not None else 0
    root.destroy()
    return npc_vehicles, npc_pedestrians


def extract_map_name_from_filename(filename):
    name_without_ext = os.path.splitext(filename)[0]
    match = re.match(r"(Town\d+HD?)(_|$)", name_without_ext)
    return match.group(1) if match else name_without_ext


def mouse_event_handler(event, x, y, flags, param):
    global scale, offset_x, offset_y, drag, drag_start, map_img_copy
    global select_phase, first_point, second_point, navigation_points, theta_value
    if event == cv2.EVENT_RBUTTONDOWN:
        drag = True
        drag_start = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE and drag:
        dx = x - drag_start[0]
        dy = y - drag_start[1]
        offset_x += dx / scale
        offset_y += dy / scale
        drag_start = (x, y)
        update_display()
    elif event == cv2.EVENT_RBUTTONUP:
        drag = False
    elif event == cv2.EVENT_MOUSEWHEEL:
        if map_img_original is None: return
        mouse_x = (x - offset_x) / scale
        mouse_y = (y - offset_y) / scale
        if flags > 0:
            scale *= 1.2
        else:
            scale /= 1.2
        scale = np.clip(scale, 0.1, 10.0)
        offset_x = x - mouse_x * scale
        offset_y = y - mouse_y * scale
        update_display()
    elif event == cv2.EVENT_LBUTTONDOWN:
        if map_img_original is None or not current_calib_params:
            messagebox.showwarning("警告", "需要先加载地图")
            return
        original_u = (x - offset_x) / scale
        original_v = (y - offset_y) / scale
        map_size = current_calib_params["map_size"]
        if not (0 <= original_u < map_size and 0 <= original_v < map_size):
            return
        original_u = int(round(original_u))
        original_v = int(round(original_v))
        world_x, world_y = pixel2world(original_u, original_v, current_calib_params)
        if select_phase == 1:
            first_point["pixel"] = (original_u, original_v)
            first_point["world"] = (world_x, world_y)
            cv2.circle(map_img_copy, (original_u, original_v), 6, (0, 0, 255), -1)
            cv2.putText(map_img_copy, f"birth({world_x},{world_y})", (original_u + 10, original_v - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            update_display()
            print(f"\n已选出生点：x={world_x}, y={world_y}")
            messagebox.showinfo("阶段1完成", "已确定出生点，请点击第二个点确定车辆朝向")
            select_phase = 2
        elif select_phase == 2:
            world_x1, world_y1 = first_point["world"]
            theta_value = calculate_theta_from_two_points(world_x1, world_y1, world_x, world_y)
            second_point["pixel"] = (original_u, original_v)
            second_point["world"] = (world_x, world_y)
            first_pixel = first_point["pixel"]
            cv2.circle(map_img_copy, (original_u, original_v), 6, (255, 0, 0), -1)
            cv2.line(map_img_copy, first_pixel, (original_u, original_v), (0, 255, 255), 2)
            cv2.putText(map_img_copy, f"theta:{theta_value}°", (original_u + 10, original_v - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            update_display()
            print(f"\n已选朝向点：x={world_x}, y={world_y}")
            print(f"朝向角度：{theta_value}°")
            z = get_height_input(world_x1, world_y1, theta_value)
            npc_vehicles, npc_pedestrians = get_npc_count_input()
            save_spawn_params(world_x1, world_y1, current_map_name, z, theta_value, npc_vehicles, npc_pedestrians)
            navigation_points = []
            messagebox.showinfo("阶段2完成",
                                "出生点已保存。\n现在开始选择导航点：\n- 每点左键添加，距离需40-60米\n- Enter撤销上一个点\n- Tab结束并保存")
            select_phase = 3
            redraw_all_markers()
        elif select_phase == 3:
            if navigation_points:
                ref_world = navigation_points[-1]["world"]
            else:
                ref_world = first_point["world"]
            new_point = (world_x, world_y)
            dist = calculate_distance(ref_world, new_point)
            if 40.0 <= dist <= 60.0:
                navigation_points.append({"pixel": (original_u, original_v), "world": new_point})
                redraw_all_markers()
                print(f"导航点 #{len(navigation_points)} 添加成功，距离参考点 {dist:.1f}m")
            else:
                messagebox.showwarning("距离不符", f"该点与上一个点距离为 {dist:.1f} 米，必须在40-60米之间！")


def handle_keypress(key):
    global select_phase, navigation_points, map_img_copy
    if key == 13 and select_phase == 3:
        if navigation_points:
            navigation_points.pop()
            print(f"已撤销最后一个导航点，剩余 {len(navigation_points)} 个点")
            redraw_all_markers()
        else:
            print("没有可撤销的导航点")
    elif key == 9 and select_phase == 3:
        save_navigation_points()
        save_route_map()
        messagebox.showinfo("提示", "导航点&路线图已保存！")


def redraw_all_markers():
    global map_img_copy, map_img_original
    map_img_copy = map_img_original.copy()
    if first_point["pixel"] != (0, 0):
        u1, v1 = first_point["pixel"]
        cv2.circle(map_img_copy, (u1, v1), 6, (0, 0, 255), -1)
        wx, wy = first_point["world"]
        cv2.putText(map_img_copy, f"birth({wx},{wy})", (u1 + 10, v1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255),
                    2)
    if second_point["pixel"] != (0, 0):
        u2, v2 = second_point["pixel"]
        u1, v1 = first_point["pixel"]
        cv2.circle(map_img_copy, (u2, v2), 6, (255, 0, 0), -1)
        cv2.line(map_img_copy, (u1, v1), (u2, v2), (0, 255, 255), 2)
        cv2.putText(map_img_copy, f"theta:{theta_value}°", (u2 + 10, v2 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 0, 0), 2)
    all_points = [first_point] + navigation_points
    for i in range(len(all_points) - 1):
        cv2.line(map_img_copy, all_points[i]["pixel"], all_points[i + 1]["pixel"], (0, 255, 0), 2)
    for idx, p in enumerate(navigation_points, 1):
        u, v = p["pixel"]
        cv2.circle(map_img_copy, (u, v), 5, (0, 255, 0), -1)
        cv2.putText(map_img_copy, f"#{idx}", (u + 8, v - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    if select_phase == 3 and current_calib_params is not None:
        px_per_m = current_calib_params["px_per_m_x"]
        r40 = int(40 * px_per_m)
        r50 = int(50 * px_per_m)
        r60 = int(60 * px_per_m)
        if len(navigation_points) > 0:
            center = navigation_points[-1]["pixel"]
        else:
            center = first_point["pixel"]
        cv2.circle(map_img_copy, center, r40, (0, 255, 255), 1)
        cv2.circle(map_img_copy, center, r50, (255, 0, 255), 1)
        cv2.circle(map_img_copy, center, r60, (255, 255, 255), 1)
    update_display()


def update_display():
    global map_img_original, map_img_display, offset_x, offset_y, scale
    if map_img_original is None: return
    h, w = map_img_original.shape[:2]
    new_w = int(w * scale)
    new_h = int(h * scale)
    img_scaled = cv2.resize(map_img_copy, (new_w, new_h))
    canvas_h, canvas_w = 1000, 1000
    map_img_display = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    x1 = int(max(0, -offset_x))
    y1 = int(max(0, -offset_y))
    x2 = int(min(new_w, canvas_w - offset_x))
    y2 = int(min(new_h, canvas_h - offset_y))
    canvas_x1 = int(max(0, offset_x))
    canvas_y1 = int(max(0, offset_y))
    canvas_x2 = canvas_x1 + (x2 - x1)
    canvas_y2 = canvas_y1 + (y2 - y1)
    if x1 < x2 and y1 < y2:
        map_img_display[canvas_y1:canvas_y2, canvas_x1:canvas_x2] = img_scaled[y1:y2, x1:x2]
    phase_names = ["", "Phase1:born_point", "Phase2:direction", f"Phase3:navigation_point(selected{len(navigation_points)}个)"]
    cv2.putText(map_img_display, f"Phase: {phase_names[select_phase]}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (255, 255, 255), 2)
    cv2.putText(map_img_display, f"Scale: {scale:.2f}x | Map: {current_map_name}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (200, 200, 200), 1)
    cv2.imshow(f"Map Coordinate Tool - {current_map_name}", map_img_display)


def load_map_auto_match():
    global map_img_original, map_img_copy, map_img_display, current_map_name, current_calib_params
    global select_phase, first_point, second_point, navigation_points, theta_value
    if not os.path.exists(FIXED_MAP_FOLDER):
        raise FileNotFoundError(f"固定地图文件夹不存在：{FIXED_MAP_FOLDER}")
    root = tk.Tk()
    root.withdraw()
    map_path = filedialog.askopenfilename(title="选择地图图片文件", initialdir=FIXED_MAP_FOLDER,
                                          filetypes=[("Image Files", "*.png *.jpg *.jpeg *.tga *.bmp"),
                                                     ("All Files", "*.*")])
    if not map_path:
        raise ValueError("未选择地图文件！")
    map_img_original = cv2.imread(map_path)
    if map_img_original is None:
        raise ValueError(f"无法加载地图文件：{map_path}")
    filename = os.path.basename(map_path)
    current_map_name = extract_map_name_from_filename(filename)
    if current_map_name not in CONFIG_DATA:
        raise ValueError(f"未找到{current_map_name}的校准配置！")
    current_calib_params = CONFIG_DATA[current_map_name]
    map_img_copy = map_img_original.copy()
    map_img_display = map_img_copy.copy()
    global scale, offset_x, offset_y
    scale = 1.0
    offset_x = 0
    offset_y = 0
    select_phase = 1
    first_point = {"pixel": (0, 0), "world": (0.0, 0.0)}
    second_point = {"pixel": (0, 0), "world": (0.0, 0.0)}
    navigation_points = []
    theta_value = 0.0
    print(f"成功加载地图：{filename}")
    print(f"自动匹配配置：{current_map_name}")
    return map_path


if __name__ == "__main__":
    try:
        load_map_auto_match()
        cv2.namedWindow(f"Map Coordinate Tool - {current_map_name}", cv2.WINDOW_NORMAL)
        cv2.resizeWindow(f"Map Coordinate Tool - {current_map_name}", 1000, 1000)
        cv2.setMouseCallback(f"Map Coordinate Tool - {current_map_name}", mouse_event_handler)
        update_display()
        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            else:
                handle_keypress(key)
    except Exception as e:
        print(f"程序出错：{e}")
    finally:
        cv2.destroyAllWindows()
