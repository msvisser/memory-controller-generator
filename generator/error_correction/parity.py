from typing import Optional

import numpy as np

from . import GenericCode
from .matrix_util import generator_matrix_from_parity_check_matrix


class ParityCode(GenericCode):
    """
    Implementation of a parity-check code (SED).

    This class implements a parity-check code, which can detect a single error using a single parity bit over all
    data bits.
    """

    def __init__(self, data_bits: int) -> None:
        super().__init__(data_bits=data_bits, parity_bits=1)

    def generate_matrices(self, timeout: Optional[float] = None) -> None:
        self.parity_check_matrix = np.ones((1, self.total_bits), dtype=np.int)
        self.generator_matrix = generator_matrix_from_parity_check_matrix(self.parity_check_matrix)
