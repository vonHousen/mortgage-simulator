"""Shared controls for result charts."""

import streamlit as st

from mortgage_simulator.app.session_state import FOCUS_ON_TYPICAL_PAYMENTS_KEY

TYPICAL_PAYMENTS_HELP = (
    "Limit payment chart scales to the 99th percentile so typical monthly payments are easier to compare."
)


def typical_payments_toggle() -> bool:
    """Render and return the shared payment-chart focus selection."""
    return st.toggle(
        "Focus on typical payments",
        help=TYPICAL_PAYMENTS_HELP,
        key=FOCUS_ON_TYPICAL_PAYMENTS_KEY,
    )
