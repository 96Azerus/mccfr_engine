# mccfr_engine/ofc_game.py (v2 - с Action Abstraction)
import random
import itertools
from typing import List, Tuple, Set, Optional, Dict
from copy import deepcopy
from collections import Counter

from card import Card, FULL_DECK_CARDS
from evaluator import calculate_payoffs, get_hand_rank, get_row_royalty, FANTASY_BONUS, RANK_QUEEN, HAND_TYPE_TRIPS_3, get_hand_rank

# --- Классы Deck и Board остаются без изменений ---
class Deck:
    def __init__(self, cards_to_exclude: Set[int] = None):
        self.cards = list(FULL_DECK_CARDS - (cards_to_exclude or set()))
        random.shuffle(self.cards)
    def deal(self, n: int) -> List[int]:
        return [self.cards.pop() for _ in range(n) if self.cards]

class Board:
    def __init__(self):
        self.rows: Dict[str, List[Optional[int]]] = {'top': [None]*3, 'middle': [None]*5, 'bottom': [None]*5}
    
    def get_all_cards(self) -> Set[int]:
        return {c for row in self.rows.values() for c in row if c is not None}

    def get_row_cards(self, row_name: str) -> List[int]:
        return [c for c in self.rows[row_name] if c is not None]

    def get_available_slots(self) -> List[Tuple[str, int]]:
        return [(r, i) for r, slots in self.rows.items() for i, c in enumerate(slots) if c is None]

    def is_foul(self) -> bool:
        if len(self.get_row_cards('top')) != 3 or len(self.get_row_cards('middle')) != 5 or len(self.get_row_cards('bottom')) != 5:
            return False
        top_rank, _, _ = get_hand_rank(self.get_row_cards('top'))
        mid_rank, _, _ = get_hand_rank(self.get_row_cards('middle'))
        bot_rank, _, _ = get_hand_rank(self.get_row_cards('bottom'))
        return (top_rank < mid_rank) or (mid_rank < bot_rank)

    def get_total_royalty(self) -> int:
        if self.is_foul(): return 0
        total = 0
        total += get_row_royalty(self.get_row_cards('top'), 'top')
        total += get_row_royalty(self.get_row_cards('middle'), 'middle')
        total += get_row_royalty(self.get_row_cards('bottom'), 'bottom')
        return total

    def to_str_tuple(self) -> Tuple[str, ...]:
        return tuple(Card.to_str(c) if c else '_' for r in ['top', 'middle', 'bottom'] for c in self.rows[r])

    def apply_placement(self, placement: Tuple) -> 'Board':
        new_board = deepcopy(self)
        for card, (row, idx) in placement:
            new_board.rows[row][idx] = card
        return new_board

# --- Новая эвристическая функция для Action Abstraction ---
def score_placement_heuristic(board: Board) -> float:
    """Простая эвристика для оценки перспективности доски."""
    score = 0.0
    # Бонус за готовые роялти
    score += board.get_total_royalty() * 1.5 
    
    # Бонус за пары и сеты
    all_cards = board.get_all_cards()
    ranks = [Card.get_rank_int(c) for c in all_cards]
    rank_counts = Counter(ranks)
    for rank, count in rank_counts.items():
        if count == 2: score += 2  # Пара
        if count == 3: score += 10 # Сет
        if count == 4: score += 25 # Каре

    # Штраф за "мертвые" карты на топе (например, 2,3,4)
    top_cards = board.get_row_cards('top')
    if top_cards:
        top_ranks = [Card.get_rank_int(c) for c in top_cards]
        if max(top_ranks) < 8: # Если старшая карта на топе меньше T
            score -= 5

    return score

