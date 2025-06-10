# mccfr_engine/ofc_game.pxd (v12)

# Объявляем C-уровень наших будущих скомпилированных классов
# БЕЗ cimport из .py файлов

cdef class Deck:
    cdef public list cards

cdef class Board:
    cdef public dict rows

cdef class GameState:
    cdef public int players, street, dealer, current_player
    cdef public list boards, discards
    cdef public list dealt_cards
    cdef public Deck deck
    cdef public bint _is_terminal
