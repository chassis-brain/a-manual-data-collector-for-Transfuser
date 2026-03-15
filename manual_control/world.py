import carla
import sys
import random
import os
from fill_waypoints import fill_waypoints_auto
from utils import find_weather_presets, get_actor_display_name
from sensors import (
    CollisionSensor,
    LaneInvasionSensor,
    GnssSensor,
    IMUSensor,
    RadarSensor,
    CameraManager
)


class World(object):
    def __init__(self, client, carla_world, hud, args, npc_vehicle_count=0, npc_pedestrian_count=0):
        self.client = client
        self.world = carla_world
        self.map = self.world.get_map()
        self.sync = args.sync
        self.actor_role_name = args.rolename
        self.custom_x = args.x
        self.custom_y = args.y
        self.custom_z = args.z if args.z is not None else 0.5
        self.custom_theta = args.theta if args.theta is not None else 0.0
        self.npc_vehicles = []
        self.npc_pedestrians = []
        self.npc_vehicle_count = npc_vehicle_count
        self.npc_pedestrian_count = npc_pedestrian_count
        try:
            self.traffic_manager = self.client.get_trafficmanager(8000)
            self.traffic_manager.set_global_distance_to_leading_vehicle(2.0)
            self.traffic_manager.set_synchronous_mode(self.sync)
        except Exception as e:
            print(f"获取Traffic Manager失败：{e}，NPC车辆将无法启用自动驾驶")
            self.traffic_manager = None
        self.hud = hud
        self.player = None
        self.collision_sensor = None
        self.lane_invasion_sensor = None
        self.gnss_sensor = None
        self.imu_sensor = None
        self.radar_sensor = None
        self.camera_manager = None
        self._weather_presets = find_weather_presets()
        self._weather_index = 0
        self._actor_filter = args.filter
        self._actor_generation = args.generation
        self._gamma = args.gamma
        self.recording_enabled = False
        self.recording_start = 0
        self.frame = 0
        self.snapshot = None
        self._vehicles = None
        self._walkers = None
        self._spectator = self.world.get_spectator()
        self._map_layer = 0
        self._map_layer_names = [
            carla.MapLayer.NONE,
            carla.MapLayer.Buildings,
            carla.MapLayer.Decals,
            carla.MapLayer.Foliage,
            carla.MapLayer.Ground,
            carla.MapLayer.ParkedVehicles,
            carla.MapLayer.Particles,
            carla.MapLayer.Props,
            carla.MapLayer.StreetLights,
            carla.MapLayer.Walls,
            carla.MapLayer.All
        ]
        try:
            self.restart()
            self.spawn_npc_vehicles()
            self.spawn_npc_pedestrians()
        except Exception as e:
            print(f"初始化时出现错误：{e}")
            self.destroy()
            sys.exit(1)
        self.world.on_tick(hud.on_world_tick)
        self.hud.notification("Press 'H' or '?' for help.", seconds=4.0)

    def get_actor_display_name(self, actor, truncate=250):
        return get_actor_display_name(actor, truncate)

    def toggle_recording(self):
        town_name = self.map.name.split('/')[-1]
        was_recording = self.sensor_manager.recording
        self.sensor_manager.toggle_recording(town_name)
        if was_recording and not self.sensor_manager.recording:
            save_path = self.sensor_manager.save_root
            if save_path and os.path.exists(save_path):
                print("\n录制结束，自动处理 waypoints...")
                fill_waypoints_auto(save_path)

    def spawn_npc_vehicles(self):
        if self.npc_vehicle_count <= 0:
            return
        if self.traffic_manager is None:
            print("Traffic Manager未初始化，跳过NPC车辆生成")
            return
        print(f"\n开始生成 {self.npc_vehicle_count} 辆NPC车辆...")
        blueprint_library = self.world.get_blueprint_library()
        vehicle_blueprints = blueprint_library.filter("vehicle.*")
        vehicle_blueprints = [bp for bp in vehicle_blueprints if
                              not any(x in bp.id for x in ['cycle', 'bike', 'motorcycle'])]
        spawn_points = self.map.get_spawn_points()
        if not spawn_points:
            print("未找到车辆生成点，跳过NPC车辆生成")
            return
        generated_count = 0
        max_attempts = self.npc_vehicle_count * 3
        attempt = 0
        while generated_count < self.npc_vehicle_count and attempt < max_attempts:
            attempt += 1
            try:
                blueprint = random.choice(vehicle_blueprints)
                spawn_point = random.choice(spawn_points)
                if blueprint.has_attribute('color'):
                    color = random.choice(blueprint.get_attribute('color').recommended_values)
                    blueprint.set_attribute('color', color)
                blueprint.set_attribute('role_name', 'autopilot')
                vehicle = self.world.try_spawn_actor(blueprint, spawn_point)
                if vehicle:
                    try:
                        vehicle.set_autopilot(True, self.traffic_manager.get_port())
                    except:
                        vehicle.set_autopilot(True)
                    self.traffic_manager.vehicle_percentage_speed_difference(vehicle, 0)
                    self.npc_vehicles.append(vehicle)
                    generated_count += 1
                    print(f"生成NPC车辆 {generated_count}/{self.npc_vehicle_count}: {vehicle.type_id}")
            except Exception as e:
                continue
        print(f"NPC车辆生成完成：实际生成 {generated_count} 辆（目标 {self.npc_vehicle_count} 辆）")

    def spawn_npc_pedestrians(self):
        if self.npc_pedestrian_count <= 0:
            return
        print(f"\n开始生成 {self.npc_pedestrian_count} 个NPC行人...")
        blueprint_library = self.world.get_blueprint_library()
        pedestrian_blueprints = blueprint_library.filter("walker.pedestrian.*")
        if not pedestrian_blueprints:
            print("未找到行人蓝图，跳过人生成")
            return
        spawn_points = self.map.get_spawn_points()
        if not spawn_points:
            min_x, max_x = -100, 100
            min_y, max_y = -100, 100
        else:
            xs = [p.location.x for p in spawn_points]
            ys = [p.location.y for p in spawn_points]
            min_x, max_x = min(xs) - 50, max(xs) + 50
            min_y, max_y = min(ys) - 50, max(ys) + 50
        walkers_spawn_points = []
        for _ in range(self.npc_pedestrian_count * 2):
            spawn_point = carla.Transform()
            spawn_point.location.x = random.uniform(min_x, max_x)
            spawn_point.location.y = random.uniform(min_y, max_y)
            spawn_point.location.z = 0.1
            spawn_point.rotation.yaw = random.uniform(0, 360)
            walkers_spawn_points.append(spawn_point)
        generated_count = 0
        max_attempts = self.npc_pedestrian_count * 3
        attempt = 0
        while generated_count < self.npc_pedestrian_count and attempt < max_attempts:
            attempt += 1
            try:
                blueprint = random.choice(pedestrian_blueprints)
                spawn_point = random.choice(walkers_spawn_points)
                pedestrian = self.world.try_spawn_actor(blueprint, spawn_point)
                if pedestrian:
                    walker_controller_bp = blueprint_library.find('controller.ai.walker')
                    if not walker_controller_bp:
                        walker_controller_bp = blueprint_library.find('walker.controller.ai')
                    controller = self.world.spawn_actor(walker_controller_bp, carla.Transform(), pedestrian)
                    if controller:
                        controller.start()
                        target_x = spawn_point.location.x + random.uniform(-10, 10)
                        target_y = spawn_point.location.y + random.uniform(-10, 10)
                        controller.go_to_location(carla.Location(target_x, target_y, 0.1))
                        controller.set_max_speed(random.uniform(0.5, 1.5))
                        self.npc_pedestrians.append((pedestrian, controller))
                        generated_count += 1
                        print(f"生成NPC行人 {generated_count}/{self.npc_pedestrian_count}: {pedestrian.type_id}")
                    else:
                        pedestrian.destroy()
            except Exception as e:
                continue
        print(f"NPC行人生成完成：实际生成 {generated_count} 个（目标 {self.npc_pedestrian_count} 个）")

    def restart(self):
        self.player_max_speed = 1.589
        self.player_max_speed_fast = 3.713
        cam_index = self.camera_manager.index if (self.camera_manager and hasattr(self.camera_manager, 'index')) else 0
        cam_pos_index = self.camera_manager.transform_index if (
                    self.camera_manager and hasattr(self.camera_manager, 'transform_index')) else 0
        blueprint = self.world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', self.actor_role_name)
        if blueprint.has_attribute('color'):
            blueprint.set_attribute('color', '255,255,255')
        if blueprint.has_attribute('is_invincible'):
            blueprint.set_attribute('is_invincible', 'true')
        self.player_max_speed = 15.0
        self.player_max_speed_fast = 25.0
        spawn_point = carla.Transform()
        if self.player is not None:
            self.destroy()
            if self.custom_x is not None and self.custom_y is not None:
                spawn_point.location.x = self.custom_x
                spawn_point.location.y = self.custom_y
                spawn_point.location.z = self.custom_z
                spawn_point.rotation.yaw = self.custom_theta
            else:
                spawn_point = self.player.get_transform()
                spawn_point.location.z += 2.0
        else:
            if self.custom_x is not None and self.custom_y is not None:
                spawn_point.location.x = self.custom_x
                spawn_point.location.y = self.custom_y
                spawn_point.location.z = self.custom_z
                spawn_point.rotation.yaw = self.custom_theta
            else:
                spawn_points = self.map.get_spawn_points()
                if spawn_points:
                    spawn_point = random.choice(spawn_points)
                else:
                    print('没有可用的生成点，退出程序')
                    sys.exit(1)
        spawn_point.rotation.roll = 0.0
        spawn_point.rotation.pitch = 0.0
        self.player = None
        max_attempts = 10
        attempt = 0
        while self.player is None and attempt < max_attempts:
            self.player = self.world.try_spawn_actor(blueprint, spawn_point)
            attempt += 1
            if self.player is None:
                spawn_points = self.map.get_spawn_points()
                if spawn_points:
                    spawn_point = random.choice(spawn_points)
        if self.player is None:
            print('无法生成玩家车辆，退出程序')
            sys.exit(1)
        self.modify_vehicle_physics(self.player)
        self.show_vehicle_telemetry = False
        self.collision_sensor = CollisionSensor(self.player, self.hud)
        self.lane_invasion_sensor = LaneInvasionSensor(self.player, self.hud)
        self.gnss_sensor = GnssSensor(self.player)
        self.imu_sensor = IMUSensor(self.player)
        self.camera_manager = CameraManager(self.player, self.hud, self._gamma)
        self.camera_manager.transform_index = cam_pos_index
        self.camera_manager.set_sensor(cam_index, notify=False)
        from sensor_manager import SensorManager
        self.sensor_manager = SensorManager(self.player, self.world, self.hud)
        actor_type = get_actor_display_name(self.player)
        self.hud.notification(actor_type)
        if self.sync:
            self.world.tick()
        else:
            self.world.wait_for_tick()

    def next_weather(self, reverse=False):
        self._weather_index += -1 if reverse else 1
        self._weather_index %= len(self._weather_presets)
        preset = self._weather_presets[self._weather_index]
        self.hud.notification('Weather: %s' % preset[1])
        self.world.set_weather(preset[0])

    def next_map_layer(self, reverse=False):
        self._map_layer += -1 if reverse else 1
        self._map_layer %= len(self._map_layer_names)
        selected = self._map_layer_names[self._map_layer]
        self.hud.notification('LayerMap selected: %s' % selected)

    def load_map_layer(self, unload=False):
        selected = self._map_layer_names[self._map_layer]
        if unload:
            self.hud.notification('Unloading map layer: %s' % selected)
            self.world.unload_map_layer(selected)
        else:
            self.hud.notification('Loading map layer: %s' % selected)
            self.world.load_map_layer(selected)

    def toggle_radar(self):
        if self.radar_sensor is None:
            self.radar_sensor = RadarSensor(self.player)
        elif self.radar_sensor and self.radar_sensor.sensor is not None:
            self.radar_sensor.sensor.destroy()
            self.radar_sensor = None

    def modify_vehicle_physics(self, actor):
        try:
            physics_control = actor.get_physics_control()
            physics_control.use_sweep_wheel_collision = True
            actor.apply_physics_control(physics_control)
        except Exception:
            pass

    def tick(self, clock):
        self.hud.tick(self, clock)
        self.sensor_manager.tick()

    def render(self, display):
        if self.camera_manager:
            self.camera_manager.render(display)
        self.hud.render(display)

    def destroy(self):
        if self.npc_vehicles:
            print("\n清理NPC车辆...")
            for vehicle in self.npc_vehicles:
                if vehicle and vehicle.is_alive:
                    try:
                        vehicle.destroy()
                    except:
                        pass
            self.npc_vehicles.clear()
        if self.npc_pedestrians:
            print("清理NPC行人...")
            for pedestrian, controller in self.npc_pedestrians:
                if controller and controller.is_alive:
                    try:
                        controller.stop()
                        controller.destroy()
                    except:
                        pass
                if pedestrian and pedestrian.is_alive:
                    try:
                        pedestrian.destroy()
                    except:
                        pass
            self.npc_pedestrians.clear()
        if self.radar_sensor:
            try:
                self.toggle_radar()
            except:
                pass
        sensors = []
        if self.collision_sensor and hasattr(self.collision_sensor, 'sensor') and self.collision_sensor.sensor:
            sensors.append(self.collision_sensor.sensor)
        if self.lane_invasion_sensor and hasattr(self.lane_invasion_sensor,
                                                 'sensor') and self.lane_invasion_sensor.sensor:
            sensors.append(self.lane_invasion_sensor.sensor)
        if self.gnss_sensor and hasattr(self.gnss_sensor, 'sensor') and self.gnss_sensor.sensor:
            sensors.append(self.gnss_sensor.sensor)
        if self.imu_sensor and hasattr(self.imu_sensor, 'sensor') and self.imu_sensor.sensor:
            sensors.append(self.imu_sensor.sensor)
        if self.camera_manager and hasattr(self.camera_manager, 'sensor') and self.camera_manager.sensor:
            sensors.append(self.camera_manager.sensor)
        for sensor in sensors:
            if sensor and sensor.is_alive:
                try:
                    sensor.stop()
                    sensor.destroy()
                except:
                    pass
        if self.player and self.player.is_alive:
            try:
                self.player.destroy()
            except:
                pass
        self.player = None
        self.collision_sensor = None
        self.lane_invasion_sensor = None
        self.gnss_sensor = None
        self.imu_sensor = None
        self.radar_sensor = None
        self.camera_manager = None
        print("所有Actor和传感器已清理完成")
