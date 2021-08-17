import abc
import logging
import signal
import time
from dataclasses import dataclass
from functools import reduce
from typing import Optional, List, Sequence

import numpy as np
import pyboolector
from nmigen.utils import bits_for
from pyboolector import Boolector, BoolectorNode

from . import GenericCode
from .matrix_util import generator_matrix_from_parity_check_matrix

sigint_tripped = False
"""Global flag indicating if SIGINT was raised"""


def sigint_handler(signum, frame):
    """Handles SIGINT and sets ``sigint_tripped``"""
    global sigint_tripped
    sigint_tripped = True


def termination_function(start, timeout):
    return (time.time() - start > timeout) or sigint_tripped


@dataclass
class BoolectorOptimizationGoal:
    """
    Optimization goal for the Boolector based codes.

    This class holds a reference to a Boolector expression which should be minimized. The initial value is used as an
    initial bound for the optimization of the expression. As an addition, a description string can be added for
    debugging purposes.
    """
    expression: BoolectorNode
    initial_value: int
    description: str = ""


class BoolectorCode(GenericCode):
    def __init__(self, data_bits, parity_bits):
        super().__init__(data_bits=data_bits, parity_bits=parity_bits)

        self.boolector = None
        self.data_vars = []
        self.parity_vars = []
        self.all_vars = []

    def generate_matrices(self, timeout: Optional[float] = None) -> None:
        """
        Generate the parity-check and generator matrices for this error correction code.

        :param timeout: Optional timeout in seconds
        :return: None
        """
        # Create a Boolector instance and set the MODEL_GEN and INCREMENTAL options
        self.boolector = b = Boolector()
        b.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
        b.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)

        # Register the SIGINT handler and enable the termination function of Boolector
        signal.signal(signal.SIGINT, sigint_handler)
        b.Set_term(termination_function, (time.time(), timeout))

        # Define the BitVector sort for parity-check matrix columns
        column_sort = b.BitVecSort(self.parity_bits)

        # Create the variables for the data and parity columns
        for i in range(self.data_bits):
            self.data_vars.append(b.Var(column_sort, f"d{i}"))
        for i in range(self.parity_bits):
            self.parity_vars.append(b.Var(column_sort, f"p{i}"))

        # Create a list of all variables
        self.all_vars = [*self.data_vars, *self.parity_vars]

        # Force the parity columns to be one-hot
        for i in range(self.parity_bits):
            b.Assert(self.parity_vars[i] == (1 << i))

        # Force all data columns to be non-zero
        for i in range(self.data_bits):
            b.Assert(self.data_vars[i] != 0)

        # Apply all subclass defined conditions
        self.conditions()

        # Run the Boolector optimizer to generate the parity-check matrix
        model = self._optimize()
        if model is None:
            raise ValueError("Unable to generate a model")

        self.parity_check_matrix = model
        self.generator_matrix = generator_matrix_from_parity_check_matrix(self.parity_check_matrix)

    def _parity_check_matrix_from_model(self):
        """Create a numpy matrix from the Boolector variable assignments."""
        matrix = np.empty((self.parity_bits, self.total_bits), dtype=np.int)

        for i, var in enumerate(self.all_vars):
            col = np.fromiter(var.assignment[::-1], dtype=np.int)
            matrix[:, i] = col

        return matrix

    def _optimize(self) -> Optional:
        """Run Boolector multiple times to generate a parity-check matrix and optimize it."""
        b = self.boolector
        optimisation_goals = self.optimization_goals()

        # Run an initial satisfiability check
        result = b.Sat()
        if result == b.SAT:
            best_model = self._parity_check_matrix_from_model()
        else:
            # This model cannot be satisfied at all
            return None

        for opt_goal in optimisation_goals:
            logging.debug(f"Starting optimisation of {opt_goal.description} with {opt_goal.initial_value}")
            opt_best = None

            # Assume that the optimization goal can be satisfied
            b.Assume(opt_goal.expression <= opt_goal.initial_value)

            while True:
                # Attempt to satisfy the optimization goal
                result = b.Sat()
                if result == b.SAT:
                    # A model could be found for this optimization goal
                    best_model = self._parity_check_matrix_from_model()

                    opt_best = int(opt_goal.expression.assignment, 2)
                    logging.debug(f"Found assignment of {opt_best}")

                    # Attempt to lower the goal for optimization
                    b.Fixate_assumptions()
                    b.Assume(opt_goal.expression < opt_best)
                elif result == b.UNSAT:
                    # Optimization of this goal cannot be improved
                    logging.debug(f"Cannot improve the optimization of {opt_goal.description} more than {opt_best}")
                    break
                else:
                    # The termination function was triggered
                    logging.debug("Termination by SIGINT or timeout was triggered")
                    return best_model

        return best_model

    @abc.abstractmethod
    def conditions(self) -> None:
        """
        Define conditions on the columns of the parity-check matrix.

        This method can be implemented by subclasses to specify their own conditions on the columns of the
        parity-check matrix. It is up to the subclass to determine which conditions should be applied to generate a
        useful error correction code.
        """
        pass

    @abc.abstractmethod
    def optimization_goals(self) -> List[BoolectorOptimizationGoal]:
        """
        Optimization goals for this error correction code.

        A code can specify a number of optimization goals, which will be handled in order. Each optimization goal is
        optimized as much a possible, after that the next optimization goal is used. If no optimization goals are
        supplied, a valid parity-check matrix will be generated without any optimization.

        :return: List of optimization goals
        """
        return []

    def common_optimization_goals(self) -> List[BoolectorOptimizationGoal]:
        """
        Common optimization goals for error correction codes.

        This will return a list with two optimization goals which are commonly used by error correction codes. The
        first optimization goal is to reduce the maximum number of bits set in the rows of the parity-check matrix.
        The second optimization goal is to reduce the overall total number of bits set in the parity-check matrix.

        :return: List of optimization goals
        """
        b = self.boolector

        # Calculate the maximum number of bits needed to count all ones in the matrix
        total_matrix_bits = self.parity_bits * self.total_bits
        count_bits_required = bits_for(total_matrix_bits)

        # Zero and one constant values
        zero = b.Const(0, count_bits_required)
        one = b.Const(1, count_bits_required)

        # For each row count the number of bits set
        bits_set_in_row = []
        for row in reversed(range(self.parity_bits)):
            bits_set = b.Const(0, count_bits_required)
            for col in range(self.total_bits):
                bits_set += b.Cond(self.all_vars[col][row] == 0, zero, one)
            bits_set_in_row.append(bits_set)

        # Max function for boolector expressions
        def boolector_max(p, q):
            """If p >= q, return p else q"""
            condition = b.Ugte(p, q)
            return b.Cond(condition, p, q)

        # Calculate the maximum number of bits set per row
        bitcounts_max = reduce(boolector_max, bits_set_in_row)
        # Calculate the total number of bits set
        total_bits = sum(bits_set_in_row)

        # Return the optimization goals
        return [
            BoolectorOptimizationGoal(bitcounts_max, self.total_bits, "maximum bits per row"),
            BoolectorOptimizationGoal(total_bits, self.parity_bits * self.total_bits, "overall total bits"),
        ]

    def assert_all_unique(self, expressions: Sequence[BoolectorNode]) -> None:
        """
        Assert that all expressions in the list have a unique value.

        :param expressions: List of expressions
        :return: None
        """
        length = len(expressions)
        for i in range(length):
            for j in range(i + 1, length):
                self.boolector.Assert(expressions[i] != expressions[j])
