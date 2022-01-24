import abc
import logging
import signal
import time
from dataclasses import dataclass
from functools import reduce
from typing import Optional, List, Sequence

import numpy as np
import pyboolector
from amaranth.utils import bits_for
from pyboolector import Boolector, BoolectorNode

from . import GenericCode
from ..util.matrix import generator_matrix_from_parity_check_matrix

sigint_tripped = False
"""Global flag indicating if SIGINT was raised"""


def sigint_handler(signum, frame):
    """Handles SIGINT and sets ``sigint_tripped``"""
    global sigint_tripped
    sigint_tripped = True


def termination_function(start, timeout):
    global sigint_tripped
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
    upper_bound: int
    lower_bound: int = 0
    description: str = ""


class BoolectorCode(GenericCode):
    """
    Boolector based auto-optimizing implementation of an error correction code.

    This implementation does not actually provide an error correction code, instead it can be used as the base of
    other error correction codes that require an optimizing search to generate their matrices.

    Basic implementations using this base class can only implement the ``conditions`` method, which allows them to
    give the conditions on the parity-check matrix. When the parity-check matrix is generated these conditions will
    be satisfied by Boolector, or an error will be thrown. Boolector will generate a parity-check matrix satisfying
    the requested conditions, however no other guarantees regarding quality are given.

    For error correction codes that would perform better under certain conditions it is possible to implement the
    ``optimization_goals`` method. This method should return a list of ``BoolectorOptimizationGoal``. Each of these
    optimization goals will be executed in order. Only when an optimization goal cannot be optimized further,
    or the lower bound is reached, will it continue optimizing the next goal.

    Both the ``DuttaToubaCode`` and the ``SheLiCode`` are implemented using the ``BoolectorCode`` framework and can
    be used as a reference for implementing other codes.
    """

    def __init__(self, data_bits, parity_bits):
        super().__init__(data_bits=data_bits, parity_bits=parity_bits)

        self.boolector: Boolector = None
        self.data_vars = []
        self.parity_vars = []
        self.all_vars = []

        self.row_popcount_max = None
        self.total_popcount = None

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
        matrix = np.empty((self.parity_bits, self.total_bits), dtype=int)

        for i, var in enumerate(self.all_vars):
            col = np.fromiter(var.assignment[::-1], dtype=int)
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
            logging.debug(f"Starting optimisation of {opt_goal.description} " +
                          f"from {opt_goal.upper_bound} down to {opt_goal.lower_bound}")
            opt_best = None

            # Assume that the optimization goal can be satisfied
            b.Assume(opt_goal.expression <= opt_goal.upper_bound)

            while True:
                # Attempt to satisfy the optimization goal
                result = b.Sat()
                if result == b.SAT:
                    # A model could be found for this optimization goal
                    best_model = self._parity_check_matrix_from_model()

                    opt_best = int(opt_goal.expression.assignment, 2)
                    logging.debug(f"Found assignment with {opt_best}")

                    # Attempt to lower the goal for optimization
                    b.Fixate_assumptions()
                    if opt_best == opt_goal.lower_bound:
                        logging.debug("Lower bound reached")
                        break
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
        return [
            self.maximum_ones_per_row_optimization_goal(),
            self.total_ones_optimization_goal(),
        ]

    def _generate_popcount_scaffolding(self) -> None:
        """
        Build the Boolector nodes representing the maximum row popcount and total popcount.

        :return: None
        """
        # If these nodes already exist do not recreate them
        if self.row_popcount_max is not None and self.total_popcount is not None:
            return

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
        self.row_popcount_max = reduce(boolector_max, bits_set_in_row)
        # Calculate the total number of bits set
        self.total_popcount = sum(bits_set_in_row)

    def maximum_ones_per_row_optimization_goal(self) -> BoolectorOptimizationGoal:
        """
        Get the optimization goal for the maximum number of ones per row.

        This optimization goal uses the ``self.row_popcount_max`` Boolector node to optimize the maximum number of
        ones per row. The maximum number of ones per row is always upper bounded by ``self.data_bits + 1`` as all the
        data bit columns could contain a one in this row, but the parity-check columns always contain only a single
        one per row.

        :return: BoolectorOptimizationGoal for maximum ones per row
        """
        self._generate_popcount_scaffolding()
        return BoolectorOptimizationGoal(
            expression=self.row_popcount_max,
            upper_bound=self.data_bits + 1,
            description="maximum ones per row"
        )

    def total_ones_optimization_goal(self) -> BoolectorOptimizationGoal:
        """
        Get the optimization goal for the total number of ones in the matrix.

        This optimization goal uses the ``self.total_popcount`` Boolector node to optimize the total number of ones
        in the parity-check matrix. The total number of ones is always upper bounded by ``self.parity_bits * (
        self.data_bits + 1)`` as each row is upper bounded by ``self.data_bits + 1`` and there are
        ``self.parity_bits`` number of rows.

        :return: BoolectorOptimizationGoal for total ones in matrix
        """
        self._generate_popcount_scaffolding()
        return BoolectorOptimizationGoal(
            expression=self.total_popcount,
            upper_bound=self.parity_bits * (self.data_bits + 1),
            description="total ones in matrix"
        )

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
