import itertools
import logging
import math
import time
from collections import Counter
from typing import Optional

import numpy as np
from nmigen import *
from numpy.typing import NDArray

from . import GenericCode, GenericErrorCalculator
from ..util.matrix import generator_matrix_from_systematic


class HsiaoCode(GenericCode):
    """
    Implementation of a Hsiao code (SEC-DED).

    This class implements a Hsiao code using an exhaustive search method. This will search all possible parity-check
    matrices which conform to the Hsiao code specification. That is, all columns will be unique and of odd weight.
    All possible matrices will be searched, and the matrix with the most balanced rows will be chosen.

    The definition of this code can be found in: M.Y. Hsiao, "A Class of Optimal Minimum Odd-weight-column SEC-DED
    Codes", IBM Journal of Research & Development, 1970.
    """

    def __init__(self, data_bits: int) -> None:
        # Determine the number of parity bits required for the specified number of data bits
        parity_bits = 0
        for m in itertools.count():
            if 2 ** m - m - 1 >= data_bits:
                parity_bits = m + 1
                break

        super().__init__(data_bits=data_bits, parity_bits=parity_bits)

        # All single bit errors are correctable
        for i in range(self.total_bits):
            self.correctable_errors.append((i,))

        # All two bit errors are detectable
        for i in range(self.total_bits):
            for j in range(i + 1, self.total_bits):
                self.detectable_errors.append((i, j))

    def generate_matrices(self, timeout: Optional[float] = None) -> None:
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

        # If no timeout is set, assume a timeout of 24 hours
        if timeout is None:
            timeout = 3600 * 24
        timeout_time = time.time() + timeout

        # Initialise the lowest maximum row weight as the number of bits, as this is the maximum weight of a row
        lowest_max_row_weight = self.total_bits
        lowest_candidate = None

        # Search for the candidate with the lowest difference in row weight
        for candidate_columns in flexible_column_combinations:
            # Build the complete column list
            candidate = fixed_columns + list(candidate_columns)
            # Count the number of ones in each row
            c = Counter(itertools.chain(*candidate))

            # Calculate the minimum and maximum weight of the rows
            max_row_weight = max(c.values())
            min_row_weight = min(c.values())

            # If this candidate has the lowest maximum row weight, store it
            if max_row_weight < lowest_max_row_weight:
                lowest_max_row_weight = max_row_weight
                lowest_candidate = candidate

                # If the difference between the lowest weight and highest weight rows is one or zero, the rows of the
                # matrix are completely balanced
                if max_row_weight - min_row_weight <= 1:
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

    def error_calculator(self) -> "HsiaoErrorCalculator":
        return HsiaoErrorCalculator(self)


class HsiaoErrorCalculator(GenericErrorCalculator):
    """
    Implementation of the error calculation for Hsiao codes.

    This implementation still calculates the occurrence of an error by check for a non-zero syndrome. However,
    uncorrectable errors can be detected by simply checking if there was an error, and checking that the syndrome is
    of even weight.
    """

    def elaborate(self, platform) -> Module:
        """Elaborate the module implementation"""
        m = Module()
        m.d.comb += [
            self.error.eq(self.syndrome != 0),
            self.uncorrectable_error.eq(self.error & (self.syndrome.xor() == 0)),
        ]
        return m


