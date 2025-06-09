# mccfr_engine/evaluator.py
"""
Модуль для оценки рук и подсчета очков в OFC Pineapple.
Объединяет проверенные эвалюаторы для 3 и 5 карт и логику роялти.
"""
import itertools
import logging
from collections import Counter
from typing import List, Tuple, Dict, Optional

from card import Card, PRIMES, INT_RANKS, INVALID_CARD, STR_RANKS

# --- ofc_evaluator_5card.py content ---
class LookupTable5Card:
    MAX_STRAIGHT_FLUSH = 10; MAX_FOUR_OF_A_KIND = 166; MAX_FULL_HOUSE = 322
    MAX_FLUSH = 1599; MAX_STRAIGHT = 1609; MAX_THREE_OF_A_KIND = 2467
    MAX_TWO_PAIR = 3325; MAX_PAIR = 6185; MAX_HIGH_CARD = 7462
    WORST_RANK_5CARD = MAX_HIGH_CARD + 1
    RANK_CLASS_TO_STRING = {1: "Straight Flush", 2: "Four of a Kind", 3: "Full House", 4: "Flush", 5: "Straight", 6: "Three of a Kind", 7: "Two Pair", 8: "Pair", 9: "High Card"}
    
    def __init__(self):
        self.flush_lookup: Dict[int, int] = {}
        self.unsuited_lookup: Dict[int, int] = {}
        self._calculate_flushes()
        self._calculate_multiples()

    def _calculate_flushes(self):
        straight_flushes_rank_bits = [0b1111100000000, 0b0111110000000, 0b0011111000000, 0b0001111100000, 0b0000111110000, 0b0000011111000, 0b0000001111100, 0b0000000111110, 0b0000000011111, 0b1000000001111]
        all_flush_rank_bits = [sum(1 << i for i in combo) for combo in itertools.combinations(INT_RANKS, 5)]
        normal_flush_rank_bits = sorted([rb for rb in all_flush_rank_bits if rb not in set(straight_flushes_rank_bits)], reverse=True)
        
        rank = 1
        for sf_bits in straight_flushes_rank_bits:
            self.flush_lookup[self._prime_product_from_rankbits(sf_bits)] = rank; rank += 1
        rank = self.MAX_FULL_HOUSE + 1
        for f_bits in normal_flush_rank_bits:
            self.flush_lookup[self._prime_product_from_rankbits(f_bits)] = rank; rank += 1
        self._calculate_straights_and_highcards(straight_flushes_rank_bits, normal_flush_rank_bits)

    def _calculate_straights_and_highcards(self, straights_rank_bits, highcards_rank_bits):
        rank = self.MAX_FLUSH + 1
        for s_bits in straights_rank_bits:
            self.unsuited_lookup[self._prime_product_from_rankbits(s_bits)] = rank; rank += 1
        rank = self.MAX_PAIR + 1
        for h_bits in highcards_rank_bits:
            self.unsuited_lookup[self._prime_product_from_rankbits(h_bits)] = rank; rank += 1

    def _calculate_multiples(self):
        backwards_ranks = range(len(INT_RANKS) - 1, -1, -1)
        rank = self.MAX_STRAIGHT_FLUSH + 1
        for quad_idx in backwards_ranks:
            for kick_idx in [k for k in backwards_ranks if k != quad_idx]:
                self.unsuited_lookup[PRIMES[quad_idx]**4 * PRIMES[kick_idx]] = rank; rank += 1
        rank = self.MAX_FOUR_OF_A_KIND + 1
        for trip_idx in backwards_ranks:
            for pair_idx in [p for p in backwards_ranks if p != trip_idx]:
                self.unsuited_lookup[PRIMES[trip_idx]**3 * PRIMES[pair_idx]**2] = rank; rank += 1
        rank = self.MAX_STRAIGHT + 1
        for trip_idx in backwards_ranks:
            for k1, k2 in itertools.combinations([k for k in backwards_ranks if k != trip_idx], 2):
                self.unsuited_lookup[PRIMES[trip_idx]**3 * PRIMES[k1] * PRIMES[k2]] = rank; rank += 1
        rank = self.MAX_THREE_OF_A_KIND + 1
        for p1, p2 in itertools.combinations(backwards_ranks, 2):
            for kick_idx in [k for k in backwards_ranks if k != p1 and k != p2]:
                self.unsuited_lookup[PRIMES[p1]**2 * PRIMES[p2]**2 * PRIMES[kick_idx]] = rank; rank += 1
        rank = self.MAX_TWO_PAIR + 1
        for pair_idx in backwards_ranks:
            for k1, k2, k3 in itertools.combinations([k for k in backwards_ranks if k != pair_idx], 3):
                self.unsuited_lookup[PRIMES[pair_idx]**2 * PRIMES[k1] * PRIMES[k2] * PRIMES[k3]] = rank; rank += 1

    def _prime_product_from_rankbits(self, rankbits: int) -> int:
        return int(itertools.accumulate((PRIMES[i] for i in INT_RANKS if rankbits & (1 << i)), func=lambda x, y: x * y, initial=1)[-1])

