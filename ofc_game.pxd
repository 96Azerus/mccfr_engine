# mccfr_engine/ofc_game.pxd

# Объявляем, что эти классы существуют и доступны для cimport
cdef class Deck:
    cdef list cards
    cdef shuffle(self)
    cdef deal(self, int n)

cdef class Board:
    cdef public dict rows
    # Объявляем методы, которые могут быть вызваны из других Cython-модулей
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
    
    cdef _handle_deal(self)
    cpdef bint is_terminal(self)
    cpdef get_payoffs(self)
    cpdef list get_legal_actions(self)
    cpdef apply_action(self, action)
    cpdef tuple get_infoset_key(self)
