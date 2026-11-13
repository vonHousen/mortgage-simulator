"""Present the selected mortgage scenario."""

import polars as pl
import streamlit as st

from mortgage_simulator.app.presentation.chart_controls import typical_payments_toggle
from mortgage_simulator.app.presentation.investment_results import render_investment_results
from mortgage_simulator.app.presentation.result_metrics import (
    render_cost_indicators,
    render_decision_highlights,
    render_horizon_settlement,
    render_raw_totals,
)
from mortgage_simulator.app.presentation.result_tables import SCHEDULE_COLUMN_CONFIG, schedule_columns
from mortgage_simulator.app.session_state import get_results, get_terms
from mortgage_simulator.reporting.mortgage_charts import balance_chart, cash_outflow_chart, payment_composition_chart
from mortgage_simulator.reporting.payment_schedules import schedule_frame
from mortgage_simulator.reporting.scenario_comparison import compare

results = get_results()
st.title("Results")
st.caption("Compare each overpayment strategy with the no-overpayment Baseline.")

if results is None:
    st.info("Run a simulation to compare your scenarios.", icon=":material/info:")
    if st.button("Go to scenarios", icon=":material/arrow_back:"):
        st.switch_page("app_pages/overpayment_scenarios.py")
    st.stop()

report = compare(results)
terms = get_terms()
with st.container(border=True):
    st.subheader(":material/compare_arrows: Viewing scenario", anchor=False)
    selected_name = st.selectbox(
        "Scenario",
        [scenario.scenario_name for scenario in report.scenarios],
        index=1 if len(report.scenarios) > 1 else 0,
        help="Choose the scenario shown in every metric, chart, and table below. Differences use the Baseline.",
    )
    st.caption("Changing this selection updates all results below. Baseline remains the comparison reference.")
selected = next(scenario for scenario in report.scenarios if scenario.scenario_name == selected_name)
include_subsidy = terms.subsidy.enabled

render_investment_results(next(result for result in results if result.scenario_name == selected_name))

with st.expander("Raw totals", expanded=False):
    render_raw_totals(selected, include_subsidy=include_subsidy)
if terms.settle_remaining_principal_at_horizon:
    with st.expander("Horizon settlement", expanded=False):
        st.caption(
            "Every scenario repays the full original principal. Ending balances and horizon payoff timing therefore "
            "converge, and cash-outflow differences equal mortgage-cost differences."
        )
        render_horizon_settlement(selected)
with st.expander("Cost indicators", expanded=True):
    render_cost_indicators(selected, include_subsidy=include_subsidy)
with st.expander("Difference from Baseline", expanded=True):
    render_decision_highlights(selected, include_subsidy=include_subsidy)

schedule = schedule_frame(results, include_subsidy=include_subsidy)
selected_schedule = schedule.filter(pl.col("scenario") == selected_name)
with st.expander("Remaining principal", expanded=True):
    st.altair_chart(balance_chart(selected_schedule, filled=True), width="stretch")
with st.expander("Monthly cash outflow", expanded=False):
    show_terminal_payment = False
    if terms.settle_remaining_principal_at_horizon:
        show_terminal_payment = st.toggle("Show terminal payment")
    focus_on_typical_payments = typical_payments_toggle()
    st.altair_chart(
        cash_outflow_chart(
            selected_schedule,
            filled=True,
            show_terminal_payment=show_terminal_payment,
            focus_on_typical_payments=focus_on_typical_payments,
        ),
        width="stretch",
    )
with st.expander("Payment composition", expanded=True):
    show_after_subsidy = False
    if include_subsidy:
        show_after_subsidy = st.toggle("Show interest after subsidy")
    st.altair_chart(
        payment_composition_chart(
            selected_schedule,
            selected_name,
            after_subsidy=show_after_subsidy,
            show_terminal_payment=show_terminal_payment,
            include_subsidy=include_subsidy,
            focus_on_typical_payments=focus_on_typical_payments,
        ),
        width="stretch",
    )

with st.expander("Monthly schedule", expanded=False):
    fees_column, overpayments_column = st.columns(2)
    with fees_column:
        split_fees = st.toggle("Split fees")
    with overpayments_column:
        split_overpayments = st.toggle("Split overpayments")
    st.dataframe(
        selected_schedule.select(
            schedule_columns(
                split_fees=split_fees,
                split_overpayments=split_overpayments,
                include_subsidy=include_subsidy,
            )
        ),
        column_config=SCHEDULE_COLUMN_CONFIG,
        hide_index=True,
        width="stretch",
    )
