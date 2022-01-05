import logging
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray


def parity_check_matrix_to_systematic(input_parity_check_matrix: NDArray) -> Tuple[NDArray, List[Tuple[int, int]]]:
    """
    Create a systematic parity-check matrix from any valid parity-check matrix.

    :param input_parity_check_matrix: input non-systematic parity-check matrix
    :return: systematic parity-check matrix, and a list of swapped columns
    :raises ValueError: if the input parity-check matrix contains a redundant row
    """
    parity_check_matrix = np.array(input_parity_check_matrix, dtype=int)
    rows, cols = parity_check_matrix.shape
    col_swaps = []
    row_swaps = list(range(rows))

    for (row_offset, col_offset) in zip(reversed(range(rows)), reversed(range(cols))):
        # Make sure the 1 bit is set for the identity diagonal
        if parity_check_matrix[row_offset, col_offset] != 1:
            # First, try to find a row higher up to swap down
            for row in reversed(range(row_offset)):
                if parity_check_matrix[row, col_offset] == 1:
                    logging.debug(f"swapping rows {row_offset} {row}")
                    parity_check_matrix[[row, row_offset], :] = parity_check_matrix[[row_offset, row], :]
                    row_swaps[row], row_swaps[row_offset] = row_swaps[row_offset], row_swaps[row]
                    break
            else:
                # Otherwise, look for a column to swap to the right
                for col in reversed(range(col_offset)):
                    if parity_check_matrix[row_offset, col] == 1:
                        col_swaps.append((col_offset, col))
                        logging.debug(f"swapping columns {col_offset} {col}")
                        parity_check_matrix[:, [col, col_offset]] = parity_check_matrix[:, [col_offset, col]]
                        break
                else:
                    logging.debug(parity_check_matrix)
                    raise ValueError(
                        f"""Unable to find a row or a column with a one to fill position {row_offset} {col_offset}.
                        Row {row_swaps[row_offset]} in the original matrix is redundant."""
                    )

        # Clear the column above this diagonal
        for row in reversed(range(row_offset)):
            if parity_check_matrix[row, col_offset] == 1:
                logging.debug(f"summing rows {row_offset} -> {row}")
                parity_check_matrix[row] ^= parity_check_matrix[row_offset]

    # Clear the triangle below the diagonal
    for col in range(rows):
        for row in range(col + 1, rows):
            if parity_check_matrix[row, -(rows - col)] == 1:
                logging.debug(f"summing rows {col} -> {row}")
                parity_check_matrix[row] ^= parity_check_matrix[col]

    # Return the new parity-check matrix, and a list of column swaps to apply to the generator matrix
    return parity_check_matrix, col_swaps


def generator_matrix_from_systematic(parity_check_matrix: NDArray) -> NDArray:
    """
    Create a systematic generator matrix from a systematic parity-check matrix.

    :param parity_check_matrix: input systematic parity-check matrix
    :return: systematic generator matrix
    :raises ValueError: if the parity-check matrix is not in systematic form
    """
    parity_bits, length = parity_check_matrix.shape
    data_bits = length - parity_bits

    # Verify that the matrix is in systematic form by looking for an identity matrix on the right side of the
    # parity-check matrix
    if not np.array_equal(parity_check_matrix[:, length-parity_bits:], np.identity(parity_bits)):
        raise ValueError("Check matrix is not in systematic form")

    # Get the parity part from the parity-check matrix
    parity_part = parity_check_matrix[:, 0:data_bits]
    # Create a new identity matrix
    identity_part = np.identity(data_bits, dtype=int)
    # Concatenate the matrices to create the generator matrix
    generator_matrix = np.hstack((identity_part, parity_part.T))
    return generator_matrix


def generator_matrix_from_parity_check_matrix(parity_check_matrix: NDArray) -> NDArray:
    """
    Create a matching generator matrix for any valid parity-check matrix.

    This will first convert the parity-check matrix into systematic form. After which, the systematic generator matrix
    is created. Finally, this systematic generator matrix is converted into a valid generator matrix for the original
    parity-check matrix by swapping columns.

    This function uses ``parity_check_matrix_to_systematic`` and ``generator_matrix_from_systematic``.

    :param parity_check_matrix: input parity-check matrix
    :return: matching generator matrix
    """
    # Calculate the systematic parity-check and generator matrix
    parity_check_systematic, col_swaps = parity_check_matrix_to_systematic(parity_check_matrix)
    generator_systematic = generator_matrix_from_systematic(parity_check_systematic)

    # Calculate the generator matrix for the original parity-check matrix
    generator_matrix = np.array(generator_systematic, dtype=int)
    for (a, b) in col_swaps[::-1]:
        generator_matrix[:, [b, a]] = generator_matrix[:, [a, b]]

    # Assert that both matrices are compatible
    assert ((np.matmul(parity_check_matrix, generator_matrix.T) % 2) == 0).all()

    return generator_matrix


def np_array_to_value(array: NDArray) -> int:
    """
    Convert binary numpy vector to value.

    :param array: numpy vector
    :return: value as int
    """
    (size,) = array.shape
    return sum(
        (1 << i) if array[i] else 0
        for i in range(size)
    )
