"""Streamlit entrypoint and multipage router."""

import streamlit as st

from mortgage_simulator.app.scenario_defaults import load_local_scenarios
from mortgage_simulator.app.session_state import initialize_state
from mortgage_simulator.settings import AppSettings


def main() -> None:
    """Configure and run the mortgage simulator navigation."""
    st.set_page_config(
        page_title="Mortgage simulator",
        page_icon=":material/home_work:",
        layout="wide",
    )
    settings = AppSettings()
    terms = settings.to_mortgage_terms()
    initialize_state(settings, terms, load_local_scenarios(settings, terms))
    page = st.navigation(
        [
            st.Page(
                "app_pages/mortgage_setup.py",
                title="Mortgage setup",
                icon=":material/tune:",
                default=True,
            ),
            st.Page("app_pages/overpayment_scenarios.py", title="Scenarios", icon=":material/compare_arrows:"),
            st.Page("app_pages/scenario_results.py", title="Results", icon=":material/analytics:"),
            st.Page(
                "app_pages/all_scenarios_comparison.py",
                title="Comparison",
                icon=":material/monitoring:",
            ),
        ],
        position="top",
    )
    page.run()


if __name__ == "__main__":
    main()
