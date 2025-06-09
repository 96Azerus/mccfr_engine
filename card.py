# mccfr_engine/card.py
"""Базовая логика для представления карт OFC Pineapple."""
from typing import List, Tuple, Dict, Optional, Set

# --- Константы Карт ---
STR_RANKS: str = '23456789TJQKA'
INT_RANKS: range = range(13)
PRIMES: List[int] = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41]

RANK_CHAR_TO_INT: Dict[str, int] = {rank: i for i, rank in enumerate(STR_RANKS)}
SUIT_CHAR_TO_INT: Dict[str, int] = {'s': 1, 'h': 2, 'd': 4, 'c': 8}

INT_RANK_TO_CHAR: Dict[int, str] = {i: rank for i, rank in enumerate(STR_RANKS)}
INT_SUIT_TO_CHAR: Dict[int, str] = {1: 's', 2: 'h', 4: 'd', 8: 'c'}

INVALID_CARD: int = -1
NUM_CARDS: int = 52

class Card:
    @staticmethod
    def from_str(card_str: str) -> int:
        if not isinstance(card_str, str) or len(card_str) < 2:
            raise ValueError(f"Invalid card string format: {card_str}")
        
        rank_char = card_str[:-1].upper()
        if rank_char == "10": rank_char = 'T'
        suit_char = card_str[-1].lower()

        rank_int = RANK_CHAR_TO_INT.get(rank_char)
        suit_int = SUIT_CHAR_TO_INT.get(suit_char)

        if rank_int is None: raise ValueError(f"Invalid rank: {rank_char}")
        if suit_int is None: raise ValueError(f"Invalid suit: {suit_char}")

        rank_prime = PRIMES[rank_int]
        bitrank = 1 << (rank_int + 16)
        suit = suit_int << 12
        rank = rank_int << 8
        return bitrank | suit | rank | rank_prime

    @staticmethod
    def to_str(card_int: Optional[int]) -> str:
        if not isinstance(card_int, int) or card_int <= 0: return "??"
        rank_char = INT_RANK_TO_CHAR[Card.get_rank_int(card_int)]
        suit_char = INT_SUIT_TO_CHAR[Card.get_suit_int(card_int)]
        return rank_char + suit_char

    @staticmethod
    def get_rank_int(card_int: int) -> int: return (card_int >> 8) & 0xF
    @staticmethod
    def get_suit_int(card_int: int) -> int: return (card_int >> 12) & 0xF
    @staticmethod
    def get_prime(card_int: int) -> int: return card_int & 0x3F

# Инициализация полной колоды
FULL_DECK_CARDS: Set[int] = {Card.from_str(r + s) for r in STR_RANKS for s in SUIT_CHAR_TO_INT.keys()}
if len(FULL_DECK_CARDS) != 52:
    raise RuntimeError("Deck initialization failed, card count is not 52.")
