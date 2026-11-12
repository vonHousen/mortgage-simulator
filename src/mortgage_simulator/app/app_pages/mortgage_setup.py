"""Mortgage setup page."""

from decimal import Decimal, InvalidOperation

import streamlit as st
from pydantic import ValidationError

from mortgage_simulator.app.session_state import TERMS_KEY, clear_results, get_terms
from mortgage_simulator.app.simulation_inputs import MortgageInputs, build_terms
from mortgage_simulator.simulation.models import InsuranceCalculationMethod, InterestCalculationMethod

PERCENT = Decimal("100")
INTEREST_CALCULATION_LABELS = {
    InterestCalculationMethod.CALENDAR_DAYS: "Calendar days",
    InterestCalculationMethod.EQUAL_MONTHS: "Equal months (1/12)",
}
INSURANCE_CALCULATION_LABELS = {
    InsuranceCalculationMethod.OPENING_BALANCE: "Opening balance",
    InsuranceCalculationMethod.MIDPOINT_BALANCE: "Midpoint balance",
    InsuranceCalculationMethod.TWO_INTERVAL_WEIGHTED: "Two-interval weighted",
}
SETUP_ROW_STYLES = """
<style>
@media (max-width: 1100px) {
    .st-key-setup-sections {
        flex-direction: column !important;
    }
}
</style>
"""

terms = get_terms()

st.title("Mortgage setup")
st.caption("Configure the mortgage terms shared by every overpayment scenario.")

st.html(SETUP_ROW_STYLES)
setup_row = st.container(horizontal=True, key="setup-sections")
left_group = setup_row.container(height="stretch")
loan_details = left_group.container(border=True)
timeline = left_group.container(border=True)
interest_rates = setup_row.container(border=True, height="stretch")

with loan_details:
    st.subheader("Loan details")
    principal_column, term_column = st.columns(2)
    with principal_column:
        principal = st.number_input(
            "Principal (PLN)",
            min_value=1.0,
            value=float(terms.principal),
            step=10000.0,
        )
    with term_column:
        contractual_term_years = st.number_input(
            "Contractual term (years)",
            min_value=1,
            value=terms.contractual_term_months // 12,
        )

with timeline:
    st.subheader("Timeline")
    payment_date_column, horizon_column = st.columns(2)
    with payment_date_column:
        first_payment_date = st.date_input(
            "First payment date",
            value=terms.first_payment_date,
            format="DD/MM/YYYY",
        )
    with horizon_column:
        horizon = st.number_input(
            "Analysis horizon (months)",
            min_value=1,
            max_value=120,
            value=terms.analysis_horizon_months,
        )
        settle_remaining_principal_at_horizon = st.toggle(
            "Settle remaining principal at horizon",
            value=terms.settle_remaining_principal_at_horizon,
            help=(
                "Repay the remaining balance after the final regular horizon payment so every scenario "
                "repays the same principal."
            ),
        )

with interest_rates:
    st.subheader("Interest rates")
    first_rate_column, second_rate_column = st.columns(2)
    with first_rate_column:
        first_rate = st.number_input(
            "Interest, months 1-60 (%)",
            min_value=0.0,
            value=float(terms.rate_periods[0].annual_rate * PERCENT),
            step=0.01,
        )
    with second_rate_column:
        second_rate = st.number_input(
            "Interest, months 61-120 (%)",
            min_value=0.0,
            value=float(terms.rate_periods[1].annual_rate * PERCENT),
            step=0.01,
        )
    interest_calculation_method = st.segmented_control(
        "Interest calculation",
        options=tuple(InterestCalculationMethod),
        default=terms.interest_calculation_method,
        required=True,
        format_func=INTEREST_CALCULATION_LABELS.__getitem__,
        help=("Calendar days accrues interest between consecutive payment dates, splitting periods at New Year."),
    )
    subsidy_enabled = st.toggle(
        "Enable BK2% subsidy",
        value=terms.subsidy.enabled,
        help="Apply the configured BK2% subsidy to monthly mortgage payments.",
    )

