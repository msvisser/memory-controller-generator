import operator
from functools import reduce
from typing import TypeVar, Iterable
T = TypeVar('T')


def or_reduce(elements: Iterable[T]) -> T:
    """Reduce a sequence using the or operator"""
    return reduce(operator.or_, elements, 0)


def xor_reduce(elements: Iterable[T]) -> T:
    """Reduce a sequence using the xor operator"""
    return reduce(operator.xor, elements, 0)
