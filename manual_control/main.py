#!/usr/bin/env python
from __future__ import print_function
import glob
import os
import sys
import json

try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass
import carla
import argparse
import logging
import pygame
from world import World
from hud import HUD, InGameMiniMap
from controllers import KeyboardControl
from config import PARAM_FILE_PATH


def game_loop(args):
    pygame.init()
    pygame.font.init()
    world = None
    original_settings = None
    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(20.0)
        if args.map:
            sim_world = client.load_world(args.map)
        else:
            sim_world = client.get_world()
        if args.sync:
            original_settings = sim_world.get_settings()
            settings = sim_world.get_settings()
            if not settings.synchronous_mode:
                settings.synchronous_mode = True
                settings.fixed_delta_seconds = 0.05
            sim_world.apply_settings(settings)
            traffic_manager = client.get_trafficmanager()
            traffic_manager.set_synchronous_mode(True)
        display = pygame.display.set_mode(
            (args.width, args.height),
            pygame.HWSURFACE | pygame.DOUBLEBUF)
        display.fill((0, 0, 0))
        pygame.display.flip()
        hud = HUD(args.width, args.height)
        world = World(client, sim_world, hud, args,
                      npc_vehicle_count=args.npc_vehicles,
                      npc_pedestrian_count=args.npc_pedestrians)
        controller = KeyboardControl(world, args.autopilot)
        minimap = InGameMiniMap()
        clock = pygame.time.Clock()
        while True:
            if args.sync:
                sim_world.tick()
            clock.tick_busy_loop(60)
            if controller.parse_events(client, world, clock, args.sync):
                return
            try:
                x = world.player.get_transform().location.x
                y = world.player.get_transform().location.y
                minimap.update_pos(x, y)
            except:
                pass
            world.tick(clock)
            world.render(display)
            minimap.render(display)
            pygame.display.flip()
    finally:
        if original_settings:
            sim_world.apply_settings(original_settings)
        if world and world.recording_enabled:
            client.stop_recorder()
        if world:
            world.destroy()
        pygame.quit()


def main():
    argparser = argparse.ArgumentParser(description='CARLA Manual Control Client')
    argparser.add_argument('-v', '--verbose', action='store_true', dest='debug', help='print debug information')
    argparser.add_argument('--host', default='127.0.0.1', help='IP of the host server')
    argparser.add_argument('--port', default=2000, type=int, help='TCP port')
    argparser.add_argument('-a', '--autopilot', action='store_true', help='enable autopilot')
    argparser.add_argument('--res', default='1280x720', help='window resolution')
    argparser.add_argument('--filter', default='vehicle.*', help='actor filter')
    argparser.add_argument('--generation', default='2', help='actor generation')
    argparser.add_argument('--rolename', default='hero', help='actor role name')
    argparser.add_argument('--gamma', default=2.2, type=float, help='Gamma correction')
    argparser.add_argument('--sync', action='store_true', help='Activate synchronous mode')
    argparser.add_argument('--map', default='', help='map name')
    argparser.add_argument('--x', type=float, default=None, help='spawn x')
    argparser.add_argument('--y', type=float, default=None, help='spawn y')
    argparser.add_argument('--z', type=float, default=None, help='spawn z')
    argparser.add_argument('--theta', type=float, default=None, help='spawn yaw')
    argparser.add_argument('--npc_vehicles', type=int, default=0, help='npc vehicles')
    argparser.add_argument('--npc_pedestrians', type=int, default=0, help='npc pedestrians')
    args = argparser.parse_args()
    if os.path.exists(PARAM_FILE_PATH):
        try:
            with open(PARAM_FILE_PATH, 'r', encoding='utf-8') as f:
                spawn_params = json.load(f)
            if args.x is None: args.x = spawn_params.get('x')
            if args.y is None: args.y = spawn_params.get('y')
            if args.z is None: args.z = spawn_params.get('z', 0.5)
            if args.theta is None: args.theta = spawn_params.get('theta', 0.0)
            if args.npc_vehicles == 0: args.npc_vehicles = spawn_params.get('npc_vehicles', 0)
            if args.npc_pedestrians == 0: args.npc_pedestrians = spawn_params.get('npc_pedestrians', 0)
            if args.map == '': args.map = spawn_params.get('map')
            print(f"从文件加载：x={args.x}, y={args.y}, z={args.z}, theta={args.theta}, map={args.map}")
        except Exception as e:
            print(f"读取参数失败: {e}")
    args.width, args.height = [int(x) for x in args.res.split('x')]
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)
    logging.info('listening to server %s:%s', args.host, args.port)
    help_text = """
Welcome to CARLA manual control.
Use W/S/A/D to drive.
ESC to quit.
"""
    print(help_text)
    try:
        game_loop(args)
    except KeyboardInterrupt:
        print('\nBye!')


if __name__ == '__main__':
    main()
