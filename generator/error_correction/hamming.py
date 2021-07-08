import numpy as np
from . import GenericCode
from .matrix_util import generator_matrix_from_parity_check_matrix


class HammingCode(GenericCode):
    def __init__(self, data_bits):
        # Determine the number of parity bits required for the specified number of data bits
        parity_bits = 0
        i = 1
        data_bits_realized = 0
        while data_bits_realized < data_bits:
            if (i & (i - 1)):
                data_bits_realized += 1
            else:
                parity_bits += 1
            i += 1

        super().__init__(data_bits=data_bits, parity_bits=parity_bits)

    def generate_matrices(self, timeout=None):
        self.parity_check_matrix = np.zeros((self.parity_bits, self.data_bits + self.parity_bits), dtype=np.uint)

        # Set the columns of the parity-check matrix to increasing binary values
        for col_idx, col in enumerate(self.parity_check_matrix.T):
            for bit in range(self.parity_bits):
                col[bit] = 1 if (col_idx + 1) & (1 << bit) else 0

        # Create the generator matrix from the parity-check matrix
        self.generator_matrix = generator_matrix_from_parity_check_matrix(self.parity_check_matrix)

        # Add the list of correctable errors
        for i in range(self.total_bits):
            self.correctable_errors.append((i,))


class ExtendedHammingCode(HammingCode):
    def __init__(self, data_bits):
        # Inherit the number of parity bits from the Hamming code
        super().__init__(data_bits)
        # But increment by one, as we are adding a single over-all parity check
        self.parity_bits += 1

    def generate_matrices(self, timeout=None):
        self.parity_check_matrix = np.zeros((self.parity_bits, self.data_bits + self.parity_bits), dtype=np.uint)

        # Set the columns of the parity-check matrix to increasing binary values
        # For the extended hamming code we ignore the last row and column
        for col_idx, col in enumerate(self.parity_check_matrix.T[:-1]):
            for bit in range(self.parity_bits - 1):
                col[bit] = 1 if (col_idx + 1) & (1 << bit) else 0

        # Fill the bottom row with ones
        self.parity_check_matrix[-1] = np.ones((self.total_bits,))

        # Create the generator matrix from the parity-check matrix
        self.generator_matrix = generator_matrix_from_parity_check_matrix(self.parity_check_matrix)

        # Add the list of correctable errors
        for i in range(self.total_bits):
            self.correctable_errors.append((i,))
