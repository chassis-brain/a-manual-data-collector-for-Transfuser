import os
import json
import glob


def fill_waypoints_auto(root_dir):
    meas_dir = os.path.join(root_dir, "measurements")

    if not os.path.isdir(meas_dir):
        print(f"未找到measurements文件夹: {meas_dir}")
        return

    json_files = sorted(glob.glob(os.path.join(meas_dir, "*.json")))
    if not json_files:
        print("没有找到json文件")
        return

    total_frames = len(json_files)
    print(f"共 {total_frames} 帧 measurements，开始填充 waypoints...")

    # 先把所有帧的 x,y 读出来
    frames_xy = []
    for fpath in json_files:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        x = data["x"]
        y = data["y"]
        frames_xy.append((x, y))

    if not frames_xy:
        print("无有效坐标")
        return

    last_x, last_y = frames_xy[-1]

    # 逐帧处理
    for idx, fpath in enumerate(json_files):
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        wp = []
        for i in range(1, 9):  # 未来 1~8 帧
            target_idx = idx + i
            if target_idx < total_frames:
                x, y = frames_xy[target_idx]
            else:
                x, y = last_x, last_y
            wp.append([x, y])

        data["waypoints"] = wp

        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    print("waypoints填充全部完成！\n")
