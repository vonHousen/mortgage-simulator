"""Deposit interest and mortgage integration tests."""

from decimal import Decimal

import pytest

from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import (
    DepositInvestment,
    InterestCalculationMethod,
    InvestmentMode,
    LumpSum,
    OverpaymentScenario,
    RatePeriod,
)
from tests.factories import default_mortgage_terms, default_subsidy_terms


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
        assert result.net_financing_cost == min(c.net_financing_cost for c in result.investment_candidates)
        for candidate in result.investment_candidates:
            manual = investment.model_copy(update={"mode": InvestmentMode.MANUAL, "term_count": candidate.term_count})
            actual = simulate(terms, OverpaymentScenario(name="Manual", investment=manual))
            assert actual.summary.total_mortgage_cost == candidate.total_mortgage_cost
            assert actual.net_financing_cost == candidate.net_financing_cost

    @pytest.mark.parametrize(("deposit_rate", "expected_terms"), [("0.10", 1), ("0", 0)])
    def test_automatic_when_interest_rates_differ_expect_lowest_net_cost(
        self, deposit_rate: str, expected_terms: int
    ) -> None:
        # Arrange
        terms = default_mortgage_terms(
            interest_calculation_method=InterestCalculationMethod.EQUAL_MONTHS,
            analysis_horizon_months=13,
            rate_periods=(RatePeriod(start_month=1, end_month=13, annual_rate=Decimal("0.02")),),
            subsidy=default_subsidy_terms(enabled=False),
        )
        investment = DepositInvestment(
            initial_amount=Decimal("100000"),
            start_month=1,
            annual_rate=Decimal(deposit_rate),
            term_months=12,
            mode=InvestmentMode.AUTOMATIC,
        )
        # Act
        result = simulate(terms, OverpaymentScenario(name="Compare", investment=investment))
        # Assert
        assert result.investment is not None
        assert result.investment.planned_term_count == expected_terms
        assert result.net_financing_cost == min(c.net_financing_cost for c in result.investment_candidates)
        if expected_terms:
            immediate = next(c for c in result.investment_candidates if c.term_count == 0)
            assert result.summary.total_mortgage_cost > immediate.total_mortgage_cost
            assert result.investment.net_earnings == Decimal("8100")
            assert (immediate.net_financing_cost - result.net_financing_cost).quantize(Decimal("0.01")) == Decimal(
                "6100.00"
            )

    def test_automatic_when_zero_rates_expect_immediate_tie_winner(self) -> None:
        # Arrange
        terms = default_mortgage_terms(
            rate_periods=(RatePeriod(start_month=1, end_month=120, annual_rate=Decimal("0")),),
            subsidy=default_subsidy_terms(enabled=False),
        )
        investment = DepositInvestment(
            initial_amount=Decimal("1000"),
            start_month=1,
            annual_rate=Decimal("0"),
            term_months=12,
            mode=InvestmentMode.AUTOMATIC,
        )
        # Act
        result = simulate(terms, OverpaymentScenario(name="Tie", investment=investment))
        # Assert
        assert result.investment is not None
        assert result.investment.planned_term_count == 0
        assert result.net_financing_cost == 0

    def test_automatic_when_payoff_collapses_maturities_expect_fewer_planned_terms(self) -> None:
        # Arrange
        terms = default_mortgage_terms(
            rate_periods=(RatePeriod(start_month=1, end_month=120, annual_rate=Decimal("0")),),
            subsidy=default_subsidy_terms(enabled=False),
        )
        investment = DepositInvestment(
            initial_amount=Decimal("1000"),
            start_month=1,
            annual_rate=Decimal("0.10"),
            term_months=3,
            mode=InvestmentMode.AUTOMATIC,
        )
        scenario = OverpaymentScenario(
            name="Payoff", investment=investment, lump_sums=(LumpSum(month=2, amount=terms.principal),)
        )
        # Act
        result = simulate(terms, scenario)
        # Assert
        assert result.investment is not None
        assert result.investment.planned_term_count == 1
        assert result.investment.completion_month == 4
        first, second = result.investment_candidates[:2]
        assert first.net_financing_cost == second.net_financing_cost
        assert first.repayment_month == second.repayment_month == 4
        assert first.term_count == 1
        assert second.term_count == 2

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
