# mccfr_engine/mccfr.py
import numpy as np
import random

def mccfr_traverse(state, player_id, strategy_profile):
    if state.is_terminal():
        payoffs = state.get_payoffs()
        return payoffs[player_id]

    # Если ход не текущего игрока, сэмплируем действие и идем дальше
    if player_id != state.current_player:
        legal_actions = state.get_legal_actions()
        if not legal_actions: # Если у оппонента нет ходов (конец игры)
            return state.get_payoffs()[player_id]
        
        action = random.choice(legal_actions) # Простой сэмплинг для оппонента
        next_state = state.apply_action(action)
        return mccfr_traverse(next_state, player_id, strategy_profile)

    # Если ход текущего игрока, применяем CFR
    infoset_key = state.get_infoset_key(player_id)
    legal_actions = state.get_legal_actions()
    num_actions = len(legal_actions)

    if num_actions == 0:
        return state.get_payoffs()[player_id]

    if infoset_key not in strategy_profile:
        strategy_profile[infoset_key] = {
            'regret_sum': np.zeros(num_actions, dtype=np.float32),
            'strategy_sum': np.zeros(num_actions, dtype=np.float32)
        }
    
    node = strategy_profile[infoset_key]
    
    # Regret Matching
    regrets = node['regret_sum']
    positive_regrets = np.maximum(regrets, 0)
    regret_sum_total = np.sum(positive_regrets)
    
    if regret_sum_total > 0:
        strategy = positive_regrets / regret_sum_total
    else:
        strategy = np.ones(num_actions) / num_actions

    # Обновляем среднюю стратегию
    node['strategy_sum'] += strategy

    # Сэмплируем действия и считаем утилиты для каждого
    action_utils = np.zeros(num_actions)
    for i, action in enumerate(legal_actions):
        next_state = state.apply_action(action)
        action_utils[i] = mccfr_traverse(next_state, player_id, strategy_profile)

    # Обновление сожалений
    node_util = np.sum(strategy * action_utils)
    regrets = action_utils - node_util
    node['regret_sum'] += regrets
    
    return node_util
