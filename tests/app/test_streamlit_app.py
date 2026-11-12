"""Smoke tests for the Streamlit application entrypoint."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import polars as pl
import pytest
from polars.testing import assert_frame_equal
from streamlit.proto import Block_pb2
from streamlit.testing.v1 import AppTest

from mortgage_simulator.app.investment_controls import INVESTMENTS_KEY
from mortgage_simulator.app.session_state import (
    FOCUS_ON_TYPICAL_PAYMENTS_KEY,
    LUMP_SUMS_KEY,
    RESULTS_KEY,
    SCENARIOS_KEY,
    TERMS_KEY,
)
from mortgage_simulator.app.streamlit_app import main
from mortgage_simulator.reporting.payment_schedules import schedule_frame
from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import (
    InsuranceCalculationMethod,
    InterestCalculationMethod,
    MortgageTerms,
    OverpaymentScenario,
    SimulationResult,
    SubsidyTerms,
)
from tests.factories import (
    default_mortgage_terms,
    default_subsidy_terms,
    synthetic_overpayment_scenario,
    synthetic_terms,
)


def test_app_when_started_expect_setup_page_and_top_navigation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Start on a focused mortgage setup page."""
    # Arrange
    app_path = Path("src/mortgage_simulator/app/streamlit_app.py").resolve()
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(app_path)

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    assert app.title[0].value == "Mortgage setup"
    assert len(app.number_input) == 12
    assert {
        "Principal (PLN)",
        "Contractual term (years)",
        "Analysis horizon (months)",
        "Interest, months 1-60 (%)",
        "Interest, months 61-120 (%)",
    }.issubset(number_input.label for number_input in app.number_input)
    assert app.date_input[0].label == "First payment date"
    assert app.date_input[0].value == date(2024, 1, 1)
    assert len(app.segmented_control) == 2
    interest_method = next(widget for widget in app.segmented_control if widget.label == "Interest calculation")
    assert interest_method.label == "Interest calculation"
    assert interest_method.options == ["Calendar days", "Equal months (1/12)"]
    assert interest_method.value == InterestCalculationMethod.CALENDAR_DAYS
    insurance_method = next(
        widget for widget in app.segmented_control if widget.label == "Monthly insurance calculation"
    )
    assert insurance_method.label == "Monthly insurance calculation"
    assert insurance_method.options == ["Opening balance", "Midpoint balance", "Two-interval weighted"]
    assert insurance_method.value == InsuranceCalculationMethod.TWO_INTERVAL_WEIGHTED
    assert app.toggle[0].label == "Settle remaining principal at horizon"
    assert app.toggle[0].value is True
    assert app.toggle[1].label == "Enable BK2% subsidy"
    assert app.toggle[1].value is True
    assert {"Loan details", "Timeline", "Interest rates"}.issubset(subheader.value for subheader in app.subheader)
    insurance_end = next(widget for widget in app.number_input if widget.label == "Insurance and monthly-fee end month")
    assert insurance_end.value is None
    assert app.button[0].label == "Save and continue"
    assert {expander.label for expander in app.expander}.issuperset({"Fee assumptions", "Subsidy assumptions"})


def test_app_when_configured_scenario_file_exists_expect_session_editors_seeded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Load the environment-selected scenario file while starting the Streamlit workflow."""
    # Arrange
    app_path = Path("src/mortgage_simulator/app/streamlit_app.py").resolve()
    relative_config_path = Path("data/config/scenarios-aggressive.json")
    config_path = tmp_path / relative_config_path
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        """
{
  "scenarios": [
    {
      "name": "Local plan",
      "recurring_amount": 1250,
      "recurring_start_month": 7,
      "lump_sums": [{"month": 18, "amount": 8000}]
    }
  ]
}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("MS_SCENARIOS__CONFIG_PATH", str(relative_config_path))
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(app_path)

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    assert app.session_state[SCENARIOS_KEY].to_dicts() == [
        {
            "name": "Local plan",
            "strategy": "Fixed overpayment",
            "recurring_value": 1250.0,
            "start_month": 7,
        }
    ]
    assert app.session_state[LUMP_SUMS_KEY].to_dicts() == [{"scenario": "Local plan", "month": 18, "amount": 8000.0}]


def test_navigation_when_configured_expect_four_workflow_pages() -> None:
    """Expose setup, scenario, result, and comparison pages in workflow order."""
    # Arrange
    selected_page = MagicMock()
    with (
        patch("mortgage_simulator.app.streamlit_app.initialize_state"),
        patch("mortgage_simulator.app.streamlit_app.st.set_page_config"),
        patch("mortgage_simulator.app.streamlit_app.st.Page") as page,
        patch("mortgage_simulator.app.streamlit_app.st.navigation", return_value=selected_page),
    ):
        # Act
        main()

    # Assert
    assert [call.kwargs["title"] for call in page.call_args_list] == [
        "Mortgage setup",
        "Scenarios",
        "Results",
        "Comparison",
    ]
    selected_page.run.assert_called_once_with()


