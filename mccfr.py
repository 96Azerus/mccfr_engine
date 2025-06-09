# mccfr_engine/mccfr.py (v3 - правильное имя функции)
import numpy as np

def mccfr_traverse(state, strategy_profile): # ВОЗВРАЩАЕМ ИМЯ mccfr_traverse
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
        # Если нет действий, просто передаем ход следующему
        # Это может случиться, если колода закончилась до заполнения доски
        return mccfr_traverse(state.apply_action(None), strategy_profile)

    if infoset_key not in strategy_profile:
        strategy_profile[infoset_key] = {
            'regret_sum': np.zeros(num_actions, dtype=np.float32),
            'strategy_sum': np.zeros(num_actions, dtype=np.float32),
        }
    
    node = strategy_profile[infoset_key]
    
    # Проверка на случай, если количество действий изменилось (не должно, но для безопасности)
    if len(node['regret_sum']) != num_actions:
        node['regret_sum'] = np.zeros(num_actions, dtype=np.float32)
        node['strategy_sum'] = np.zeros(num_actions, dtype=np.float32)

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
        action_utils[i] = mccfr_traverse(next_state, strategy_profile)

    # Ожидаемая утилита узла для всех игроков
    node_utils = np.dot(strategy, action_utils)
    
    # Обновление сожалений для текущего игрока
    current_player_action_utils = action_utils[:, current_player]
    current_player_node_util = node_utils[current_player]
    
    regrets_update = current_player_action_utils - current_player_node_util
    node['regret_sum'] += regrets_update
    
    return node_utils
