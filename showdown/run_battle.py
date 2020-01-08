import importlib
import json
import asyncio
import concurrent.futures
from copy import deepcopy
from showdown.helpers import normalize_name

import constants
import config
from config import logger
from config import reset_logger
from showdown.engine.evaluate import Scoring
from showdown.battle import Pokemon
from showdown.battle_modifier import update_battle

from showdown.websocket_client import PSWebsocketClient

import urllib.request

headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:23.0) Gecko/20100101 Firefox/23.0'}

def battle_is_finished(msg):
    return constants.WIN_STRING in msg and constants.CHAT_STRING not in msg


async def async_pick_move(battle):
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        best_move = await loop.run_in_executor(
            pool, battle.find_best_move
        )
    return best_move


async def handle_team_preview(battle, ps_websocket_client):
    battle_copy = deepcopy(battle)
    battle_copy.user.active = Pokemon.get_dummy()
    battle_copy.opponent.active = Pokemon.get_dummy()

    best_move = await async_pick_move(battle_copy)
    size_of_team = len(battle.user.reserve) + 1
    team_list_indexes = list(range(1, size_of_team))
    choice_digit = int(best_move[0].split()[-1])

    team_list_indexes.remove(choice_digit)
    message = ["/team {}{}|{}".format(choice_digit, "".join(str(x) for x in team_list_indexes), battle.rqid)]
    battle.user.active = battle.user.reserve.pop(choice_digit - 1)

    await ps_websocket_client.send_message(battle.battle_tag, message)


async def get_battle_tag_and_opponent(ps_websocket_client: PSWebsocketClient):
    while True:
        msg = await ps_websocket_client.receive_message()
        split_msg = msg.split('|')
        first_msg = split_msg[0]
        if 'battle' in first_msg:
            battle_tag = first_msg.replace('>', '').strip()
            user_name = split_msg[-1].replace('☆', '').strip()
            opponent_name = split_msg[4].replace(user_name, '').replace('vs.', '').strip()
            return battle_tag, opponent_name


async def initialize_battle_with_tag(ps_websocket_client: PSWebsocketClient):
    battle_module = importlib.import_module('showdown.battle_bots.{}.main'.format(config.battle_bot_module))

    battle_tag, opponent_name = await get_battle_tag_and_opponent(ps_websocket_client)
    while True:
        msg = await ps_websocket_client.receive_message()
        split_msg = msg.split('|')
        if split_msg[1].strip() == 'request' and split_msg[2].strip():
            user_json = json.loads(split_msg[2].strip('\''))
            user_id = user_json[constants.SIDE][constants.ID]
            opponent_id = constants.ID_LOOKUP[user_id]
            battle = battle_module.BattleBot(battle_tag)
            battle.opponent.name = opponent_id
            battle.opponent.account_name = opponent_name
            return battle, opponent_id, user_json


async def start_random_battle(ps_websocket_client: PSWebsocketClient, pokemon_battle_type):
    battle, opponent_id, user_json = await initialize_battle_with_tag(ps_websocket_client)
    battle.battle_type = constants.RANDOM_BATTLE
    battle.generation = pokemon_battle_type[:4]

    # keep reading messages until the opponent's first pokemon is seen
    while True:
        msg = await ps_websocket_client.receive_message()
        if constants.START_STRING in msg:
            split_msg = msg.split(constants.START_STRING)[-1].split('\n')
            for line in split_msg:
                if opponent_id in line and constants.SWITCH_STRING in line:
                    battle.start_random_battle(user_json, line)

                elif battle.started:
                    await update_battle(battle, line)

            # first move needs to be picked here
            best_move = await async_pick_move(battle)
            await ps_websocket_client.send_message(battle.battle_tag, best_move)

            return battle


async def start_standard_battle(ps_websocket_client: PSWebsocketClient, pokemon_battle_type):
    battle, opponent_id, user_json = await initialize_battle_with_tag(ps_websocket_client)
    battle.battle_type = constants.STANDARD_BATTLE
    battle.generation = pokemon_battle_type[:4]

    msg = ''
    while constants.START_TEAM_PREVIEW not in msg:
        msg = await ps_websocket_client.receive_message()

    preview_string_lines = msg.split(constants.START_TEAM_PREVIEW)[-1].split('\n')

    opponent_pokemon = []
    for line in preview_string_lines:
        if not line:
            continue

        split_line = line.split('|')
        if split_line[1] == constants.TEAM_PREVIEW_POKE and split_line[2].strip() == opponent_id:
            opponent_pokemon.append(split_line[3])

    battle.initialize_team_preview(user_json, opponent_pokemon, pokemon_battle_type)
    await handle_team_preview(battle, ps_websocket_client)

    return battle


async def start_battle(ps_websocket_client, pokemon_battle_type):
    if "random" in pokemon_battle_type:
        Scoring.POKEMON_ALIVE_STATIC = 30  # random battle benefits from a lower static score for an alive pkmn
        battle = await start_random_battle(ps_websocket_client, pokemon_battle_type)
    else:
        battle = await start_standard_battle(ps_websocket_client, pokemon_battle_type)

    reset_logger(logger, "{}-{}.log".format(battle.opponent.account_name, battle.battle_tag))
    await ps_websocket_client.send_message(battle.battle_tag, [config.greeting_message])
    #await ps_websocket_client.send_message(battle.battle_tag, ['/timer on'])

    return battle


async def pokemon_battle(ps_websocket_client, pokemon_battle_type):

    battle = await start_battle(ps_websocket_client, pokemon_battle_type)
    while True:
        msg = await ps_websocket_client.receive_message()
        if battle_is_finished(msg):
            if getattr(battle, "update_trainer", None):
                await update_battle(battle, msg)
                battle.update_trainer()
            winner = msg.split(constants.WIN_STRING)[-1].split('\n')[0].strip()
            logger.debug("Winner: {}".format(winner))
            await ps_websocket_client.send_message(battle.battle_tag, [config.battle_ending_message])
            score = await search_opponent_score(battle)
            with open('record.txt','a') as f:
                if winner == config.username:
                    f.write('win {}\n'.format(score))
                else:
                    f.write('lose {}\n'.format(score))

            await ps_websocket_client.leave_battle(battle.battle_tag, save_replay=config.save_replay)
            return winner
        else:
            action_required = await update_battle(battle, msg)
            if action_required:
                if getattr(battle, "update_trainer", None):
                    battle.update_trainer()
                if not battle.wait:
                    best_move = await async_pick_move(battle)
                    await ps_websocket_client.send_message(battle.battle_tag, best_move)


async def search_opponent_score(battle):
    opponent_name = normalize_name(battle.opponent.account_name)
    logger.debug("opponent_name : {}".format(opponent_name))
    chaper_url = "https://play.pokemonshowdown.com/~~showdown/action.php?act=ladderget&user={}".format(opponent_name)
    req = urllib.request.Request(url=chaper_url, headers=headers)
    msg = urllib.request.urlopen(req).read()
    information = json.loads(msg[1:])

    score = '0'
    for info in information:
        if info['formatid'] == config.pokemon_mode:
            score = info['elo']
            break
    return score