def test_setup_page_when_rendered_expect_sections_in_wrapping_horizontal_row() -> None:
    """Arrange the primary setup cards responsively."""
    # Arrange
    app_path = Path("src/mortgage_simulator/app/streamlit_app.py").resolve()
    app = AppTest.from_file(app_path)

    # Act
    app.run(timeout=10)

    # Assert
    setup_row = app._tree[0].children[2]
    assert setup_row.proto.flex_container.direction == Block_pb2.Block.FlexContainer.HORIZONTAL
    assert setup_row.proto.flex_container.wrap is True
    assert setup_row.proto.id.endswith("-setup-sections")
    assert len(setup_row.children) == 2
    left_group, interest_rates = setup_row.children.values()
    assert left_group.proto.flex_container.border is False
    assert interest_rates.proto.flex_container.border is True
    assert len(left_group.children) == 2
    assert all(section.proto.flex_container.border for section in left_group.children.values())
    responsive_styles = app.get("html")[0].proto.body
    assert "@media (max-width: 1100px)" in responsive_styles
    assert ".st-key-setup-sections" in responsive_styles
    assert "flex-direction: column" in responsive_styles


def test_setup_assumptions_when_rendered_expect_semantic_sections_and_full_width_insurance_method() -> None:
    """Group advanced mortgage inputs by purpose without constraining the insurance selector."""
    # Arrange
    app_path = Path("src/mortgage_simulator/app/streamlit_app.py").resolve()
    app = AppTest.from_file(app_path)

    # Act
    app.run(timeout=10)

    # Assert
    setup_row = app._tree[0].children[2]
    left_group, interest_rates = setup_row.children.values()
    loan_details, timeline = left_group.children.values()
    fee_assumptions = loan_details.expander[0]
    subsidy_assumptions = interest_rates.expander[0]
    assert [subheader.value for subheader in loan_details.subheader] == ["Loan details"]
    assert [subheader.value for subheader in timeline.subheader] == ["Timeline"]
    assert fee_assumptions.label == "Fee assumptions"
    assert subsidy_assumptions.label == "Subsidy assumptions"
    assert {widget.label for widget in fee_assumptions.number_input} == {
        "Annual fixed fee (PLN)",
        "Monthly insurance rate (%)",
        "Other monthly fees (PLN)",
        "Insurance and monthly-fee end month",
    }
    assert {widget.label for widget in subsidy_assumptions.number_input} == {
        "Subsidy coefficient W, months 1-60 (%)",
        "Subsidy coefficient W, months 61-120 (%)",
        "Subsidized reference rate (%)",
    }
    insurance_method = fee_assumptions.segmented_control[0]
    assert insurance_method.label == "Monthly insurance calculation"
    assert insurance_method in fee_assumptions.children.values()
    first_fee_row = fee_assumptions.children[0]
    last_fee_row = fee_assumptions.children[2]
    assert [column.number_input[0].label for column in first_fee_row.columns] == [
        "Annual fixed fee (PLN)",
        "Other monthly fees (PLN)",
    ]
    assert [column.number_input[0].label for column in last_fee_row.columns] == [
        "Monthly insurance rate (%)",
        "Insurance and monthly-fee end month",
    ]


def test_setup_page_when_subsidy_disabled_expect_assumptions_hidden() -> None:
    """Hide subsidy assumptions while preserving their stored values."""
    # Arrange
    terms = default_mortgage_terms(
        subsidy=SubsidyTerms(
            enabled=False,
            coefficient=Decimal("0.05"),
            second_coefficient=Decimal("0.05"),
            reference_rate=Decimal("0.02"),
        )
    )
    app = AppTest.from_file("src/mortgage_simulator/app/app_pages/mortgage_setup.py")
    app.session_state[TERMS_KEY] = terms

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    subsidy_toggle = next(toggle for toggle in app.toggle if toggle.label == "Enable BK2% subsidy")
    assert subsidy_toggle.value is False
    assert "Subsidy assumptions" not in [expander.label for expander in app.expander]
    assert "Subsidy coefficient W, months 1-60 (%)" not in [widget.label for widget in app.number_input]
    assert "Subsidized reference rate (%)" not in [widget.label for widget in app.number_input]
    assert app.session_state[TERMS_KEY].subsidy.coefficient == Decimal("0.05")
    assert app.session_state[TERMS_KEY].subsidy.reference_rate == Decimal("0.02")


