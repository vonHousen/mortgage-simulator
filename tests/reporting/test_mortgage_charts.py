"""Tests for Altair chart construction."""

from datetime import date
from decimal import Decimal
from typing import Any, cast

import altair as alt
import polars as pl
import pytest

from mortgage_simulator.reporting.mortgage_charts import (
    balance_chart,
    cash_outflow_chart,
    payment_composition_chart,
)
from mortgage_simulator.reporting.payment_schedules import schedule_frame
from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import OverpaymentScenario
from tests.factories import default_mortgage_terms


class TestCharts:
    """Tests for report visualization specifications."""

    def test_date_axis_charts_when_today_in_range_expect_current_date_rule(self) -> None:
        """Mark today's date on every chart whose horizontal axis contains it."""
        # Arrange
        today = date.today()
        frame = _schedule_frame(first_payment_date=today.replace(day=1))

        # Act
        specifications = (
            balance_chart(frame).to_dict(),
            cash_outflow_chart(frame).to_dict(),
            payment_composition_chart(frame, "Baseline").to_dict(),
        )

        # Assert
        for specification in specifications:
            _assert_current_date_rule(specification, today)

    def test_date_axis_charts_when_today_outside_range_expect_no_current_date_rule(self) -> None:
        """Keep today from extending charts whose schedules do not contain it."""
        # Arrange
        frame = _schedule_frame(first_payment_date=date(2000, 1, 1))

        # Act
        specifications = (
            balance_chart(frame).to_dict(),
            cash_outflow_chart(frame).to_dict(),
            payment_composition_chart(frame, "Baseline").to_dict(),
        )

        # Assert
        for specification in specifications:
            assert _current_date_rules(specification) == []

    def test_balance_chart_when_frame_provided_expect_scenario_line_chart(self) -> None:
        """Plot closing balance as a line with a nearest-month hover guide."""
        # Arrange
        frame = _schedule_frame()

        # Act
        chart = balance_chart(frame)

        # Assert
        assert isinstance(chart, alt.LayerChart)
        specification = chart.to_dict()
        assert "line" in _marks(specification)
        assert "area" not in _marks(specification)
        _assert_scenario_hover(specification, "closing_balance")

    def test_balance_chart_when_filled_expect_area_with_boundary(self) -> None:
        """Fill a selected scenario while retaining a clear line boundary."""
        # Arrange
        frame = _schedule_frame().filter(pl.col("scenario") == "Overpayment")

        # Act
        chart = balance_chart(frame, filled=True)

        # Assert
        specification = chart.to_dict()
        assert {"area", "line", "rule", "point"}.issubset(_marks(specification))
        _assert_scenario_hover(specification, "closing_balance")

    def test_cash_outflow_chart_when_frame_provided_expect_scenario_line_chart(self) -> None:
        """Plot monthly cash outflow by month and scenario."""
        # Arrange
        frame = _schedule_frame()

        # Act
        chart = cash_outflow_chart(frame)

        # Assert
        specification = chart.to_dict()
        assert "line" in _marks(specification)
        assert "area" not in _marks(specification)
        _assert_scenario_hover(specification, "cash_outflow")

    def test_cash_outflow_chart_when_filled_expect_area_with_boundary(self) -> None:
        """Fill selected-scenario cash outflow with a line boundary."""
        # Arrange
        frame = _schedule_frame().filter(pl.col("scenario") == "Overpayment")

        # Act
        chart = cash_outflow_chart(frame, filled=True)

        # Assert
        specification = chart.to_dict()
        assert {"area", "line", "rule", "point"}.issubset(_marks(specification))
        _assert_scenario_hover(specification, "cash_outflow")

    def test_cash_outflow_chart_when_terminal_payment_hidden_expect_regular_outflow(self) -> None:
        """Exclude horizon settlement from the default plotted cash outflow."""
        # Arrange
        frame = _schedule_frame().filter(pl.col("scenario") == "Baseline")
        final_month = frame.row(-1, named=True)

        # Act
        rows = _chart_rows(cash_outflow_chart(frame).to_dict())

        # Assert
        assert rows[-1]["cash_outflow"] == pytest.approx(
            float(final_month["cash_outflow"] - final_month["horizon_settlement"])
        )

    def test_cash_outflow_chart_when_terminal_payment_shown_expect_complete_outflow(self) -> None:
        """Restore complete final-month cash outflow when requested."""
        # Arrange
        frame = _schedule_frame().filter(pl.col("scenario") == "Baseline")
        final_month = frame.row(-1, named=True)

        # Act
        rows = _chart_rows(cash_outflow_chart(frame, show_terminal_payment=True).to_dict())

        # Assert
        assert rows[-1]["cash_outflow"] == pytest.approx(float(final_month["cash_outflow"]))

    def test_cash_outflow_chart_when_not_focused_expect_unrestricted_scale(self) -> None:
        """Leave the default cash-outflow scale unrestricted."""
        # Arrange
        frame = _cash_outflow_focus_frame()

        # Act
        specification = cash_outflow_chart(frame).to_dict()

        # Assert
        assert "scale" not in specification["layer"][0]["encoding"]["y"]
        assert specification["title"] == "Monthly cash outflow"

    def test_cash_outflow_chart_when_focused_expect_chart_wide_p99_clamped_with_exact_tooltips(self) -> None:
        """Focus every scenario on one p99 ceiling without replacing source amounts."""
        # Arrange
        frame = _cash_outflow_focus_frame()
        expected_ceiling = 10000.0

        # Act
        specification = cash_outflow_chart(
            frame,
            show_terminal_payment=True,
            focus_on_typical_payments=True,
        ).to_dict()

        # Assert
        y_encoding = specification["layer"][0]["encoding"]["y"]
        assert y_encoding["scale"] == {"clamp": True, "domain": [0, expected_ceiling]}
        assert specification["title"] == {
            "text": "Monthly cash outflow",
            "subtitle": (
                "Focused at the 99th percentile: 10,000.00 PLN. "
                "Larger values are clamped but retain their exact tooltip amounts."
            ),
        }
        assert max(row["cash_outflow"] for row in _chart_rows(specification)) == 20000.0
        tooltip_fields = {
            tooltip["field"]
            for layer in specification["layer"]
            for tooltip in layer.get("encoding", {}).get("tooltip", [])
        }
        assert "cash_outflow" in tooltip_fields

    def test_cash_outflow_chart_when_focused_expect_terminal_visibility_applied_before_p99(self) -> None:
        """Exclude hidden terminal settlements before calculating the focused ceiling."""
        # Arrange
        frame = _cash_outflow_focus_frame()

        # Act
        hidden_specification = cash_outflow_chart(frame, focus_on_typical_payments=True).to_dict()
        shown_specification = cash_outflow_chart(
            frame,
            show_terminal_payment=True,
            focus_on_typical_payments=True,
        ).to_dict()

        # Assert
        assert hidden_specification["layer"][0]["encoding"]["y"]["scale"]["domain"] == [0, 100.0]
        assert shown_specification["layer"][0]["encoding"]["y"]["scale"]["domain"] == [0, 10000.0]

    def test_composition_chart_when_gross_view_expect_interest_split_with_subsidy(self) -> None:
        """Split gross interest into after-subsidy interest and positive subsidy."""
        # Arrange
        frame = _schedule_frame()
        baseline_month = frame.filter((pl.col("scenario") == "Baseline") & (pl.col("month") == 1)).row(0, named=True)

        # Act
        specification = payment_composition_chart(frame, "Baseline").to_dict()

        # Assert
        rows = _chart_rows(specification)
        first_month = {row["component"]: row["amount"] for row in rows if row["month"] == 1}
        assert first_month["Interest after subsidy"] == pytest.approx(
            float(baseline_month["interest"] - baseline_month["subsidy"])
        )
        assert first_month["Subsidy"] == pytest.approx(float(baseline_month["subsidy"]))
        assert first_month["Interest after subsidy"] + first_month["Subsidy"] == pytest.approx(
            float(baseline_month["interest"])
        )
        _assert_composition_interaction(specification)

    def test_composition_chart_when_after_subsidy_expect_subsidy_omitted(self) -> None:
        """Show net interest without a separate subsidy component."""
        # Arrange
        frame = _schedule_frame()
        baseline_month = frame.filter((pl.col("scenario") == "Baseline") & (pl.col("month") == 1)).row(0, named=True)

        # Act
        specification = payment_composition_chart(frame, "Baseline", after_subsidy=True).to_dict()

        # Assert
        rows = _chart_rows(specification)
        first_month = {row["component"]: row["amount"] for row in rows if row["month"] == 1}
        assert "Subsidy" not in first_month
        assert first_month["Interest after subsidy"] == pytest.approx(
            float(baseline_month["interest"] - baseline_month["subsidy"])
        )
        _assert_composition_interaction(specification)

    def test_composition_chart_when_subsidy_excluded_expect_gross_interest_component(self) -> None:
        """Render gross interest directly when subsidy reporting is disabled."""
        # Arrange
        frame = _schedule_frame().drop("subsidy")
        baseline_month = frame.filter((pl.col("scenario") == "Baseline") & (pl.col("month") == 1)).row(0, named=True)

        # Act
        specification = payment_composition_chart(frame, "Baseline", include_subsidy=False).to_dict()

        # Assert
        rows = _chart_rows(specification)
        first_month = {row["component"]: row["amount"] for row in rows if row["month"] == 1}
        assert "Subsidy" not in first_month
        assert "Interest after subsidy" not in first_month
        assert first_month["Gross interest"] == pytest.approx(float(baseline_month["interest"]))
        _assert_composition_interaction(specification)

    def test_composition_chart_when_terminal_payment_hidden_expect_component_omitted(self) -> None:
        """Omit horizon settlement from payment composition by default."""
        # Arrange
        frame = _schedule_frame()

        # Act
        rows = _chart_rows(payment_composition_chart(frame, "Baseline").to_dict())

        # Assert
        assert "Horizon settlement" not in {row["component"] for row in rows}

    def test_composition_chart_when_terminal_payment_shown_expect_component_included(self) -> None:
        """Restore horizon settlement in payment composition when requested."""
        # Arrange
        frame = _schedule_frame()
        final_month = frame.filter(pl.col("scenario") == "Baseline").row(-1, named=True)

        # Act
        rows = _chart_rows(payment_composition_chart(frame, "Baseline", show_terminal_payment=True).to_dict())

        # Assert
        terminal_rows = [row for row in rows if row["component"] == "Horizon settlement"]
        assert terminal_rows[-1]["amount"] == pytest.approx(float(final_month["horizon_settlement"]))

    def test_composition_chart_when_not_focused_expect_unrestricted_scale(self) -> None:
        """Leave the default payment-composition scale unrestricted."""
        # Arrange
        frame = _payment_composition_focus_frame()

        # Act
        specification = payment_composition_chart(frame, "Baseline").to_dict()

        # Assert
        assert "scale" not in specification["layer"][0]["encoding"]["y"]
        assert specification["title"] == "Payment composition — Baseline"

    def test_composition_chart_when_focused_expect_monthly_stack_p99_with_exact_tooltips(self) -> None:
        """Focus on monthly visible stack totals without replacing component amounts."""
        # Arrange
        frame = _payment_composition_focus_frame()
        expected_ceiling = 800.0

        # Act
        specification = payment_composition_chart(
            frame,
            "Baseline",
            focus_on_typical_payments=True,
        ).to_dict()

        # Assert
        y_encoding = specification["layer"][0]["encoding"]["y"]
        assert y_encoding["scale"] == {"clamp": True, "domain": [0, expected_ceiling]}
        assert specification["title"] == {
            "text": "Payment composition — Baseline",
            "subtitle": (
                "Focused at the 99th percentile: 800.00 PLN. "
                "Larger values are clamped but retain their exact tooltip amounts."
            ),
        }
        assert max(row["amount"] for row in _chart_rows(specification)) == 4000.0
        tooltip_fields = {
            tooltip["field"]
            for layer in specification["layer"]
            for tooltip in layer.get("encoding", {}).get("tooltip", [])
        }
        assert {"payment_date", "month", "component", "amount"}.issubset(tooltip_fields)

    def test_composition_chart_when_focused_expect_terminal_visibility_applied_before_p99(self) -> None:
        """Include terminal settlements in the focused ceiling only when visible."""
        # Arrange
        frame = _payment_composition_focus_frame()

        # Act
        hidden_specification = payment_composition_chart(
            frame,
            "Baseline",
            focus_on_typical_payments=True,
        ).to_dict()
        shown_specification = payment_composition_chart(
            frame,
            "Baseline",
            show_terminal_payment=True,
            focus_on_typical_payments=True,
        ).to_dict()

        # Assert
        assert hidden_specification["layer"][0]["encoding"]["y"]["scale"]["domain"] == [0, 800.0]
        assert shown_specification["layer"][0]["encoding"]["y"]["scale"]["domain"] == [0, 1300.0]

    @pytest.mark.parametrize(
        ("after_subsidy", "include_subsidy", "expected_ceiling"),
        [
            pytest.param(False, True, 800.0, id="gross"),
            pytest.param(True, True, 750.0, id="after-subsidy"),
            pytest.param(False, False, 800.0, id="subsidy-disabled"),
        ],
    )
    def test_composition_chart_when_focused_expect_ceiling_from_visible_subsidy_mode(
        self,
        after_subsidy: bool,
        include_subsidy: bool,
        expected_ceiling: float,
    ) -> None:
        """Calculate the focused ceiling from the components visible in each subsidy mode."""
        # Arrange
        frame = _payment_composition_focus_frame()
        if not include_subsidy:
            frame = frame.drop("subsidy")

        # Act
        specification = payment_composition_chart(
            frame,
            "Baseline",
            after_subsidy=after_subsidy,
            include_subsidy=include_subsidy,
            focus_on_typical_payments=True,
        ).to_dict()

        # Assert
        assert specification["layer"][0]["encoding"]["y"]["scale"]["domain"] == [0, expected_ceiling]

    def test_composition_chart_when_rendered_expect_semantic_stack_order(self) -> None:
        """Place scheduled principal at the bottom and costs above principal payments."""
        # Arrange
        frame = _schedule_frame()

        # Act
        specification = payment_composition_chart(frame, "Baseline").to_dict()

        # Assert
        first_month_order = {
            row["component"]: row["component_order"] for row in _chart_rows(specification) if row["month"] == 1
        }
        assert first_month_order == {
            "Scheduled principal": 0,
            "Recurring overpayment": 1,
            "Lump sum": 2,
            "Fees": 4,
            "Interest after subsidy": 5,
            "Subsidy": 6,
        }
        assert specification["layer"][0]["encoding"]["order"] == {
            "field": "component_order",
            "sort": "ascending",
            "type": "quantitative",
        }

    def test_composition_chart_when_toggled_expect_stable_theme_colors(self) -> None:
        """Keep each shared component on the same theme color across chart modes."""
        # Arrange
        frame = _schedule_frame()
        expected_domain = [
            "Scheduled principal",
            "Recurring overpayment",
            "Lump sum",
            "Horizon settlement",
            "Fees",
            "Interest after subsidy",
            "Subsidy",
        ]

        # Act
        gross_specification = payment_composition_chart(frame, "Baseline").to_dict()
        net_specification = payment_composition_chart(frame, "Baseline", after_subsidy=True).to_dict()

        # Assert
        gross_color = gross_specification["layer"][0]["encoding"]["color"]
        net_color = net_specification["layer"][0]["encoding"]["color"]
        assert gross_color["scale"] == {"domain": expected_domain}
        assert net_color["scale"] == {"domain": expected_domain}
        assert gross_color["legend"]["values"] == [value for value in expected_domain if value != "Horizon settlement"]
        assert net_color["legend"]["values"] == [
            value for value in expected_domain[:-1] if value != "Horizon settlement"
        ]


