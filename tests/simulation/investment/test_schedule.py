"""Deposit schedule arithmetic tests."""

from decimal import Decimal

import pytest

from mortgage_simulator.simulation.investment.schedule import deposit_term
from mortgage_simulator.simulation.models import DepositInvestment


class TestDeposit:
    """Maturity arithmetic and compounding."""

    @pytest.mark.parametrize(("months", "expected"), [(3, "101215.00"), (36, "114580.00")])
    def test_term_when_fixed_rate_expect_net_balance(self, months: int, expected: str) -> None:
        # Arrange
        investment = DepositInvestment(
            initial_amount=Decimal("100000"),
            start_month=1,
            annual_rate=Decimal("0.06"),
            term_months=months,
            term_count=1,
        )
        # Act
        term = deposit_term(investment.initial_amount, investment, 1 + months)
        # Assert
        assert term.closing_balance == Decimal(expected)

    def test_renewal_when_two_terms_expect_tax_each_term(self) -> None:
        # Arrange
        investment = DepositInvestment(
            initial_amount=Decimal("100000"), start_month=1, annual_rate=Decimal("0.06"), term_months=3, term_count=2
        )
        # Act
        first = deposit_term(investment.initial_amount, investment, 4)
        second = deposit_term(first.closing_balance, investment, 7)
        # Assert
        assert second.gross_interest == Decimal("1518.23")
        assert second.tax == Decimal("288.47")
        assert second.closing_balance == Decimal("102444.76")
