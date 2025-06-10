# mccfr_engine/ofc_game.pyx (v10)
import random
import itertools
from typing import List, Tuple, Set, Optional, Dict
from collections import Counter
from libc.stdlib cimport rand, RAND_MAX

# Обычный импорт из .py файлов
import card
import evaluator

# cimport из .pxd файла
from ofc_game cimport Deck, Board

cdef class Deck:
    def __cinit__(self, list cards=None):
        if cards is not None:
            self.cards = cards
        else:
            self.cards = list(card.FULL_DECK_CARDS)
            self.shuffle()

    cdef shuffle(self):
        cdef int i, j, n
        n = len(self.cards)
        for i in range(n - 1, 0, -1):
            j = <int>(rand() / (RAND_MAX + 1.0) * (i + 1))
            self.cards[i], self.cards[j] = self.cards[j], self.cards[i]

    cdef deal(self, int n):
        cdef list dealt = self.cards[:n]
        cdef list remaining = self.cards[n:]
        return dealt, remaining

cdef class Board:
    def __cinit__(self):
        self.rows = {'top': [None]*3, 'middle': [None]*5, 'bottom': [None]*5}
    
    def get_all_cards(self):
        # ИСПРАВЛЕНО: Убираем генератор
        all_c = set()
        for row in self.rows.values():
            for c in row:
                if c is not None:
                    all_c.add(c)
        return all_c

    def get_row_cards(self, str row_name):
        return [c for c in self.rows[row_name] if c is not None]

    def get_available_slots(self):
        # ИСПРАВЛЕНО: Убираем генератор
        slots = []
        for r, row_slots in self.rows.items():
            for i, c in enumerate(row_slots):
                if c is None:
                    slots.append((r, i))
        return slots

    def is_foul(self):
        if len(self.get_row_cards('top')) != 3 or len(self.get_row_cards('middle')) != 5 or len(self.get_row_cards('bottom')) != 5:
            return False
        top_rank, _, _ = evaluator.get_hand_rank(self.get_row_cards('top'))
        mid_rank, _, _ = evaluator.get_hand_rank(self.get_row_cards('middle'))
        bot_rank, _, _ = evaluator.get_hand_rank(self.get_row_cards('bottom'))
        return (top_rank < mid_rank) or (mid_rank < bot_rank)

    def to_int_tuple(self):
        # ИСПРАВЛЕНО: Убираем генератор
        t = []
        for r in ['top', 'middle', 'bottom']:
            for c in self.rows[r]:
                t.append(c)
        return tuple(t)

cdef class GameState:
    def __cinit__(self, GameState from_state=None):
        if from_state:
            self.players = from_state.players
            self.boards = [Board() for _ in range(self.players)]
            for i in range(self.players):
                self.boards[i].rows = {k: list(v) for k, v in from_state.boards[i].rows.items()}
            self.discards = [list(d) for d in from_state.discards]
            self.dealt_cards = from_state.dealt_cards
            self.street = from_state.street
            self.dealer = from_state.dealer
            self.current_player = from_state.current_player
            self.deck = from_state.deck
            self._is_terminal = from_state._is_terminal
        else:
            self.players = 2
            self.boards = [Board() for _ in range(self.players)]
            self.discards = [[] for _ in range(self.players)]
            self.dealt_cards = None
            self.street = 1
            self.dealer = <int>(rand() / (RAND_MAX + 1.0) * self.players)
            self.current_player = (self.dealer + 1) % self.players
            self.deck = Deck()
            self._is_terminal = False
            self._handle_deal()

    cdef _handle_deal(self):
        cdef int num_to_deal = 5 if self.street == 1 else 3
        dealt, remaining = self.deck.deal(num_to_deal)
        self.dealt_cards = dealt
        self.deck = Deck(remaining)
        if not self.dealt_cards or len(self.dealt_cards) < num_to_deal:
             self._is_terminal = True

    def is_terminal(self):
        if self._is_terminal: return True
        if self.street > 5: return True
        # ИСПРАВЛЕНО: Убираем генератор
        for b in self.boards:
            if len(b.get_all_cards()) == 13:
                return True
        return False

    def get_payoffs(self):
        return evaluator.calculate_payoffs(self.boards[0], self.boards[1])

    def get_legal_actions(self):
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

    def apply_action(self, action):
        new_state = GameState(from_state=self)
        
        if action:
            placement, discarded_card = action
            for c, (row, idx) in placement:
                new_state.boards[new_state.current_player].rows[row][idx] = c
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

    def get_infoset_key(self):
        player_board = self.boards[self.current_player].to_int_tuple()
        opponent_board = self.boards[(self.current_player + 1) % self.players].to_int_tuple()
        my_discards = tuple(sorted(self.discards[self.current_player]))
        dealt = tuple(sorted(self.dealt_cards)) if self.dealt_cards else tuple()
        
        return (self.street, self.current_player, player_board, opponent_board, dealt, my_discards)
