"""Altair visualizations built from reporting output."""

from datetime import date
from typing import cast

import altair as alt
import polars as pl

CHART_HEIGHT = 360
AREA_OPACITY = 0.22
HOVER_POINT_SIZE = 70
CURRENT_DATE_RULE_COLOR = "#6B7280"
CURRENT_DATE_RULE_DASH = (6, 4)
TYPICAL_PAYMENT_QUANTILE = 0.99
SCENARIO_COLORS = ("#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2")
PAYMENT_COMPONENT_LABELS = {
    "scheduled_principal": "Scheduled principal",
    "recurring_overpayment": "Recurring overpayment",
    "lump_sum": "Lump sum",
    "horizon_settlement": "Horizon settlement",
    "fees": "Fees",
    "interest": "Gross interest",
    "interest_after_subsidy": "Interest after subsidy",
    "subsidy": "Subsidy",
}
PAYMENT_COMPONENTS = (
    "scheduled_principal",
    "recurring_overpayment",
    "lump_sum",
    "horizon_settlement",
    "fees",
    "interest_after_subsidy",
    "subsidy",
)
PAYMENT_COMPONENT_ORDER = {component: order for order, component in enumerate(PAYMENT_COMPONENTS)}
PAYMENT_COMPONENT_ORDER["interest"] = PAYMENT_COMPONENT_ORDER["interest_after_subsidy"]
PAYMENT_COMPONENT_COLOR_DOMAIN = tuple(PAYMENT_COMPONENT_LABELS[component] for component in PAYMENT_COMPONENTS)


def balance_chart(frame: pl.DataFrame, *, filled: bool = False) -> alt.LayerChart:
    """Build the remaining-principal comparison chart.

    Args:
        frame: Long schedule frame containing every scenario month.

    Returns:
        An interactive scenario chart with optional area fill.
    """
    return _scenario_chart(frame, "closing_balance", "Remaining principal", filled=filled)


def cash_outflow_chart(
    frame: pl.DataFrame,
    *,
    filled: bool = False,
    show_terminal_payment: bool = False,
    focus_on_typical_payments: bool = False,
) -> alt.LayerChart:
    """Build the monthly cash-outflow comparison chart.

    Args:
        frame: Long schedule frame containing every scenario month.
        filled: Whether to fill the area beneath each scenario line.
        show_terminal_payment: Whether horizon settlement contributes to plotted cash outflow.
        focus_on_typical_payments: Whether to clamp the y-axis at the nearest-value 99th percentile.

    Returns:
        An interactive scenario chart with optional area fill.
    """
    if not show_terminal_payment:
        frame = frame.with_columns((pl.col("cash_outflow") - pl.col("horizon_settlement")).alias("cash_outflow"))
    y_max, title = _focused_payment_axis(
        frame,
        "cash_outflow",
        "Monthly cash outflow",
        focus=focus_on_typical_payments,
    )
    return _scenario_chart(frame, "cash_outflow", title, filled=filled, y_max=y_max)


