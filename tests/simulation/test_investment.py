"""Deposit interest and mortgage integration tests."""

from decimal import Decimal

import pytest

from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.investment import deposit_term
from mortgage_simulator.simulation.models import DepositInvestment, InvestmentMode, LumpSum, OverpaymentScenario
from tests.factories import default_mortgage_terms


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


class TestInvestmentSimulation:
    """Scenario integration and optimization."""

    def test_automatic_when_candidates_expect_minimum_manual_cost(self) -> None:
        # Arrange
        terms = default_mortgage_terms()
        investment = DepositInvestment(
            initial_amount=Decimal("10000"),
            start_month=1,
            annual_rate=Decimal("0.06"),
            term_months=12,
            mode=InvestmentMode.AUTOMATIC,
        )
        # Act
        result = simulate(terms, OverpaymentScenario(name="Deposit", investment=investment))
        # Assert
        assert result.investment is not None
        assert result.summary.total_mortgage_cost == min(c.total_mortgage_cost for c in result.investment_candidates)
        for candidate in result.investment_candidates:
            manual = investment.model_copy(update={"mode": InvestmentMode.MANUAL, "term_count": candidate.term_count})
            actual = simulate(terms, OverpaymentScenario(name="Manual", investment=manual))
            assert actual.summary.total_mortgage_cost == candidate.total_mortgage_cost

    def test_payoff_when_during_term_expect_no_renewal(self) -> None:
        # Arrange
        terms = default_mortgage_terms()
        investment = DepositInvestment(
            initial_amount=Decimal("10000"), start_month=1, annual_rate=Decimal("0.06"), term_months=3, term_count=3
        )
        scenario = OverpaymentScenario(
            name="Early", investment=investment, lump_sums=(LumpSum(month=2, amount=terms.principal),)
        )
        # Act
        result = simulate(terms, scenario)
        # Assert
        assert result.investment is not None
        assert len(result.investment.terms) == 1
        assert result.investment.completion_month == 4
        assert result.investment.applied_repayment == 0
        assert result.investment.retained_surplus == Decimal("10121.50")

    def test_surplus_when_maturity_at_horizon_expect_applied_before_settlement(self) -> None:
        # Arrange
        terms = default_mortgage_terms()
        investment = DepositInvestment(
            initial_amount=terms.principal * 2,
            start_month=1,
            annual_rate=Decimal("0"),
            term_months=terms.analysis_horizon_months - 1,
            term_count=1,
        )
        # Act
        result = simulate(terms, OverpaymentScenario(name="Surplus", investment=investment))
        # Assert
        assert result.investment is not None
        assert result.summary.horizon_settlement == 0
        assert result.investment.applied_repayment > 0
        assert result.investment.applied_repayment + result.investment.retained_surplus == investment.initial_amount
