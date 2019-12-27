from showdown.battle import Battle
from showdown.engine.objects import StateMutator

from showdown.engine.find_state_instructions import get_all_state_instructions

from ..safest.main import pick_safest_move_from_battles

from ..helpers import format_decision

from .trainer import QlearningTrainer, Counter
from copy import deepcopy

from showdown.engine.damage_calculator import is_super_effective

from config import logger

REWARD_STATE = {'EW': -10.,#enery wins
                'UW': 10.,#user wins
                'ED':1.,#enermy dies
                'UD':-1.,#user dies
                'ND':0.,#nobody dies
                'BD':.5#both die
                }

def features(state):
    f = Counter()
    user_pkmn = state.self.active
    opponent_pkmn = state.opponent.active

    #compare the element of 2 pkmn
    #feature1 : user > oppo
    f['f1'] = 0
    for user_type in user_pkmn.types:
        if is_super_effective(user_type, opponent_pkmn.types):
            f['f1'] = 1
            break

    #feature2 : oppo > user
    f['f2'] = 0
    for opponent_type in opponent_pkmn.types:
        if is_super_effective(opponent_type, user_pkmn.types):
            f['f2'] = 1
            break


    #feature3 : speed
    f['f3']  = 0
    if user_pkmn.speed > opponent_pkmn.speed:
        f['f3'] = 1


    #feature4 : user's hp
    f['f4'] = 0
    if user_pkmn.maxhp:
        f['f4'] = float(user_pkmn.hp)/ user_pkmn.maxhp#it is possible that maxhp be 0

    #feature5 : oppo's hp
    f['f5'] = 0
    if opponent_pkmn.maxhp:
        f['f5'] = float(opponent_pkmn.hp) / opponent_pkmn.maxhp

    #feature6 : boost
    f['f6'] = max(user_pkmn.attack_boost, user_pkmn.special_attack_boost)

    #feature7 : oppo's boost
    f['f7'] = max(opponent_pkmn.attack_boost, opponent_pkmn.special_attack_boost)

    #feature8 : abnomal status
    f['f8'] = 0
    if opponent_pkmn.status:
        f['f8'] = 1
    elif user_pkmn.status:
        f['f8'] = -1

    #feature9 : user's reserve pkmn's hp
    f['f9'] = 0
    a = 0
    s = 0
    for pkmn in state.self.reserve.values():
        a += pkmn.hp
        s += pkmn.maxhp
    if s:
        f['f9'] = a / s

    #feature10 : oppo's reserve pkmn's hp
    f['f10'] = 0
    a = 0
    s = 0
    for pkmn in state.opponent.reserve.values():
        a += pkmn.hp
        s += pkmn.maxhp
    if s:
        f['f10'] = a / s

    return f




class TrainerOne(QlearningTrainer):
    def getFeatures(self, state, action):
        result = Counter()
        largest_prob = 0

        battles = state.prepare_battles(join_moves_together=True)
        b = battles[0]
        state = b.create_state()
        mutator = StateMutator(state)
        user_options, opponent_options = b.get_all_options()

        for opponent_move in opponent_options[:]:
            state_instructions = get_all_state_instructions(mutator, action, opponent_move)
            for instructions in state_instructions:
                mutator.apply(instructions.instructions)
                features_array = features(mutator.state)
                
                prob = instructions.percentage
                result += features_array.mul(prob)

                mutator.reverse(instructions.instructions)

        if len(opponent_options):
            result.mul(1.0/len(opponent_options))

        return result
                    



    def getLegalActions(self, state):
        #state is the battle object
        actions = []

        user_options, opponent_options = state.get_all_options()
            
        return user_options

    def getRewards(self, **args):
        state = args['new_state']
        
        if state.self.active.hp <= 0 and not any(pkmn.hp for pkmn in state.self.reserve.values()):
            reward_state = 'EW'
        elif state.opponent.active.hp <= 0 and not any(pkmn.hp for pkmn in state.opponent.reserve.values()) and len(state.opponent.reserve) == 5:
            reward_state = 'UW'
        elif state.self.active.hp <= 0 and state.opponent.active.hp <= 0:
            reward_state = 'BD'
        elif state.self.active.hp <= 0:
            reward_state = 'UD'
        elif state.opponent.active.hp <= 0:
            reward_state = 'ED'
        else:
            reward_state = 'ND'
        return REWARD_STATE[reward_state]

global_trainer = TrainerOne(alpha=0.01, gamma=0.8)

class BattleBot(Battle):
    def __init__(self, *args, **kwargs):
        super(BattleBot, self).__init__(*args, **kwargs)
        self.last_state = None
        self.last_chosen_action = None
        self.trainer = global_trainer

    def find_best_move(self):

        #code from safest 
        battles = self.prepare_battles(join_moves_together=True)
        option = pick_safest_move_from_battles(battles)

        self.last_state = deepcopy(self)
        self.last_chosen_action = option

        return format_decision(self, option)

    def update_trainer(self):
        battle = deepcopy(self)

        state = battle.create_state()

        if self.last_state and self.last_chosen_action:
            self.trainer.update(self.last_state, self.last_chosen_action, battle, new_state=state)
        logger.info(self.trainer.weights)
