import itertools
import math
from collections import Counter
import time
from typing import Optional

import numpy as np

from . import GenericCode
from .matrix_util import generator_matrix_from_systematic


class HsiaoCode(GenericCode):
    def __init__(self, data_bits: int):
        parity_bits = 0
        for m in itertools.count():
            if 2 ** m - m - 1 >= data_bits:
                parity_bits = m + 1
                break

        super().__init__(data_bits=data_bits, parity_bits=parity_bits)

    def generate_matrices(self, timeout: Optional[float] = None):
        # Find all columns which are always used
        columns_needed = self.data_bits
        fixed_columns = []
        num_ones = 3
        while columns_needed > 0:
            # Calculate the number of columns possible with this number of ones
            available_at_num_ones = math.comb(self.parity_bits, num_ones)
            if columns_needed >= available_at_num_ones:
                # If all columns are required, add them to the fixed columns list
                columns_needed -= available_at_num_ones
                combinations = itertools.combinations(range(self.parity_bits), num_ones)
                fixed_columns.extend(combinations)
            else:
                # Otherwise, these columns will end up as flexible
                break
            num_ones += 2

        # Create a list of possible additional columns
        flexible_columns = itertools.combinations(range(self.parity_bits), num_ones)
        # Create an iterator over all possible options
        flexible_column_combinations = itertools.combinations(flexible_columns, columns_needed)
        print(math.comb(math.comb(self.parity_bits, num_ones), columns_needed))

        lowest_diff = None
        lowest_candidate = None
        timeout_time = time.time() + timeout
        # Search for the candidate with the lowest difference in row weight
        for candidate_columns in flexible_column_combinations:
            # Build the complete column list
            total = fixed_columns + list(candidate_columns)
            # Count the number of ones in each row
            c = Counter(itertools.chain(*total))

            # Calculate the average number of ones in each row
            average = sum(c.values()) / self.parity_bits
            # Determine the absolute difference of each row from the average
            difference = sum(abs(average - value) for value in c.values())

            # If this candidate is the best so far, store it
            if lowest_diff is None or difference < lowest_diff:
                lowest_diff = difference
                lowest_candidate = total
                if difference == 0:
                    # If the current difference is zero, the rows are completely balanced, so this is a perfect solution
                    break

            if time.time() > timeout_time:
                break

        # Extend the candidate with the identity columns
        lowest_candidate.extend(itertools.combinations(range(self.parity_bits), 1))
        # Build the parity-check matrix from the column definitions
        self.parity_check_matrix = np.zeros((self.parity_bits, self.total_bits), dtype=np.int)
        for col, set_rows in enumerate(lowest_candidate):
            for row in set_rows:
                self.parity_check_matrix[row, col] = 1

        # Create the generator matrix from the parity-check matrix, in this case the parity-check matrix is already
        # in systematic form, so no extra work is required
        self.generator_matrix = generator_matrix_from_systematic(self.parity_check_matrix)

        # Append all single bit errors to the correctable list
        for i in range(self.total_bits):
            self.correctable_errors.append((i,))
