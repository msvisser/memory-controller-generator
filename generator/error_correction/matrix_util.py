import logging
import numpy as np


def transform_check_matrix_to_systematic(M):
    rows, cols = M.shape
    col_swaps = []
    row_swaps = list(range(rows))

    for (row_offset, col_offset) in zip(reversed(range(rows)), reversed(range(cols))):
        # Make sure the 1 bit is set for the identity diagonal
        if M[row_offset, col_offset] != 1:
            # First, try to find a row higher up to swap down
            for row in reversed(range(row_offset)):
                if M[row, col_offset] == 1:
                    logging.debug(f"swapping rows {row_offset} {row}")
                    M[[row, row_offset], :] = M[[row_offset, row], :]
                    row_swaps[row], row_swaps[row_offset] = row_swaps[row_offset], row_swaps[row]
                    break
            else:
                # Otherwise, look for a column to swap to the right
                for col in reversed(range(col_offset)):
                    if M[row_offset, col] == 1:
                        col_swaps.append((col_offset, col))
                        logging.debug(f"swapping columns {col_offset} {col}")
                        M[:, [col, col_offset]] = M[:, [col_offset, col]]
                        break
                else:
                    logging.debug(M)
                    raise ValueError(f"Unable to find a row or a column with a one to fill position {row_offset} {col_offset}. Row {row_swaps[row_offset]} in the original matrix is redundant.")

        # Clear the column above this diagonal
        for row in reversed(range(row_offset)):
            if M[row, col_offset] == 1:
                logging.debug(f"summing rows {row_offset} -> {row}")
                M[row] ^= M[row_offset]

    # Clear the triangle below the diagonal
    for col in range(rows):
        for row in range(col + 1, rows):
            if M[row, -(rows - col)] == 1:
                logging.debug(f"summing rows {col} -> {row}")
                M[row] ^= M[col]

    # Return a list of column swaps to apply to the generator matrix
    return col_swaps


def generate_matrix_from_check_matrix(H):
    parity_bits, length = H.shape
    data_bits = length - parity_bits

    # Verify that the matrix is in systematic form by looking for an identity matrix
    # at the right side of the parity-check matrix
    if not np.array_equal(H[:,-parity_bits:], np.identity(parity_bits)):
        raise ValueError("Check matrix is not in systematic form")

    # Get the A part from the parity-check matrix
    A = H[:,0:data_bits]
    # Create a new identity matrix for G
    I = np.identity(data_bits, dtype=np.int)
    # Concatenate the matrices to create G
    G = np.hstack((I, A.T))
    return G


def np_array_to_value(array: np.array):
    (size,) = array.shape
    return sum(
        (1 << i) if array[i] else 0
        for i in range(size)
    )
