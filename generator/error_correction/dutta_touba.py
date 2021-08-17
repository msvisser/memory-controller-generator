import itertools
import math
from typing import List

from . import BoolectorCode
from .boolector import BoolectorOptimizationGoal


class DuttaToubaCode(BoolectorCode):
    def __init__(self, data_bits):
        # Determine the number of parity bits required for the specified number of data bits
        parity_bits = 0
        for m in itertools.count():
            if 2 ** m - m - 1 >= data_bits:
                parity_bits = m + 1
                break

        super().__init__(data_bits=data_bits, parity_bits=parity_bits)

        # Mark all single bit errors as correctable
        for i in range(self.total_bits):
            self.correctable_errors.append((i,))
        # Mark all adjacent 2-bit errors as correctable
        for i in range(1, self.total_bits):
            self.correctable_errors.append((i - 1, i))

        # TODO: Not all random 2-bit errors are detectable, but some are, so they should probably be marked.

    def conditions(self) -> None:
        # Collect all correctable syndromes
        correctable_syndromes = []

        # All single column syndromes should be correctable
        for i in range(self.total_bits):
            correctable_syndromes.append(self.all_vars[i])
        # All adjacent column syndromes should be correctable
        for i in range(1, self.total_bits):
            correctable_syndromes.append(self.all_vars[i - 1] ^ self.all_vars[i])

        # Assert that all correctable syndromes are unique
        self.assert_all_unique(correctable_syndromes)

        # Assert that every column has an odd weight
        b = self.boolector
        for i in range(self.total_bits):
            b.Assert(b.Redxor(self.all_vars[i]) == 1)

    def optimization_goals(self) -> List[BoolectorOptimizationGoal]:
        goals = self.common_optimization_goals()

        # Calculate the minimum total bitcount
        total_bits_lowerbound = 0
        columns_needed = self.total_bits
        for i in itertools.count(start=1, step=2):
            possible_columns = math.comb(self.parity_bits, i)
            if possible_columns < columns_needed:
                columns_needed -= possible_columns
                total_bits_lowerbound += i * possible_columns
            else:
                total_bits_lowerbound += i * columns_needed
                break

        per_row_lowerbound = (total_bits_lowerbound + self.parity_bits - 1) // self.parity_bits

        # FIXME: This is a gigantic hack
        goals[0].lower_bound = per_row_lowerbound
        goals[1].lower_bound = total_bits_lowerbound

        return goals
