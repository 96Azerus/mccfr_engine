# mccfr_engine/ofc_game.py (v7 - правильное управление состоянием без deepcopy)
import random
import itertools
from typing import List, Tuple, Set, Optional, Dict
from collections import Counter
from copy import copy

from card import Card, FULL_DECK_CARDS
from evaluator import calculate_payoffs, get_hand_rank, get_row_royalty, FANTASY_BONUS, RANK_QUEEN, HAND_TYPE_TRIPS_3

class Deck:
    def __init__(self, cards: Optional[List[int]] = None):
        self.cards = cards if cards is not None else list(FULL_DECK_CARDS)
        if cards is None:
            random.shuffle(self.cards)
    def deal(self, n: int) -> Tuple[List[int], List[int]]:
        dealt = self.cards[:n]
        remaining = self.cards[n:]
        return dealt, remaining

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

    def to_int_tuple(self) -> Tuple[Optional[int], ...]:
        return tuple(c for r in ['top', 'middle', 'bottom'] for c in self.rows[r])

class GameState:
    def __init__(self, from_state: Optional['GameState'] = None):
        if from_state:
            # Быстрое копирование без deepcopy
            self.players = from_state.players
            self.boards = [copy(b) for b in from_state.boards]
            for i, board in enumerate(self.boards):
                board.rows = {k: list(v) for k, v in from_state.boards[i].rows.items()}
            self.discards = [list(d) for d in from_state.discards]
            self.dealt_cards = from_state.dealt_cards
            self.street = from_state.street
            self.dealer = from_state.dealer
            self.current_player = from_state.current_player
            self.deck = from_state.deck
            self._is_terminal = from_state._is_terminal
        else:
            # Инициализация новой игры
            self.players = 2
            self.boards = [Board() for _ in range(self.players)]
            self.discards = [[] for _ in range(self.players)]
            self.dealt_cards: Optional[List[int]] = None
            self.street = 1
            self.dealer = random.randint(0, self.players - 1)
            self.current_player = (self.dealer + 1) % self.players
            self.deck = Deck()
            self._is_terminal = False
            self._handle_deal()

    def _handle_deal(self):
        num_to_deal = 5 if self.street == 1 else 3
        dealt, remaining = self.deck.deal(num_to_deal)
        self.dealt_cards = dealt
        self.deck = Deck(remaining)
        if not self.dealt_cards or len(self.dealt_cards) < num_to_deal:
             self._is_terminal = True

    def is_terminal(self) -> bool:
        if self._is_terminal: return True
        if self.street > 5: return True
        if all(len(b.get_all_cards()) == 13 for b in self.boards): return True
        return False

    def get_payoffs(self) -> List[float]:
        fantasy_payoffs = [0.0] * self.players
        for i, board in enumerate(self.boards):
            if len(board.get_row_cards('top')) == 3 and not board.is_foul():
                _, hand_type, _ = get_hand_rank(board.get_row_cards('top'))
                bonus = 0
                if hand_type == HAND_TYPE_TRIPS_3:
                    trip_rank = Counter(Card.get_rank_int(c) for c in board.get_row_cards('top')).most_common(1)[0][0]
                    bonus = FANTASY_BONUS.get('trips', 30) + trip_rank
                else:
                    ranks = Counter(Card.get_rank_int(c) for c in board.get_row_cards('top'))
                    pair_rank = next((r for r, count in ranks.items() if count == 2), -1)
                    if pair_rank >= RANK_QUEEN:
                        bonus = FANTASY_BONUS.get(pair_rank, 0)
                if bonus > 0:
                    fantasy_payoffs[i] += bonus
                    fantasy_payoffs[1-i] -= bonus
        
        base_payoffs = calculate_payoffs(self.boards[0], self.boards[1])
        return [base + fantasy for base, fantasy in zip(base_payoffs, fantasy_payoffs)]

    def get_legal_actions(self) -> List[Tuple]:
        if self.is_terminal() or not self.dealt_cards: return []
        
        cards_to_place_options = []
        if self.street == 1:
            cards_to_place_options.append((self.dealt_cards, None))
        else:
            cards_to_place = self.dealt_cards[:-1]
            discarded_card = self.dealt_cards[-1]
            cards_to_place_options.append((cards_to_place, discarded_card))

        actions = set()
        available_slots = self.boards[self.current_player].get_available_slots()
        
        for cards_to_place, discarded_card in cards_to_place_options:
            if len(available_slots) < len(cards_to_place): continue
            
            limit = 20 if len(cards_to_place) > 2 else 60
            slot_permutations = list(itertools.permutations(available_slots, len(cards_to_place)))
            if len(slot_permutations) > limit:
                slot_permutations = random.sample(slot_permutations, limit)

            for slots in slot_permutations:
                placement = tuple(zip(cards_to_place, slots))
                actions.add((placement, discarded_card))
        
        return list(actions)

    def apply_action(self, action: Optional[Tuple]) -> 'GameState':
        new_state = GameState(from_state=self)
        
        if action:
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

    def get_infoset_key(self) -> Tuple:
        player_board = self.boards[self.current_player].to_int_tuple()
        opponent_board = self.boards[(self.current_player + 1) % self.players].to_int_tuple()
        my_discards = tuple(sorted(self.discards[self.current_player]))
        dealt = tuple(sorted(self.dealt_cards)) if self.dealt_cards else tuple()
        
        return (self.street, self.current_player, player_board, opponent_board, dealt, my_discards)
