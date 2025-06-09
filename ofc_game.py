# mccfr_engine/ofc_game.py (v4 - исправления логики)
import random
import itertools
from typing import List, Tuple, Set, Optional, Dict
from copy import deepcopy
from collections import Counter

from card import Card, FULL_DECK_CARDS
from evaluator import calculate_payoffs, get_hand_rank, get_row_royalty, FANTASY_BONUS, RANK_QUEEN, HAND_TYPE_TRIPS_3, evaluator_5card_instance

class Deck:
    def __init__(self, cards_to_exclude: Set[int] = None):
        self.cards = list(FULL_DECK_CARDS - (cards_to_exclude or set()))
        random.shuffle(self.cards)
    def deal(self, n: int) -> List[int]:
        dealt = []
        for _ in range(n):
            if self.cards:
                dealt.append(self.cards.pop())
        return dealt

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

def score_placement_heuristic(board: Board) -> float:
    score = 0.0
    score += board.get_total_royalty() * 1.5 
    all_cards = board.get_all_cards()
    ranks = [Card.get_rank_int(c) for c in all_cards]
    rank_counts = Counter(ranks)
    for rank, count in rank_counts.items():
        if count == 2: score += 2
        if count == 3: score += 10
        if count == 4: score += 25
    top_cards = board.get_row_cards('top')
    if top_cards:
        top_ranks = [Card.get_rank_int(c) for c in top_cards]
        if max(top_ranks) < 8: score -= 5
    return score

class GameState:
    def __init__(self, players=2):
        self.players = players
        self.boards = [Board() for _ in range(players)]
        self.discards = [[] for _ in range(players)]
        self.dealt_cards: Optional[List[int]] = None
        self.street = 1
        self.dealer = random.randint(0, players - 1)
        self.current_player = (self.dealer + 1) % self.players
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
        # Проверка на Фантазию (упрощенная)
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
             if self.street > 5 or all(len(b.get_all_cards()) == 13 for b in self.boards):
                 self._is_terminal = True
             else:
                 return [0.0] * self.players
        base_payoffs = calculate_payoffs(self.boards[0], self.boards[1])
        return [base + fantasy for base, fantasy in zip(base_payoffs, self._payoffs)]

    def get_legal_actions(self) -> List[Tuple]:
        if self.is_terminal() or not self.dealt_cards: return []
        
        cards_to_place_options = []
        if self.street == 1:
            cards_to_place_options.append((self.dealt_cards, None))
        else:
            # Упрощенная логика сброса для скорости
            cards_to_place = self.dealt_cards[:-1]
            discarded_card = self.dealt_cards[-1]
            cards_to_place_options.append((cards_to_place, discarded_card))

        actions = set()
        available_slots = self.boards[self.current_player].get_available_slots()
        
        for cards_to_place, discarded_card in cards_to_place_options:
            if len(available_slots) < len(cards_to_place): continue
            
            # Ограничиваем количество перестановок
            limit = 40 if len(cards_to_place) > 2 else 120
            slot_permutations = list(itertools.permutations(available_slots, len(cards_to_place)))
            if len(slot_permutations) > limit:
                slot_permutations = random.sample(slot_permutations, limit)

            for slots in slot_permutations:
                placement = tuple(zip(cards_to_place, slots))
                actions.add((placement, discarded_card))
        
        return list(actions)

    def apply_action(self, action: Optional[Tuple]) -> 'GameState':
        new_state = deepcopy(self)
        
        if action: # Если есть действие (не пустой ход)
            placement, discarded_card = action
            for card, (row, idx) in placement:
                new_state.boards[new_state.current_player].rows[row][idx] = card
            if discarded_card is not None:
                new_state.discards[new_state.current_player].append(discarded_card)

        # Переход хода
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
        
        # На улице 1 карты оппонента видны, но мы это опускаем для уменьшения пространства состояний.
        # MCCFR будет учиться играть против диапазона, что более общо.
        # Важно, что мы видим свою руку.
        if self.street > 1:
            # На улицах 2-5 мы не видим карты оппонента, поэтому dealt не включаем в ключ для оппонента
            if player_id != self.current_player:
                dealt = tuple(['?'] * len(dealt))

        return f"S:{self.street}|P:{player_id}|DLR:{self.dealer}|Board:{player_board}|OppB:{opponent_board}|Dealt:{dealt}|MyDisc:{my_discards}"