subsidy_coefficient = float(terms.subsidy.coefficient * PERCENT)
second_subsidy_coefficient = float(terms.subsidy.second_coefficient * PERCENT)
subsidy_reference = float(terms.subsidy.reference_rate * PERCENT)
if subsidy_enabled:
    with interest_rates.expander("Subsidy assumptions"):
        subsidy_coefficient_column, second_subsidy_coefficient_column = st.columns(2)
        with subsidy_coefficient_column:
            subsidy_coefficient = st.number_input(
                "Subsidy coefficient W, months 1-60 (%)",
                min_value=0.0,
                value=subsidy_coefficient,
                step=0.01,
            )
        with second_subsidy_coefficient_column:
            second_subsidy_coefficient = st.number_input(
                "Subsidy coefficient W, months 61-120 (%)",
                min_value=0.0,
                value=second_subsidy_coefficient,
                help="The 5.5% default is an editable forecast assumption.",
            )
        subsidy_reference = st.number_input(
            "Subsidized reference rate (%)",
            min_value=0.0,
            value=subsidy_reference,
            step=0.01,
        )

with loan_details.expander("Fee assumptions"):
    annual_fee_column, monthly_fees_column = st.columns(2)
    with annual_fee_column:
        annual_fee = st.number_input(
            "Annual fixed fee (PLN)",
            min_value=0.0,
            value=float(terms.fees.annual_fixed_fee),
        )
    with monthly_fees_column:
        monthly_fees = st.number_input(
            "Other monthly fees (PLN)",
            min_value=0.0,
            value=float(terms.fees.monthly_fixed_fees),
        )

    insurance_calculation_method = st.segmented_control(
        "Monthly insurance calculation",
        options=tuple(InsuranceCalculationMethod),
        default=terms.fees.insurance_calculation_method,
        required=True,
        format_func=INSURANCE_CALCULATION_LABELS.__getitem__,
        help=(
            "Two-interval weighted is the best empirical fit to the reviewed charges, not a verified "
            "contractual formula. Calculations use the generated payment schedule dates."
        ),
        width="stretch",
    )

    insurance_rate_column, insurance_end_column = st.columns(2)
    with insurance_rate_column:
        insurance_rate = st.number_input(
            "Monthly insurance rate (%)",
            min_value=0.0,
            value=float(terms.fees.monthly_insurance_rate * PERCENT),
            step=0.001,
            format="%.3f",
        )
    with insurance_end_column:
        insurance_end = st.number_input(
            "Insurance and monthly-fee end month",
            min_value=0,
            max_value=120,
            value=terms.fees.insurance_end_month,
            placeholder="No end month",
            help="Leave empty to apply insurance and other monthly fees throughout the calculated schedule.",
        )

if st.button("Save and continue", type="primary", icon=":material/arrow_forward:"):
    inputs: MortgageInputs = {
        "first_payment_date": first_payment_date,
        "interest_calculation_method": interest_calculation_method,
        "principal": principal,
        "contractual_term_years": contractual_term_years,
        "horizon": horizon,
        "settle_remaining_principal_at_horizon": settle_remaining_principal_at_horizon,
        "first_rate": first_rate,
        "second_rate": second_rate,
        "subsidy_enabled": subsidy_enabled,
        "subsidy_coefficient": subsidy_coefficient,
        "second_subsidy_coefficient": second_subsidy_coefficient,
        "subsidy_reference": subsidy_reference,
        "annual_fee": annual_fee,
        "insurance_rate": insurance_rate,
        "insurance_calculation_method": insurance_calculation_method,
        "monthly_fees": monthly_fees,
        "insurance_end": insurance_end,
    }
    try:
        updated_terms = build_terms(inputs)
    except (InvalidOperation, TypeError, ValueError, ValidationError) as error:
        st.error(f"Invalid mortgage setup: {error}", icon=":material/error:")
    else:
        st.session_state[TERMS_KEY] = updated_terms
        clear_results()
        st.switch_page("app_pages/overpayment_scenarios.py")

with st.expander("Assumptions and limitations", type="compact"):
    st.markdown(
        """
- Calendar-day interest accrues between consecutive payment dates and uses each calendar year's actual day count.
- Equal months (1/12) reproduces the interest behavior of `mortgage-simulation-v2.xlsx`.
- BK2% subsidy calculations can be disabled while preserving the configured coefficient and reference rate.
- Monthly insurance supports opening-balance, midpoint-balance, and best-effort two-interval weighted calculations.
- Insurance calculations use generated payment dates rather than a custom per-installment posting-date schedule.
- The model uses equal-principal payments and stops after month 120 or payoff.
- Horizon settlement is an immediate principal payment after the final regular horizon payment. It does not include an
  early-repayment charge, refinancing cost, inflation, opportunity cost, or funding constraints.
- It does not verify current BK2% law, eligibility, or a specific bank contract.
- Results are estimates for scenario exploration, not financial or legal advice.
"""
    )
