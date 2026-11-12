"""Tests for the pure mortgage calculation engine."""

from datetime import date
from decimal import Decimal

import pytest

from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import (
    FeeTerms,
    InsuranceCalculationMethod,
    InterestCalculationMethod,
    LumpSum,
    MortgageTerms,
    OverpaymentScenario,
    RatePeriod,
    SubsidyTerms,
)
from tests.factories import (
    default_fee_terms,
    default_mortgage_terms,
    default_subsidy_terms,
    non_zero_synthetic_fee_terms,
    synthetic_overpayment_scenario,
    synthetic_terms,
)

MONEY_TOLERANCE = Decimal("0.0001")
ZERO_SYNTHETIC_FEES = default_fee_terms()
NON_ZERO_SYNTHETIC_FEES = non_zero_synthetic_fee_terms()


class TestSimulateBaseline:
    """Tests for the shared synthetic baseline schedule."""

    @pytest.mark.parametrize(
        (
            "fees",
            "expected_monthly_insurance",
            "expected_monthly_fixed_fees",
            "expected_annual_fixed_fee",
            "expected_fees",
            "expected_cash_outflow",
        ),
        [
            pytest.param(
                ZERO_SYNTHETIC_FEES,
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("3055.555555555555555555555556"),
                id="zero-fees",
            ),
            pytest.param(
                NON_ZERO_SYNTHETIC_FEES,
                Decimal("250.0000"),
                Decimal("15"),
                Decimal("600"),
                Decimal("865.0000"),
                Decimal("3920.555555555555555555555556"),
                id="non-zero-fees",
            ),
        ],
    )
    def test_simulate_when_baseline_expect_first_month_values(
        self,
        fees: FeeTerms,
        expected_monthly_insurance: Decimal,
        expected_monthly_fixed_fees: Decimal,
        expected_annual_fixed_fee: Decimal,
        expected_fees: Decimal,
        expected_cash_outflow: Decimal,
    ) -> None:
        """Calculate the first synthetic payment from opening principal."""
        # Arrange
        terms = _synthetic_terms().model_copy(update={"fees": fees})
        scenario = OverpaymentScenario(name="Baseline")

        # Act
        result = simulate(terms, scenario)

        # Assert
        payment = result.payments[0]
        assert payment.month == 1
        assert payment.payment_date == date(2024, 1, 1)
        assert payment.scheduled_principal == Decimal("1388.888888888888888888888889")
        assert payment.interest == Decimal("2916.666666666666666666666667")
        assert payment.subsidy == Decimal("1250.00")
        assert payment.monthly_insurance == expected_monthly_insurance
        assert payment.monthly_fixed_fees == expected_monthly_fixed_fees
        assert payment.annual_fixed_fee == expected_annual_fixed_fee
        assert payment.fees == expected_fees
        assert payment.cash_outflow_without_fees == Decimal("3055.555555555555555555555556")
        assert payment.cash_outflow == payment.cash_outflow_without_fees + payment.fees
        assert payment.cash_outflow == expected_cash_outflow

    @pytest.mark.parametrize(
        (
            "fees",
            "expected_monthly_insurance",
            "expected_monthly_fixed_fees",
            "expected_annual_fixed_fee",
            "expected_fees",
            "expected_cash_outflow",
        ),
        [
            pytest.param(
                ZERO_SYNTHETIC_FEES,
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("3124.999999999999999999999997"),
                id="zero-fees",
            ),
            pytest.param(
                NON_ZERO_SYNTHETIC_FEES,
                Decimal("208.6862477231329690346083785"),
                Decimal("15"),
                Decimal("600"),
                Decimal("823.6862477231329690346083785"),
                Decimal("3948.686247723132969034608376"),
                id="non-zero-fees",
            ),
        ],
    )
    def test_simulate_when_rate_period_changes_expect_month_61_values(
        self,
        fees: FeeTerms,
        expected_monthly_insurance: Decimal,
        expected_monthly_fixed_fees: Decimal,
        expected_annual_fixed_fee: Decimal,
        expected_fees: Decimal,
        expected_cash_outflow: Decimal,
    ) -> None:
        """Apply the second rate and annual fixed fee at month 61."""
        # Arrange
        terms = _synthetic_terms().model_copy(update={"fees": fees})
        scenario = OverpaymentScenario(name="Baseline")

        # Act
        result = simulate(terms, scenario)

        # Assert
        payment = result.payments[60]
        assert payment.month == 61
        assert payment.interest == Decimal("2777.777777777777777777777773")
        assert payment.subsidy == Decimal("1041.666666666666666666666665")
        assert payment.monthly_insurance == expected_monthly_insurance
        assert payment.monthly_fixed_fees == expected_monthly_fixed_fees
        assert payment.annual_fixed_fee == expected_annual_fixed_fee
        assert payment.fees == expected_fees
        assert payment.cash_outflow == expected_cash_outflow

    @pytest.mark.parametrize(
        ("fees", "expected_total_fees", "expected_total_cash_outflow", "expected_total_mortgage_cost"),
        [
            pytest.param(
                ZERO_SYNTHETIC_FEES,
                Decimal("0"),
                Decimal("352395.8333333333333333333330"),
                Decimal("185729.1666666666666666666662"),
                id="zero-fees",
            ),
            pytest.param(
                NON_ZERO_SYNTHETIC_FEES,
                Decimal("32882.98041894353369763205825"),
                Decimal("385278.8137522768670309653911"),
                Decimal("218612.1470856102003642987244"),
                id="non-zero-fees",
            ),
        ],
    )
    def test_simulate_when_baseline_expect_ten_year_summary(
        self,
        fees: FeeTerms,
        expected_total_fees: Decimal,
        expected_total_cash_outflow: Decimal,
        expected_total_mortgage_cost: Decimal,
    ) -> None:
        """Aggregate the synthetic baseline values over 120 months."""
        # Arrange
        terms = _synthetic_terms().model_copy(update={"fees": fees})
        scenario = OverpaymentScenario(name="Baseline")

        # Act
        result = simulate(terms, scenario)

        # Assert
        assert len(result.payments) == 120
        assert result.summary.total_principal == Decimal("166666.6666666666666666666673")
        assert result.summary.total_interest == Decimal("310937.4999999999999999999995")
        assert result.summary.total_subsidy == Decimal("125208.3333333333333333333333")
        assert result.summary.total_fees == expected_total_fees
        assert result.summary.total_cash_outflow == expected_total_cash_outflow
        assert result.summary.total_mortgage_cost == expected_total_mortgage_cost
        assert result.summary.ending_balance == Decimal("333333.3333333333333333333320")
        assert result.summary.payoff_month is None
        if expected_total_fees == Decimal("0"):
            assert all(
                payment.monthly_insurance == Decimal("0")
                and payment.monthly_fixed_fees == Decimal("0")
                and payment.annual_fixed_fee == Decimal("0")
                and payment.fees == Decimal("0")
                for payment in result.payments
            )
        assert result.summary.total_cash_outflow == sum(
            (payment.cash_outflow for payment in result.payments), start=Decimal("0")
        )
        assert result.summary.total_principal == sum(
            (
                payment.scheduled_principal + payment.recurring_overpayment + payment.lump_sum
                for payment in result.payments
            ),
            start=Decimal("0"),
        )
        expected_cost = result.summary.total_interest - result.summary.total_subsidy + result.summary.total_fees
        opening_balances = sum((payment.opening_balance for payment in result.payments), start=Decimal("0"))
        expected_net_rate = (
            Decimal("12") * (result.summary.total_interest - result.summary.total_subsidy) / opening_balances
        )
        assert result.summary.total_mortgage_cost == expected_cost
        assert result.summary.mortgage_cost_to_original_principal == expected_cost / terms.principal
        assert result.summary.mortgage_cost_to_principal_repaid == expected_cost / result.summary.total_principal
        assert result.summary.net_average_annual_interest_rate == expected_net_rate

    def test_simulate_when_subsidy_disabled_expect_zero_subsidy_and_gross_costs(self) -> None:
        """Exclude preserved subsidy assumptions from every calculated value."""
        # Arrange
        original_terms = _synthetic_terms()
        terms = original_terms.model_copy(
            update={
                "subsidy": SubsidyTerms(
                    enabled=False,
                    coefficient=original_terms.subsidy.coefficient,
                    second_coefficient=original_terms.subsidy.coefficient,
                    reference_rate=original_terms.subsidy.reference_rate,
                )
            }
        )

        # Act
        result = simulate(terms, OverpaymentScenario(name="No subsidy"))

        # Assert
        assert all(payment.subsidy == Decimal("0") for payment in result.payments)
        assert result.summary.total_subsidy == Decimal("0")
        assert result.summary.total_mortgage_cost == result.summary.total_interest + result.summary.total_fees
        opening_balances = sum((payment.opening_balance for payment in result.payments), start=Decimal("0"))
        expected_rate = Decimal("12") * result.summary.total_interest / opening_balances
        assert result.summary.net_average_annual_interest_rate == expected_rate

    def test_simulate_when_schedule_crosses_year_expect_payment_dates(self) -> None:
        """Advance exact payment dates across a calendar-year boundary."""
        # Arrange
        terms = default_mortgage_terms(first_payment_date=date(2024, 11, 18))
        scenario = OverpaymentScenario(name="Baseline")

        # Act
        result = simulate(terms, scenario)

        # Assert
        assert result.payments[0].payment_date == date(2024, 11, 18)
        assert result.payments[1].payment_date == date(2024, 12, 18)
        assert result.payments[2].payment_date == date(2025, 1, 18)

    def test_simulate_when_fee_end_is_none_expect_monthly_charges_through_horizon(self) -> None:
        """Apply balance-based insurance and monthly fees throughout the schedule."""
        # Arrange
        terms = default_mortgage_terms(fees=non_zero_synthetic_fee_terms())

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        month_120 = result.payments[119]
        expected_fees = month_120.monthly_insurance + terms.fees.monthly_fixed_fees
        assert month_120.fees == expected_fees

    def test_simulate_when_fee_end_is_set_expect_inclusive_end_month(self) -> None:
        """Stop monthly insurance and fees after the configured inclusive month."""
        # Arrange
        terms = default_mortgage_terms(fees=non_zero_synthetic_fee_terms(insurance_end_month=60))

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        assert result.payments[59].monthly_insurance > Decimal("0")
        assert result.payments[59].monthly_fixed_fees > Decimal("0")
        assert result.payments[60].monthly_insurance == Decimal("0")
        assert result.payments[60].monthly_fixed_fees == Decimal("0")
        assert result.payments[60].annual_fixed_fee == terms.fees.annual_fixed_fee