class Evaluator5Card:
    def __init__(self): self.table = LookupTable5Card()
    def evaluate(self, cards: List[int]) -> int:
        if len(cards) != 5: raise ValueError("Requires 5 cards")
        suit_mask = cards[0] & cards[1] & cards[2] & cards[3] & cards[4] & 0xF000
        if suit_mask != 0:
            rank_bitmask = sum(1 << Card.get_rank_int(c) for c in cards)
            return self.table.flush_lookup.get(self.table._prime_product_from_rankbits(rank_bitmask), self.table.WORST_RANK_5CARD)
        else:
            prime_product = int(itertools.accumulate((Card.get_prime(c) for c in cards), func=lambda x, y: x * y, initial=1)[-1])
            return self.table.unsuited_lookup.get(prime_product, self.table.WORST_RANK_5CARD)
    def get_rank_class(self, hand_rank: int) -> int:
        if not (0 < hand_rank < self.table.WORST_RANK_5CARD): return 9
        if hand_rank <= self.table.MAX_STRAIGHT_FLUSH: return 1
        elif hand_rank <= self.table.MAX_FOUR_OF_A_KIND: return 2
        elif hand_rank <= self.table.MAX_FULL_HOUSE: return 3
        elif hand_rank <= self.table.MAX_FLUSH: return 4
        elif hand_rank <= self.table.MAX_STRAIGHT: return 5
        elif hand_rank <= self.table.MAX_THREE_OF_A_KIND: return 6
        elif hand_rank <= self.table.MAX_TWO_PAIR: return 7
        elif hand_rank <= self.table.MAX_PAIR: return 8
        return 9
    def class_to_string(self, class_int: int) -> str: return self.table.RANK_CLASS_TO_STRING.get(class_int, "Unknown")

evaluator_5card_instance = Evaluator5Card()