def _schedule_frame(*, first_payment_date: date | None = None) -> pl.DataFrame:
    terms = (
        default_mortgage_terms()
        if first_payment_date is None
        else default_mortgage_terms(first_payment_date=first_payment_date)
    )
    results = [
        simulate(terms, OverpaymentScenario(name="Baseline")),
        simulate(
            terms,
            OverpaymentScenario(
                name="Overpayment",
                recurring_amount=Decimal("1500"),
                recurring_start_month=37,
            ),
        ),
    ]
    return schedule_frame(results)


def _cash_outflow_focus_frame() -> pl.DataFrame:
    payment_dates = pl.date_range(date(2024, 1, 1), date(2024, 2, 19), interval="1d", eager=True).to_list()
    rows = []
    for scenario, terminal_outflow in (("Baseline", 10000.0), ("Overpayment", 20000.0)):
        for month, payment_date in enumerate(payment_dates, start=1):
            is_terminal_month = month == len(payment_dates)
            rows.append(
                {
                    "scenario": scenario,
                    "month": month,
                    "payment_date": payment_date,
                    "cash_outflow": terminal_outflow if is_terminal_month else 100.0,
                    "horizon_settlement": terminal_outflow - 100.0 if is_terminal_month else 0.0,
                }
            )
    return pl.DataFrame(rows)


