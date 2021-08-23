import abc
import logging
from typing import Optional, List, Tuple

import numpy as np
from nmigen import *
from numpy.typing import NDArray

from .matrix_util import np_array_to_value
from ..util import or_reduce, xor_reduce


class GenericCode(abc.ABC):
    """
    Generic implementation of an error correction code.

    This implementation does not actually provide an error correction code, but instead is a framework to build error
    correction codes on. Basic implementations of an error correction only have to implement the ``generate_matrices``
    method, which determines the parity-check and generator matrix for the code. More complex codes can override the
    ``encoder`` and ``decoder`` methods to return specialised encoder and decoder modules instead of using the
    ``GenericEncoder`` and ``GenericDecoder``.
    """

    def __init__(self, data_bits: int, parity_bits: int) -> None:
        self.data_bits = data_bits
        self.parity_bits = parity_bits

        self.generator_matrix: Optional[NDArray] = None
        self.parity_check_matrix: Optional[NDArray] = None
        self.correctable_errors: List[Tuple] = []
        self.detectable_errors: List[Tuple] = []

        logging.info(f"Selected {self.__class__.__name__}({data_bits},{parity_bits},{self.total_bits})")

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

    def flip_calculator(self) -> "GenericFlipCalculator":
        """
        Construct a flip calculator module for this code.

        :return: GenericFlipCalculator for this code
        :raises ValueError: if the parity-check matrix is None
        """
        if self.parity_check_matrix is None:
            raise ValueError("Parity-check matrix is None")

        return GenericFlipCalculator(self)

    def error_calculator(self) -> "GenericErrorCalculator":
        """
        Construct an error calculator module for this code.

        :return: GenericErrorCalculator for this code
        """
        return GenericErrorCalculator(self)


class GenericEncoder(Elaboratable):
    """
    Generic implementation of an encoder module for error correction codes.

    This class provides a simple, but functional, implementation of an encoder module. This encoder will work for any
    error correction code with a valid generator matrix. However, the resulting module might not be optimal for some
    error correction codes.

    This implementation will use each column of the generator matrix to determine a bit of the encoded data. This is
    done by calculating the exclusive-or result of all data bits for which there is a one in the column.
    """

    def __init__(self, code: GenericCode) -> None:
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

            m.d.comb += self.enc_out[col_idx].eq(xor_reduce(input_parts))

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

    def __init__(self, code: GenericCode) -> None:
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

        m.submodules.error_calculator = error_calculator = self.code.error_calculator()
        m.submodules.flip_calculator = flip_calculator = self.code.flip_calculator()

        if self.code.parity_bits > 0:
            # Calculate the syndrome for this parity-check matrix
            syndrome_signal = Signal(unsigned(self.code.parity_bits))
            for row_idx, row in enumerate(self.code.parity_check_matrix):
                input_parts = []
                for i, select in enumerate(row):
                    if select:
                        input_parts.append(self.enc_in[i])

                m.d.comb += syndrome_signal[row_idx].eq(xor_reduce(input_parts))

            # Send the calculated syndrome to the flips calculator
            m.d.comb += flip_calculator.syndrome.eq(syndrome_signal)

            # Flip the input bits to correct any errors
            m.d.comb += self.enc_out.eq(self.enc_in ^ flip_calculator.flips)

            # Determine if an error or uncorrectable error happened
            m.d.comb += [
                error_calculator.syndrome.eq(syndrome_signal),
                error_calculator.flips.eq(flip_calculator.flips),
                self.error.eq(error_calculator.error),
                self.uncorrectable_error.eq(error_calculator.uncorrectable_error),
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

                if np.array_equal(col, match_vec):
                    m.d.comb += self.data_out[bit].eq(self.enc_out[col_idx])
                    break
            else:
                raise ValueError(f"Generator matrix does not directly map data bit {bit} to an encoded bit")

        return m

    def ports(self) -> List[Signal]:
        """List of module signals externally available"""
        return [self.enc_in, self.enc_out, self.data_out, self.error, self.uncorrectable_error]


class GenericFlipCalculator(Elaboratable):
    """
    Generic implementation of a flip calculator for a decoder module.

    This class provides the calculation of which bits to flip based on the supplied syndrome signal. Calculating when
    to flip a bit can be done using the parity-check matrix and a list of correctable errors. First, the syndrome
    value for each correctable error is calculated. Second, for each bit we match all syndromes that require the bit
    to flip.

    This implementation take the naive approach of completely matching the syndrome for each error. While this
    approach will always work for codes with a valid parity-check matrix and respective correctable error list,
    it might not be the most optimal solution. Error correction codes that require a different implementation can
    override the ``flip_calculator`` method of ``GenericCode`` to return their own implementation.
    """

    def __init__(self, code: GenericCode) -> None:
        self.code = code

        self.syndrome = Signal(unsigned(code.parity_bits))
        """Input of the error correction syndrome"""
        self.flips = Signal(unsigned(code.total_bits))
        """Output of the bits to flip"""

    def elaborate(self, platform) -> Module:
        """Elaborate the module implementation"""
        m = Module()

        # Calculate which syndromes cause a bit to flip
        flip_bit_syndromes: List[List[int]] = [[] for _ in range(self.code.total_bits)]
        for error in self.code.correctable_errors:
            # Calculate the linear combination of the error bit columns in the parity-check matrix.
            error_syn = np.zeros((self.code.parity_bits,), dtype=np.int)
            for i in error:
                error_syn ^= self.code.parity_check_matrix.T[i]

            for i in error:
                flip_bit_syndromes[i].append(np_array_to_value(error_syn))

        # Calculate which bits to flip to correct the error(s)
        for bit, syndromes in enumerate(flip_bit_syndromes):
            flip = or_reduce(self.syndrome == syndrome for syndrome in syndromes)
            m.d.comb += self.flips[bit].eq(flip)

        return m

    def ports(self) -> List[Signal]:
        """List of module signals externally available"""
        return [self.syndrome, self.flips]


class GenericErrorCalculator(Elaboratable):
    """
    Generic implementation of an error calculator for a decoder module.

    This class provides the calculations required to determine if an error, or an uncorrectable error occurred. The
    ``error`` signal will indicate that an error has occurred by checking if the syndrome is non-zero. The
    ``uncorrectable_error`` signal will indicate if the detected error is uncorrectable by checking if no flips were
    applied.

    This implementation is rather naive, as it has to check that all flips are zero. For many error correction codes
    there might be a simpler way to detect whether an uncorrectable error has occurred. In that case the error
    correction code can override the ``error_calculator`` method on ``GenericCode`` and return a custom
    implementation for the error calculator.
    """

    def __init__(self, code: GenericCode) -> None:
        self.code = code

        self.syndrome = Signal(unsigned(code.parity_bits))
        """Input of the error correction syndrome"""
        self.flips = Signal(unsigned(code.total_bits))
        """Input of the bits to flip"""

        self.error = Signal()
        """Output signalling the occurrence of an error"""
        self.uncorrectable_error = Signal()
        """Output signalling the occurrence of an uncorrectable error"""

    def elaborate(self, platform) -> Module:
        """Elaborate the module implementation"""
        m = Module()
        m.d.comb += [
            self.error.eq(self.syndrome != 0),
            self.uncorrectable_error.eq(self.error & (self.flips == 0)),
        ]
        return m

    def ports(self) -> List[Signal]:
        """List of module signals externally available"""
        return [self.syndrome, self.flips, self.error, self.uncorrectable_error]
