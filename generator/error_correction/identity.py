import numpy as np
from . import GenericCode


class IdentityCode(GenericCode):
    def __init__(self, data_bits):
        super().__init__(data_bits=data_bits, parity_bits=0)

    def generate_matrices(self, timeout=None):
        self.generator_matrix = np.identity(self.data_bits, dtype=np.uint)
        self.parity_check_matrix = np.zeros((0, 0), dtype=np.uint)