def _payment_composition_focus_frame() -> pl.DataFrame:
    penultimate_month = 99
    final_month = 100
    payment_dates = pl.date_range(date(2024, 1, 1), date(2024, 4, 9), interval="1d", eager=True).to_list()
    rows = []
    for month, payment_date in enumerate(payment_dates, start=1):
        multiplier = 100.0 if month == final_month else 10.0 if month == penultimate_month else 1.0
        rows.append(
            {
                "scenario": "Baseline",
                "month": month,
                "payment_date": payment_date,
                "scheduled_principal": 40.0 * multiplier,
                "recurring_overpayment": 0.0,
                "lump_sum": 0.0,
                "horizon_settlement": (
                    500.0 if month == penultimate_month else 5000.0 if month == final_month else 0.0
                ),
                "fees": 10.0 * multiplier,
                "interest": 30.0 * multiplier,
                "subsidy": 5.0 * multiplier,
            }
        )
    return pl.DataFrame(rows)


def _chart_rows(specification: dict[str, Any]) -> list[dict[str, Any]]:
    datasets = specification.get("datasets")
    if not isinstance(datasets, dict) or len(datasets) != 1:
        raise AssertionError("expected one embedded chart dataset")
    rows = next(iter(datasets.values()))
    if not isinstance(rows, list):
        raise AssertionError("expected embedded chart rows")
    return cast(list[dict[str, Any]], rows)


