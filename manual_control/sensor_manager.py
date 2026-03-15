import os
import time
import cv2
import numpy as np
import carla
import json
import shutil
from config import DataConfig
from config import NAV_POINTS_FILE_PATH


class SensorManager:
    def __init__(self, vehicle, world, hud):
        self.vehicle = vehicle
        self.hud = hud
        self.world = world
        self.cfg = DataConfig()
        self.targets = []
        self.target_index = 0
        self.target_reached_threshold = 3.0
        self._load_navigation_points()
        self.cameras = {}
        self.rgb = [None, None, None]
        self.depth = [None, None, None]
        self.sem = [None, None, None]
        self.lidar_data = None
        self._setup_lidar()
        self.recording = False
        self.save_interval = 0.5
        self.last_save_time = 0
        self.frame = 0
        self.save_root = None
        self._setup_all_cameras()

    def _load_navigation_points(self):
        nav_file = NAV_POINTS_FILE_PATH
        if not os.path.exists(nav_file):
            print(f"导航文件不存在: {nav_file}，使用空列表")
            self.targets = []
            return
        with open(nav_file, 'r') as f:
            data = json.load(f)
        self.targets = data.get("targets", [])
        print(f"已加载 {len(self.targets)} 个目标点")

    def _setup_all_cameras(self):
        cfg = self.cfg
        w = str(cfg.camera_width)
        h = str(cfg.camera_height)
        fov = str(cfg.camera_fov)
        positions = {
            "front": carla.Rotation(yaw=0),
            "left": carla.Rotation(yaw=-60),
            "right": carla.Rotation(yaw=60)
        }
        for pos_name, rot in positions.items():
            trans = carla.Transform(
                carla.Location(*cfg.camera_pos),
                rot
            )
            bp = self.world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", w)
            bp.set_attribute("image_size_y", h)
            bp.set_attribute("fov", fov)
            cam = self.world.spawn_actor(bp, trans, attach_to=self.vehicle)
            cam.listen(lambda img, key=f"rgb_{pos_name}": self._on_image(img, key))
            self.cameras[f"rgb_{pos_name}"] = cam
            bp = self.world.get_blueprint_library().find("sensor.camera.depth")
            bp.set_attribute("image_size_x", w)
            bp.set_attribute("image_size_y", h)
            bp.set_attribute("fov", fov)
            cam = self.world.spawn_actor(bp, trans, attach_to=self.vehicle)
            cam.listen(lambda img, key=f"depth_{pos_name}": self._on_image(img, key))
            self.cameras[f"depth_{pos_name}"] = cam
            bp = self.world.get_blueprint_library().find("sensor.camera.semantic_segmentation")
            bp.set_attribute("image_size_x", w)
            bp.set_attribute("image_size_y", h)
            bp.set_attribute("fov", fov)
            cam = self.world.spawn_actor(bp, trans, attach_to=self.vehicle)
            cam.listen(lambda img, key=f"sem_{pos_name}": self._on_image(img, key))
            self.cameras[f"sem_{pos_name}"] = cam

    def _on_image(self, img, key):
        array = np.frombuffer(img.raw_data, dtype=np.uint8)
        array = array.reshape((img.height, img.width, 4))[:, :, :3].copy()
        if key.startswith("rgb"):
            if "front" in key:
                self.rgb[0] = array
            elif "left" in key:
                self.rgb[1] = array
            elif "right" in key:
                self.rgb[2] = array
        elif key.startswith("depth"):
            img.convert(carla.ColorConverter.Depth)
            if "front" in key:
                self.depth[0] = array
            elif "left" in key:
                self.depth[1] = array
            elif "right" in key:
                self.depth[2] = array
        elif key.startswith("sem"):
            img.convert(carla.ColorConverter.CityScapesPalette)
            if "front" in key:
                self.sem[0] = array
            elif "left" in key:
                self.sem[1] = array
            elif "right" in key:
                self.sem[2] = array

    def _is_ready(self, buffer):
        return all(x is not None for x in buffer)

    def _stitch_960x160(self, imgs):
        h = 160
        w = 320

        def center_crop(img):
            oh, ow = img.shape[:2]
            y1 = (oh - h) // 2
            x1 = (ow - w) // 2
            return img[y1:y1 + h, x1:x1 + w].copy()

        f = center_crop(imgs[0])
        l = center_crop(imgs[1])
        r = center_crop(imgs[2])
        return np.hstack([l, f, r])

    def _setup_lidar(self):
        bp = self.world.get_blueprint_library().find("sensor.lidar.ray_cast")
        bp.set_attribute("range", "50")
        bp.set_attribute("rotation_frequency", "20")
        bp.set_attribute("channels", "64")
        bp.set_attribute("upper_fov", "10")
        bp.set_attribute("lower_fov", "-30")
        bp.set_attribute("points_per_second", "100000")
        trans = carla.Transform(carla.Location(x=0.0, y=0.0, z=2.5))
        self.lidar = self.world.spawn_actor(bp, trans, attach_to=self.vehicle)
        self.lidar.listen(lambda data: self._on_lidar(data))

    def _on_lidar(self, data):
        points = np.frombuffer(data.raw_data, dtype=np.dtype("f4"))
        points = np.reshape(points, (-1, 4))
        self.lidar_data = points

    def toggle_recording(self, town_name):
        from config import ROOT_SAVE_DIR, DEFAULT_SCENARIO, DEFAULT_ROUTE
        self.recording = not self.recording
        if self.recording:
            self.frame = 0
            self.last_save_time = time.time()
            self.save_root = os.path.join(ROOT_SAVE_DIR, DEFAULT_SCENARIO, town_name, DEFAULT_ROUTE)
            if os.path.exists(self.save_root):
                import shutil
                print(f"删除旧数据文件夹: {self.save_root}")
                shutil.rmtree(self.save_root)  # 递归删除整个文件夹
            os.makedirs(os.path.join(self.save_root, "rgb"), exist_ok=True)
            os.makedirs(os.path.join(self.save_root, "depth"), exist_ok=True)
            os.makedirs(os.path.join(self.save_root, "semantics"), exist_ok=True)
            os.makedirs(os.path.join(self.save_root, "lidar"), exist_ok=True)
            os.makedirs(os.path.join(self.save_root, "measurements"), exist_ok=True)
            os.makedirs(os.path.join(self.save_root, "label_raw"), exist_ok=True)
            self.hud.notification("录制数据集", 2)
            print("保存路径:", self.save_root)
        else:
            self.hud.notification("停止录制", 2)

    def tick(self):
        if not self.recording:
            return
        now = time.time()
        if now - self.last_save_time < self.save_interval:
            return
        self.last_save_time = now
        if not self._is_ready(self.rgb): return
        if not self._is_ready(self.depth): return
        if not self._is_ready(self.sem): return
        if self.lidar_data is None: return
        name = f"{self.frame:04d}.png"
        name_npy = f"{self.frame:04d}.npy"
        name_json = f"{self.frame:04d}.json"
        rgb_out = self._stitch_960x160(self.rgb)
        depth_out = self._stitch_960x160(self.depth)
        sem_out = self._stitch_960x160(self.sem)
        cv2.imwrite(os.path.join(self.save_root, "rgb", name), rgb_out)
        cv2.imwrite(os.path.join(self.save_root, "depth", name), depth_out)
        cv2.imwrite(os.path.join(self.save_root, "semantics", name), sem_out)
        self._save_lidar(name_npy)
        self._save_measurements(name_json)
        self._save_labels(name_json)
        self.frame += 1

    def _save_lidar(self, name):
        lidar_path = os.path.join(self.save_root, "lidar", name)
        np.save(lidar_path, self.lidar_data)

    def _save_measurements(self, name):
        tf = self.vehicle.get_transform()
        vel = self.vehicle.get_velocity()
        ctrl = self.vehicle.get_control()
        speed = np.sqrt(vel.x ** 2 + vel.y ** 2)
        theta = np.radians(tf.rotation.yaw)
        if self.targets and self.target_index < len(self.targets):
            target_x, target_y = self.targets[self.target_index]
            dx = target_x - tf.location.x
            dy = target_y - tf.location.y
            dist = np.hypot(dx, dy)
            if dist < self.target_reached_threshold:
                self.target_index += 1
                if self.target_index >= len(self.targets):
                    print("所有目标点已完成，停留在最后一个点")
                    self.target_index = len(self.targets) - 1
            target_x, target_y = self.targets[self.target_index]
            x_command = target_x
            y_command = target_y
        else:
            x_command = 0.0
            y_command = 0.0
        ego_matrix = tf.get_matrix()
        ego_matrix = np.array(ego_matrix).reshape((4, 4)).tolist()
        meas = {
            "x": tf.location.x,
            "y": tf.location.y,
            "theta": theta,
            "speed": speed,
            "steer": ctrl.steer,
            "throttle": ctrl.throttle,
            "brake": ctrl.brake,
            "light_hazard": 0,
            "x_command": x_command,
            "y_command": y_command,
            "waypoints": [[0.0, 0.0] for _ in range(8)],
            "ego_matrix": ego_matrix
        }
        path = os.path.join(self.save_root, "measurements", name)
        with open(path, 'w') as f:
            json.dump(meas, f, indent=2)

    def _save_labels(self, name):
        ego_tf = self.vehicle.get_transform()
        ego_theta = np.radians(ego_tf.rotation.yaw)
        labels = []
        for actor in self.world.get_actors().filter("*vehicle*"):
            try:
                tf = actor.get_transform()
                bbox = actor.bounding_box
                extent = bbox.extent
                vel = actor.get_velocity()
                speed = np.sqrt(vel.x ** 2 + vel.y ** 2)
                dx = tf.location.x - ego_tf.location.x
                dy = tf.location.y - ego_tf.location.y
                yaw = np.radians(tf.rotation.yaw) - ego_theta
                label = {
                    "id": actor.id,
                    "position": [dx, dy, 0.0],
                    "extent": [extent.z, extent.x, extent.y],
                    "yaw": yaw,
                    "speed": speed,
                    "brake": 0.0,
                    "num_points": 10,
                    "distance": np.sqrt(dx ** 2 + dy ** 2),
                    "ego_matrix": np.eye(4).tolist()
                }
                labels.append(label)
            except:
                continue
        path = os.path.join(self.save_root, "label_raw", name)
        with open(path, 'w') as f:
            json.dump(labels, f, indent=2)

    def destroy(self):
        for cam in self.cameras.values():
            if cam: cam.destroy()
        if hasattr(self, 'lidar') and self.lidar:
            self.lidar.destroy()
        print("所有相机，LiDAR已销毁")
