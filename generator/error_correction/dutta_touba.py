import itertools
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
        return self.common_optimization_goals()