class GameState:
    # --- __init__, _handle_deal, is_terminal, get_payoffs остаются без изменений ---
    def __init__(self, players=2):
        self.players = players
        self.boards = [Board() for _ in range(players)]
        self.discards = [[] for _ in range(players)]
        self.dealt_cards: Optional[List[int]] = None
        self.street = 1
        self.current_player = random.randint(0, players - 1)
        self.dealer = self.current_player
        self.deck = Deck()
        self._is_terminal = False
        self._payoffs = [0.0] * players
        self._handle_deal()

    def _handle_deal(self):
        num_to_deal = 5 if self.street == 1 else 3
        self.dealt_cards = self.deck.deal(num_to_deal)
        if not self.dealt_cards or len(self.dealt_cards) < num_to_deal:
             self._is_terminal = True

    def is_terminal(self) -> bool:
        if self._is_terminal: return True
        if self.street > 5: return True
        for i, board in enumerate(self.boards):
            if len(board.get_row_cards('top')) == 3 and not board.is_foul():
                _, hand_type, _ = get_hand_rank(board.get_row_cards('top'))
                if hand_type == HAND_TYPE_TRIPS_3:
                    trip_rank = Counter(Card.get_rank_int(c) for c in board.get_row_cards('top')).most_common(1)[0][0]
                    bonus = FANTASY_BONUS.get('trips', 30) + trip_rank
                    self._payoffs[i] += bonus; self._payoffs[1-i] -= bonus
                    self._is_terminal = True; return True
                ranks = Counter(Card.get_rank_int(c) for c in board.get_row_cards('top'))
                pair_rank = next((r for r, count in ranks.items() if count == 2), -1)
                if pair_rank >= RANK_QUEEN:
                    bonus = FANTASY_BONUS.get(pair_rank, 0)
                    self._payoffs[i] += bonus; self._payoffs[1-i] -= bonus
                    self._is_terminal = True; return True
        return False

    def get_payoffs(self) -> List[float]:
        if not self._is_terminal:
             if self.street > 5 or not self.dealt_cards: self._is_terminal = True
             else: return [0.0] * self.players
        base_payoffs = calculate_payoffs(self.boards[0], self.boards[1])
        return [base + fantasy for base, fantasy in zip(base_payoffs, self._payoffs)]

    # --- Обновленный get_legal_actions ---
    def get_legal_actions(self) -> List[Tuple]:
        if self.is_terminal(): return []
        
        cards_to_place_options = []
        if self.street == 1:
            cards_to_place_options.append((self.dealt_cards, None))
        else:
            for card_to_discard in self.dealt_cards:
                cards_to_place = [c for c in self.dealt_cards if c != card_to_discard]
                cards_to_place_options.append((cards_to_place, card_to_discard))

        scored_actions = []
        available_slots = self.boards[self.current_player].get_available_slots()
        
        for cards_to_place, discarded_card in cards_to_place_options:
            if len(available_slots) < len(cards_to_place): continue
            
            # Генерируем все перестановки
            slot_permutations = list(itertools.permutations(available_slots, len(cards_to_place)))
            
            for slots in slot_permutations:
                placement = tuple(zip(cards_to_place, slots))
                # Применяем размещение к временной доске и оцениваем
                temp_board = self.boards[self.current_player].apply_placement(placement)
                score = score_placement_heuristic(temp_board)
                scored_actions.append((score, (placement, discarded_card)))

        # Сортируем действия по эвристической оценке и берем лучшие
        scored_actions.sort(key=lambda x: x[0], reverse=True)
        
        # ACTION_ABSTRACTION_LIMIT - ключевой параметр для тюнинга
        ACTION_ABSTRACTION_LIMIT = 30 
        
        top_actions = [action for score, action in scored_actions[:ACTION_ABSTRACTION_LIMIT]]
        
        return top_actions

    # --- apply_action и get_infoset_key остаются без изменений ---
    def apply_action(self, action: Tuple) -> 'GameState':
        new_state = deepcopy(self)
        placement, discarded_card = action
        for card, (row, idx) in placement:
            new_state.boards[new_state.current_player].rows[row][idx] = card
        if discarded_card is not None:
            new_state.discards[new_state.current_player].append(discarded_card)
        if new_state.current_player == new_state.dealer:
            new_state.street += 1
        new_state.current_player = (new_state.current_player + 1) % new_state.players
        if new_state.street > 5:
            new_state._is_terminal = True
        else:
            new_state._handle_deal()
        return new_state

    def get_infoset_key(self, player_id: int) -> str:
        player_board = self.boards[player_id].to_str_tuple()
        opponent_board = self.boards[1 - player_id].to_str_tuple()
        my_discards = tuple(sorted([Card.to_str(c) for c in self.discards[player_id]]))
        dealt = tuple(sorted([Card.to_str(c) for c in self.dealt_cards])) if self.dealt_cards else tuple()
        if self.street > 1 and player_id != self.current_player:
            dealt = tuple(['?'] * len(dealt))
        return f"S:{self.street}|P:{player_id}|DLR:{self.dealer}|Board:{player_board}|OppB:{opponent_board}|Dealt:{dealt}|MyDisc:{my_discards}"