def test_setup_page_when_saved_expect_previous_results_cleared() -> None:
    """Invalidate simulations calculated from earlier mortgage assumptions."""
    # Arrange
    app = AppTest.from_file("src/mortgage_simulator/app/app_pages/mortgage_setup.py")
    app.session_state[TERMS_KEY] = default_mortgage_terms()
    app.session_state[RESULTS_KEY] = _default_results()
    app.run(timeout=10)

    # Act
    with patch("streamlit.switch_page"):
        app.button[0].click().run(timeout=10)

    # Assert
    assert not app.exception
    assert app.session_state[RESULTS_KEY] is None


def test_scenarios_page_when_started_expect_payment_editors() -> None:
    """Render separate editors for recurring and one-off overpayments."""
    # Arrange
    app = _scenarios_app()

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    assert app.title[0].value == "Overpayment scenarios"
    assert len(app.dataframe) == 2
    strategy_caption = next(caption.value for caption in app.caption if "Constant cash outflow" in caption.value)
    assert "Lump sums and horizon settlement are additional" in strategy_caption
    assert any(button.label == "Run simulation" for button in app.button)


def test_scenarios_page_when_subsidy_disabled_expect_gross_interest_copy() -> None:
    """Describe constant cash outflow using conventional-mortgage terminology."""
    # Arrange
    terms = default_mortgage_terms(subsidy=default_subsidy_terms(enabled=False))
    app = _scenarios_app(terms=terms)

    # Act
    app.run(timeout=10)

    # Assert
    strategy_caption = next(caption.value for caption in app.caption if "Constant cash outflow" in caption.value)
    assert "gross interest" in strategy_caption
    assert "net interest" not in strategy_caption


def test_scenario_editor_when_starting_month_entered_expect_value_retained() -> None:
    """Keep a newly added row's starting month through the editor rerun."""
    # Arrange
    app = _scenarios_app()
    app.run(timeout=10)
    app.session_state["scenario_editor"] = {
        "edited_rows": {},
        "added_rows": [{"name": "Monthly plan", "strategy": "Fixed overpayment", "recurring_value": 1000.0}],
        "deleted_rows": [],
    }
    app.run(timeout=10)

    # Act
    app.session_state["scenario_editor"] = {
        "edited_rows": {},
        "added_rows": [
            {
                "name": "Monthly plan",
                "strategy": "Fixed overpayment",
                "recurring_value": 1000.0,
                "start_month": 13,
            }
        ],
        "deleted_rows": [],
    }
    app.run(timeout=10)

    # Assert
    assert not app.exception
    editor_state = app.session_state["scenario_editor"]
    assert editor_state["added_rows"] == [
        {
            "name": "Monthly plan",
            "strategy": "Fixed overpayment",
            "recurring_value": 1000.0,
            "start_month": 13,
        }
    ]


def test_scenarios_page_when_fixed_strategy_submitted_expect_fixed_overpayment_result() -> None:
    """Run the existing fixed-overpayment strategy through the scenario page."""
    # Arrange
    app = _scenarios_app("Fixed overpayment", 1000.0)
    app.run(timeout=10)

    # Act
    next(button for button in app.button if button.label == "Run simulation").click().run(timeout=10)

    # Assert
    results = app.session_state[RESULTS_KEY]
    assert results[1].payments[24].recurring_overpayment == Decimal("1000.0")


def test_scenarios_page_when_target_strategy_submitted_expect_target_overpayment_result() -> None:
    """Run a constant cash-outflow strategy through the scenario page."""
    # Arrange
    target = Decimal("5000")
    app = _scenarios_app("Constant cash outflow", float(target), lump_sum_amount=None)
    app.run(timeout=10)

    # Act
    next(button for button in app.button if button.label == "Run simulation").click().run(timeout=10)

    # Assert
    payment = app.session_state[RESULTS_KEY][1].payments[24]
    assert payment.recurring_overpayment > Decimal("0")
    assert payment.cash_outflow == target


def test_failed_run_when_results_exist_expect_previous_results_preserved() -> None:
    """Keep the last successful results when new scenario input is invalid."""
    # Arrange
    app = _scenarios_app()
    existing_results = (simulate(default_mortgage_terms(), OverpaymentScenario(name="Baseline")),)
    app.session_state[RESULTS_KEY] = existing_results
    app.session_state[LUMP_SUMS_KEY] = pl.DataFrame(
        {"scenario": ["Unknown"], "month": [25], "amount": [Decimal("12000")]}
    )
    app.run(timeout=10)

    # Act
    next(button for button in app.button if button.label == "Run simulation").click().run(timeout=10)

    # Assert
    assert not app.exception
    assert "unknown scenarios" in app.error[0].value
    assert app.session_state[RESULTS_KEY] == existing_results


def test_results_page_when_no_simulation_expect_empty_state() -> None:
    """Guide users back to Scenarios instead of rendering empty charts."""
    # Arrange
    app = _results_app(None)

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    assert app.title[0].value == "Results"
    assert "Run a simulation" in app.info[0].value
    assert len(app.metric) == 0
    assert len(app.get("arrow_vega_lite_chart")) == 0


