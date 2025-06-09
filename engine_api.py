# mccfr_engine/engine_api.py
import pickle
import numpy as np
import random

from ofc_game import GameState 
from card import Card

class MCCFREngine:
    def __init__(self, strategy_path: str):
        try:
            with open(strategy_path, 'rb') as f:
                self.strategy_profile = pickle.load(f)
            print(f"Движок MCCFR успешно загружен. {len(self.strategy_profile)} инфосетов.")
        except FileNotFoundError:
            print(f"Ошибка: Файл стратегии не найден по пути {strategy_path}")
            self.strategy_profile = {}

    def get_action(self, current_game_state: GameState):
        player_id = current_game_state.current_player
        infoset_key = current_game_state.get_infoset_key(player_id)
        legal_actions = current_game_state.get_legal_actions()
        
        if not legal_actions: return None

        if infoset_key not in self.strategy_profile:
            print(f"Warning: Infoset not found. Choosing random action. Key: {infoset_key}")
            return random.choice(legal_actions)

        node_info = self.strategy_profile[infoset_key]
        strategy = node_info['strategy_sum']
        
        if len(strategy) != len(legal_actions):
             print(f"Warning: Strategy length mismatch. Choosing random action. Strategy: {len(strategy)}, Actions: {len(legal_actions)}")
             return random.choice(legal_actions)

        total_sum = np.sum(strategy)
        if total_sum > 0:
            normalized_strategy = strategy / total_sum
        else:
            normalized_strategy = np.ones(len(legal_actions)) / len(legal_actions)

        best_action_index = np.argmax(normalized_strategy)
        return legal_actions[best_action_index]
