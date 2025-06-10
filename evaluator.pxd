cdef class Card:
    @staticmethod
    int from_str(str)
    @staticmethod
    str to_str(int)
    @staticmethod
    int get_rank_int(int)
    @staticmethod
    int get_suit_int(int)

cdef set FULL_DECK_CARDS