# --- ofc_evaluator_3card.py content ---
HAND_TYPE_TRIPS_3 = "Trips"; HAND_TYPE_PAIR_3 = "Pair"; HAND_TYPE_HIGH_CARD_3 = "High Card"
WORST_RANK_3CARD = 455
three_card_lookup: Dict[Tuple[int, int, int], Tuple[int, str, str]] = {
    (12, 12, 12): (1, 'Trips', 'AAA'), (11, 11, 11): (2, 'Trips', 'KKK'), (10, 10, 10): (3, 'Trips', 'QQQ'), (9, 9, 9): (4, 'Trips', 'JJJ'), (8, 8, 8): (5, 'Trips', 'TTT'), (7, 7, 7): (6, 'Trips', '999'), (6, 6, 6): (7, 'Trips', '888'), (5, 5, 5): (8, 'Trips', '777'), (4, 4, 4): (9, 'Trips', '666'), (3, 3, 3): (10, 'Trips', '555'), (2, 2, 2): (11, 'Trips', '444'), (1, 1, 1): (12, 'Trips', '333'), (0, 0, 0): (13, 'Trips', '222'),
    (12, 12, 11): (14, 'Pair', 'AAK'), (12, 12, 10): (15, 'Pair', 'AAQ'), (12, 12, 9): (16, 'Pair', 'AAJ'), (12, 12, 8): (17, 'Pair', 'AAT'), (12, 12, 7): (18, 'Pair', 'AA9'), (12, 12, 6): (19, 'Pair', 'AA8'), (12, 12, 5): (20, 'Pair', 'AA7'), (12, 12, 4): (21, 'Pair', 'AA6'), (12, 12, 3): (22, 'Pair', 'AA5'), (12, 12, 2): (23, 'Pair', 'AA4'), (12, 12, 1): (24, 'Pair', 'AA3'), (12, 12, 0): (25, 'Pair', 'AA2'),
    (11, 11, 10): (27, 'Pair', 'KKQ'), (11, 11, 9): (28, 'Pair', 'KKJ'), (11, 11, 8): (29, 'Pair', 'KKT'), (11, 11, 7): (30, 'Pair', 'KK9'), (11, 11, 6): (31, 'Pair', 'KK8'), (11, 11, 5): (32, 'Pair', 'KK7'), (11, 11, 4): (33, 'Pair', 'KK6'), (11, 11, 3): (34, 'Pair', 'KK5'), (11, 11, 2): (35, 'Pair', 'KK4'), (11, 11, 1): (36, 'Pair', 'KK3'), (11, 11, 0): (37, 'Pair', 'KK2'), (12, 11, 11): (26, 'Pair', 'KKA'),
    (10, 10, 9): (40, 'Pair', 'QQJ'), (10, 10, 8): (41, 'Pair', 'QQT'), (10, 10, 7): (42, 'Pair', 'QQ9'), (10, 10, 6): (43, 'Pair', 'QQ8'), (10, 10, 5): (44, 'Pair', 'QQ7'), (10, 10, 4): (45, 'Pair', 'QQ6'), (10, 10, 3): (46, 'Pair', 'QQ5'), (10, 10, 2): (47, 'Pair', 'QQ4'), (10, 10, 1): (48, 'Pair', 'QQ3'), (10, 10, 0): (49, 'Pair', 'QQ2'), (12, 10, 10): (38, 'Pair', 'QQA'), (11, 10, 10): (39, 'Pair', 'QQK'),
    (9, 9, 8): (53, 'Pair', 'JJT'), (9, 9, 7): (54, 'Pair', 'JJ9'), (9, 9, 6): (55, 'Pair', 'JJ8'), (9, 9, 5): (56, 'Pair', 'JJ7'), (9, 9, 4): (57, 'Pair', 'JJ6'), (9, 9, 3): (58, 'Pair', 'JJ5'), (9, 9, 2): (59, 'Pair', 'JJ4'), (9, 9, 1): (60, 'Pair', 'JJ3'), (9, 9, 0): (61, 'Pair', 'JJ2'), (12, 9, 9): (50, 'Pair', 'JJA'), (11, 9, 9): (51, 'Pair', 'JJK'), (10, 9, 9): (52, 'Pair', 'JJQ'),
    (8, 8, 7): (66, 'Pair', 'TT9'), (8, 8, 6): (67, 'Pair', 'TT8'), (8, 8, 5): (68, 'Pair', 'TT7'), (8, 8, 4): (69, 'Pair', 'TT6'), (8, 8, 3): (70, 'Pair', 'TT5'), (8, 8, 2): (71, 'Pair', 'TT4'), (8, 8, 1): (72, 'Pair', 'TT3'), (8, 8, 0): (73, 'Pair', 'TT2'), (12, 8, 8): (62, 'Pair', 'TTA'), (11, 8, 8): (63, 'Pair', 'TTK'), (10, 8, 8): (64, 'Pair', 'TTQ'), (9, 8, 8): (65, 'Pair', 'TTJ'),
    (7, 7, 6): (79, 'Pair', '998'), (7, 7, 5): (80, 'Pair', '997'), (7, 7, 4): (81, 'Pair', '996'), (7, 7, 3): (82, 'Pair', '995'), (7, 7, 2): (83, 'Pair', '994'), (7, 7, 1): (84, 'Pair', '993'), (7, 7, 0): (85, 'Pair', '992'), (12, 7, 7): (74, 'Pair', '99A'), (11, 7, 7): (75, 'Pair', '99K'), (10, 7, 7): (76, 'Pair', '99Q'), (9, 7, 7): (77, 'Pair', '99J'), (8, 7, 7): (78, 'Pair', '99T'),
    (6, 6, 5): (92, 'Pair', '887'), (6, 6, 4): (93, 'Pair', '886'), (6, 6, 3): (94, 'Pair', '885'), (6, 6, 2): (95, 'Pair', '884'), (6, 6, 1): (96, 'Pair', '883'), (6, 6, 0): (97, 'Pair', '882'), (12, 6, 6): (86, 'Pair', '88A'), (11, 6, 6): (87, 'Pair', '88K'), (10, 6, 6): (88, 'Pair', '88Q'), (9, 6, 6): (89, 'Pair', '88J'), (8, 6, 6): (90, 'Pair', '88T'), (7, 6, 6): (91, 'Pair', '889'),
    (5, 5, 4): (105, 'Pair', '776'), (5, 5, 3): (106, 'Pair', '775'), (5, 5, 2): (107, 'Pair', '774'), (5, 5, 1): (108, 'Pair', '773'), (5, 5, 0): (109, 'Pair', '772'), (12, 5, 5): (98, 'Pair', '77A'), (11, 5, 5): (99, 'Pair', '77K'), (10, 5, 5): (100, 'Pair', '77Q'), (9, 5, 5): (101, 'Pair', '77J'), (8, 5, 5): (102, 'Pair', '77T'), (7, 5, 5): (103, 'Pair', '779'), (6, 5, 5): (104, 'Pair', '778'),
    (4, 4, 3): (118, 'Pair', '665'), (4, 4, 2): (119, 'Pair', '664'), (4, 4, 1): (120, 'Pair', '663'), (4, 4, 0): (121, 'Pair', '662'), (12, 4, 4): (110, 'Pair', '66A'), (11, 4, 4): (111, 'Pair', '66K'), (10, 4, 4): (112, 'Pair', '66Q'), (9, 4, 4): (113, 'Pair', '66J'), (8, 4, 4): (114, 'Pair', '66T'), (7, 4, 4): (115, 'Pair', '669'), (6, 4, 4): (116, 'Pair', '668'), (5, 4, 4): (117, 'Pair', '667'),
    (3, 3, 2): (131, 'Pair', '554'), (3, 3, 1): (132, 'Pair', '553'), (3, 3, 0): (133, 'Pair', '552'), (12, 3, 3): (122, 'Pair', '55A'), (11, 3, 3): (123, 'Pair', '55K'), (10, 3, 3): (124, 'Pair', '55Q'), (9, 3, 3): (125, 'Pair', '55J'), (8, 3, 3): (126, 'Pair', '55T'), (7, 3, 3): (127, 'Pair', '559'), (6, 3, 3): (128, 'Pair', '558'), (5, 3, 3): (129, 'Pair', '557'), (4, 3, 3): (130, 'Pair', '556'),
    (2, 2, 1): (144, 'Pair', '443'), (2, 2, 0): (145, 'Pair', '442'), (12, 2, 2): (134, 'Pair', '44A'), (11, 2, 2): (135, 'Pair', '44K'), (10, 2, 2): (136, 'Pair', '44Q'), (9, 2, 2): (137, 'Pair', '44J'), (8, 2, 2): (138, 'Pair', '44T'), (7, 2, 2): (139, 'Pair', '449'), (6, 2, 2): (140, 'Pair', '448'), (5, 2, 2): (141, 'Pair', '447'), (4, 2, 2): (142, 'Pair', '446'), (3, 2, 2): (143, 'Pair', '445'),
    (1, 1, 0): (157, 'Pair', '332'), (12, 1, 1): (146, 'Pair', '33A'), (11, 1, 1): (147, 'Pair', '33K'), (10, 1, 1): (148, 'Pair', '33Q'), (9, 1, 1): (149, 'Pair', '33J'), (8, 1, 1): (150, 'Pair', '33T'), (7, 1, 1): (151, 'Pair', '339'), (6, 1, 1): (152, 'Pair', '338'), (5, 1, 1): (153, 'Pair', '337'), (4, 1, 1): (154, 'Pair', '336'), (3, 1, 1): (155, 'Pair', '335'), (2, 1, 1): (156, 'Pair', '334'),
    (1, 0, 0): (169, 'Pair', '223'), (12, 0, 0): (158, 'Pair', '22A'), (11, 0, 0): (159, 'Pair', '22K'), (10, 0, 0): (160, 'Pair', '22Q'), (9, 0, 0): (161, 'Pair', '22J'), (8, 0, 0): (162, 'Pair', '22T'), (7, 0, 0): (163, 'Pair', '229'), (6, 0, 0): (164, 'Pair', '228'), (5, 0, 0): (165, 'Pair', '227'), (4, 0, 0): (166, 'Pair', '226'), (3, 0, 0): (167, 'Pair', '225'), (2, 0, 0): (168, 'Pair', '224'),
    (12, 11, 10): (170, 'High Card', 'AKQ'), (12, 11, 9): (171, 'High Card', 'AKJ'), (12, 11, 8): (172, 'High Card', 'AKT'), (12, 11, 7): (173, 'High Card', 'AK9'), (12, 11, 6): (174, 'High Card', 'AK8'), (12, 11, 5): (175, 'High Card', 'AK7'), (12, 11, 4): (176, 'High Card', 'AK6'), (12, 11, 3): (177, 'High Card', 'AK5'), (12, 11, 2): (178, 'High Card', 'AK4'), (12, 11, 1): (179, 'High Card', 'AK3'), (12, 11, 0): (180, 'High Card', 'AK2'),
    (12, 10, 9): (181, 'High Card', 'AQJ'), (12, 10, 8): (182, 'High Card', 'AQT'), (12, 10, 7): (183, 'High Card', 'AQ9'), (12, 10, 6): (184, 'High Card', 'AQ8'), (12, 10, 5): (185, 'High Card', 'AQ7'), (12, 10, 4): (186, 'High Card', 'AQ6'), (12, 10, 3): (187, 'High Card', 'AQ5'), (12, 10, 2): (188, 'High Card', 'AQ4'), (12, 10, 1): (189, 'High Card', 'AQ3'), (12, 10, 0): (190, 'High Card', 'AQ2'),
    (12, 9, 8): (191, 'High Card', 'AJT'), (12, 9, 7): (192, 'High Card', 'AJ9'), (12, 9, 6): (193, 'High Card', 'AJ8'), (12, 9, 5): (194, 'High Card', 'AJ7'), (12, 9, 4): (195, 'High Card', 'AJ6'), (12, 9, 3): (196, 'High Card', 'AJ5'), (12, 9, 2): (197, 'High Card', 'AJ4'), (12, 9, 1): (198, 'High Card', 'AJ3'), (12, 9, 0): (199, 'High Card', 'AJ2'),
    (12, 8, 7): (200, 'High Card', 'AT9'), (12, 8, 6): (201, 'High Card', 'AT8'), (12, 8, 5): (202, 'High Card', 'AT7'), (12, 8, 4): (203, 'High Card', 'AT6'), (12, 8, 3): (204, 'High Card', 'AT5'), (12, 8, 2): (205, 'High Card', 'AT4'), (12, 8, 1): (206, 'High Card', 'AT3'), (12, 8, 0): (207, 'High Card', 'AT2'),
    (12, 7, 6): (208, 'High Card', 'A98'), (12, 7, 5): (209, 'High Card', 'A97'), (12, 7, 4): (210, 'High Card', 'A96'), (12, 7, 3): (211, 'High Card', 'A95'), (12, 7, 2): (212, 'High Card', 'A94'), (12, 7, 1): (213, 'High Card', 'A93'), (12, 7, 0): (214, 'High Card', 'A92'),
    (12, 6, 5): (215, 'High Card', 'A87'), (12, 6, 4): (216, 'High Card', 'A86'), (12, 6, 3): (217, 'High Card', 'A85'), (12, 6, 2): (218, 'High Card', 'A84'), (12, 6, 1): (219, 'High Card', 'A83'), (12, 6, 0): (220, 'High Card', 'A82'),
    (12, 5, 4): (221, 'High Card', 'A76'), (12, 5, 3): (222, 'High Card', 'A75'), (12, 5, 2): (223, 'High Card', 'A74'), (12, 5, 1): (224, 'High Card', 'A73'), (12, 5, 0): (225, 'High Card', 'A72'),
    (12, 4, 3): (226, 'High Card', 'A65'), (12, 4, 2): (227, 'High Card', 'A64'), (12, 4, 1): (228, 'High Card', 'A63'), (12, 4, 0): (229, 'High Card', 'A62'),
    (12, 3, 2): (230, 'High Card', 'A54'), (12, 3, 1): (231, 'High Card', 'A53'), (12, 3, 0): (232, 'High Card', 'A52'),
    (12, 2, 1): (233, 'High Card', 'A43'), (12, 2, 0): (234, 'High Card', 'A42'),
    (12, 1, 0): (235, 'High Card', 'A32'),
    (11, 10, 9): (236, 'High Card', 'KQJ'), (11, 10, 8): (237, 'High Card', 'KQT'), (11, 10, 7): (238, 'High Card', 'KQ9'), (11, 10, 6): (239, 'High Card', 'KQ8'), (11, 10, 5): (240, 'High Card', 'KQ7'), (11, 10, 4): (241, 'High Card', 'KQ6'), (11, 10, 3): (242, 'High Card', 'KQ5'), (11, 10, 2): (243, 'High Card', 'KQ4'), (11, 10, 1): (244, 'High Card', 'KQ3'), (11, 10, 0): (245, 'High Card', 'KQ2'),
    (11, 9, 8): (246, 'High Card', 'KJT'), (11, 9, 7): (247, 'High Card', 'KJ9'), (11, 9, 6): (248, 'High Card', 'KJ8'), (11, 9, 5): (249, 'High Card', 'KJ7'), (11, 9, 4): (250, 'High Card', 'KJ6'), (11, 9, 3): (251, 'High Card', 'KJ5'), (11, 9, 2): (252, 'High Card', 'KJ4'), (11, 9, 1): (253, 'High Card', 'KJ3'), (11, 9, 0): (254, 'High Card', 'KJ2'),
    (11, 8, 7): (255, 'High Card', 'KT9'), (11, 8, 6): (256, 'High Card', 'KT8'), (11, 8, 5): (257, 'High Card', 'KT7'), (11, 8, 4): (258, 'High Card', 'KT6'), (11, 8, 3): (259, 'High Card', 'KT5'), (11, 8, 2): (260, 'High Card', 'KT4'), (11, 8, 1): (261, 'High Card', 'KT3'), (11, 8, 0): (262, 'High Card', 'KT2'),
    (11, 7, 6): (263, 'High Card', 'K98'), (11, 7, 5): (264, 'High Card', 'K97'), (11, 7, 4): (265, 'High Card', 'K96'), (11, 7, 3): (266, 'High Card', 'K95'), (11, 7, 2): (267, 'High Card', 'K94'), (11, 7, 1): (268, 'High Card', 'K93'), (11, 7, 0): (269, 'High Card', 'K92'),
    (11, 6, 5): (270, 'High Card', 'K87'), (11, 6, 4): (271, 'High Card', 'K86'), (11, 6, 3): (272, 'High Card', 'K85'), (11, 6, 2): (273, 'High Card', 'K84'), (11, 6, 1): (274, 'High Card', 'K83'), (11, 6, 0): (275, 'High Card', 'K82'),
    (11, 5, 4): (276, 'High Card', 'K76'), (11, 5, 3): (277, 'High Card', 'K75'), (11, 5, 2): (278, 'High Card', 'K74'), (11, 5, 1): (279, 'High Card', 'K73'), (11, 5, 0): (280, 'High Card', 'K72'),
    (11, 4, 3): (281, 'High Card', 'K65'), (11, 4, 2): (282, 'High Card', 'K64'), (11, 4, 1): (283, 'High Card', 'K63'), (11, 4, 0): (284, 'High Card', 'K62'),
    (11, 3, 2): (285, 'High Card', 'K54'), (11, 3, 1): (286, 'High Card', 'K53'), (11, 3, 0): (287, 'High Card', 'K52'),
    (11, 2, 1): (288, 'High Card', 'K43'), (11, 2, 0): (289, 'High Card', 'K42'),
    (11, 1, 0): (290, 'High Card', 'K32'),
    (10, 9, 8): (291, 'High Card', 'QJT'), (10, 9, 7): (292, 'High Card', 'QJ9'), (10, 9, 6): (293, 'High Card', 'QJ8'), (10, 9, 5): (294, 'High Card', 'QJ7'), (10, 9, 4): (295, 'High Card', 'QJ6'), (10, 9, 3): (296, 'High Card', 'QJ5'), (10, 9, 2): (297, 'High Card', 'QJ4'), (10, 9, 1): (298, 'High Card', 'QJ3'), (10, 9, 0): (299, 'High Card', 'QJ2'),
    (10, 8, 7): (300, 'High Card', 'QT9'), (10, 8, 6): (301, 'High Card', 'QT8'), (10, 8, 5): (302, 'High Card', 'QT7'), (10, 8, 4): (303, 'High Card', 'QT6'), (10, 8, 3): (304, 'High Card', 'QT5'), (10, 8, 2): (305, 'High Card', 'QT4'), (10, 8, 1): (306, 'High Card', 'QT3'), (10, 8, 0): (307, 'High Card', 'QT2'),
    (10, 7, 6): (308, 'High Card', 'Q98'), (10, 7, 5): (309, 'High Card', 'Q97'), (10, 7, 4): (310, 'High Card', 'Q96'), (10, 7, 3): (311, 'High Card', 'Q95'), (10, 7, 2): (312, 'High Card', 'Q94'), (10, 7, 1): (313, 'High Card', 'Q93'), (10, 7, 0): (314, 'High Card', 'Q92'),
    (10, 6, 5): (315, 'High Card', 'Q87'), (10, 6, 4): (316, 'High Card', 'Q86'), (10, 6, 3): (317, 'High Card', 'Q85'), (10, 6, 2): (318, 'High Card', 'Q84'), (10, 6, 1): (319, 'High Card', 'Q83'), (10, 6, 0): (320, 'High Card', 'Q82'),
    (10, 5, 4): (321, 'High Card', 'Q76'), (10, 5, 3): (322, 'High Card', 'Q75'), (10, 5, 2): (323, 'High Card', 'Q74'), (10, 5, 1): (324, 'High Card', 'Q73'), (10, 5, 0): (325, 'High Card', 'Q72'),
    (10, 4, 3): (326, 'High Card', 'Q65'), (10, 4, 2): (327, 'High Card', 'Q64'), (10, 4, 1): (328, 'High Card', 'Q63'), (10, 4, 0): (329, 'High Card', 'Q62'),
    (10, 3, 2): (330, 'High Card', 'Q54'), (10, 3, 1): (331, 'High Card', 'Q53'), (10, 3, 0): (332, 'High Card', 'Q52'),
    (10, 2, 1): (333, 'High Card', 'Q43'), (10, 2, 0): (334, 'High Card', 'Q42'),
    (10, 1, 0): (335, 'High Card', 'Q32'),
    (9, 8, 7): (336, 'High Card', 'JT9'), (9, 8, 6): (337, 'High Card', 'JT8'), (9, 8, 5): (338, 'High Card', 'JT7'), (9, 8, 4): (339, 'High Card', 'JT6'), (9, 8, 3): (340, 'High Card', 'JT5'), (9, 8, 2): (341, 'High Card', 'JT4'), (9, 8, 1): (342, 'High Card', 'JT3'), (9, 8, 0): (343, 'High Card', 'JT2'),
    (9, 7, 6): (344, 'High Card', 'J98'), (9, 7, 5): (345, 'High Card', 'J97'), (9, 7, 4): (346, 'High Card', 'J96'), (9, 7, 3): (347, 'High Card', 'J95'), (9, 7, 2): (348, 'High Card', 'J94'), (9, 7, 1): (349, 'High Card', 'J93'), (9, 7, 0): (350, 'High Card', 'J92'),
    (9, 6, 5): (351, 'High Card', 'J87'), (9, 6, 4): (352, 'High Card', 'J86'), (9, 6, 3): (353, 'High Card', 'J85'), (9, 6, 2): (354, 'High Card', 'J84'), (9, 6, 1): (355, 'High Card', 'J83'), (9, 6, 0): (356, 'High Card', 'J82'),
    (9, 5, 4): (357, 'High Card', 'J76'), (9, 5, 3): (358, 'High Card', 'J75'), (9, 5, 2): (359, 'High Card', 'J74'), (9, 5, 1): (360, 'High Card', 'J73'), (9, 5, 0): (361, 'High Card', 'J72'),
    (9, 4, 3): (362, 'High Card', 'J65'), (9, 4, 2): (363, 'High Card', 'J64'), (9, 4, 1): (364, 'High Card', 'J63'), (9, 4, 0): (365, 'High Card', 'J62'),
    (9, 3, 2): (366, 'High Card', 'J54'), (9, 3, 1): (367, 'High Card', 'J53'), (9, 3, 0): (368, 'High Card', 'J52'),
    (9, 2, 1): (369, 'High Card', 'J43'), (9, 2, 0): (370, 'High Card', 'J42'),
    (9, 1, 0): (371, 'High Card', 'J32'),
    (8, 7, 6): (372, 'High Card', 'T98'), (8, 7, 5): (373, 'High Card', 'T97'), (8, 7, 4): (374, 'High Card', 'T96'), (8, 7, 3): (375, 'High Card', 'T95'), (8, 7, 2): (376, 'High Card', 'T94'), (8, 7, 1): (377, 'High Card', 'T93'), (8, 7, 0): (378, 'High Card', 'T92'),
    (8, 6, 5): (379, 'High Card', 'T87'), (8, 6, 4): (380, 'High Card', 'T86'), (8, 6, 3): (381, 'High Card', 'T85'), (8, 6, 2): (382, 'High Card', 'T84'), (8, 6, 1): (383, 'High Card', 'T83'), (8, 6, 0): (384, 'High Card', 'T82'),
    (8, 5, 4): (385, 'High Card', 'T76'), (8, 5, 3): (386, 'High Card', 'T75'), (8, 5, 2): (387, 'High Card', 'T74'), (8, 5, 1): (388, 'High Card', 'T73'), (8, 5, 0): (389, 'High Card', 'T72'),
    (8, 4, 3): (390, 'High Card', 'T65'), (8, 4, 2): (391, 'High Card', 'T64'), (8, 4, 1): (392, 'High Card', 'T63'), (8, 4, 0): (393, 'High Card', 'T62'),
    (8, 3, 2): (394, 'High Card', 'T54'), (8, 3, 1): (395, 'High Card', 'T53'), (8, 3, 0): (396, 'High Card', 'T52'),
    (8, 2, 1): (397, 'High Card', 'T43'), (8, 2, 0): (398, 'High Card', 'T42'),
    (8, 1, 0): (399, 'High Card', 'T32'),
    (7, 6, 5): (400, 'High Card', '987'), (7, 6, 4): (401, 'High Card', '986'), (7, 6, 3): (402, 'High Card', '985'), (7, 6, 2): (403, 'High Card', '984'), (7, 6, 1): (404, 'High Card', '983'), (7, 6, 0): (405, 'High Card', '982'),
    (7, 5, 4): (406, 'High Card', '976'), (7, 5, 3): (407, 'High Card', '975'), (7, 5, 2): (408, 'High Card', '974'), (7, 5, 1): (409, 'High Card', '973'), (7, 5, 0): (410, 'High Card', '972'),
    (7, 4, 3): (411, 'High Card', '965'), (7, 4, 2): (412, 'High Card', '964'), (7, 4, 1): (413, 'High Card', '963'), (7, 4, 0): (414, 'High Card', '962'),
    (7, 3, 2): (415, 'High Card', '954'), (7, 3, 1): (416, 'High Card', '953'), (7, 3, 0): (417, 'High Card', '952'),
    (7, 2, 1): (418, 'High Card', '943'), (7, 2, 0): (419, 'High Card', '942'),
    (7, 1, 0): (420, 'High Card', '932'),
    (6, 5, 4): (421, 'High Card', '876'), (6, 5, 3): (422, 'High Card', '875'), (6, 5, 2): (423, 'High Card', '874'), (6, 5, 1): (424, 'High Card', '873'), (6, 5, 0): (425, 'High Card', '872'),
    (6, 4, 3): (426, 'High Card', '865'), (6, 4, 2): (427, 'High Card', '864'), (6, 4, 1): (428, 'High Card', '863'), (6, 4, 0): (429, 'High Card', '862'),
    (6, 3, 2): (430, 'High Card', '854'), (6, 3, 1): (431, 'High Card', '853'), (6, 3, 0): (432, 'High Card', '852'),
    (6, 2, 1): (433, 'High Card', '843'), (6, 2, 0): (434, 'High Card', '842'),
    (6, 1, 0): (435, 'High Card', '832'),
    (5, 4, 3): (436, 'High Card', '765'), (5, 4, 2): (437, 'High Card', '764'), (5, 4, 1): (438, 'High Card', '763'), (5, 4, 0): (439, 'High Card', '762'),
    (5, 3, 2): (440, 'High Card', '754'), (5, 3, 1): (441, 'High Card', '753'), (5, 3, 0): (442, 'High Card', '752'),
    (5, 2, 1): (443, 'High Card', '743'), (5, 2, 0): (444, 'High Card', '742'),
    (5, 1, 0): (445, 'High Card', '732'),
    (4, 3, 2): (446, 'High Card', '654'), (4, 3, 1): (447, 'High Card', '653'), (4, 3, 0): (448, 'High Card', '652'),
    (4, 2, 1): (449, 'High Card', '643'), (4, 2, 0): (450, 'High Card', '642'),
    (4, 1, 0): (451, 'High Card', '632'),
    (3, 2, 1): (452, 'High Card', '543'), (3, 2, 0): (453, 'High Card', '542'),
    (3, 1, 0): (454, 'High Card', '532'),
    (2, 1, 0): (455, 'High Card', '432')
}
def evaluate_3_card_ofc(card1: int, card2: int, card3: int) -> Tuple[int, str, str]:
    ranks = sorted([Card.get_rank_int(c) for c in [card1, card2, card3]], reverse=True)
    result = three_card_lookup.get(tuple(ranks))
    if result is None: raise ValueError("Combination not found")
    return result

