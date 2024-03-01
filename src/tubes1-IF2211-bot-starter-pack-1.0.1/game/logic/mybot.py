from abc import ABC
from typing import Optional, List, Tuple
import random
from game.logic.base import BaseLogic
from game.models import GameObject, Board, Position
from ..util import *
import math


def calculate_distance(a: Position, b: Position) -> int:
    return (abs((a.x - b.x)**2 + (a.y - b.y)**2))


def find_nearest_diamond(current: Position, diamonds: List[GameObject]) -> Optional[Position]:
    if not diamonds:
        return None
    nearest_diamond = min(
        diamonds, key=lambda diamond: calculate_distance(current, diamond.position))
    return nearest_diamond.position


def find_nearest_teleporter_pair(current: Position, teleporters: List[GameObject]) -> Optional[Tuple[Position, Position]]:
    nearest_teleporter_pair = None
    min_distance = float('inf')

    # Group teleporters
    teleporter_pairs = {}
    for teleporter in teleporters:
        pair_id = teleporter.properties.pair_id
        if pair_id not in teleporter_pairs:
            teleporter_pairs[pair_id] = []
        teleporter_pairs[pair_id].append(teleporter)

    # Cari teleporter terdekat
    for pair_id, pair in teleporter_pairs.items():
        if len(pair) == 2:
            teleporter, paired_teleporter = pair
            distance = calculate_distance(current, teleporter.position)
            if distance < min_distance:
                min_distance = distance
                nearest_teleporter_pair = (
                    teleporter.position, paired_teleporter.position)

    return nearest_teleporter_pair


def get_direction_pribadi(current_x, current_y, dest_x, dest_y, avoid_teleporters=[]):
    delta_x = clamp(dest_x - current_x, -1, 1)
    delta_y = clamp(dest_y - current_y, -1, 1)

    if (current_x + delta_x, current_y + delta_y) in avoid_teleporters and (dest_x, dest_y) not in avoid_teleporters:
        if delta_x != 0:
            if (current_x, current_y + 1) not in avoid_teleporters:
                delta_y = 1
            elif (current_x, current_y - 1) not in avoid_teleporters:
                delta_y = -1
            delta_x = 0
        elif delta_y != 0:
            if (current_x + 1, current_y) not in avoid_teleporters:
                delta_x = 1
            elif (current_x - 1, current_y) not in avoid_teleporters:
                delta_x = -1
            delta_y = 0
    else:
        if delta_x != 0:
            delta_y = 0

    return (delta_x, delta_y)


def is_on_path_or_close(diamond_position, bot_position, base_position, threshold):
    # Check if the diamond is on the straight line path between the bot and the base
    on_path = (diamond_position.x == bot_position.x == base_position.x) or (
        diamond_position.y == bot_position.y == base_position.y)
    # Check if the diamond is within the threshold distance from the path
    close_to_path = calculate_distance(diamond_position, bot_position) <= threshold or calculate_distance(
        diamond_position, base_position) <= threshold
    return on_path or close_to_path


class BertBots(BaseLogic):
    def __init__(self):
        self.directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        self.goal_position: Optional[Position] = None
        self.current_direction = 0

    def next_move(self, board_bot: GameObject, board: Board):
        props = board_bot.properties
        base = props.base
        radius = board.height // 2
        time_left = props.milliseconds_left / 1000
        bot_position = board_bot.position
        # print(board.height)

        diamond_game_objects = []
        teleport_game_objects = []
        diamond_button_game_objects = []
        for obj in board.game_objects:
            if obj.type == 'DiamondGameObject':
                diamond_game_objects.append(obj)
            elif obj.type == 'TeleportGameObject':
                teleport_game_objects.append(obj)
            elif obj.type == 'DiamondButtonGameObject':
                diamond_button_game_objects.append(obj)

        time_to_reach_base = round(math.sqrt(calculate_distance(
            board_bot.position, base)))
        # print(board.game_objects)
        # print(board_bot.properties.diamonds)
        nearest_diamond = find_nearest_diamond(
            bot_position, diamond_game_objects)
        nearest_teleporter_pair = find_nearest_teleporter_pair(
            bot_position, teleport_game_objects)
        nearest_teleporter, paired_teleporter = nearest_teleporter_pair

        # print(radius)
        if props.diamonds >= props.inventory_size - 1:
            distance_to_base = calculate_distance(
                bot_position, base)
            distance_to_base_via_teleport = calculate_distance(
                paired_teleporter, base) + calculate_distance(bot_position, nearest_teleporter)

            if distance_to_base_via_teleport < distance_to_base:
                self.goal_position = nearest_teleporter
            else:
                path_diamonds = [diamond for diamond in diamond_game_objects if is_on_path_or_close(
                    diamond.position, bot_position, base, threshold=3) and diamond.properties.points + props.diamonds <= props.inventory_size]

                if path_diamonds:
                    nearest_path_diamond = find_nearest_diamond(
                        bot_position, path_diamonds)
                    self.goal_position = nearest_path_diamond
                else:
                    self.goal_position = base
        elif (props.diamonds >= 2 and time_left < time_to_reach_base+3):
            self.goal_position = base
        elif not any(diamond for diamond in diamond_game_objects if calculate_distance(diamond.position, base) <= radius**2):
            nearest_diamond_button = find_nearest_diamond(
                base, diamond_button_game_objects)
            distance_to_diamond_button = calculate_distance(
                bot_position, nearest_diamond_button)

            # Find the nearest diamond to the nearest diamond button
            nearest_diamond_to_button = find_nearest_diamond(
                nearest_diamond_button, diamond_game_objects)
            if nearest_diamond_to_button:
                distance_diamond_to_button = calculate_distance(
                    nearest_diamond_button, nearest_diamond_to_button)
                if distance_to_diamond_button < distance_diamond_to_button:
                    self.goal_position = nearest_diamond_button
                else:
                    self.goal_position = nearest_diamond_to_button
            else:
                self.goal_position = nearest_diamond_button
        else:
            if nearest_diamond:
                distance_to_diamond = calculate_distance(
                    bot_position, nearest_diamond)
                if nearest_teleporter and distance_to_diamond > calculate_distance(nearest_teleporter, nearest_diamond):
                    self.goal_position = nearest_teleporter
                else:
                    self.goal_position = nearest_diamond
            else:
                self.goal_position = base

        if self.goal_position:
            if bot_position == nearest_teleporter and self.goal_position == nearest_teleporter:
                # Move out of the teleporter
                delta_x, delta_y = random.choice(
                    [(1, 0), (0, 1), (-1, 0), (0, -1)])
            else:
                teleporter_positions = [
                    teleporter.position for teleporter in teleport_game_objects]

                # Pass this list to get_direction
                delta_x, delta_y = get_direction_pribadi(
                    bot_position.x,
                    bot_position.y,
                    self.goal_position.x,
                    self.goal_position.y,
                    avoid_teleporters=teleporter_positions
                )
        else:
            # Roam around
            delta = self.directions[self.current_direction]
            delta_x = delta[0]
            delta_y = delta[1]
            if random.random() > 0.6:
                self.current_direction = (self.current_direction + 1) % len(
                    self.directions
                )
        return delta_x, delta_y
