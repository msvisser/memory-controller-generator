from typing import Optional

import numpy as np

from . import GenericCode


class IdentityCode(GenericCode):
    """
    Implementation of the identity code

    This error correction code does not actually do any error detection or correction. Instead, it will simply pass
    the input data to the encoded output. When decoding, there is no check to verify the correctness of the data.
    """

    def __init__(self, data_bits: int) -> None:
        super().__init__(data_bits=data_bits, parity_bits=0)

    def generate_matrices(self, timeout: Optional[float] = None) -> None:
        self.generator_matrix = np.identity(self.data_bits, dtype=np.int)
        self.parity_check_matrix = np.zeros((0, 0), dtype=np.int)