def test_results_page_when_simulation_exists_expect_highlights_and_raw_totals() -> None:
    """Show relative insights, absolute amounts, and detailed data."""
    # Arrange
    app = _results_app(_default_results())

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    assert len(app.metric) == 23
    assert [metric.label for metric in app.metric[:8]] == [
        "Total cash outflow",
        "Principal repaid",
        "Total mortgage cost",
        "Ending balance",
        "Gross interest",
        "Fees paid",
        "Subsidy received",
        "Payoff month",
    ]
    assert [metric.label for metric in app.metric[8:12]] == [
        "Principal repaid before settlement",
        "Terminal settlement",
        "Principal deferred to settlement",
        "Settlement reduction vs Baseline",
    ]
    assert [metric.label for metric in app.metric[12:15]] == [
        "Cost / original principal",
        "Cost / principal repaid",
        "Net average annual interest rate",
    ]
    assert [metric.label for metric in app.metric[15:]] == [
        "Total mortgage cost saved",
        "Balance reduced",
        "Additional cash paid",
        "Payoff timing",
        "Interest saved",
        "Subsidy difference",
        "Net average annual interest rate difference",
        "Overpayment savings rate",
    ]
    assert app.metric[0].value == "437,515.64 PLN"
    assert app.metric[2].value == "162,848.97 PLN"
    metrics = {metric.label: metric for metric in app.metric}
    assert metrics["Principal repaid before settlement"].value == "274,666.67 PLN"
    assert metrics["Terminal settlement"].value == "0.00 PLN"
    assert metrics["Principal deferred to settlement"].value == "0.00%"
    assert metrics["Settlement reduction vs Baseline"].value == "0.00 PLN"
    assert metrics["Total mortgage cost saved"].value == "22,875.87 PLN"
    assert metrics["Interest saved"].value == "37,125.87 PLN"
    assert metrics["Subsidy difference"].value == "-14,250.00 PLN"
    assert metrics["Net average annual interest rate difference"].value == "-0.05 p.p."
    assert metrics["Overpayment savings rate"].value == "21.18%"
    assert metrics["Overpayment savings rate"].proto.help == (
        "Baseline total mortgage cost minus this scenario's total mortgage cost, divided by recurring and lump-sum "
        "overpayments actually applied during the analysis horizon. Terminal horizon settlement is excluded."
    )
    assert metrics["Balance reduced"].proto.help == (
        "Baseline ending balance minus this scenario's ending balance. "
        "It is the additional principal eliminated by the analysis horizon."
    )
    assert metrics["Additional cash paid"].proto.help == (
        "This scenario's total cash outflow minus Baseline total cash outflow. "
        "It includes additional principal and changes in interest, subsidy, and fees."
    )
    subheaders = [subheader.value for subheader in app.subheader]
    assert subheaders[:4] == ["Raw totals", "Horizon settlement", "Cost indicators", "Difference from Baseline"]
    assert {"Remaining principal", "Monthly cash outflow", "Payment composition"}.issubset(
        subheader.value for subheader in app.subheader
    )
    results_charts = app.get("vega_lite_chart")
    first_results_spec = json.loads(results_charts[0].proto.spec)
    second_results_spec = json.loads(results_charts[1].proto.spec)
    assert {"area", "line", "rule", "point"}.issubset(_chart_marks(first_results_spec))
    assert {"area", "line", "rule", "point"}.issubset(_chart_marks(second_results_spec))
    assert [toggle.label for toggle in app.toggle] == [
        "Show terminal payment",
        "Focus on typical payments",
        "Show interest after subsidy",
        "Split fees",
        "Split overpayments",
    ]
    assert [toggle.value for toggle in app.toggle] == [False, False, False, False, False]
    assert len(app.dataframe) == 1
    assert len(app.download_button) == 0
    assert all(expander.label != "Detailed comparison" for expander in app.expander)


def test_results_page_when_schedule_toggles_are_disabled_expect_aggregate_columns_side_by_side() -> None:
    """Place disabled component toggles above the aggregate monthly schedule."""
    # Arrange
    app = _results_app(_default_results())

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    schedule_toggle_columns = [column for column in app.columns if len(column.toggle) == 1]
    assert len(schedule_toggle_columns) == 2
    assert [column.toggle[0].label for column in schedule_toggle_columns] == ["Split fees", "Split overpayments"]
    assert [column.toggle[0].value for column in schedule_toggle_columns] == [False, False]
    page_elements = list(app)
    monthly_schedule = next(subheader for subheader in app.subheader if subheader.value == "Monthly schedule")
    schedule_toggles = [toggle for toggle in app.toggle if toggle.label in {"Split fees", "Split overpayments"}]
    assert len(schedule_toggles) == 2
    monthly_schedule_index = page_elements.index(monthly_schedule)
    schedule_dataframe_index = page_elements.index(app.dataframe[0])
    assert all(
        monthly_schedule_index < page_elements.index(toggle) < schedule_dataframe_index for toggle in schedule_toggles
    )
    assert list(app.dataframe[0].value.columns) == [
        "month",
        "payment_date",
        "opening_balance",
        "scheduled_principal",
        "overpayments",
        "interest",
        "subsidy",
        "fees",
        "cash_outflow_without_fees",
        "cash_outflow",
        "closing_balance",
    ]


