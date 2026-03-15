import pygame
import os
import datetime
import math
import carla
import cv2
from config import CONFIG_DATA, FIXED_MAP_FOLDER, PARAM_FILE_PATH, NAV_POINTS_FILE_PATH
import json


class HUD(object):
    def __init__(self, width, height):
        self.dim = (width, height)
        font = pygame.font.Font(pygame.font.get_default_font(), 20)
        font_name = 'courier' if os.name == 'nt' else 'mono'
        fonts = [x for x in pygame.font.get_fonts() if font_name in x]
        default_font = 'ubuntumono'
        mono = default_font if default_font in fonts else fonts[0]
        mono = pygame.font.match_font(mono)
        self._font_mono = pygame.font.Font(mono, 12 if os.name == 'nt' else 14)  # 这里也需要改
        self._notifications = FadingText(font, (width, 40), (0, height - 40))
        self.help = HelpText(pygame.font.Font(mono, 16), width, height)
        self.server_fps = 0
        self.frame = 0
        self.simulation_time = 0
        self._show_info = True
        self._info_text = []
        self._server_clock = pygame.time.Clock()

    def on_world_tick(self, timestamp):
        self._server_clock.tick()
        self.server_fps = self._server_clock.get_fps()
        self.frame = timestamp.frame
        self.simulation_time = timestamp.elapsed_seconds

    def tick(self, world, clock):
        self._notifications.tick(world, clock)
        if not self._show_info:
            return
        t = world.player.get_transform()
        v = world.player.get_velocity()
        c = world.player.get_control()
        compass = world.imu_sensor.compass
        heading = 'N' if compass > 270.5 or compass < 89.5 else ''
        heading += 'S' if 90.5 < compass < 269.5 else ''
        heading += 'E' if 0.5 < compass < 179.5 else ''
        heading += 'W' if 180.5 < compass < 359.5 else ''
        colhist = world.collision_sensor.get_collision_history()
        collision = [colhist[x + self.frame - 200] for x in range(0, 200)]
        max_col = max(1.0, max(collision))
        collision = [x / max_col for x in collision]
        vehicles = world.world.get_actors().filter('vehicle.*')
        self._info_text = [
            'Server:  % 16.0f FPS' % self.server_fps,
            'Client:  % 16.0f FPS' % clock.get_fps(),
            '',
            'Vehicle: % 20s' % world.get_actor_display_name(world.player, truncate=20),
            'Map:     % 20s' % world.map.name.split('/')[-1],
            'Simulation time: % 12s' % datetime.timedelta(seconds=int(self.simulation_time)),
            '',
            'Speed:   % 15.0f km/h' % (3.6 * math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2)),
            u'Compass:% 17.0f\N{DEGREE SIGN} % 2s' % (compass, heading),
            'Accelero: (%5.1f,%5.1f,%5.1f)' % (world.imu_sensor.accelerometer),
            'Gyroscop: (%5.1f,%5.1f,%5.1f)' % (world.imu_sensor.gyroscope),
            'Location:% 20s' % ('(% 5.1f, % 5.1f)' % (t.location.x, t.location.y)),
            'GNSS:% 24s' % ('(% 2.6f, % 3.6f)' % (world.gnss_sensor.lat, world.gnss_sensor.lon)),
            'Height:  % 18.0f m' % t.location.z,
            '']
        if isinstance(c, carla.VehicleControl):
            self._info_text += [
                ('Throttle:', c.throttle, 0.0, 1.0),
                ('Steer:', c.steer, -1.0, 1.0),
                ('Brake:', c.brake, 0.0, 1.0),
                ('Reverse:', c.reverse),
                ('Hand brake:', c.hand_brake),
                ('Manual:', c.manual_gear_shift),
                'Gear:        %s' % {-1: 'R', 0: 'N'}.get(c.gear, c.gear)]
        elif isinstance(c, carla.WalkerControl):
            self._info_text += [
                ('Speed:', c.speed, 0.0, 5.556),
                ('Jump:', c.jump)]
        self._info_text += [
            '',
            'Collision:',
            collision,
            '',
            'Number of vehicles: % 8d' % len(vehicles)]
        if len(vehicles) > 1:
            self._info_text += ['Nearby vehicles:']
            distance = lambda l: math.sqrt(
                (l.x - t.location.x) ** 2 + (l.y - t.location.y) ** 2 + (l.z - t.location.z) ** 2)
            vehicles = [(distance(x.get_location()), x) for x in vehicles if x.id != world.player.id]
            for d, vehicle in sorted(vehicles, key=lambda vehicles: vehicles[0]):
                if d > 200.0:
                    break
                vehicle_type = world.get_actor_display_name(vehicle, truncate=22)
                self._info_text.append('% 4dm %s' % (d, vehicle_type))

    def toggle_info(self):
        self._show_info = not self._show_info

    def notification(self, text, seconds=2.0):
        self._notifications.set_text(text, seconds=seconds)

    def error(self, text):
        self._notifications.set_text('Error: %s' % text, (255, 0, 0))

    def render(self, display):
        if self._show_info:
            info_surface = pygame.Surface((220, self.dim[1]))
            info_surface.set_alpha(100)
            display.blit(info_surface, (0, 0))
            v_offset = 4
            bar_h_offset = 100
            bar_width = 106
            for item in self._info_text:
                if v_offset + 18 > self.dim[1]:
                    break
                if isinstance(item, list):
                    if len(item) > 1:
                        points = [(x + 8, v_offset + 8 + (1.0 - y) * 30) for x, y in enumerate(item)]
                        pygame.draw.lines(display, (255, 136, 0), False, points, 2)
                    item = None
                    v_offset += 18
                elif isinstance(item, tuple):
                    if isinstance(item[1], bool):
                        rect = pygame.Rect((bar_h_offset, v_offset + 8), (6, 6))
                        pygame.draw.rect(display, (255, 255, 255), rect, 0 if item[1] else 1)
                    else:
                        rect_border = pygame.Rect((bar_h_offset, v_offset + 8), (bar_width, 6))
                        pygame.draw.rect(display, (255, 255, 255), rect_border, 1)
                        f = (item[1] - item[2]) / (item[3] - item[2])
                        if item[2] < 0.0:
                            rect = pygame.Rect((bar_h_offset + f * (bar_width - 6), v_offset + 8), (6, 6))
                        else:
                            rect = pygame.Rect((bar_h_offset, v_offset + 8), (f * bar_width, 6))
                        pygame.draw.rect(display, (255, 255, 255), rect)
                    item = item[0]
                if item:  # At this point has to be a str.
                    surface = self._font_mono.render(item, True, (255, 255, 255))
                    display.blit(surface, (8, v_offset))
                v_offset += 18
        self._notifications.render(display)
        self.help.render(display)