class TestSimulateFeeComponents:
    """Tests for distinct monthly and annual fee components."""

    def test_simulate_when_first_month_expect_full_annual_fixed_fee(self) -> None:
        """Charge the complete annual fee with the first payment."""
        # Arrange
        terms = _annual_fee_terms()

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        assert result.payments[0].annual_fixed_fee == Decimal("600")

    def test_simulate_when_weighted_insurance_selected_expect_adjacent_period_weighting(self) -> None:
        """Use adjacent opening balances and payment intervals for insurance."""
        # Arrange
        terms = default_mortgage_terms(
            first_payment_date=date(2025, 1, 1),
            fees=non_zero_synthetic_fee_terms(),
        )
        previous_opening_balance = terms.principal
        opening_balance = terms.principal - terms.principal / Decimal(terms.contractual_term_months)
        previous_period_days = 31
        current_period_days = 31

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        expected_insured_balance = (
            previous_opening_balance * Decimal(current_period_days) + opening_balance * Decimal(previous_period_days)
        ) / Decimal(previous_period_days + current_period_days)
        assert result.payments[1].monthly_insurance == expected_insured_balance * terms.fees.monthly_insurance_rate

    def test_simulate_when_opening_insurance_selected_expect_current_opening_balance(self) -> None:
        """Preserve the original opening-balance insurance strategy."""
        # Arrange
        fees = non_zero_synthetic_fee_terms(insurance_calculation_method=InsuranceCalculationMethod.OPENING_BALANCE)
        terms = default_mortgage_terms(fees=fees)

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        payment = result.payments[1]
        assert payment.monthly_insurance == payment.opening_balance * terms.fees.monthly_insurance_rate

    def test_simulate_when_first_month_overpaid_expect_second_month_insurance_reduced(self) -> None:
        """Apply an overpayment's lower balance to insurance from the following month."""
        # Arrange
        terms = default_mortgage_terms(fees=non_zero_synthetic_fee_terms())
        baseline = OverpaymentScenario(name="Baseline")
        overpayment = OverpaymentScenario(
            name="Overpayment",
            recurring_amount=Decimal("1000"),
            recurring_start_month=1,
        )

        # Act
        baseline_result = simulate(terms, baseline)
        overpayment_result = simulate(terms, overpayment)

        # Assert
        assert overpayment_result.payments[0].monthly_insurance == baseline_result.payments[0].monthly_insurance
        assert overpayment_result.payments[1].monthly_insurance < baseline_result.payments[1].monthly_insurance

    def test_simulate_when_second_month_expect_no_annual_fixed_fee(self) -> None:
        """Do not charge the annual fee outside its anniversary month."""
        # Arrange
        terms = _annual_fee_terms()

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        assert result.payments[1].annual_fixed_fee == Decimal("0")

    def test_simulate_when_thirteenth_month_expect_full_annual_fixed_fee(self) -> None:
        """Charge the full annual fee on the first loan anniversary."""
        # Arrange
        terms = _annual_fee_terms()

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        assert result.payments[12].annual_fixed_fee == Decimal("600")

    def test_simulate_when_fee_components_calculated_expect_their_sum_as_fees(self) -> None:
        """Retain aggregate fees as the sum of its explicit components."""
        # Arrange
        terms = _annual_fee_terms()

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        for payment in (result.payments[0], result.payments[1], result.payments[12]):
            assert payment.fees == (payment.monthly_insurance + payment.monthly_fixed_fees + payment.annual_fixed_fee)

    def test_simulate_when_monthly_fees_end_expect_annual_fixed_fee_to_continue(self) -> None:
        """Apply annual fees after the inclusive monthly-fee end month."""
        # Arrange
        terms = _annual_fee_terms()

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        payment = result.payments[12]
        assert payment.monthly_insurance == Decimal("0")
        assert payment.monthly_fixed_fees == Decimal("0")
        assert payment.annual_fixed_fee == Decimal("600")


