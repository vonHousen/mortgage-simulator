"""Tests for Streamlit session-state management."""

from streamlit.testing.v1 import AppTest


class TestApplicationState:
    """Cover typed application state initialized in each Streamlit session."""

    def test_state_when_app_starts_expect_general_defaults(self) -> None:
        """Initialize setup, editors, and no completed results."""
        # Arrange
        app = AppTest.from_string(
            """
import streamlit as st
import polars as pl

from mortgage_simulator.app.session_state import initialize_state
from mortgage_simulator.settings import AppSettings

settings = AppSettings(_env_file=None)
initialize_state(settings, settings.to_mortgage_terms())
assert st.session_state.scenario_data.schema == {
    "name": pl.String,
    "strategy": pl.String,
    "recurring_value": pl.Float64,
    "start_month": pl.Int64,
}
assert st.session_state.lump_sum_data.schema == {
    "scenario": pl.String,
    "month": pl.Int64,
    "amount": pl.Float64,
}
st.write(str(st.session_state.mortgage_terms.principal))
st.write(str(st.session_state.scenario_data.height))
st.write(str(st.session_state.lump_sum_data.height))
st.write(str(st.session_state.simulation_results))
st.write(str(st.session_state.focus_on_typical_payments))
"""
        )

        # Act
        app.run(timeout=10)

        # Assert
        assert not app.exception
        assert [markdown.value for markdown in app.markdown] == ["500000", "0", "0", "None", "False"]

    def test_state_when_focus_configured_expect_configured_initial_value(self) -> None:
        """Seed the shared chart focus from application settings."""
        # Arrange
        app = AppTest.from_string(
            """
import streamlit as st

from mortgage_simulator.app.session_state import initialize_state
from mortgage_simulator.settings import AppSettings

settings = AppSettings(_env_file=None, charts={"focus_on_typical_payments": True})
initialize_state(settings, settings.to_mortgage_terms())
st.write(str(st.session_state.focus_on_typical_payments))
"""
        )

        # Act
        app.run(timeout=10)

        # Assert
        assert not app.exception
        assert [markdown.value for markdown in app.markdown] == ["True"]

    def test_state_when_scenario_defaults_exist_expect_editor_rows(self) -> None:
        """Convert domain scenario defaults into editable recurring and lump-sum rows."""
        # Arrange
        app = AppTest.from_string(
            """
from decimal import Decimal

import streamlit as st

from mortgage_simulator.app.session_state import initialize_state
from mortgage_simulator.settings import AppSettings
from mortgage_simulator.simulation.models import LumpSum, OverpaymentScenario

scenario_defaults = (
    OverpaymentScenario(
        name="Fixed plan",
        recurring_amount=Decimal("1500"),
        recurring_start_month=13,
        lump_sums=(
            LumpSum(month=24, amount=Decimal("10000")),
            LumpSum(month=24, amount=Decimal("5000")),
        ),
    ),
    OverpaymentScenario(
        name="Target plan",
        cash_outflow_target=Decimal("5000"),
        recurring_start_month=1,
    ),
    OverpaymentScenario(
        name="Lump-sum plan",
        lump_sums=(LumpSum(month=36, amount=Decimal("20000")),),
    ),
)
settings = AppSettings(_env_file=None)
initialize_state(settings, settings.to_mortgage_terms(), scenario_defaults)

assert st.session_state.scenario_data.to_dicts() == [
    {"name": "Fixed plan", "strategy": "Fixed overpayment", "recurring_value": 1500.0, "start_month": 13},
    {"name": "Target plan", "strategy": "Constant cash outflow", "recurring_value": 5000.0, "start_month": 1},
    {"name": "Lump-sum plan", "strategy": "Fixed overpayment", "recurring_value": 0.0, "start_month": None},
]
assert st.session_state.lump_sum_data.to_dicts() == [
    {"scenario": "Fixed plan", "month": 24, "amount": 10000.0},
    {"scenario": "Fixed plan", "month": 24, "amount": 5000.0},
    {"scenario": "Lump-sum plan", "month": 36, "amount": 20000.0},
]
st.write("defaults converted")
"""
        )

        # Act
        app.run(timeout=10)

        # Assert
        assert not app.exception
        assert [markdown.value for markdown in app.markdown] == ["defaults converted"]

    def test_results_when_replaced_expect_current_typed_tuple(self) -> None:
        """Replace stored results with the supplied complete result tuple."""
        # Arrange
        app_timeout_seconds = 10
        app = AppTest.from_string(
            """
import streamlit as st

from mortgage_simulator.app.session_state import get_results, initialize_state, store_results
from mortgage_simulator.settings import AppSettings

settings = AppSettings(_env_file=None)
initialize_state(settings, settings.to_mortgage_terms())
store_results(())
assert get_results() == ()
st.write("results stored")
"""
        )

        # Act
        app.run(timeout=app_timeout_seconds).run(timeout=app_timeout_seconds)

        # Assert
        assert not app.exception
        assert [markdown.value for markdown in app.markdown] == ["results stored"]

    def test_results_when_cleared_expect_no_current_results(self) -> None:
        """Invalidate results after shared mortgage assumptions change."""
        # Arrange
        app = AppTest.from_string(
            """
import streamlit as st

from mortgage_simulator.app.session_state import clear_results, get_results, initialize_state, store_results
from mortgage_simulator.settings import AppSettings

settings = AppSettings(_env_file=None)
initialize_state(settings, settings.to_mortgage_terms())
store_results(())

clear_results()

assert get_results() is None
st.write("results cleared")
"""
        )

        # Act
        app.run(timeout=10)

        # Assert
        assert not app.exception
        assert [markdown.value for markdown in app.markdown] == ["results cleared"]

    def test_state_when_reinitialized_expect_user_edits_preserved(self) -> None:
        """Keep all edited session values when initialization runs again."""
        # Arrange
        app = AppTest.from_string(
            """
from decimal import Decimal

import polars as pl
import streamlit as st

from mortgage_simulator.app.session_state import (
    get_lump_sum_data,
    get_results,
    get_scenario_data,
    get_terms,
    initialize_state,
)
from mortgage_simulator.settings import AppSettings
from mortgage_simulator.simulation.models import OverpaymentScenario

settings = AppSettings(_env_file=None)
initialize_state(
    settings,
    settings.to_mortgage_terms(),
    (OverpaymentScenario(name="Configured default"),),
)
edited_terms = AppSettings(_env_file=None, mortgage={"principal": Decimal("450000")}).to_mortgage_terms()
edited_scenarios = pl.DataFrame(
    {
        "name": ["Custom"],
        "strategy": ["Fixed overpayment"],
        "recurring_value": [2500.0],
        "start_month": [12],
    }
)
edited_lump_sums = pl.DataFrame(
    {"scenario": ["Custom"], "month": [12], "amount": [12000.0]}
)
edited_results = ()
st.session_state.mortgage_terms = edited_terms
st.session_state.scenario_data = edited_scenarios
st.session_state.lump_sum_data = edited_lump_sums
st.session_state.simulation_results = edited_results
st.session_state.focus_on_typical_payments = True

initialize_state(settings, settings.to_mortgage_terms())

assert get_terms() == edited_terms
assert get_scenario_data().equals(edited_scenarios)
assert get_lump_sum_data().equals(edited_lump_sums)
assert get_results() == edited_results
assert st.session_state.focus_on_typical_payments is True
st.write("edits preserved")
"""
        )

        # Act
        app.run(timeout=10)

        # Assert
        assert not app.exception
        assert [markdown.value for markdown in app.markdown] == ["edits preserved"]
