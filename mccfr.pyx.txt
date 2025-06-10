# mccfr_engine/mccfr.pyx
import numpy as np
cimport numpy as np

# Импортируем cdef-класс из другого .pyx файла
from ofc_game cimport GameState

# Указываем, что функция будет быстрой C-функцией
cpdef mccfr_traverse(GameState state, dict strategy_profile):
    if state.is_terminal():
        return state.get_payoffs()

    # infoset_key теперь кортеж, что быстрее для ключей словаря
    infoset_key = state.get_infoset_key()
    current_player = state.current_player
    legal_actions = state.get_legal_actions()
    num_actions = len(legal_actions)

    if num_actions == 0:
        next_state = state.apply_action(None)
        return mccfr_traverse(next_state, strategy_profile)

    if infoset_key not in strategy_profile:
        strategy_profile[infoset_key] = {
            'regret_sum': np.zeros(num_actions, dtype=np.float32),
            'strategy_sum': np.zeros(num_actions, dtype=np.float32),
        }
    
    node = strategy_profile[infoset_key]
    
    if node['regret_sum'].shape[0] != num_actions:
        node['regret_sum'] = np.zeros(num_actions, dtype=np.float32)
        node['strategy_sum'] = np.zeros(num_actions, dtype=np.float32)

    # Типизированные переменные для скорости
    cdef np.ndarray[np.float32_t] regrets = node['regret_sum']
    cdef np.ndarray[np.float32_t] strategy
    
    positive_regrets = np.maximum(regrets, 0)
    regret_sum_total = np.sum(positive_regrets)
    
    if regret_sum_total > 0:
        strategy = positive_regrets / regret_sum_total
    else:
        strategy = np.ones(num_actions, dtype=np.float32) / num_actions

    node['strategy_sum'] += strategy

    cdef np.ndarray[np.float64_t, ndim=2] action_utils = np.zeros((num_actions, state.players))
    cdef int i
    for i, action in enumerate(legal_actions):
        next_state = state.apply_action(action)
        action_utils[i] = mccfr_traverse(next_state, strategy_profile)

    node_utils = np.dot(strategy, action_utils)
    
    current_player_action_utils = action_utils[:, current_player]
    current_player_node_util = node_utils[current_player]
    
    regrets_update = current_player_action_utils - current_player_node_util
    node['regret_sum'] += regrets_update
    
    return node_utils