class TestSimulateOverpayment:
    """Tests for recurring, lump-sum, and payoff behavior."""

    def test_simulate_when_synthetic_scenario_expect_month_25_overpayment(self) -> None:
        """Apply both recurring and lump-sum principal in month 25."""
        # Arrange
        terms = _synthetic_terms()
        scenario = synthetic_overpayment_scenario()

        # Act
        result = simulate(terms, scenario)

        # Assert
        payment = result.payments[24]
        assert payment.recurring_overpayment == Decimal("1000")
        assert payment.lump_sum == Decimal("12000")
        assert payment.closing_balance == Decimal("452277.7777777777777777777775")

    def test_simulate_when_principal_components_exceed_balance_expect_ordered_cap(self) -> None:
        """Cap scheduled, recurring, then lump-sum principal and stop at payoff."""
        # Arrange
        terms = _zero_cost_terms()
        scenario = OverpaymentScenario(
            name="Immediate payoff",
            recurring_amount=Decimal("100"),
            recurring_start_month=1,
            lump_sums=(LumpSum(month=1, amount=Decimal("100")),),
        )

        # Act
        result = simulate(terms, scenario)

        # Assert
        assert len(result.payments) == 1
        payment = result.payments[0]
        assert payment.scheduled_principal == Decimal("10")
        assert payment.recurring_overpayment == Decimal("90")
        assert payment.lump_sum == Decimal("0")
        assert payment.closing_balance == Decimal("0")
        assert result.summary.payoff_month == 1

    def test_simulate_when_overpayment_exceeds_final_balance_expect_no_negative_balance(self) -> None:
        """Cap the final recurring payment instead of producing a negative balance."""
        # Arrange
        terms = _synthetic_terms()
        scenario = OverpaymentScenario(
            name="Capped payoff",
            recurring_amount=Decimal("10000"),
            recurring_start_month=25,
            lump_sums=(LumpSum(month=25, amount=Decimal("12000")),),
        )

        # Act
        result = simulate(terms, scenario)

        # Assert
        assert result.summary.ending_balance == Decimal("0")
        assert result.summary.payoff_month == 64
        assert result.payments[-1].recurring_overpayment == Decimal("9111.111111111111111111110481")
        assert all(payment.closing_balance >= Decimal("0") for payment in result.payments)