def test_results_page_when_schedule_toggles_are_enabled_expect_component_columns_without_chart_changes() -> None:
    """Show fee and overpayment components without changing the result charts."""
    # Arrange
    app = _results_app(_default_results())
    app.run(timeout=10)
    original_chart_specs = [chart.proto.spec for chart in app.get("vega_lite_chart")]
    schedule_toggles = {toggle.label: toggle for toggle in app.toggle}
    assert {"Split fees", "Split overpayments"}.issubset(schedule_toggles)

    # Act
    schedule_toggles["Split fees"].set_value(True).run(timeout=10)
    schedule_toggles["Split overpayments"].set_value(True).run(timeout=10)

    # Assert
    assert not app.exception
    schedule_toggles = {toggle.label: toggle for toggle in app.toggle}
    assert [schedule_toggles["Split fees"].value, schedule_toggles["Split overpayments"].value] == [True, True]
    assert list(app.dataframe[0].value.columns) == [
        "month",
        "payment_date",
        "opening_balance",
        "scheduled_principal",
        "recurring_overpayment",
        "lump_sum",
        "horizon_settlement",
        "interest",
        "subsidy",
        "monthly_insurance",
        "monthly_fixed_fees",
        "annual_fixed_fee",
        "cash_outflow_without_fees",
        "cash_outflow",
        "closing_balance",
    ]
    assert [chart.proto.spec for chart in app.get("vega_lite_chart")] == original_chart_specs


@pytest.mark.parametrize(
    ("split_fees", "split_overpayments", "expected_columns"),
    [
        pytest.param(
            True,
            False,
            [
                "month",
                "payment_date",
                "opening_balance",
                "scheduled_principal",
                "overpayments",
                "interest",
                "subsidy",
                "monthly_insurance",
                "monthly_fixed_fees",
                "annual_fixed_fee",
                "cash_outflow_without_fees",
                "cash_outflow",
                "closing_balance",
            ],
            id="split_fees_only",
        ),
        pytest.param(
            False,
            True,
            [
                "month",
                "payment_date",
                "opening_balance",
                "scheduled_principal",
                "recurring_overpayment",
                "lump_sum",
                "horizon_settlement",
                "interest",
                "subsidy",
                "fees",
                "cash_outflow_without_fees",
                "cash_outflow",
                "closing_balance",
            ],
            id="split_overpayments_only",
        ),
    ],
)
def test_results_page_when_one_schedule_toggle_is_enabled_expect_only_its_component_columns(
    split_fees: bool,
    split_overpayments: bool,
    expected_columns: list[str],
) -> None:
    """Display only the selected schedule component group."""
    # Arrange
    selected_scenario = "Overpayment"
    results = _default_results()
    app = _results_app(results)
    app.run(timeout=10)
    schedule_toggles = {toggle.label: toggle for toggle in app.toggle}

    # Act
    schedule_toggles["Split fees"].set_value(split_fees)
    schedule_toggles["Split overpayments"].set_value(split_overpayments)
    app.run(timeout=10)

    # Assert
    assert not app.exception
    expected_schedule = schedule_frame(results).filter(pl.col("scenario") == selected_scenario).select(expected_columns)
    rendered_schedule = pl.from_pandas(app.dataframe[0].value)
    assert_frame_equal(rendered_schedule, expected_schedule, check_dtypes=False)


def test_results_page_when_settlement_disabled_expect_no_settlement_section() -> None:
    """Hide settlement-specific indicators for partial-horizon simulations."""
    # Arrange
    terms = default_mortgage_terms(settle_remaining_principal_at_horizon=False)
    results = (simulate(terms, OverpaymentScenario(name="Baseline")),)
    app = _results_app(results, terms)

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    assert len(app.metric) == 19
    assert "Horizon settlement" not in [subheader.value for subheader in app.subheader]
    assert [toggle.label for toggle in app.toggle] == [
        "Focus on typical payments",
        "Show interest after subsidy",
        "Split fees",
        "Split overpayments",
    ]
    assert [toggle.value for toggle in app.toggle] == [False, False, False, False]


