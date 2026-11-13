"""Compare every simulated mortgage scenario."""

import streamlit as st

from mortgage_simulator.app.presentation.chart_controls import typical_payments_toggle
from mortgage_simulator.app.presentation.result_tables import comparison_table_frame
from mortgage_simulator.app.session_state import get_results, get_terms
from mortgage_simulator.reporting.mortgage_charts import balance_chart, cash_outflow_chart
from mortgage_simulator.reporting.payment_schedules import schedule_csv, schedule_frame
from mortgage_simulator.reporting.scenario_comparison import compare

results = get_results()
st.title("Comparison")
st.caption("Compare every simulated scenario with the no-overpayment Baseline.")

if results is None:
    st.info("Run a simulation to compare your scenarios.", icon=":material/info:")
    if st.button("Go to scenarios", icon=":material/arrow_back:"):
        st.switch_page("app_pages/overpayment_scenarios.py")
    st.stop()

terms = get_terms()
include_subsidy = terms.subsidy.enabled
schedule = schedule_frame(results, include_subsidy=include_subsidy)
st.subheader("Remaining principal")
st.altair_chart(balance_chart(schedule), width="stretch")
st.subheader("Monthly cash outflow")
focus_on_typical_payments = typical_payments_toggle()
st.altair_chart(
    cash_outflow_chart(schedule, focus_on_typical_payments=focus_on_typical_payments),
    width="stretch",
)
st.subheader("Scenario totals and differences")
st.caption(
    "Net financing cost = Total mortgage cost - Net investment earnings. Lower is better; "
    "differences are scenario minus Baseline."
)
st.caption(
    "Total mortgage cost = Gross mortgage interest - Subsidy received + Fees paid. Total "
    "mortgage payments add Principal repaid and include deposit-funded payments, not just "
    "your own contributions."
)
st.caption(
    "Net investment earnings = Gross deposit interest - Deposit tax. Earnings are counted once in Net financing cost."
)
st.caption(
    "Retained surplus = Final deposit balance - Applied to mortgage. It includes capital "
    "and earnings; do not deduct it again from Net financing cost."
)
st.dataframe(
    comparison_table_frame(
        compare(results),
        show_ending_balance=not terms.settle_remaining_principal_at_horizon,
        include_subsidy=include_subsidy,
    ),
    hide_index=True,
    width="stretch",
)
st.download_button(
    "Download combined CSV",
    data=schedule_csv(results, include_subsidy=include_subsidy),
    file_name="mortgage-scenarios.csv",
    mime="text/csv",
    icon=":material/download:",
)