class TestSimulateCashOutflowTarget:
    """Tests for recurring overpayments derived from a cash-outflow target."""

    def test_simulate_when_target_active_expect_varying_recurring_overpayments(self) -> None:
        """Adjust principal overpayment as the month's net interest changes."""
        # Arrange
        terms = _cash_outflow_target_terms()
        scenario = OverpaymentScenario(
            name="Constant outflow",
            cash_outflow_target=Decimal("200"),
            recurring_start_month=1,
        )

        # Act
        result = simulate(terms, scenario)

        # Assert
        assert result.payments[0].recurring_overpayment == Decimal("88")
        assert result.payments[1].recurring_overpayment == Decimal("89.88")
        assert result.payments[0].cash_outflow == Decimal("200")
        assert result.payments[1].cash_outflow == Decimal("200.00")

    def test_simulate_when_subsidy_disabled_expect_less_target_overpayment(self) -> None:
        """Use more of a fixed cash-outflow target for gross interest when subsidy is absent."""
        # Arrange
        base_terms = _cash_outflow_target_terms()
        enabled_terms = base_terms.model_copy(
            update={"subsidy": default_subsidy_terms(coefficient=Decimal("0.06"), reference_rate=Decimal("0"))}
        )
        disabled_terms = base_terms.model_copy(
            update={
                "subsidy": SubsidyTerms(
                    enabled=False,
                    coefficient=Decimal("0.06"),
                    second_coefficient=Decimal("0.06"),
                    reference_rate=Decimal("0"),
                )
            }
        )
        scenario = OverpaymentScenario(
            name="Constant outflow",
            cash_outflow_target=Decimal("200"),
            recurring_start_month=1,
        )

        # Act
        enabled_payment = simulate(enabled_terms, scenario).payments[0]
        disabled_payment = simulate(disabled_terms, scenario).payments[0]

        # Assert
        assert enabled_payment.recurring_overpayment == Decimal("94")
        assert disabled_payment.recurring_overpayment == Decimal("88")
        assert enabled_payment.cash_outflow == Decimal("200")
        assert disabled_payment.cash_outflow == Decimal("200")

    def test_simulate_when_target_starts_later_expect_inclusive_start_month(self) -> None:
        """Begin target-derived overpayments in the configured start month."""
        # Arrange
        terms = _cash_outflow_target_terms()
        scenario = OverpaymentScenario(
            name="Delayed target",
            cash_outflow_target=Decimal("200"),
            recurring_start_month=2,
        )

        # Act
        result = simulate(terms, scenario)

        # Assert
        assert result.payments[0].recurring_overpayment == Decimal("0")
        assert result.payments[1].recurring_overpayment == Decimal("89")
        assert result.payments[1].cash_outflow == Decimal("200")

    def test_simulate_when_target_is_below_base_outflow_expect_no_overpayment(self) -> None:
        """Allow scheduled costs to exceed a low target without negative principal."""
        # Arrange
        terms = _cash_outflow_target_terms()
        scenario = OverpaymentScenario(
            name="Low target",
            cash_outflow_target=Decimal("50"),
            recurring_start_month=1,
        )

        # Act
        result = simulate(terms, scenario)

        # Assert
        assert result.payments[0].recurring_overpayment == Decimal("0")
        assert result.payments[0].cash_outflow == Decimal("112")

    def test_simulate_when_fees_apply_expect_target_to_include_all_fees(self) -> None:
        """Subtract monthly and annual fees when deriving target overpayment."""
        # Arrange
        terms = _cash_outflow_target_terms(
            fees=default_fee_terms(
                annual_fixed_fee=Decimal("5"),
                monthly_insurance_rate=Decimal("0"),
                monthly_fixed_fees=Decimal("15"),
            )
        )
        scenario = OverpaymentScenario(
            name="Target with fees",
            cash_outflow_target=Decimal("200"),
            recurring_start_month=1,
        )

        # Act
        result = simulate(terms, scenario)

        # Assert
        assert result.payments[0].fees == Decimal("20")
        assert result.payments[0].recurring_overpayment == Decimal("68")
        assert result.payments[0].cash_outflow == Decimal("200")

    def test_simulate_when_lump_sum_applies_expect_it_outside_target(self) -> None:
        """Add lump-sum principal after the target-derived overpayment."""
        # Arrange
        terms = _cash_outflow_target_terms()
        scenario = OverpaymentScenario(
            name="Target and lump sum",
            cash_outflow_target=Decimal("200"),
            recurring_start_month=1,
            lump_sums=(LumpSum(month=1, amount=Decimal("50")),),
        )

        # Act
        result = simulate(terms, scenario)

        # Assert
        assert result.payments[0].recurring_overpayment == Decimal("88")
        assert result.payments[0].lump_sum == Decimal("50")
        assert result.payments[0].cash_outflow == Decimal("250")

    def test_simulate_when_target_exceeds_payoff_expect_remaining_balance_cap(self) -> None:
        """Cap a target-derived overpayment at the balance remaining after scheduled principal."""
        # Arrange
        terms = _zero_cost_terms()
        scenario = OverpaymentScenario(
            name="Target payoff",
            cash_outflow_target=Decimal("200"),
            recurring_start_month=1,
        )

        # Act
        result = simulate(terms, scenario)

        # Assert
        assert len(result.payments) == 1
        assert result.payments[0].recurring_overpayment == Decimal("90")
        assert result.payments[0].cash_outflow == Decimal("100")

    def test_simulate_when_horizon_settlement_applies_expect_it_outside_target(self) -> None:
        """Add final balance settlement after the target-derived overpayment."""
        # Arrange
        terms = _short_horizon_terms(settle_remaining_principal_at_horizon=True)
        scenario = OverpaymentScenario(
            name="Target and settlement",
            cash_outflow_target=Decimal("20"),
            recurring_start_month=1,
        )

        # Act
        result = simulate(terms, scenario)

        # Assert
        final_payment = result.payments[-1]
        assert final_payment.recurring_overpayment == Decimal("10")
        assert final_payment.horizon_settlement == Decimal("60")
        assert final_payment.cash_outflow == Decimal("80")


