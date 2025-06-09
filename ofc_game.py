# ofc_game.py
import random
import itertools
from typing import List, Tuple, Set, Optional, Dict
from copy import deepcopy

from card import Card, FULL_DECK_CARDS
from evaluator import calculate_payoffs, get_hand_rank, get_row_royalty, FANTASY_BONUS, RANK_QUEEN, HAND_TYPE_TRIPS_3

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

class GameState:
    def __init__(self, players=2):
        self.players = players
        self.boards = [Board() for _ in range(players)]
        self.discards = [[] for _ in range(players)]
        self.dealt_cards: Optional[List[int]] = None
        self.street = 1
        self.current_player = random.randint(0, players - 1)
        self.deck = Deck()
        self._is_terminal = False
        self._payoffs = [0.0] * players
        self._handle_deal()

    def _handle_deal(self):
        num_to_deal = 5 if self.street == 1 else 3
        self.dealt_cards = self.deck.deal(num_to_deal)
        if not self.dealt_cards: self._is_terminal = True

    def is_terminal(self) -> bool:
        if self._is_terminal: return True
        # Проверка на Фантазию (упрощенная)
        for i, board in enumerate(self.boards):
            if len(board.get_row_cards('top')) == 3 and not board.is_foul():
                _, hand_type, _ = get_hand_rank(board.get_row_cards('top'))
                if hand_type == HAND_TYPE_TRIPS_3:
                    self._payoffs[i] += FANTASY_BONUS['trips']
                    self._payoffs[1-i] -= FANTASY_BONUS['trips']
                    self._is_terminal = True
                    return True
                
                ranks = Counter(Card.get_rank_int(c) for c in board.get_row_cards('top'))
                pair_rank = next((r for r, count in ranks.items() if count == 2), -1)
                if pair_rank >= RANK_QUEEN:
                    bonus = FANTASY_BONUS.get(pair_rank, 0)
                    self._payoffs[i] += bonus
                    self._payoffs[1-i] -= bonus
                    self._is_terminal = True
                    return True
        return False

    def get_payoffs(self) -> List[float]:
        if not self.is_terminal(): return [0.0] * self.players
        base_payoffs = calculate_payoffs(self.boards[0], self.boards[1])
        return [base + fantasy for base, fantasy in zip(base_payoffs, self._payoffs)]

    def get_legal_actions(self) -> List[Tuple]:
        if self.is_terminal(): return []
        
        cards_to_place_options = []
        if self.street == 1:
            cards_to_place_options.append((self.dealt_cards, None)) # (карты для расстановки, сброшенная карта)
        else:
            for card_to_discard in self.dealt_cards:
                cards_to_place = [c for c in self.dealt_cards if c != card_to_discard]
                cards_to_place_options.append((cards_to_place, card_to_discard))

        actions = []
        available_slots = self.boards[self.current_player].get_available_slots()
        
        for cards_to_place, discarded_card in cards_to_place_options:
            if len(available_slots) < len(cards_to_place): continue
            
            # Ограничиваем количество перестановок для производительности
            slot_permutations = list(itertools.permutations(available_slots, len(cards_to_place)))
            if len(slot_permutations) > 20: # Важный параметр для тюнинга
                slot_permutations = random.sample(slot_permutations, 20)

            for slots in slot_permutations:
                placement = tuple(zip(cards_to_place, slots))
                actions.append((placement, discarded_card))
        return actions

    def apply_action(self, action: Tuple) -> 'GameState':
        new_state = deepcopy(self)
        placement, discarded_card = action
        
        for card, (row, idx) in placement:
            new_state.boards[new_state.current_player].rows[row][idx] = card
        
        if discarded_card is not None:
            new_state.discards[new_state.current_player].append(discarded_card)

        # Переход хода
        new_state.current_player = (new_state.current_player + 1) % new_state.players
        if new_state.current_player == 0: # Если круг завершен
            new_state.street += 1
        
        if new_state.street > 5:
            new_state._is_terminal = True
        else:
            new_state._handle_deal()
            
        return new_state

    def get_infoset_key(self, player_id: int) -> str:
        player_board = self.boards[player_id].to_str_tuple()
        opponent_board = self.boards[1 - player_id].to_str_tuple()
        my_discards = tuple(sorted(self.discards[player_id]))
        
        # На первой улице карты оппонента видны, но для простоты инфосета
        # мы можем это опустить, т.к. MCCFR все равно будет играть против диапазона.
        # Главное - знать свою руку.
        dealt = tuple(sorted(self.dealt_cards)) if self.dealt_cards else tuple()

        return f"S{self.street}|P{player_id}|Board:{player_board}|OppB:{opponent_board}|Dealt:{dealt}|MyDisc:{my_discards}"