def test_results_page_when_subsidy_disabled_expect_conventional_mortgage_outputs() -> None:
    """Hide subsidy-only metrics, controls, and schedule fields."""
    # Arrange
    terms = _synthetic_terms().model_copy(
        update={
            "subsidy": SubsidyTerms(
                enabled=False,
                coefficient=Decimal("0.05"),
                second_coefficient=Decimal("0.05"),
                reference_rate=Decimal("0.02"),
            )
        }
    )
    app = _results_app(_default_results(terms), terms)

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    metric_labels = [metric.label for metric in app.metric]
    toggle_labels = [toggle.label for toggle in app.toggle]
    assert "Subsidy received" not in metric_labels
    assert "Subsidy difference" not in metric_labels
    assert "Net average annual interest rate" not in metric_labels
    assert "Net average annual interest rate difference" not in metric_labels
    assert "Average annual interest rate" in metric_labels
    assert "Average annual interest rate difference" in metric_labels
    assert "Show interest after subsidy" not in toggle_labels
    assert "subsidy" not in app.dataframe[0].value.columns


def test_comparison_page_when_subsidy_disabled_expect_subsidy_rows_omitted() -> None:
    """Hide subsidy totals and differences from conventional-mortgage comparisons."""
    # Arrange
    terms = _synthetic_terms().model_copy(
        update={
            "subsidy": SubsidyTerms(
                enabled=False,
                coefficient=Decimal("0.05"),
                second_coefficient=Decimal("0.05"),
                reference_rate=Decimal("0.02"),
            )
        }
    )
    app = _comparison_app(_default_results(terms), terms)

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    labels = app.dataframe[0].value["Metric"].to_list()
    assert "Subsidy received" not in labels
    assert "Subsidy difference" not in labels
    assert "Average annual interest rate" in labels


def test_results_page_when_terminal_payment_enabled_expect_both_payment_charts_updated() -> None:
    """Apply terminal-payment visibility to cash outflow and payment composition together."""
    # Arrange
    terms = _synthetic_terms().model_copy(update={"settle_remaining_principal_at_horizon": True})
    results = (
        simulate(terms, OverpaymentScenario(name="Baseline")),
        simulate(
            terms,
            OverpaymentScenario(name="Overpayment", recurring_amount=Decimal("100"), recurring_start_month=25),
        ),
    )
    app = _results_app(results, terms)
    app.run(timeout=10)
    hidden_cash_outflow_spec = json.loads(app.get("vega_lite_chart")[1].proto.spec)
    hidden_composition_spec = json.loads(app.get("vega_lite_chart")[2].proto.spec)
    terminal_payment_toggle = next(toggle for toggle in app.toggle if toggle.label == "Show terminal payment")

    # Act
    terminal_payment_toggle.set_value(True).run(timeout=10)

    # Assert
    assert not app.exception
    assert next(toggle for toggle in app.toggle if toggle.label == "Show terminal payment").value is True
    shown_cash_outflow_spec = json.loads(app.get("vega_lite_chart")[1].proto.spec)
    shown_composition_spec = json.loads(app.get("vega_lite_chart")[2].proto.spec)
    assert shown_cash_outflow_spec["data"]["name"] != hidden_cash_outflow_spec["data"]["name"]
    assert shown_composition_spec["data"]["name"] != hidden_composition_spec["data"]["name"]


def test_results_page_when_typical_payments_enabled_expect_both_payment_charts_focused() -> None:
    """Focus both Results payment charts without changing remaining principal."""
    # Arrange
    app = _results_app(_default_results())
    app.run(timeout=10)
    original_specs = [chart.proto.spec for chart in app.get("vega_lite_chart")]
    focus_toggle = next(toggle for toggle in app.toggle if toggle.label == "Focus on typical payments")

    # Act
    focus_toggle.set_value(True).run(timeout=10)

    # Assert
    assert not app.exception
    updated_specs = [chart.proto.spec for chart in app.get("vega_lite_chart")]
    updated_toggle = next(toggle for toggle in app.toggle if toggle.label == "Focus on typical payments")
    assert updated_toggle.value is True
    assert updated_toggle.proto.help == (
        "Limit payment chart scales to the 99th percentile so typical monthly payments are easier to compare."
    )
    assert app.session_state[FOCUS_ON_TYPICAL_PAYMENTS_KEY] is True
    assert updated_specs[0] == original_specs[0]
    assert updated_specs[1] != original_specs[1]
    assert updated_specs[2] != original_specs[2]