class TestHorizonSettlement:
    """Tests for automatic repayment of principal remaining at the horizon."""

    def test_simulate_when_settlement_enabled_expect_remaining_principal_in_final_payment(self) -> None:
        """Settle the balance left after the final regular principal payment."""
        # Arrange
        terms = _short_horizon_terms(settle_remaining_principal_at_horizon=True)

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        final_payment = result.payments[-1]
        assert final_payment.scheduled_principal == Decimal("10")
        assert final_payment.horizon_settlement == Decimal("80")
        assert final_payment.closing_balance == Decimal("0")
        assert result.summary.principal_repaid_before_horizon_settlement == Decimal("20")
        assert result.summary.horizon_settlement == Decimal("80")
        assert result.summary.total_principal == Decimal("100")
        assert result.summary.payoff_month == 2

    def test_simulate_when_final_month_has_lump_sum_expect_settlement_applied_after_it(self) -> None:
        """Reduce the automatic settlement by final-month user principal payments."""
        # Arrange
        terms = _short_horizon_terms(settle_remaining_principal_at_horizon=True)
        scenario = OverpaymentScenario(
            name="Final lump sum",
            lump_sums=(LumpSum(month=2, amount=Decimal("30")),),
        )

        # Act
        result = simulate(terms, scenario)

        # Assert
        final_payment = result.payments[-1]
        assert final_payment.lump_sum == Decimal("30")
        assert final_payment.horizon_settlement == Decimal("50")
        assert result.summary.principal_repaid_before_horizon_settlement == Decimal("50")

    def test_simulate_when_settlement_disabled_expect_remaining_balance_after_horizon(self) -> None:
        """Preserve partial-horizon behavior when settlement is disabled."""
        # Arrange
        terms = _short_horizon_terms(settle_remaining_principal_at_horizon=False)

        # Act
        result = simulate(terms, OverpaymentScenario(name="Baseline"))

        # Assert
        assert result.payments[-1].horizon_settlement == Decimal("0")
        assert result.summary.principal_repaid_before_horizon_settlement == Decimal("20")
        assert result.summary.horizon_settlement == Decimal("0")
        assert result.summary.total_principal == Decimal("20")
        assert result.summary.ending_balance == Decimal("80")
        assert result.summary.payoff_month is None


