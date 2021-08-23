import itertools
import logging
import math
from typing import List, Optional

import numpy as np
from nmigen.utils import bits_for
from pyboolector import BoolectorNode

from . import BoolectorCode
from .boolector import BoolectorOptimizationGoal
from ..util.reduce import or_reduce


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

        self.correctable_syndromes: List[BoolectorNode] = []

    def generate_matrices(self, timeout: Optional[float] = None) -> None:
        super().generate_matrices(timeout=timeout)

        # Not all random 2-bit errors are detectable, but some are, so they are calculated here for use in the formal
        # verification.

        # Calculate all correctable syndromes
        correctable_syndromes = []
        for column in self.parity_check_matrix.T:
            correctable_syndromes.append(column)
        for i in range(1, self.total_bits):
            correctable_syndromes.append(self.parity_check_matrix[:, i - 1] ^ self.parity_check_matrix[:, i])

        # Check for overlapping syndromes in all 2-bit random errors
        overlapping_count = 0
        for i in range(self.total_bits):
            for j in range(i + 2, self.total_bits):
                result = self.parity_check_matrix[:, i] ^ self.parity_check_matrix[:, j]

                for column in correctable_syndromes:
                    if np.array_equal(column, result):
                        overlapping_count += 1
                        break
                else:
                    self.detectable_errors.append((i, j))

        # Show information message containing the percentage of miscorrected syndromes
        total = sum(range(1, self.total_bits - 1))
        percentage = 100 * overlapping_count / total
        logging.info(f"Miscorrected syndromes: {overlapping_count}/{total} ({percentage:.2f}%)")

    def conditions(self) -> None:
        # Collect all correctable syndromes
        self.correctable_syndromes = []

        # All single column syndromes should be correctable
        for i in range(self.total_bits):
            self.correctable_syndromes.append(self.all_vars[i])
        # All adjacent column syndromes should be correctable
        for i in range(1, self.total_bits):
            self.correctable_syndromes.append(self.all_vars[i - 1] ^ self.all_vars[i])

        # Assert that all correctable syndromes are unique
        self.assert_all_unique(self.correctable_syndromes)

        # Assert that every column has an odd weight
        b = self.boolector
        for i in range(self.total_bits):
            b.Assert(b.Redxor(self.all_vars[i]) == 1)

    def optimization_goals(self) -> List[BoolectorOptimizationGoal]:
        # Calculate the minimum total bitcount
        total_ones_lowerbound = 0
        columns_needed = self.total_bits
        for i in itertools.count(start=1, step=2):
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

        # Calculate the total number of possible overlapping syndromes
        total_possible_overlapping_syndromes = sum(range(1, self.total_bits - 1))
        bits_requried = bits_for(total_possible_overlapping_syndromes)

        b = self.boolector
        const_zero = b.Const(0, bits_requried)
        const_one = b.Const(1, bits_requried)

        # Count the number of overlapping syndromes
        overlapping_syndromes = b.Const(0, bits_requried)
        for i in range(self.total_bits):
            for j in range(i + 2, self.total_bits):
                syndrome = self.all_vars[i] ^ self.all_vars[j]
                match = or_reduce(syndrome == corr_syn for corr_syn in self.correctable_syndromes)
                overlapping_syndromes += b.Cond(match, const_one, const_zero)

        # Minimize the number of overlapping syndromes
        overlapping_syndromes_goal = BoolectorOptimizationGoal(
            expression=overlapping_syndromes,
            upper_bound=total_possible_overlapping_syndromes,
            description="overlapping syndromes"
        )

        return [
            maximum_ones_per_row_goal,
            total_ones_goal,
            overlapping_syndromes_goal,
        ]
