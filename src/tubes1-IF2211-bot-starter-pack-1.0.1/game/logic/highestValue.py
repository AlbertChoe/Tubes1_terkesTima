from abc import ABC
from typing import Optional, List, Tuple
import random
from game.logic.base import BaseLogic
from game.models import GameObject, Board, Position
from ..util import *
import math


def calculate_distance(a: Position, b: Position) -> int:
    return ((a.x - b.x)**2 + (a.y - b.y)**2)


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

    # If the next move is into a teleporter and the destination is not a teleporter, try to avoid it
    if (current_x + delta_x, current_y + delta_y) in avoid_teleporters and (dest_x, dest_y) not in avoid_teleporters:
        # Try changing the direction to avoid the teleporter
        alternative_moves = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        alternative_moves.remove((delta_x, delta_y))
        for move in alternative_moves:
            if (current_x + move[0], current_y + move[1]) not in avoid_teleporters:
                return move
        return (delta_x, delta_y)
        # If no alternative move avoids a teleporter, proceed with the original move
    else:
        if delta_x != 0:
            delta_y = 0
    return (delta_x, delta_y)


def is_on_path_or_close(diamond_position, bot_position, base_position, threshold):
    # Check if the diamond is on the straight line path between the bot and the base
    on_path = (diamond_position.x == bot_position.x == base_position.x) or (
        diamond_position.y == bot_position.y == base_position.y)
    # Check if the diamond
    #  is within the threshold distance from the path
    close_to_path = calculate_distance(diamond_position, bot_position) <= threshold or calculate_distance(
        diamond_position, base_position) <= threshold
    return on_path or close_to_path


class HighestValue(BaseLogic):
    def __init__(self):
        self.directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        self.goal_position: Optional[Position] = None
        self.current_direction = 0

    def next_move(self, board_bot: GameObject, board: Board):
        props = board_bot.properties
        base = props.base
        time_left = props.milliseconds_left / 1000
        bot_position = board_bot.position

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

        diamonds_with_2_points = [
            diamond for diamond in diamond_game_objects if diamond.properties.points == 2]
        diamonds_with_1_point = [
            diamond for diamond in diamond_game_objects if diamond.properties.points == 1]

        nearest_diamond_with_2_points = find_nearest_diamond(
            bot_position, diamonds_with_2_points)
        nearest_diamond_with_1_point = find_nearest_diamond(
            bot_position, diamonds_with_1_point)

        nearest_teleporter_pair = find_nearest_teleporter_pair(
            bot_position, teleport_game_objects)
        time_to_reach_base = math.ceil(math.sqrt(calculate_distance(
            board_bot.position, base)))
        if nearest_teleporter_pair:
            teleporter1, teleporter2 = nearest_teleporter_pair
            nearest_teleporter = teleporter1 if calculate_distance(
                bot_position, teleporter1) <= calculate_distance(bot_position, teleporter2) else teleporter2
            paired_teleporter = teleporter2 if nearest_teleporter == teleporter1 else teleporter1

        if props.diamonds >= props.inventory_size - 1:
            distance_to_base = calculate_distance(bot_position, base)
            distance_to_base_via_teleport = calculate_distance(
                paired_teleporter, base) + calculate_distance(bot_position, nearest_teleporter)

            if distance_to_base_via_teleport < distance_to_base:
                self.goal_position = nearest_teleporter
            else:
                path_diamonds_with_1_points = [diamond for diamond in diamonds_with_1_point if is_on_path_or_close(
                    diamond.position, bot_position, base, threshold=4) and diamond.properties.points + props.diamonds <= props.inventory_size]
                if path_diamonds_with_1_points:
                    nearest_path_diamond_with_1_points = find_nearest_diamond(
                        bot_position, path_diamonds_with_1_points)
                    self.goal_position = nearest_path_diamond_with_1_points
                else:
                    self.goal_position = base
        elif (props.diamonds >= 2 and time_left < time_to_reach_base + 3):
            distance_to_base = calculate_distance(bot_position, base)
            distance_to_base_via_teleport = calculate_distance(
                paired_teleporter, base) + calculate_distance(bot_position, nearest_teleporter)
            if distance_to_base_via_teleport < distance_to_base:
                self.goal_position = nearest_teleporter
            else:
                self.goal_position = base
        elif diamonds_with_2_points:
            nearest_diamond_with_2_points = find_nearest_diamond(
                bot_position, diamonds_with_2_points)
            self.goal_position = nearest_diamond_with_2_points
        else:
            self.goal_position = nearest_diamond_with_1_point
        if self.goal_position:
            if bot_position == nearest_teleporter and self.goal_position == nearest_teleporter:
                self.goal_position = base
                delta_x, delta_y = get_direction_pribadi(
                    bot_position.x, bot_position.y, self.goal_position.x, self.goal_position.y)
            else:
                teleporter_positions = [
                    teleporter.position for teleporter in teleport_game_objects]
                delta_x, delta_y = get_direction_pribadi(
                    bot_position.x, bot_position.y, self.goal_position.x, self.goal_position.y, avoid_teleporters=teleporter_positions)

        else:
            delta = self.directions[self.current_direction]
            delta_x = delta[0]
            delta_y = delta[1]
            if random.random() > 0.6:
                self.current_direction = (
                    self.current_direction + 1) % len(self.directions)

        return delta_x, delta_y