class TestInterestCalculation:
    """Tests for selectable period-interest calculations."""

    def test_simulate_when_calendar_period_crosses_new_year_expect_split_denominators(self) -> None:
        """Accrue each year segment with its own actual calendar-year denominator."""
        # Arrange
        terms = _single_period_terms(
            first_payment_date=date(2024, 1, 10),
            principal=Decimal("12000"),
            method=InterestCalculationMethod.CALENDAR_DAYS,
        )

        # Act
        result = simulate(terms, OverpaymentScenario(name="Calendar days"))

        # Assert
        expected_interest = (
            Decimal("12000") * Decimal("0.12") * (Decimal("22") / Decimal("365") + Decimal("9") / Decimal("366"))
        )
        assert result.payments[0].interest == expected_interest

    def test_simulate_when_equal_months_selected_expect_one_twelfth_interest(self) -> None:
        """Apply one twelfth of the annual rate for equal-month interest."""
        # Arrange
        terms = _single_period_terms(
            first_payment_date=date(2024, 2, 15),
            principal=Decimal("1200"),
            method=InterestCalculationMethod.EQUAL_MONTHS,
        )

        # Act
        result = simulate(terms, OverpaymentScenario(name="Equal months"))

        # Assert
        assert result.payments[0].interest == Decimal("12")

    def test_simulate_when_calendar_days_selected_expect_day_weighted_net_rate(self) -> None:
        """Annualize net interest using the same calendar-day balance exposure."""
        # Arrange
        terms = _single_period_terms(
            first_payment_date=date(2024, 2, 15),
            principal=Decimal("36600"),
            method=InterestCalculationMethod.CALENDAR_DAYS,
        )

        # Act
        result = simulate(terms, OverpaymentScenario(name="Calendar days"))

        # Assert
        assert result.summary.net_average_annual_interest_rate == Decimal("0.12")