def _assert_scenario_hover(specification: dict[str, Any], value_column: str) -> None:
    assert specification["height"] == 360
    assert {"line", "rule", "point"}.issubset(_marks(specification))
    _assert_nearest_month_selection(specification)
    serialized = str(specification)
    assert "scenario" in serialized
    assert value_column in serialized
    assert "month" in serialized
    assert "payment_date" in serialized
    assert "%d/%m/%Y" in serialized
    assert ",.2f" in serialized


def _assert_composition_interaction(specification: dict[str, Any]) -> None:
    assert {"area", "rule", "point"}.issubset(_marks(specification))
    _assert_nearest_month_selection(specification)
    serialized = str(specification)
    assert "component" in serialized
    assert "amount" in serialized
    assert "month" in serialized
    assert "payment_date" in serialized
    assert "%d/%m/%Y" in serialized
    assert ",.2f" in serialized
    assert any(parameter.get("bind") == "scales" for parameter in specification["params"])


def _assert_nearest_month_selection(specification: dict[str, Any]) -> None:
    parameters = _selection_parameters(specification)
    nearest = next(parameter for parameter in parameters if parameter["name"] == "nearest_month")
    assert nearest["select"]["nearest"] is True
    assert nearest["select"]["fields"] == ["payment_date"]


def _assert_current_date_rule(specification: dict[str, Any], today: date) -> None:
    rules = _current_date_rules(specification)
    assert len(rules) == 1
    rule = rules[0]
    assert rule["mark"] == {
        "type": "rule",
        "color": "#6B7280",
        "strokeDash": [6, 4],
    }
    assert rule["encoding"] == {
        "tooltip": {"value": f"Today: {today:%d/%m/%Y}"},
        "x": {"datum": {"year": today.year, "month": today.month, "date": today.day}},
    }


def _current_date_rules(specification: dict[str, Any]) -> list[dict[str, Any]]:
    rules = []
    mark = specification.get("mark")
    if isinstance(mark, dict) and mark.get("type") == "rule" and mark.get("strokeDash"):
        rules.append(specification)
    for child in specification.get("layer", []):
        rules.extend(_current_date_rules(child))
    return rules


def _marks(specification: dict[str, Any]) -> set[str]:
    marks: set[str] = set()
    mark = specification.get("mark")
    if isinstance(mark, str):
        marks.add(mark)
    elif isinstance(mark, dict) and isinstance(mark.get("type"), str):
        marks.add(mark["type"])
    for child in specification.get("layer", []):
        marks.update(_marks(child))
    return marks


def _selection_parameters(specification: dict[str, Any]) -> list[dict[str, Any]]:
    parameters = list(specification.get("params", []))
    for child in specification.get("layer", []):
        parameters.extend(_selection_parameters(child))
    return parameters
