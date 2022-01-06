import itertools
import math
from typing import List

from . import BoolectorCode
from .boolector import BoolectorOptimizationGoal


class SheLiCode(BoolectorCode):
    """
    Implementation of the SEC-DAEC-DAAEC-TAEC code defined by She and Li in [1].

    This code will always correct all 1-bit, 2-bit adjacent, 2-bit almost adjacent and 3-bit adjacent errors. For any
    other type of error no specific behaviour is guaranteed and will likely result in a miscorrection.

    This implementation uses the ``BoolectorCode`` framework to search for a parity-check matrix with the required
    properties. Furthermore, it will try to minimize the maximum number of ones per row, the total number of ones.

    For this code there is no clear analytical lower-bound on the maximum number of ones per row. Therefore,
    the lower-bound used by the optimization goal is most likely much lower than the practical lower-bound. This
    means that Boolector will take much longer to check that there does not exist any possible parity-check matrix
    with a lower maximum number of ones per row. This means that getting a well optimized code can take much longer
    than with the ``DuttaToubaCode``.

    [1] She, X., Li, N. and Waileen Jensen, D. (2012). SEU tolerant memory using error correction code. IEEE
    Transactions on Nuclear Science 59 (1 PART 2), 205–210. https://doi.org/10.1109/TNS.2011.2176513
    """

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