def payment_composition_chart(
    frame: pl.DataFrame,
    scenario_name: str,
    *,
    after_subsidy: bool = False,
    show_terminal_payment: bool = False,
    include_subsidy: bool = True,
    focus_on_typical_payments: bool = False,
) -> alt.LayerChart:
    """Build a stacked payment-component chart for one scenario.

    Args:
        frame: Long schedule frame containing every scenario month.
        scenario_name: Scenario to select from the frame.
        after_subsidy: Whether to omit the separate subsidy band and show net interest only.
        show_terminal_payment: Whether to include horizon settlement in the composition.
        include_subsidy: Whether the input and chart include subsidy values.
        focus_on_typical_payments: Whether to clamp the y-axis at the nearest-value 99th percentile.

    Returns:
        A stacked area chart of principal, net interest, subsidy when selected, and fees.
    """
    selected = _payment_composition_frame(
        frame,
        scenario_name,
        after_subsidy=after_subsidy,
        show_terminal_payment=show_terminal_payment,
        include_subsidy=include_subsidy,
    )
    visible_labels = [
        PAYMENT_COMPONENT_LABELS[component]
        for component in _payment_components(after_subsidy, show_terminal_payment, include_subsidy)
    ]
    monthly_totals = selected.group_by("scenario", "month", "payment_date").agg(pl.col("amount").sum())
    y_max, title = _focused_payment_axis(
        monthly_totals,
        "amount",
        f"Payment composition — {scenario_name}",
        focus=focus_on_typical_payments,
    )
    nearest_month = _nearest_month_selection()
    y_scale = alt.Undefined if y_max is None else alt.Scale(domain=[0, y_max], clamp=True)
    base = alt.Chart(selected).encode(
        x=alt.X("payment_date:T", title="Payment date", axis=alt.Axis(format="%d/%m/%Y")),
        y=alt.Y(
            "amount:Q",
            title="Amount (PLN)",
            stack="zero",
            axis=alt.Axis(format=",.0f"),
            scale=y_scale,
        ),
        color=alt.Color(
            "component:N",
            title="Component",
            scale=alt.Scale(
                domain=list(
                    PAYMENT_COMPONENT_COLOR_DOMAIN
                    if include_subsidy
                    else (*PAYMENT_COMPONENT_COLOR_DOMAIN[:5], PAYMENT_COMPONENT_LABELS["interest"])
                )
            ),
            legend=alt.Legend(values=visible_labels),
        ),
        order=alt.Order("component_order:Q", sort="ascending"),
    )
    area = base.mark_area()
    selector = base.mark_point(opacity=0).add_params(  # ty: ignore[unresolved-attribute]  # Altair fluent API.
        nearest_month
    )
    points = base.mark_point(size=HOVER_POINT_SIZE).encode(  # ty: ignore[unresolved-attribute]  # Altair fluent API.
        opacity=alt.condition(nearest_month, alt.value(1), alt.value(0)),
        tooltip=[
            alt.Tooltip("payment_date:T", title="Payment date", format="%d/%m/%Y"),
            alt.Tooltip("month:Q", title="Simulation month", format=".0f"),
            alt.Tooltip("component:N", title="Component"),
            alt.Tooltip("amount:Q", title="Amount (PLN)", format=",.2f"),
        ],
    )
    rule = (
        alt.Chart(selected)
        .mark_rule(color="#9CA3AF")
        .encode(x="payment_date:T")  # ty: ignore[unresolved-attribute]  # Altair fluent API.
        .transform_filter(nearest_month)
    )
    layers = [area]
    current_date_rule = _current_date_rule(selected)
    if current_date_rule is not None:
        layers.append(current_date_rule)
    layers.extend([selector, points, rule])
    return (
        alt.LayerChart(
            layer=layers  # ty: ignore[invalid-argument-type]  # ty cannot model Altair's generated chart types.
        )
        .properties(title=title, height=CHART_HEIGHT)
        .add_params(alt.selection_interval(bind="scales"))
    )


def _payment_composition_frame(
    frame: pl.DataFrame,
    scenario_name: str,
    *,
    after_subsidy: bool,
    show_terminal_payment: bool,
    include_subsidy: bool,
) -> pl.DataFrame:
    components = _payment_components(after_subsidy, show_terminal_payment, include_subsidy)
    selected = frame.filter(pl.col("scenario") == scenario_name)
    if include_subsidy:
        selected = selected.with_columns((pl.col("interest") - pl.col("subsidy")).alias("interest_after_subsidy"))
    return (
        selected.unpivot(
            on=components,
            index=["scenario", "month", "payment_date"],
            variable_name="component",
            value_name="amount",
        )
        .with_columns(
            pl.col("component").replace_strict(PAYMENT_COMPONENT_ORDER).alias("component_order"),
            pl.col("component").replace_strict(PAYMENT_COMPONENT_LABELS),
        )
        .with_columns(pl.col("amount").cast(pl.Float64))
    )


def _focused_payment_axis(
    frame: pl.DataFrame,
    value_column: str,
    title: str,
    *,
    focus: bool,
) -> tuple[float | None, str | alt.Title]:
    if not focus:
        return None, title
    ceiling = float(
        frame.select(pl.col(value_column).quantile(TYPICAL_PAYMENT_QUANTILE, interpolation="nearest")).item()
    )
    focused_title = alt.Title(
        title,
        subtitle=(
            f"Focused at the 99th percentile: {ceiling:,.2f} PLN. "
            "Larger values are clamped but retain their exact tooltip amounts."
        ),
    )
    return ceiling, focused_title


