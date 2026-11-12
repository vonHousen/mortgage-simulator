"""Configure overpayment scenarios and run the simulation."""

from decimal import InvalidOperation

import streamlit as st
from pydantic import ValidationError

from mortgage_simulator.app.investment_controls import get_investments, render_investment_controls
from mortgage_simulator.app.session_state import (
    LUMP_SUMS_KEY,
    SCENARIOS_KEY,
    get_lump_sum_data,
    get_scenario_data,
    get_terms,
    store_results,
)
from mortgage_simulator.app.simulation_inputs import build_request, lump_sum_column_config, scenario_column_config
from mortgage_simulator.settings import AppSettings
from mortgage_simulator.simulation.engine import simulate

st.title("Overpayment scenarios")
st.caption("Compare recurring strategies and optional one-off payments with the Baseline.")
terms = get_terms()
interest_label = "net interest" if terms.subsidy.enabled else "gross interest"

with st.container(border=True):
    st.subheader("Recurring strategies")
    st.caption(
        "Choose Fixed overpayment for the same additional principal each month, or Constant cash outflow "
        f"to vary the overpayment so scheduled principal, {interest_label}, and fees reach the target. "
        "Lump sums and horizon settlement are additional outflow. Baseline is included automatically."
    )
    scenario_data = st.data_editor(
        get_scenario_data(),
        column_config=scenario_column_config(terms.analysis_horizon_months),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="scenario_editor",
    )

with st.container(border=True):
    st.subheader("One-off lump sums")
    st.caption("Assign each payment to one of the scenario names above.")
    lump_sum_data = st.data_editor(
        get_lump_sum_data(),
        column_config=lump_sum_column_config(get_terms().analysis_horizon_months),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="lump_sum_editor",
    )

pending_investment = render_investment_controls(scenario_data.get_column("name").to_list(), terms)
if pending_investment:
    st.caption("Apply or cancel investment edits and resolve scenario references before running.")

if st.button("Run simulation", type="primary", icon=":material/play_arrow:", disabled=pending_investment):
    st.session_state[SCENARIOS_KEY] = scenario_data
    st.session_state[LUMP_SUMS_KEY] = lump_sum_data
    try:
        request = build_request(
            AppSettings(),
            terms,
            scenario_data,  # ty: ignore[invalid-argument-type]  # Streamlit misidentifies Polars frames.
            lump_sum_data,  # ty: ignore[invalid-argument-type]  # Streamlit misidentifies Polars frames.
        )
        scenarios = tuple(
            scenario.model_copy(update={"investment": get_investments().get(scenario.name)})
            for scenario in request.scenarios
        )
        results = tuple(simulate(request.terms, scenario) for scenario in scenarios)
    except (InvalidOperation, KeyError, TypeError, ValueError, ValidationError) as error:
        st.error(f"Invalid simulation input: {error}", icon=":material/error:")
    else:
        store_results(results)
        st.switch_page("app_pages/scenario_results.py")
