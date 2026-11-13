"""Formatting and native Streamlit presentation for simulation results."""

from decimal import Decimal

import streamlit as st

from mortgage_simulator.simulation.models import ScenarioComparison

NET_FINANCING_COST_HELP = (
    "Net financing cost = Total mortgage cost - Net investment earnings. Lower is better. "
    "This is the automatic timing objective; principal repayments are excluded. "
    "A negative value means deposit earnings exceed mortgage charges. "
    "Earnings may already have repaid mortgage principal; they are not necessarily cash left in your account."
)
MORTGAGE_COST_HELP = (
    "Total mortgage cost = Gross mortgage interest - Subsidy received + Fees paid. "
    "Principal repays borrowed capital and is excluded from financing charges. Deposit earnings are excluded here."
)
INVESTMENT_EARNINGS_HELP = (
    "Net investment earnings = Gross deposit interest - Deposit tax. "
    "Included in the repayment balance or retained funds; deducted once in Net financing cost."
)
MORTGAGE_PAYMENTS_HELP = (
    "Total mortgage payments = Principal repaid + Gross mortgage interest - Subsidy received + Fees paid. "
    "Includes deposit-funded repayments; this is not your personal cash contribution or overall financial benefit."
)
RETAINED_SURPLUS_HELP = (
    "Retained surplus = Final deposit balance - Applied to mortgage. May include original capital and earnings; "
    "do not subtract it again from Net financing cost."
)


def pln(value: Decimal) -> str:
    """Format a complete PLN amount.

    Args:
        value: Financial amount to format.

    Returns:
        Amount with thousands separators, two decimals, and currency.
    """
    return f"{value:,.2f} PLN"


def payoff_label(month: int | None) -> str:
    """Format payoff timing within the analysis horizon.

    Args:
        month: Payoff month, or none when balance remains.

    Returns:
        Human-readable payoff status.
    """
    return f"Month {month}" if month is not None else "After horizon"


def percentage(value: Decimal) -> str:
    """Format a decimal ratio as a percentage.

    Args:
        value: Ratio where one represents 100 percent.

    Returns:
        Percentage with two decimal places.
    """
    return f"{value * Decimal('100'):,.2f}%"


def percentage_or_na(value: Decimal | None) -> str:
    """Format an optional decimal ratio as a percentage.

    Args:
        value: Ratio where one represents 100 percent, or none when undefined.

    Returns:
        Percentage with two decimal places or an unavailable label.
    """
    return percentage(value) if value is not None else "N/A"


def percentage_points(value: Decimal) -> str:
    """Format a percentage-point difference.

    Args:
        value: Difference already expressed in percentage points.

    Returns:
        Difference with two decimal places and the percentage-point unit.
    """
    return f"{value:,.2f} p.p."


def interest_saved(selected: ScenarioComparison) -> Decimal:
    """Return interest reduction relative to Baseline.

    Args:
        selected: Scenario comparison containing the Baseline delta.

    Returns:
        Positive amount when the selected scenario reduces interest.
    """
    return -selected.interest_delta


def net_financing_cost_saved(selected: ScenarioComparison) -> Decimal:
    """Return net financing cost reduction relative to Baseline.

    Args:
        selected: Scenario comparison containing the Baseline delta.

    Returns:
        Positive amount when the selected scenario reduces net financing cost.
    """
    return -selected.net_financing_cost_delta


def balance_reduction(selected: ScenarioComparison) -> Decimal:
    """Return ending-balance reduction relative to Baseline.

    Args:
        selected: Scenario comparison containing the Baseline delta.

    Returns:
        Positive amount when the selected scenario reduces ending balance.
    """
    return -selected.ending_balance_delta


def additional_cash_paid(selected: ScenarioComparison) -> Decimal:
    """Return additional cash paid relative to Baseline.

    Args:
        selected: Scenario comparison containing the Baseline delta.

    Returns:
        Positive amount when the selected scenario uses additional cash.
    """
    return selected.cash_outflow_delta


def settlement_reduction(selected: ScenarioComparison) -> Decimal:
    """Return terminal-settlement reduction relative to Baseline.

    Args:
        selected: Scenario comparison containing the Baseline delta.

    Returns:
        Positive amount when the selected scenario needs a smaller settlement.
    """
    return -selected.horizon_settlement_delta


