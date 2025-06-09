# mccfr_engine/mccfr.py (v2 - правильная рекурсия)
import numpy as np

def cfr_traverse(state, strategy_profile):
    """
    Рекурсивная функция для обхода дерева игры и обновления стратегии.
    """
    if state.is_terminal():
        return state.get_payoffs()

    current_player = state.current_player
    infoset_key = state.get_infoset_key(current_player)
    legal_actions = state.get_legal_actions()
    num_actions = len(legal_actions)

    if num_actions == 0:
        return cfr_traverse(state.apply_action(None), strategy_profile) # Если нет действий, просто передаем ход

    if infoset_key not in strategy_profile:
        strategy_profile[infoset_key] = {
            'regret_sum': np.zeros(num_actions, dtype=np.float32),
            'strategy_sum': np.zeros(num_actions, dtype=np.float32),
            'action_map': {i: action for i, action in enumerate(legal_actions)} # Сохраняем карту действий
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

    # Считаем утилиты для каждого действия
    action_utils = np.zeros((num_actions, state.players))
    for i, action in enumerate(legal_actions):
        next_state = state.apply_action(action)
        action_utils[i] = cfr_traverse(next_state, strategy_profile)

    # Ожидаемая утилита узла для всех игроков
    node_utils = np.dot(strategy, action_utils)
    
    # Обновление сожалений для текущего игрока
    # Сожаление = (утилита действия) - (средняя утилита узла)
    current_player_action_utils = action_utils[:, current_player]
    current_player_node_util = node_utils[current_player]
    
    regrets = current_player_action_utils - current_player_node_util
    node['regret_sum'] += regrets
    
    return node_utils