# --- Общая логика оценки и роялти ---
WORST_CLASS = 9
WORST_RANK = max(evaluator_5card_instance.table.MAX_HIGH_CARD, WORST_RANK_3CARD) + 1
HAND_TYPE_TO_CLASS_3CARD = {HAND_TYPE_TRIPS_3: 6, HAND_TYPE_PAIR_3: 8, HAND_TYPE_HIGH_CARD_3: 9}

def get_hand_rank(cards: List[int]) -> Tuple[int, int, str]:
    if not cards: return WORST_RANK, WORST_CLASS, "Invalid"
    num_cards = len(cards)
    if num_cards == 3:
        rank, type_str, _ = evaluate_3_card_ofc(*cards)
        hand_class = HAND_TYPE_TO_CLASS_3CARD.get(type_str, WORST_CLASS)
        return rank, hand_class, type_str
    elif num_cards == 5:
        rank = evaluator_5card_instance.evaluate(cards)
        hand_class = evaluator_5card_instance.get_rank_class(rank)
        type_str = evaluator_5card_instance.class_to_string(hand_class)
        return rank, hand_class, type_str
    return WORST_RANK, WORST_CLASS, "Invalid"

from card import RANK_CHAR_TO_INT as RANK_MAP
RANK_2=RANK_MAP['2'];RANK_3=RANK_MAP['3'];RANK_4=RANK_MAP['4'];RANK_5=RANK_MAP['5'];RANK_6=RANK_MAP['6'];RANK_7=RANK_MAP['7'];RANK_8=RANK_MAP['8'];RANK_9=RANK_MAP['9'];RANK_TEN=RANK_MAP['T'];RANK_JACK=RANK_MAP['J'];RANK_QUEEN=RANK_MAP['Q'];RANK_KING=RANK_MAP['K'];RANK_ACE=RANK_MAP['A']
ROYALTY_BOTTOM_POINTS: Dict[str, int] = { "Straight": 2, "Flush": 4, "Full House": 6, "Four of a Kind": 10, "Straight Flush": 15, "Royal Flush": 25 }
ROYALTY_MIDDLE_POINTS: Dict[str, int] = { "Three of a Kind": 2, "Straight": 4, "Flush": 8, "Full House": 12, "Four of a Kind": 20, "Straight Flush": 30, "Royal Flush": 50 }
ROYALTY_TOP_PAIRS: Dict[int, int] = { RANK_6: 1, RANK_7: 2, RANK_8: 3, RANK_9: 4, RANK_TEN: 5, RANK_JACK: 6, RANK_QUEEN: 10, RANK_KING: 11, RANK_ACE: 12 }
ROYALTY_TOP_TRIPS: Dict[int, int] = { RANK_2: 10, RANK_3: 11, RANK_4: 12, RANK_5: 13, RANK_6: 14, RANK_7: 15, RANK_8: 16, RANK_9: 17, RANK_TEN: 18, RANK_JACK: 19, RANK_QUEEN: 20, RANK_KING: 21, RANK_ACE: 22 }

