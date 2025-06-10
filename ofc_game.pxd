# mccfr_engine/ofc_game.pxd (v13 - добавлены объявления cdef методов)

cdef class Deck:
    cdef public list cards
    # Объявляем внутренние C-методы
    cdef shuffle(self)
    cdef deal(self, int n)

cdef class Board:
    cdef public dict rows
    # Объявляем публичные методы, доступные из Python и Cython
    cpdef get_all_cards(self)
    cpdef get_row_cards(self, str row_name)
    cpdef get_available_slots(self)
    cpdef bint is_foul(self)
    cpdef to_int_tuple(self)

cdef class GameState:
    cdef public int players, street, dealer, current_player
    cdef public list boards, discards
    cdef public list dealt_cards
    cdef public Deck deck
    cdef public bint _is_terminal
    # Объявляем внутренний C-метод
    cdef _handle_deal(self)
    # Объявляем публичные методы
    cpdef bint is_terminal(self)
    cpdef get_payoffs(self)
    cpdef list get_legal_actions(self)
    cpdef apply_action(self, action)
    cpdef tuple get_infoset_key(self)