def test_results_page_when_after_subsidy_enabled_expect_net_interest_composition() -> None:
    """Hide the separate subsidy band when the chart toggle is enabled."""
    # Arrange
    app = _results_app(_default_results())
    app.run(timeout=10)
    gross_composition_chart = app.get("vega_lite_chart")[2]
    gross_composition_spec = json.loads(gross_composition_chart.proto.spec)

    # Act
    subsidy_toggle = next(toggle for toggle in app.toggle if toggle.label == "Show interest after subsidy")
    subsidy_toggle.set_value(True).run(timeout=10)

    # Assert
    assert not app.exception
    assert next(toggle for toggle in app.toggle if toggle.label == "Show interest after subsidy").value is True
    composition_chart = app.get("vega_lite_chart")[2]
    composition_spec = json.loads(composition_chart.proto.spec)
    assert composition_spec["data"]["name"] != gross_composition_spec["data"]["name"]


def test_comparison_page_when_no_simulation_expect_empty_state() -> None:
    """Avoid rendering all-scenario analysis before a successful run."""
    # Arrange
    app = _comparison_app(None)

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    assert app.title[0].value == "Comparison"
    assert "Run a simulation" in app.info[0].value
    assert len(app.dataframe) == 0
    assert len(app.download_button) == 0


def test_comparison_page_when_results_exist_expect_all_scenario_views() -> None:
    """Show comparison charts, totals, and combined export together."""
    # Arrange
    app = _comparison_app(_default_results())

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    assert app.title[0].value == "Comparison"
    assert {"Remaining principal", "Monthly cash outflow", "Scenario totals and differences"}.issubset(
        subheader.value for subheader in app.subheader
    )
    comparison_charts = app.get("vega_lite_chart")
    first_comparison_spec = json.loads(comparison_charts[0].proto.spec)
    second_comparison_spec = json.loads(comparison_charts[1].proto.spec)
    assert "line" in _chart_marks(first_comparison_spec)
    assert "area" not in _chart_marks(first_comparison_spec)
    assert "line" in _chart_marks(second_comparison_spec)
    assert "area" not in _chart_marks(second_comparison_spec)
    focus_toggle = next(toggle for toggle in app.toggle if toggle.label == "Focus on typical payments")
    assert focus_toggle.value is False
    assert focus_toggle.proto.help == (
        "Limit payment chart scales to the 99th percentile so typical monthly payments are easier to compare."
    )
    assert len(app.dataframe) == 1
    comparison_table = app.dataframe[0].value
    assert comparison_table.columns.to_list() == ["Metric", "Baseline", "Overpayment"]
    assert "Ending balance" not in comparison_table["Metric"].to_list()
    assert "Ending balance difference" not in comparison_table["Metric"].to_list()
    assert app.download_button[0].label == "Download combined CSV"


def test_comparison_page_when_typical_payments_configured_expect_shared_value_and_only_cash_chart_updated() -> None:
    """Use the shared configured focus without changing comparison data outputs."""
    # Arrange
    app = _comparison_app(_default_results())
    app.session_state[FOCUS_ON_TYPICAL_PAYMENTS_KEY] = True

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    focus_toggle = next(toggle for toggle in app.toggle if toggle.label == "Focus on typical payments")
    chart_specs = [json.loads(chart.proto.spec) for chart in app.get("vega_lite_chart")]
    assert focus_toggle.value is True
    assert "scale" not in chart_specs[0]["layer"][0]["encoding"]["y"]
    assert chart_specs[1]["layer"][0]["encoding"]["y"]["scale"]["clamp"] is True
    assert len(app.dataframe) == 1
    assert len(app.download_button) == 1


def test_comparison_page_when_settlement_disabled_expect_ending_balance_rows() -> None:
    """Retain ending-balance comparisons for a partial-horizon simulation."""
    # Arrange
    terms = default_mortgage_terms(settle_remaining_principal_at_horizon=False)
    app = _comparison_app(_default_results(terms), terms)

    # Act
    app.run(timeout=10)

    # Assert
    assert not app.exception
    comparison_table = app.dataframe[0].value
    assert "Ending balance" in comparison_table["Metric"].to_list()
    assert "Ending balance difference" in comparison_table["Metric"].to_list()