def get_row_royalty(cards: List[int], row_name: str) -> int:
    if not cards: return 0
    rank_val, hand_class_val, type_str_val = get_hand_rank(cards)
    if rank_val == WORST_RANK: return 0
    if row_name == "top":
        if hand_class_val == 6: # Trips
            trip_rank = Counter(Card.get_rank_int(c) for c in cards).most_common(1)[0][0]
            return ROYALTY_TOP_TRIPS.get(trip_rank, 0)
        elif hand_class_val == 8: # Pair
            pair_rank = Counter(Card.get_rank_int(c) for c in cards).most_common(1)[0][0]
            return ROYALTY_TOP_PAIRS.get(pair_rank, 0)
    elif row_name == "middle":
        return ROYALTY_MIDDLE_POINTS.get(type_str_val, 0)
    elif row_name == "bottom":
        return ROYALTY_BOTTOM_POINTS.get(type_str_val, 0)
    return 0

# --- Новая логика для подсчета итогов ---
FANTASY_BONUS = {RANK_QUEEN: 15, RANK_KING: 20, RANK_ACE: 25, 'trips': 30}
SCOOP_BONUS = 3

def calculate_payoffs(board_p1, board_p2) -> Tuple[float, float]:
    p1_foul = board_p1.is_foul()
    p2_foul = board_p2.is_foul()
    if p1_foul and p2_foul: return 0.0, 0.0
    if p1_foul: return -float(SCOOP_BONUS + (get_row_royalty(board_p2.get_row_cards('top'), 'top') + get_row_royalty(board_p2.get_row_cards('middle'), 'middle') + get_row_royalty(board_p2.get_row_cards('bottom'), 'bottom'))), float(SCOOP_BONUS + (get_row_royalty(board_p2.get_row_cards('top'), 'top') + get_row_royalty(board_p2.get_row_cards('middle'), 'middle') + get_row_royalty(board_p2.get_row_cards('bottom'), 'bottom')))
    if p2_foul: return float(SCOOP_BONUS + (get_row_royalty(board_p1.get_row_cards('top'), 'top') + get_row_royalty(board_p1.get_row_cards('middle'), 'middle') + get_row_royalty(board_p1.get_row_cards('bottom'), 'bottom'))), -float(SCOOP_BONUS + (get_row_royalty(board_p1.get_row_cards('top'), 'top') + get_row_royalty(board_p1.get_row_cards('middle'), 'middle') + get_row_royalty(board_p1.get_row_cards('bottom'), 'bottom')))

    line_score_p1 = 0
    for row in ['top', 'middle', 'bottom']:
        p1_rank, _, _ = get_hand_rank(board_p1.get_row_cards(row))
        p2_rank, _, _ = get_hand_rank(board_p2.get_row_cards(row))
        if p1_rank < p2_rank: line_score_p1 += 1
        elif p1_rank > p2_rank: line_score_p1 -= 1
    
    if abs(line_score_p1) == 3: line_score_p1 += SCOOP_BONUS if line_score_p1 > 0 else -SCOOP_BONUS

    royalty_p1 = board_p1.get_total_royalty(); royalty_p2 = board_p2.get_total_royalty()
    total_score_p1 = line_score_p1 + (royalty_p1 - royalty_p2)
    return float(total_score_p1), float(-total_score_p1)
