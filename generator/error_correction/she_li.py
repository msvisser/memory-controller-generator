import itertools
import math
from typing import List

from . import BoolectorCode
from .boolector import BoolectorOptimizationGoal


class SheLiCode(BoolectorCode):
    def __init__(self, data_bits):
        # Calculate the number of parity bits using the equation from the paper: k + c - 1 <= 2**(c - 2)
        parity_bits = 0
        for m in itertools.count():
            if data_bits + m - 1 <= 2 ** (m - 2):
                parity_bits = m
                break

        super().__init__(data_bits=data_bits, parity_bits=parity_bits)

        # Mark single bit errors as correctable
        for i in range(self.total_bits):
            self.correctable_errors.append((i,))
        # Mark 2-bit adjacent errors as correctable
        for i in range(1, self.total_bits):
            self.correctable_errors.append((i - 1, i))
        # Mark 2-bit almost adjacent and 3-bit adjacent errors as correctable
        for i in range(2, self.total_bits):
            self.correctable_errors.append((i - 2, i))
            self.correctable_errors.append((i - 2, i - 1, i))

    def conditions(self) -> None:
        # Collect all correctable syndromes
        correctable_syndromes = []

        # All single bit error syndromes should be correctable
        for i in range(self.total_bits):
            correctable_syndromes.append(self.all_vars[i])
        # All adjacent 2-bit error syndromes should be correctable
        for i in range(1, self.total_bits):
            correctable_syndromes.append(self.all_vars[i - 1] ^ self.all_vars[i])
        # All almost adjacent 2-bit error syndromes should be correctable
        for i in range(2, self.total_bits):
            correctable_syndromes.append(self.all_vars[i - 2] ^ self.all_vars[i])
        # All adjacent 3-bit error syndromes should be correctable
        for i in range(2, self.total_bits):
            correctable_syndromes.append(self.all_vars[i - 2] ^ self.all_vars[i - 1] ^ self.all_vars[i])

        # Assert that all correctable syndromes are unique
        self.assert_all_unique(correctable_syndromes)

    def optimization_goals(self) -> List[BoolectorOptimizationGoal]:
        # Calculate the minimum total bitcount
        total_ones_lowerbound = 0
        columns_needed = self.total_bits
        for i in itertools.count(start=1):
            possible_columns = math.comb(self.parity_bits, i)
            if possible_columns < columns_needed:
                columns_needed -= possible_columns
                total_ones_lowerbound += i * possible_columns
            else:
                total_ones_lowerbound += i * columns_needed
                break

        maximum_ones_per_row_lowerbound = (total_ones_lowerbound + self.parity_bits - 1) // self.parity_bits

        # Generate the common goals
        maximum_ones_per_row_goal = self.maximum_ones_per_row_optimization_goal()
        total_ones_goal = self.total_ones_optimization_goal()

        # Assign the lower bounds
        maximum_ones_per_row_goal.lower_bound = maximum_ones_per_row_lowerbound
        total_ones_goal.lower_bound = total_ones_lowerbound

        return [
            maximum_ones_per_row_goal,
            total_ones_goal
        ]