def _payment_components(
    after_subsidy: bool,
    show_terminal_payment: bool,
    include_subsidy: bool = True,
) -> tuple[str, ...]:
    if include_subsidy:
        components = PAYMENT_COMPONENTS[:-1] if after_subsidy else PAYMENT_COMPONENTS
    else:
        components = (*PAYMENT_COMPONENTS[:5], "interest")
    if show_terminal_payment:
        return components
    return tuple(component for component in components if component != "horizon_settlement")


def _nearest_month_selection() -> alt.Parameter:
    return alt.selection_point(
        name="nearest_month",
        nearest=True,
        on="pointerover",
        fields=["payment_date"],
        empty=False,
        clear="pointerout",
    )


def _scenario_color(scenarios: list[str]) -> alt.Color:
    return alt.Color(
        "scenario:N",
        title="Scenario",
        scale=alt.Scale(domain=scenarios, range=list(SCENARIO_COLORS[: len(scenarios)])),
    )


def _scenario_tooltips(value_column: str) -> list[alt.Tooltip]:
    return [
        alt.Tooltip("payment_date:T", title="Payment date", format="%d/%m/%Y"),
        alt.Tooltip("month:Q", title="Simulation month", format=".0f"),
        alt.Tooltip("scenario:N", title="Scenario"),
        alt.Tooltip(f"{value_column}:Q", title="Amount (PLN)", format=",.2f"),
    ]


def _current_date_rule(frame: pl.DataFrame) -> alt.Chart | None:
    today = date.today()
    payment_dates = frame.get_column("payment_date")
    first_payment_date = cast(date, payment_dates.min())
    last_payment_date = cast(date, payment_dates.max())
    if today < first_payment_date or today > last_payment_date:
        return None
    return cast(
        alt.Chart,
        alt.Chart(frame)  # ty: ignore[unresolved-attribute]  # Altair fluent API.
        .transform_aggregate(current_date_row_count="count()")
        .mark_rule(color=CURRENT_DATE_RULE_COLOR, strokeDash=list(CURRENT_DATE_RULE_DASH))
        .encode(x=alt.datum(today), tooltip=alt.value(f"Today: {today:%d/%m/%Y}")),
    )


def _scenario_chart(
    frame: pl.DataFrame,
    value_column: str,
    title: str | alt.Title,
    *,
    filled: bool,
    y_max: float | None = None,
) -> alt.LayerChart:
    scenarios = frame.get_column("scenario").unique(maintain_order=True).to_list()
    chart_frame = frame.select(
        "scenario",
        "month",
        "payment_date",
        pl.col(value_column).cast(pl.Float64),
    )
    nearest_month = _nearest_month_selection()
    y_scale = alt.Undefined if y_max is None else alt.Scale(domain=[0, y_max], clamp=True)
    base = alt.Chart(chart_frame).encode(
        x=alt.X("payment_date:T", title="Payment date", axis=alt.Axis(format="%d/%m/%Y")),
        y=alt.Y(
            f"{value_column}:Q",
            title="Amount (PLN)",
            axis=alt.Axis(format=",.0f"),
            scale=y_scale,
        ),
        color=_scenario_color(scenarios),
    )
    layers = []
    if filled:
        layers.append(base.mark_area(opacity=AREA_OPACITY))
    layers.append(base.mark_line())
    current_date_rule = _current_date_rule(chart_frame)
    if current_date_rule is not None:
        layers.append(current_date_rule)
    layers.extend(
        [
            base.mark_point(opacity=0).add_params(  # ty: ignore[unresolved-attribute]  # Altair fluent API.
                nearest_month
            ),
            base.mark_point(size=HOVER_POINT_SIZE).encode(  # ty: ignore[unresolved-attribute]  # Altair fluent API.
                opacity=alt.condition(nearest_month, alt.value(1), alt.value(0)),
                tooltip=_scenario_tooltips(value_column),
            ),
            alt.Chart(chart_frame)  # ty: ignore[unresolved-attribute]  # Altair fluent API.
            .mark_rule(color="#9CA3AF")
            .encode(x="payment_date:T")
            .transform_filter(nearest_month),
        ]
    )
    return (
        alt.LayerChart(layer=layers)
        .properties(title=title, height=CHART_HEIGHT)
        .add_params(alt.selection_interval(bind="scales"))
    )