def _zero_cost_terms() -> MortgageTerms:
    return default_mortgage_terms(
        principal=Decimal("100"),
        contractual_term_months=10,
        analysis_horizon_months=10,
        rate_periods=(RatePeriod(start_month=1, end_month=10, annual_rate=Decimal("0")),),
        subsidy=default_subsidy_terms(coefficient=Decimal("0"), reference_rate=Decimal("0")),
        fees=default_fee_terms(
            annual_fixed_fee=Decimal("0"),
            monthly_insurance_rate=Decimal("0"),
            monthly_fixed_fees=Decimal("0"),
            insurance_end_month=0,
        ),
    )


def _annual_fee_terms() -> MortgageTerms:
    return default_mortgage_terms(
        analysis_horizon_months=13,
        fees=non_zero_synthetic_fee_terms(insurance_end_month=1),
    )


def _cash_outflow_target_terms(*, fees: FeeTerms | None = None) -> MortgageTerms:
    return default_mortgage_terms(
        interest_calculation_method=InterestCalculationMethod.EQUAL_MONTHS,
        principal=Decimal("1200"),
        contractual_term_months=12,
        analysis_horizon_months=3,
        settle_remaining_principal_at_horizon=False,
        rate_periods=(RatePeriod(start_month=1, end_month=3, annual_rate=Decimal("0.12")),),
        subsidy=default_subsidy_terms(coefficient=Decimal("0"), reference_rate=Decimal("0")),
        fees=fees
        or default_fee_terms(
            annual_fixed_fee=Decimal("0"),
            monthly_insurance_rate=Decimal("0"),
            monthly_fixed_fees=Decimal("0"),
            insurance_end_month=0,
        ),
    )


def _synthetic_terms() -> MortgageTerms:
    return synthetic_terms(interest_calculation_method=InterestCalculationMethod.EQUAL_MONTHS)


def _short_horizon_terms(*, settle_remaining_principal_at_horizon: bool) -> MortgageTerms:
    return default_mortgage_terms(
        principal=Decimal("100"),
        contractual_term_months=10,
        analysis_horizon_months=2,
        settle_remaining_principal_at_horizon=settle_remaining_principal_at_horizon,
        rate_periods=(RatePeriod(start_month=1, end_month=2, annual_rate=Decimal("0")),),
        subsidy=default_subsidy_terms(coefficient=Decimal("0"), reference_rate=Decimal("0")),
        fees=default_fee_terms(
            annual_fixed_fee=Decimal("0"),
            monthly_insurance_rate=Decimal("0"),
            monthly_fixed_fees=Decimal("0"),
            insurance_end_month=0,
        ),
    )


def _single_period_terms(
    first_payment_date: date,
    principal: Decimal,
    method: InterestCalculationMethod,
) -> MortgageTerms:
    return default_mortgage_terms(
        first_payment_date=first_payment_date,
        interest_calculation_method=method,
        principal=principal,
        contractual_term_months=12,
        analysis_horizon_months=1,
        rate_periods=(RatePeriod(start_month=1, end_month=1, annual_rate=Decimal("0.12")),),
        subsidy=default_subsidy_terms(coefficient=Decimal("0"), reference_rate=Decimal("0")),
        fees=default_fee_terms(
            annual_fixed_fee=Decimal("0"),
            monthly_insurance_rate=Decimal("0"),
            monthly_fixed_fees=Decimal("0"),
            insurance_end_month=0,
        ),
    )
