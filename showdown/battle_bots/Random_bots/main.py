import constants
from data import all_move_json
from showdown.battle import Battle
from showdown.engine.damage_calculator import calculate_damage
from showdown.engine.find_state_instructions import update_attacking_move
from ..helpers import format_decision
from config import logger


import random

m_debug = True

class BattleBot(Battle):
    '''
    This battle bot aims at generate a random move
    from both current moves and switchings
    '''
    def __init__(self, *args, **kwargs):
        super(BattleBot, self).__init__(*args, **kwargs)

    def generate_random_move(self):
        '''
        Generate a random move from moves and switching
        :return: a formatted random move
        '''
        state = self.create_state()
        my_options = self.get_all_options()[0]

        moves = []
        switches = []
        for option in my_options:
            if option.startswith(constants.SWITCH_STRING + " "):
                switches.append(option)
            else:
                moves.append(option)

        all_choices = moves + switches


        if self.force_switch or not moves:
            _choose = random.choice(switches)
            if (m_debug):
                logger.debug("Force to switch as {}".format(_choose))
            return format_decision(self, _choose)


        _choose = random.choice(all_choices)
        if (m_debug):
            logger.debug("Generate random move : {}".format(_choose))

        return format_decision(self, _choose)

    def find_best_move(self):
        '''
        as templated
        :return: a rmove

        '''
        return self.generate_random_move()