class TestInvestmentControls:
    """Investment management on the scenario page."""

    def test_add_when_applied_expect_session_investment(self) -> None:
        # Arrange
        app = _scenarios_app()
        app.run(timeout=10)
        # Act
        next(button for button in app.button if button.label == "Add investment").click().run()
        # Assert
        assert not app.exception
        assert next(button for button in app.button if button.label == "Run simulation").disabled
        # Act
        app.number_input(key="deposit_capital").set_value(25000.0)
        app.number_input(key="deposit_rate").set_value(6.0)
        next(button for button in app.button if button.label == "Apply investment").click().run()
        # Assert
        assert not app.exception
        item = app.session_state[INVESTMENTS_KEY]["Overpayment"]
        assert item.initial_amount == Decimal("25000")
        assert item.annual_rate == Decimal("0.06")
        assert not next(button for button in app.button if button.label == "Run simulation").disabled

    def test_add_when_cancelled_expect_no_investment(self) -> None:
        # Arrange
        app = _scenarios_app()
        app.run()
        # Act
        next(button for button in app.button if button.label == "Add investment").click().run()
        next(button for button in app.button if button.label == "Cancel").click().run()
        # Assert
        assert not app.exception
        assert app.session_state[INVESTMENTS_KEY] == {}

    def test_draft_when_navigating_and_switching_modes_expect_term_count_preserved(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Arrange
        count = 7
        app_path = Path("src/mortgage_simulator/app/streamlit_app.py").resolve()
        monkeypatch.chdir(tmp_path)
        app = AppTest.from_file(app_path).run()
        app.session_state[SCENARIOS_KEY] = pl.DataFrame(
            {
                "name": ["Deposit"],
                "strategy": ["Fixed overpayment"],
                "recurring_value": [0.0],
                "start_month": [None],
            },
            schema={"name": pl.String, "strategy": pl.String, "recurring_value": pl.Float64, "start_month": pl.Int64},
        )
        app.switch_page("app_pages/overpayment_scenarios.py").run()
        next(button for button in app.button if button.label == "Add investment").click().run()
        app.number_input(key="deposit_count").set_value(count).run()
        # Act
        app.switch_page("app_pages/mortgage_setup.py").run()
        app.switch_page("app_pages/overpayment_scenarios.py").run()
        # Assert
        assert not app.exception
        assert app.number_input(key="deposit_count").value == count
        # Act
        app.segmented_control(key="deposit_mode").set_value("automatic").run()
        app.segmented_control(key="deposit_mode").set_value("manual").run()
        # Assert
        assert app.number_input(key="deposit_count").value == count
        # Act
        next(button for button in app.button if button.label == "Cancel").click().run()
        app.run()
        # Assert
        assert not app.exception
        assert app.session_state[INVESTMENTS_KEY] == {}


def _scenarios_app(
    strategy: str = "Fixed overpayment",
    recurring_value: float = 1000.0,
    lump_sum_amount: float | None = 12000.0,
    terms: MortgageTerms | None = None,
) -> AppTest:
    app = AppTest.from_file("src/mortgage_simulator/app/app_pages/overpayment_scenarios.py")
    app.session_state[INVESTMENTS_KEY] = {}
    app.session_state[TERMS_KEY] = terms or default_mortgage_terms()
    app.session_state[SCENARIOS_KEY] = pl.DataFrame(
        {
            "name": ["Overpayment"],
            "strategy": [strategy],
            "recurring_value": [recurring_value],
            "start_month": [25],
        }
    )
    if lump_sum_amount is None:
        app.session_state[LUMP_SUMS_KEY] = pl.DataFrame(
            schema={"scenario": pl.String, "month": pl.Int64, "amount": pl.Float64}
        )
    else:
        app.session_state[LUMP_SUMS_KEY] = pl.DataFrame(
            {"scenario": ["Overpayment"], "month": [25], "amount": [lump_sum_amount]}
        )
    app.session_state[RESULTS_KEY] = None
    return app


def _results_app(results: tuple[SimulationResult, ...] | None, terms: MortgageTerms | None = None) -> AppTest:
    app = AppTest.from_file("src/mortgage_simulator/app/app_pages/scenario_results.py")
    app.session_state[RESULTS_KEY] = results
    app.session_state[TERMS_KEY] = terms or default_mortgage_terms()
    return app


def _comparison_app(
    results: tuple[SimulationResult, ...] | None,
    terms: MortgageTerms | None = None,
) -> AppTest:
    app = AppTest.from_file("src/mortgage_simulator/app/app_pages/all_scenarios_comparison.py")
    app.session_state[RESULTS_KEY] = results
    app.session_state[TERMS_KEY] = terms or default_mortgage_terms()
    return app


def _default_results(terms: MortgageTerms | None = None) -> tuple[SimulationResult, ...]:
    terms = terms or _synthetic_terms()
    return (
        simulate(terms, OverpaymentScenario(name="Baseline")),
        simulate(terms, synthetic_overpayment_scenario()),
    )


def _synthetic_terms() -> MortgageTerms:
    """Return shared synthetic assumptions for value-sensitive UI assertions."""
    return synthetic_terms()


def _chart_marks(specification: dict[str, Any]) -> set[str]:
    """Collect mark types from a layered Vega-Lite specification.

    Args:
        specification: Parsed Vega-Lite chart specification.

    Returns:
        Mark types used by the chart and its nested layers.
    """
    marks: set[str] = set()
    mark = specification.get("mark")
    if isinstance(mark, str):
        marks.add(mark)
    elif isinstance(mark, dict) and isinstance(mark.get("type"), str):
        marks.add(mark["type"])
    for child in specification.get("layer", []):
        marks.update(_chart_marks(child))
    return marks
