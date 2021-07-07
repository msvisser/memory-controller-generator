from nmigen import *
import numpy as np
from functools import reduce

from .matrix_util import np_array_to_value


class GenericCode():
    def __init__(self, data_bits, parity_bits):
        self.data_bits = data_bits
        self.parity_bits = parity_bits

        self.generator_matrix = None
        self.parity_check_matrix = None
        self.correctable_errors = []

    @property
    def total_bits(self):
        return self.data_bits + self.parity_bits

    def generate_matrices(self, timeout=None):
        raise NotImplementedError()

    def encoder(self) -> "GenericEncoder":
        if self.generator_matrix is None:
            raise ValueError("Generator matrix has not been created")

        return GenericEncoder(self)

    def decoder(self) -> "GenericDecoder":
        if self.parity_check_matrix is None:
            raise ValueError("Parity-check matrix has not been created")

        return GenericDecoder(self)


class GenericEncoder(Elaboratable):
    def __init__(self, code: GenericCode):
        self.code = code
        print(self.code.generator_matrix)
        self.data_in = Signal(unsigned(code.data_bits))
        self.enc_out = Signal(unsigned(code.total_bits))

    def elaborate(self, platform):
        m = Module()

        # Calculate each encoded bit from the specified column of the generator matrix
        for col_idx, col in enumerate(self.code.generator_matrix.T):
            input_parts = []
            for i, select in enumerate(col):
                if select:
                    input_parts.append(self.data_in[i])

            m.d.comb += self.enc_out[col_idx].eq(reduce(lambda a, b: a ^ b, input_parts))

        return m

    def ports(self):
        return [self.data_in, self.enc_out]


class GenericDecoder(Elaboratable):
    def __init__(self, code: GenericCode):
        self.code = code
        print(self.code.parity_check_matrix)
        print(self.code.generator_matrix)

        self.enc_in = Signal(unsigned(code.total_bits))
        self.enc_out = Signal(unsigned(code.total_bits))
        self.data_out = Signal(unsigned(code.data_bits))
        self.error = Signal()
        self.uncorrectable_error = Signal()

    def elaborate(self, platform):
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

            # Determine if an error happened
            m.d.comb += self.error.eq(syndrome_signal.any())

            # Calculate which syndromes cause a bit to flip
            flip_bit_syndromes = [[] for _ in range(self.code.total_bits)]
            for error in self.code.correctable_errors:
                error_syn = sum(self.code.parity_check_matrix.T[i] for i in error)

                for i in error:
                    flip_bit_syndromes[i].append(np_array_to_value(error_syn))
            print(flip_bit_syndromes)

            # Flip the input bits if correction is required
            flips = Signal(unsigned(self.code.total_bits))
            for bit, syndromes in enumerate(flip_bit_syndromes):
                flip = reduce(
                    lambda a, b: a | b,
                    (syndrome_signal == syndrome for syndrome in syndromes),
                    C(False)
                )
                m.d.comb += flips[bit].eq(flip)

            m.d.comb += self.enc_out.eq(self.enc_in ^ flips)

            # Determine if an uncorrectable error happened
            m.d.comb += self.uncorrectable_error.eq(self.error & (flips == 0))
        else:
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

        return m

    def ports(self):
        return [self.enc_in, self.enc_out, self.data_out, self.error, self.uncorrectable_error]
