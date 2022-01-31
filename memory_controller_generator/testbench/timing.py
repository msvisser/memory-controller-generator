import logging
import time

import numpy as np

from memory_controller_generator.error_correction import IdentityCode, ParityCode, HammingCode, ExtendedHammingCode, \
    HsiaoCode, HsiaoConstructedCode, DuttaToubaCode, SheLiCode

if __name__ == "__main__":
    np.set_printoptions(linewidth=200)

    output_file = open("timing.txt", "w")

    log_format = "%(levelname)8s: %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format)

    codes = [IdentityCode, ParityCode, HammingCode, ExtendedHammingCode, HsiaoCode, HsiaoConstructedCode,
             DuttaToubaCode, SheLiCode]
    # Measure the time it takes to generate the matrices for this code
    for code_class in codes:
        output_file.write(f"{code_class.__name__}: ")
        for bits in [8, 16, 24, 32, 64]:
            start = time.time()
            code = code_class(data_bits=bits)
            try:
                code.generate_matrices(timeout=5*60.0)
                duration = 1000 * (time.time() - start)
                logging.info(f"Matrix generation took {duration:.2f}ms")
                output_file.write(f"{duration:.2f} & ")
            except ValueError:
                logging.info("Matrix generation failed...")
                output_file.write("failed & ")
        output_file.write("\n")
        output_file.flush()
