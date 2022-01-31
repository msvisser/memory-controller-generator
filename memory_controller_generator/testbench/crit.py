import logging
import time
from collections import Counter

import numpy as np

from memory_controller_generator.error_correction import HammingCode, ExtendedHammingCode, HsiaoCode, \
    HsiaoConstructedCode, DuttaToubaCode, SheLiCode

if __name__ == "__main__":
    np.set_printoptions(linewidth=200)

    log_format = "%(levelname)8s: %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format)

    codes = [HammingCode, ExtendedHammingCode, HsiaoCode, HsiaoConstructedCode, DuttaToubaCode, SheLiCode]
    # Measure the time it takes to generate the matrices for this code
    for code_class in codes:
        start = time.time()
        code = code_class(data_bits=32)
        code.generate_matrices(timeout=5 * 60.0)
        duration = 1000 * (time.time() - start)
        logging.info(f"Matrix generation took {duration:.2f}ms")

        row_max = max(sum(code.parity_check_matrix.T))

        counter = Counter()
        for err in code.correctable_errors:
            counter.update(err)
        syns = counter.most_common(1)[0][1]

        logging.info(f"row_max: {row_max}, n: {code.total_bits}, k: {code.data_bits}, syns: {syns}")