class FadingText(object):
    def __init__(self, font, dim, pos):
        self.font = font
        self.dim = dim
        self.pos = pos
        self.seconds_left = 0
        self.surface = pygame.Surface(self.dim)

    def set_text(self, text, color=(255, 255, 255), seconds=2.0):
        text_texture = self.font.render(text, True, color)
        self.surface = pygame.Surface(self.dim)
        self.seconds_left = seconds
        self.surface.fill((0, 0, 0, 0))
        self.surface.blit(text_texture, (10, 11))

    def tick(self, _, clock):
        delta_seconds = 1e-3 * clock.get_time()
        self.seconds_left = max(0.0, self.seconds_left - delta_seconds)
        self.surface.set_alpha(500.0 * self.seconds_left)

    def render(self, display):
        display.blit(self.surface, self.pos)


class HelpText(object):
    """Helper class to handle text output using pygame"""

    def __init__(self, font, width, height):
        lines = [
            "Welcome to CARLA manual control.",
            "",
            "Use ARROWS or WASD keys for control.",
            "",
            "    W            : throttle",
            "    S            : brake",
            "    A/D          : steer left/right",
            "    Q            : toggle reverse",
            "    Space        : hand-brake",
            "    P            : toggle autopilot",
            "    M            : toggle manual transmission",
            "    ,/.          : gear up/down",
            "    CTRL + W     : toggle constant velocity mode at 60 km/h",
            "",
            "    L            : toggle next light type",
            "    SHIFT + L    : toggle high beam",
            "    Z/X          : toggle right/left blinker",
            "    I            : toggle interior light",
            "",
            "    TAB          : change sensor position",
            "    ` or N       : next sensor",
            "    [1-9]        : change to sensor [1-9]",
            "    G            : toggle radar visualization",
            "    C            : change weather (Shift+C reverse)",
            "    Backspace    : change vehicle",
            "",
            "    O            : open/close all doors of vehicle",
            "    T            : toggle vehicle's telemetry",
            "",
            "    V            : Select next map layer (Shift+V reverse)",
            "    B            : Load current selected map layer (Shift+B to unload)",
            "",
            "    R            : toggle recording images to disk",
            "",
            "    CTRL + R     : toggle recording of simulation (replacing any previous)",
            "    CTRL + P     : start replaying last recorded simulation",
            "    CTRL + +     : increments the start time of the replay by 1 second (+SHIFT = 10 seconds)",
            "    CTRL + -     : decrements the start time of the replay by 1 second (+SHIFT = 10 seconds)",
            "",
            "    F1           : toggle HUD",
            "    H/?          : toggle help",
            "    ESC          : quit"
        ]
        self.font = font
        self.line_space = 18
        self.dim = (780, len(lines) * self.line_space + 12)
        self.pos = (0.5 * width - 0.5 * self.dim[0], 0.5 * height - 0.5 * self.dim[1])
        self.seconds_left = 0
        self.surface = pygame.Surface(self.dim)
        self.surface.fill((0, 0, 0, 0))
        for n, line in enumerate(lines):
            text_texture = self.font.render(line, True, (255, 255, 255))
            self.surface.blit(text_texture, (22, n * self.line_space))
            self._render = False
        self.surface.set_alpha(220)

    def toggle(self):
        self._render = not self._render

    def render(self, display):
        if self._render:
            display.blit(self.surface, self.pos)