class HsiaoConstructedCode(HsiaoCode):
    """
    Implementation of the Hsiao code (SEC-DED) using a construction algorithm.

    This implementation of the Hsiao code uses a construction based algorithm to build the balanced parity-check
    matrix without doing any searching. Instead, the matrix is constructed using the recursive ``delta`` function,
    whose documentation contains more information about the algorithm.

    The definition of this algorithm can be found in: L. Chen, "Hsiao-Code Check Matrices and Recursively Balanced
    Matrices", 2013, https://arxiv.org/pdf/0803.1217.pdf.
    """

    def generate_matrices(self, timeout: Optional[float] = None) -> None:
        # Calculate the weight of the highest weight columns
        max_weight = 1
        prev_total = 0
        total = math.comb(self.parity_bits, max_weight)
        while self.total_bits > total:
            max_weight += 2
            prev_total = total
            total += math.comb(self.parity_bits, max_weight)

        # Calculate the number of max weight columns
        max_weight_columns = self.total_bits - prev_total

        # Determine the parts that make up the parity-check matrix
        parts = []
        # First build all sub-matrices where all columns are present
        for weight in range(3, max_weight, 2):
            parts.append(self.delta(self.parity_bits, weight, math.comb(self.parity_bits, weight)))
        # Then append the smaller final sub-matrix
        parts.append(self.delta(self.parity_bits, max_weight, max_weight_columns))
        # Finally, append the identity matrix at the end
        parts.append(np.identity(self.parity_bits, dtype=np.int))

        # Build the parity-check matrix by stacking the parts
        self.parity_check_matrix = np.hstack(parts)

        # Calculate the generator matrix from the parity-check matrix
        self.generator_matrix = generator_matrix_from_systematic(self.parity_check_matrix)

    @staticmethod
    def delta(rows: int, weight: int, columns: int) -> NDArray:
        """
        Compute the delta sub-matrix.

        This method follows the recursive procedure outlined in the paper, with the optimisation discussed in section
        4. There are a number of ending states, which are defined in section 3, which result in a direct output of a
        matrix. If the parameters specified do not result in an ending state, the algorithm will build the required
        matrix using two recursive calls with smaller parameters.

        :param rows: Rows in the resulting matrix
        :param weight: Weight of each column in the matrix
        :param columns: Number of columns in the matrix
        :return: Delta matrix with the specified parameters
        """
        if columns == 0:
            # No columns, so return a zero column matrix
            logging.debug(f"m==0 >> R: {rows}, w: {weight}")
            return np.zeros((rows, 0), dtype=np.int)
        elif weight == 0:
            # Single column with zero weight
            logging.debug(f"J==0 >> R: {rows}, m: {columns}")
            assert columns == 1
            return np.zeros((rows, 1), dtype=np.int)
        elif weight == rows:
            # Single column with maximum weight
            logging.debug(f"J==R >> R: {rows}, m: {columns}")
            assert columns == 1
            return np.ones((rows, 1), dtype=np.int)
        elif columns == 1:
            # Single column of specified weight, fill the first n rows with 1, where n = weight
            logging.debug(f"m==1 >> R: {rows}, J: {weight}")
            mat = np.zeros((rows, 1), dtype=np.int)
            mat[0:weight] = 1
            return mat
        elif weight == 1:
            # Weight is 1, so identity matrix padded with zero rows
            logging.debug(f"J==1 >> R: {rows}, m: {columns}")
            assert rows >= columns
            ident = np.identity(columns, dtype=np.int)
            zeros = np.zeros((rows - columns, columns), dtype=np.int)
            return np.vstack((ident, zeros))
        elif weight == rows - 1:
            # Weight is rows - 1, so all ones with identity subtracted from the bottom rows
            logging.debug(f"J==R-1 >> R: {rows}, m: {columns}")
            assert rows >= columns
            ones = np.ones((rows - columns, columns), dtype=np.int)
            ident = 1 - np.identity(columns, dtype=np.int)
            return np.vstack((ones, ident))
        else:
            # General case that requires splitting
            logging.debug(f"general case >> R: {rows}, J: {weight}, m: {columns}")
            assert 2 <= weight <= rows - 2
            assert 2 <= columns <= math.comb(rows, weight)

            # Recursively calculate sub-parts of the matrix
            m1 = math.ceil((columns * weight) / rows)
            logging.debug(f"R: {rows}, J:{weight}, m: {columns}, m1: {m1}, m2: {columns - m1}")
            delta1 = HsiaoConstructedCode.delta(rows - 1, weight - 1, m1)
            delta2 = HsiaoConstructedCode.delta(rows - 1, weight, columns - m1)

            # Calculate the shifting of rows required in delta2
            r1 = ((weight - 1) * m1) % (rows - 1)
            r2 = (weight * (columns - m1)) % (rows - 1)

            if r1 + r2 > (rows - 1):
                # Shift the first r2-rp rows to the bottom
                rp = r1 + r2 - (rows - 1)
                order = list(range(r2 - rp, rows - 1)) + list(range(r2 - rp))
            else:
                # Shift the first r2 rows to r1+1
                move_rows = list(range(r2))
                order = list(range(r2, rows - 1))
                order[r1 + 1:r1 + 1] = move_rows

            # Reorder delta2 to get delta2 prime
            delta2_prime = delta2[order]

            # Create the top row of the resulting matrix
            ones = np.ones((1, m1), dtype=np.int)
            zeros = np.zeros((1, columns - m1), dtype=np.int)
            top = np.hstack((ones, zeros))

            # Create the bottom sub-matrix of the resulting matrix
            bot = np.hstack((delta1, delta2_prime))
            result = np.vstack((top, bot))

            return result
