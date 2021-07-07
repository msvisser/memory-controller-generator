import abc
from functools import reduce
from typing import Optional, List

import numpy as np
from nmigen import *

from .matrix_util import np_array_to_value


class GenericCode(abc.ABC):
    """
    Generic implementation of an error correction code.

    This implementation does not actually provide an error correction code, but instead is a framework to build error
    correction codes on. Basic implementations of an error correction only have to implement the ``generate_matrices``
    method, which determines the parity-check and generator matrix for the code. More complex codes can override the
    ``encoder`` and ``decoder`` methods to return specialised encoder and decoder modules instead of using the
    ``GenericEncoder`` and ``GenericDecoder``.
    """

    def __init__(self, data_bits: int, parity_bits: int):
        self.data_bits = data_bits
        self.parity_bits = parity_bits

        self.generator_matrix = None
        self.parity_check_matrix = None
        self.correctable_errors = []

    @property
    def total_bits(self) -> int:
        """
        The total number of bits used by this code. That is the number of data bits plus the number of parity bits.
        """
        return self.data_bits + self.parity_bits

    @abc.abstractmethod
    def generate_matrices(self, timeout: Optional[float] = None) -> None:
        """
        Generate the parity-check and generator matrices for this error correction code.

        Since the operation of generating matrices can be quite expensive depending on the specific code,
        calling this function is required. This also allows the caller to set a predetermined time-limit on the
        duration of this operation.

        :param timeout: Optional timeout in seconds
        :return: None
        """
        return

    def encoder(self) -> "GenericEncoder":
        """
        Construct an encoder module for this code.

        :return: GenericEncoder for this code
        :raises ValueError: if the generator matrix is None
        """
        if self.generator_matrix is None:
            raise ValueError("Generator matrix is None")

        return GenericEncoder(self)

    def decoder(self) -> "GenericDecoder":
        """
        Construct a decoder module for this code.

        :return: GenericDecoder for this code
        :raises ValueError: if the generator or parity-check matrix is None
        """
        if self.generator_matrix is None:
            raise ValueError("Generator matrix is None")
        if self.parity_check_matrix is None:
            raise ValueError("Parity-check matrix is None")

        return GenericDecoder(self)


class GenericEncoder(Elaboratable):
    """
    Generic implementation of an encoder module for error correction codes.

    This class provides a simple, but functional, implementation of an encoder module. This encoder will work for any
    error correction code with a valid generator matrix. However, the resulting module might not be optimal for some
    error correction codes.

    This implementation will use each column of the generator matrix to determine a bit of the encoded data. This is
    done by calculating the exclusive-or result of all data bits for which there is a one in the column.
    """

    def __init__(self, code: GenericCode):
        self.code = code

        self.data_in = Signal(unsigned(code.data_bits))
        """Input of the data to be encoded"""
        self.enc_out = Signal(unsigned(code.total_bits))
        """Output of the encoded data"""

    def elaborate(self, platform) -> Module:
        """Elaborate the module implementation"""
        m = Module()

        # Calculate each encoded bit from the specified column of the generator matrix
        for col_idx, col in enumerate(self.code.generator_matrix.T):
            input_parts = []
            for i, select in enumerate(col):
                if select:
                    input_parts.append(self.data_in[i])

            m.d.comb += self.enc_out[col_idx].eq(reduce(lambda a, b: a ^ b, input_parts))

        return m

    def ports(self) -> List[Signal]:
        """List of module signals externally available"""
        return [self.data_in, self.enc_out]


class GenericDecoder(Elaboratable):
    """
    Generic implementation of a decoder module for error correction codes.

    This class provides a simple, but functional, implementation of a decoder module. This decoder will work for any
    error correction code with a valid generator and parity-check matrix pair. However, the resulting module might
    not be optimal for some error correction codes.

    The implementation of this decoder first calculate the syndrome for the encoded input data. This is done using
    the rows of the parity-check matrix. After this, the bits that require flipping can be calculated using the list
    of correctable errors. Finally, the encoded input is flipped where required and return as corrected encoded
    output. Using the corrected encoded output, the data output can be calculated.
    """

    def __init__(self, code: GenericCode):
        self.code = code

        self.enc_in = Signal(unsigned(code.total_bits))
        """Input of the uncorrected encoded data"""
        self.enc_out = Signal(unsigned(code.total_bits))
        """Output of the corrected encoded data"""
        self.data_out = Signal(unsigned(code.data_bits))
        """Output of the corrected data"""
        self.error = Signal()
        """Output signalling the occurrence of an error"""
        self.uncorrectable_error = Signal()
        """Output signalling the occurrence of an uncorrectable error"""

    def elaborate(self, platform) -> Module:
        """Elaborate the module implementation"""
        m = Module()

        if self.code.parity_bits > 0:
            # Calculate the syndrome for this parity-check matrix
            syndrome_signal = Signal(unsigned(self.code.parity_bits))
            for row_idx, row in enumerate(self.code.parity_check_matrix):
                input_parts = []
                for i, select in enumerate(row):
                    if select:
                        input_parts.append(self.enc_in[i])

                m.d.comb += syndrome_signal[row_idx].eq(reduce(lambda a, b: a ^ b, input_parts, 0))

            # Calculate which syndromes cause a bit to flip
            flip_bit_syndromes = [[] for _ in range(self.code.total_bits)]
            for error in self.code.correctable_errors:
                # Calculate the linear combination of the error bit columns in the parity-check matrix. The modulo
                # two operation is required to make sure the result is a binary vector.
                error_syn = (sum(self.code.parity_check_matrix.T[i] for i in error) % 2)

                for i in error:
                    flip_bit_syndromes[i].append(np_array_to_value(error_syn))

            # Calculate which bits to flip to correct the error(s)
            flips = Signal(unsigned(self.code.total_bits))
            for bit, syndromes in enumerate(flip_bit_syndromes):
                flip = reduce(
                    lambda a, b: a | b,
                    (syndrome_signal == syndrome for syndrome in syndromes),
                    C(False)
                )
                m.d.comb += flips[bit].eq(flip)

            # Flip the input bits to correct any errors
            m.d.comb += self.enc_out.eq(self.enc_in ^ flips)

            # Determine if an error or uncorrectable error happened
            m.d.comb += [
                self.error.eq(syndrome_signal.any()),
                self.uncorrectable_error.eq(self.error & (flips == 0)),
            ]
        else:
            # If there are no parity bits, no error can be detected, and the corrected encoded data will be identical
            # to the encoded input.
            m.d.comb += [
                self.error.eq(0),
                self.uncorrectable_error.eq(0),
                self.enc_out.eq(self.enc_in),
            ]

        # Connect the correct input bits to the output
        for bit in range(self.code.data_bits):
            for col_idx, col in enumerate(self.code.generator_matrix.T):
                match_vec = np.zeros((self.code.data_bits,))
                match_vec[bit] = 1

                if (col == match_vec).all():
                    m.d.comb += self.data_out[bit].eq(self.enc_out[col_idx])
                    break
            else:
                raise ValueError(f"Generator matrix does not directly map data bit {bit} to an encoded bit")

        return m

    def ports(self) -> List[Signal]:
        """List of module signals externally available"""
        return [self.enc_in, self.enc_out, self.data_out, self.error, self.uncorrectable_error]
