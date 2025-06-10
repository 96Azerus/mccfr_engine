# mccfr_engine/evaluator.pxd
# Этот файл описывает evaluator.py для Cython
# Мы объявляем только те функции, которые будем вызывать из Cython-кода
cpdef tuple get_hand_rank(list cards)
cpdef tuple calculate_payoffs(object board_p1, object board_p2)
cpdef int get_row_royalty(list cards, str row_name)