def render_decision_highlights(selected: ScenarioComparison, *, include_subsidy: bool = True) -> None:
    """Render Baseline-relative decision metrics in two rows.

    Args:
        selected: Scenario comparison to present.
        include_subsidy: Whether to render subsidy-specific values and labels.
    """
    first_row = st.columns(4)
    first_row[0].metric(
        "Net financing cost saved",
        pln(net_financing_cost_saved(selected)),
        help=(
            "Baseline Net financing cost - This scenario's Net financing cost. "
            "Positive means lower combined cost after deposit earnings. "
            "Net financing cost = Total mortgage cost - Net investment earnings."
        ),
        border=True,
    )
    first_row[1].metric(
        "Balance reduced",
        pln(balance_reduction(selected)),
        help=(
            "Baseline ending balance minus this scenario's ending balance. "
            "It is the additional principal eliminated by the analysis horizon."
        ),
        border=True,
    )
    first_row[2].metric(
        "Additional mortgage payments",
        pln(additional_cash_paid(selected)),
        help=(
            "This scenario's Total mortgage payments minus Baseline Total mortgage payments. "
            + (
                "It includes additional principal and changes in interest, subsidy, and fees."
                if include_subsidy
                else "It includes additional principal and changes in interest and fees."
            )
        ),
        border=True,
    )
    first_row[3].metric("Payoff timing", payoff_label(selected.summary.payoff_month), border=True)

    second_row = st.columns(4 if include_subsidy else 3)
    second_row[0].metric("Interest saved", pln(interest_saved(selected)), border=True)
    rate_column_index = 2 if include_subsidy else 1
    savings_column_index = 3 if include_subsidy else 2
    if include_subsidy:
        second_row[1].metric(
            "Subsidy difference",
            pln(selected.subsidy_delta),
            help="This scenario's subsidy received minus Baseline subsidy received.",
            border=True,
        )
    second_row[rate_column_index].metric(
        f"{_average_rate_label(include_subsidy)} difference",
        percentage_points(selected.net_average_annual_interest_rate_percentage_point_delta),
        help=(f"This scenario's {_average_rate_label(include_subsidy).lower()} minus Baseline, in percentage points."),
        border=True,
    )
    second_row[savings_column_index].metric(
        "Overpayment savings rate",
        percentage_or_na(selected.mortgage_cost_savings_to_overpayment_ratio),
        help=(
            "Baseline total mortgage cost minus this scenario's total mortgage cost, divided by recurring and lump-sum "
            "overpayments actually applied during the analysis horizon. Terminal horizon settlement is excluded."
        ),
        border=True,
    )


def render_cost_indicators(selected: ScenarioComparison, *, include_subsidy: bool = True) -> None:
    """Render selected-scenario cost ratios for the analysis horizon.

    Args:
        selected: Scenario comparison to present.
        include_subsidy: Whether average interest is net of subsidy.
    """
    summary = selected.summary
    with st.container(horizontal=True, vertical_alignment="center"):
        with st.container(border=True):
            st.badge("Primary decision metric", icon=":material/flag:", color="blue")
            st.metric("Net financing cost", pln(selected.net_financing_cost), help=NET_FINANCING_COST_HELP)
            st.caption("Lower is better · Total mortgage cost - Net investment earnings")
        st.metric("Total mortgage cost", pln(summary.total_mortgage_cost), help=MORTGAGE_COST_HELP)
        st.metric("Net investment earnings", pln(selected.net_investment_earnings), help=INVESTMENT_EARNINGS_HELP)
    columns = st.columns(3)
    columns[0].metric(
        "Cost / original principal",
        percentage(summary.mortgage_cost_to_original_principal),
        help="Total mortgage cost divided by the original mortgage principal for the analysis horizon.",
        border=True,
    )
    columns[1].metric(
        "Cost / principal repaid",
        percentage(summary.mortgage_cost_to_principal_repaid),
        help="Total mortgage cost divided by principal repaid during the analysis horizon.",
        border=True,
    )
    columns[2].metric(
        _average_rate_label(include_subsidy),
        percentage(summary.net_average_annual_interest_rate),
        help=(
            "Balance-weighted annual interest after subsidy; fees are excluded."
            if include_subsidy
            else "Balance-weighted gross annual interest; fees are excluded."
        ),
        border=True,
    )


def render_horizon_settlement(selected: ScenarioComparison) -> None:
    """Render selected-scenario horizon-settlement indicators.

    Args:
        selected: Scenario comparison to present.
    """
    summary = selected.summary
    columns = st.columns(4)
    columns[0].metric(
        "Principal repaid before settlement",
        pln(summary.principal_repaid_before_horizon_settlement),
        border=True,
    )
    columns[1].metric("Terminal settlement", pln(summary.horizon_settlement), border=True)
    columns[2].metric(
        "Principal deferred to settlement",
        percentage(summary.horizon_settlement / summary.total_principal),
        border=True,
    )
    columns[3].metric(
        "Settlement reduction vs Baseline",
        pln(settlement_reduction(selected)),
        help="Baseline terminal settlement minus this scenario's terminal settlement.",
        border=True,
    )


def render_raw_totals(selected: ScenarioComparison, *, include_subsidy: bool = True) -> None:
    """Render the selected scenario's eight absolute totals.

    Args:
        selected: Scenario comparison to present.
        include_subsidy: Whether to render subsidy-specific totals and descriptions.
    """
    summary = selected.summary
    first_row = st.columns(4)
    first_row[0].metric(
        "Total mortgage payments",
        pln(summary.total_cash_outflow),
        help=MORTGAGE_PAYMENTS_HELP,
        border=True,
    )
    first_row[1].metric("Principal repaid", pln(summary.total_principal), border=True)
    first_row[2].metric(
        "Total mortgage cost",
        pln(summary.total_mortgage_cost),
        help=MORTGAGE_COST_HELP,
        border=True,
    )
    first_row[3].metric("Ending balance", pln(summary.ending_balance), border=True)

    second_row = st.columns(4 if include_subsidy else 3)
    second_row[0].metric("Gross mortgage interest", pln(summary.total_interest), border=True)
    second_row[1].metric("Fees paid", pln(summary.total_fees), border=True)
    payoff_column_index = 3 if include_subsidy else 2
    if include_subsidy:
        second_row[2].metric("Subsidy received", pln(summary.total_subsidy), border=True)
    second_row[payoff_column_index].metric("Payoff month", payoff_label(summary.payoff_month), border=True)


def _average_rate_label(include_subsidy: bool) -> str:
    return "Net average annual interest rate" if include_subsidy else "Average annual interest rate"
