"""Multiple-deposit simulation tests with independently calculated expectations."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import (
    DepositInvestment,
    InvestmentMode,
    LumpSum,
    MortgageTerms,
    OverpaymentScenario,
    RatePeriod,
)
from tests.factories import default_mortgage_terms, default_subsidy_terms

ZERO = Decimal("0")
CONTRIBUTION = Decimal("1000")
ANNUAL_RATE = Decimal("0.10")


class TestMultipleInvestments:
    """Integration of monthly and single deposits with the mortgage schedule."""

    @pytest.mark.parametrize(("mode", "term_count"), [(InvestmentMode.MANUAL, 0), (InvestmentMode.AUTOMATIC, None)])
    def test_when_series_uses_immediate_or_automatic_timing_expect_validation_error(
        self, mode: InvestmentMode, term_count: int | None
    ) -> None:
        # Act / Assert
        with pytest.raises(ValidationError, match="monthly deposits"):
            _deposit(contribution_months=2, term_count=term_count, mode=mode)

    def test_when_more_than_one_entry_uses_automatic_timing_expect_validation_error(self) -> None:
        # Arrange
        automatic = _deposit(term_count=None, mode=InvestmentMode.AUTOMATIC)
        # Act / Assert
        with pytest.raises(ValidationError, match=r"only one.*automatic"):
            OverpaymentScenario(name="Two automatic entries", investment=(automatic, automatic))

    def test_when_deposits_renew_expect_staggered_repayments(self) -> None:
        # Arrange
        terms = _terms(principal="60000", horizon=26)
        scenario = OverpaymentScenario(
            name="Monthly renewals",
            recurring_amount=Decimal("10"),
            recurring_start_month=1,
            investment=(_deposit(contribution_months=2, term_months=12, term_count=2, annual_rate=ANNUAL_RATE),),
        )
        # Act
        result = simulate(terms, scenario)
        # Assert
        # At each term end round gross interest to cents and round tax up to cents.
        # First term: 1,000 + 100 - 19. Second term: 1,081 + 108.10 - 20.54.
        expected_proceeds = Decimal("1168.56")
        assert [deposit.opening_month for deposit in result.investments] == [1, 2]
        assert [deposit.summary.completion_month for deposit in result.investments] == [25, 26]
        for deposit in result.investments:
            outcome = deposit.summary
            assert [term.closing_balance for term in outcome.terms] == [Decimal("1081"), expected_proceeds]
            assert outcome.applied_repayment == expected_proceeds
            assert outcome.retained_surplus == ZERO
            assert outcome.applied_repayment + outcome.retained_surplus == deposit.initial_amount + outcome.net_earnings
        assert [payment.lump_sum for payment in result.payments[:-2]] == [ZERO] * 24
        assert [payment.lump_sum for payment in result.payments[-2:]] == [expected_proceeds] * 2
        assert [payment.recurring_overpayment for payment in result.payments[-2:]] == [Decimal("10")] * 2
        assert result.net_investment_earnings == Decimal("337.12")
        assert result.net_financing_cost == Decimal("-337.12")

    @pytest.mark.parametrize(("horizon", "is_valid"), [(25, False), (26, True)])
    def test_when_final_maturity_reaches_boundary_expect_inclusive_horizon(self, horizon: int, is_valid: bool) -> None:
        # Arrange
        terms = _terms(principal="60000", horizon=horizon)
        scenario = OverpaymentScenario(
            name="Final maturity", investment=(_deposit(contribution_months=2, term_months=12, term_count=2),)
        )
        # Act / Assert
        if is_valid:
            assert simulate(terms, scenario).investments[-1].summary.completion_month == horizon
        else:
            with pytest.raises(ValidationError, match="horizon"):
                simulate(terms, scenario)

    def test_when_payoff_precedes_first_opening_expect_no_contribution(self) -> None:
        # Arrange
        terms = _terms(principal="60000", horizon=20)
        scenario = OverpaymentScenario(
            name="Paid before opening",
            lump_sums=(LumpSum(month=1, amount=terms.principal),),
            investment=(_deposit(start_month=2, contribution_months=3, term_months=12, annual_rate=ANNUAL_RATE),),
        )
        # Act
        result = simulate(terms, scenario)
        # Assert
        assert result.summary.payoff_month == 1
        assert result.investments == ()
        assert result.net_investment_earnings == ZERO
        assert result.retained_investment_surplus == ZERO

    def test_when_payoff_interrupts_period_expect_open_deposit_to_finish_current_term(self) -> None:
        # Arrange
        terms = _terms(principal="60000", horizon=40)
        payoff_month = 2
        scenario = OverpaymentScenario(
            name="Paid during period",
            lump_sums=(LumpSum(month=payoff_month, amount=terms.principal),),
            investment=(_deposit(contribution_months=4, term_months=12, term_count=2, annual_rate=ANNUAL_RATE),),
        )
        # Act
        result = simulate(terms, scenario)
        # Assert
        assert result.summary.payoff_month == payoff_month
        assert [deposit.opening_month for deposit in result.investments] == [1]
        outcome = result.investments[0].summary
        assert [term.maturity_month for term in outcome.terms] == [13]
        assert outcome.completion_month == 13
        assert outcome.applied_repayment == ZERO
        assert outcome.retained_surplus == Decimal("1081")
        assert result.net_investment_earnings == Decimal("81")

    def test_when_payouts_coincide_expect_mortgage_priority_and_balanced_proceeds(self) -> None:
        # Arrange
        terms = _terms(principal="3000", horizon=4, contractual_term=12)
        payout_month = 2
        scenario = OverpaymentScenario(
            name="Competing payouts",
            recurring_amount=Decimal("100"),
            recurring_start_month=1,
            lump_sums=(LumpSum(month=payout_month, amount=Decimal("400")),),
            investment=(_deposit(initial_amount=Decimal("1200")), _deposit(contribution_months=2)),
        )
        # Act
        result = simulate(terms, scenario)
        # Assert
        # After two months of 250 scheduled + 100 recurring and a 400 lump sum,
        # 1,900 remains. The monthly deposit pays 1,000 and the single pays 900.
        assert result.summary.payoff_month == payout_month
        assert result.payments[-1].lump_sum == Decimal("2300")
        by_index = {deposit.investment_index: deposit for deposit in result.investments}
        assert len(result.investments) == 2
        assert by_index[2].summary.applied_repayment == CONTRIBUTION
        assert by_index[2].summary.retained_surplus == ZERO
        assert by_index[1].summary.applied_repayment == Decimal("900")
        assert by_index[1].summary.retained_surplus == Decimal("300")
        assert result.retained_investment_surplus == Decimal("300")
        for deposit in result.investments:
            assert deposit.summary.applied_repayment + deposit.summary.retained_surplus == deposit.initial_amount

    def test_when_automatic_timing_changes_payoff_expect_manual_candidate_parity(self) -> None:
        # Arrange
        terms = _terms(principal="10000", horizon=6, contractual_term=10)
        immediate_capital = Decimal("9000")
        single = _deposit(initial_amount=immediate_capital, mode=InvestmentMode.AUTOMATIC, term_count=None)
        monthly = _deposit(contribution_months=3, term_months=2, annual_rate=ANNUAL_RATE)
        # Act
        automatic = simulate(terms, OverpaymentScenario(name="Automatic", investment=(single, monthly)))
        # Assert
        # Immediate 9,000 + first scheduled 1,000 pays the mortgage before any monthly opening.
        # A delayed single payout leaves time for the first monthly deposit to earn interest.
        manual_by_count = {}
        for count in range(terms.analysis_horizon_months):
            fixed = single.model_copy(update={"mode": InvestmentMode.MANUAL, "term_count": count})
            manual_by_count[count] = simulate(terms, OverpaymentScenario(name="Manual", investment=(fixed, monthly)))
        assert len(automatic.investment_candidates) == len(manual_by_count)
        assert manual_by_count[0].summary.payoff_month == 1
        assert not any(deposit.investment_index == 2 for deposit in manual_by_count[0].investments)
        assert manual_by_count[0].net_financing_cost == ZERO
        assert manual_by_count[1].net_financing_cost == Decimal("-13.50")
        for candidate in automatic.investment_candidates:
            assert candidate.net_financing_cost == manual_by_count[candidate.term_count].net_financing_cost
        assert automatic.investment_candidates[0].term_count == 3
        assert automatic.net_financing_cost == Decimal("-40.50")


def _terms(*, principal: str, horizon: int, contractual_term: int = 60) -> MortgageTerms:
    return default_mortgage_terms(
        principal=Decimal(principal),
        analysis_horizon_months=horizon,
        contractual_term_months=contractual_term,
        settle_remaining_principal_at_horizon=False,
        rate_periods=(RatePeriod(start_month=1, end_month=horizon, annual_rate=ZERO),),
        subsidy=default_subsidy_terms(enabled=False),
    )


def _deposit(
    *,
    initial_amount: Decimal = CONTRIBUTION,
    start_month: int = 1,
    contribution_months: int = 1,
    term_months: int = 1,
    term_count: int | None = 1,
    annual_rate: Decimal = ZERO,
    mode: InvestmentMode = InvestmentMode.MANUAL,
) -> DepositInvestment:
    return DepositInvestment(
        initial_amount=initial_amount,
        start_month=start_month,
        contribution_months=contribution_months,
        annual_rate=annual_rate,
        term_months=term_months,
        term_count=term_count,
        mode=mode,
    )