class InGameMiniMap:
    def __init__(self):
        self.map_img = None
        self.calib = None
        self.spawn_uv = None
        self.targets_uv = []
        self.trajectory = []
        self.size = 280
        self.zoom = 1.0
        self._load_map()

    def world2pixel(self, x, y):
        px_per_m_x = self.calib["px_per_m_x"]
        x_offset = self.calib["x_offset"]
        px_per_m_y = self.calib["px_per_m_y"]
        y_offset = self.calib["y_offset"]
        x_neg = self.calib["x_negative"]
        u = x * px_per_m_x + x_offset if x_neg else -x * px_per_m_x + x_offset
        v = y * px_per_m_y + y_offset
        return int(round(u)), int(round(v))

    def _load_map(self):
        with open(PARAM_FILE_PATH, 'r', encoding='utf-8') as f:
            spawn = json.load(f)
        self.map_name = spawn["map"]
        self.spawn_x = spawn["x"]
        self.spawn_y = spawn["y"]
        with open(NAV_POINTS_FILE_PATH, 'r', encoding='utf-8') as f:
            nav = json.load(f)
        self.targets = nav["targets"]
        self.calib = CONFIG_DATA[self.map_name]
        path = os.path.join(FIXED_MAP_FOLDER, f"{self.map_name}.png")
        self.map_img = cv2.imread(path)
        self.img_h, self.img_w = self.map_img.shape[:2]
        self.spawn_uv = self.world2pixel(self.spawn_x, self.spawn_y)
        self.targets_uv = [self.world2pixel(x, y) for x, y in self.targets]

    def update_pos(self, x, y):
        u, v = self.world2pixel(x, y)
        self.trajectory.append((u, v))
        if len(self.trajectory) > 150:
            self.trajectory.pop(0)

    def render(self, display):
        if self.map_img is None:
            return
        cx, cy = self.spawn_uv
        if self.trajectory:
            cx, cy = self.trajectory[-1]
        crop_size = int(self.size / self.zoom)
        x1 = max(0, cx - crop_size // 2)
        y1 = max(0, cy - crop_size // 2)
        x2 = min(self.img_w, x1 + crop_size)
        y2 = min(self.img_h, y1 + crop_size)
        crop = self.map_img[y1:y2, x1:x2].copy()
        if len(self.targets_uv) > 0:
            prev_u, prev_v = self.spawn_uv
            for (tu, tv) in self.targets_uv:
                cv2.line(crop,
                         (prev_u - x1, prev_v - y1),
                         (tu - x1, tv - y1),
                         (0, 255, 0), 2)
                prev_u, prev_v = tu, tv
        cv2.circle(crop, (self.spawn_uv[0] - x1, self.spawn_uv[1] - y1), 5, (0, 0, 255), -1)
        for (px, py) in self.targets_uv:
            cv2.circle(crop, (px - x1, py - y1), 4, (0, 255, 0), -1)
        cv2.circle(crop, (cx - x1, cy - y1), 6, (255, 0, 0), -1)
        for i in range(1, len(self.trajectory)):
            u1, v1 = self.trajectory[i - 1]
            u2, v2 = self.trajectory[i]
            cv2.line(crop,
                     (u1 - x1, v1 - y1),
                     (u2 - x1, v2 - y1),
                     (255, 0, 255), 1)
        crop = cv2.resize(crop, (self.size, self.size))
        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        surface = pygame.surfarray.make_surface(crop.swapaxes(0, 1))
        display.blit(surface, (display.get_width() - self.size - 5, display.get_height() - self.size - 5))
