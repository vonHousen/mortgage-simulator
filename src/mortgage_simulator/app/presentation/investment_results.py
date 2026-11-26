"""Investment ledgers, comparisons, and downloads."""

import polars as pl
import streamlit as st

from mortgage_simulator.app.presentation.result_metrics import (
    INVESTMENT_EARNINGS_HELP,
    MORTGAGE_COST_HELP,
    NET_FINANCING_COST_HELP,
    RETAINED_SURPLUS_HELP,
)
from mortgage_simulator.reporting.investment_schedules import (
    deposit_outcomes_frame,
    investment_candidates_frame,
    investment_ledger_frame,
)
from mortgage_simulator.simulation.models import SimulationResult


def render_investment_results(result: SimulationResult) -> None:
    """Display the selected result's investment metrics and downloadable ledgers."""
    investment = result.investment
    totals = result.investment_totals
    if totals is None:
        return
    with st.expander("Investment outcome", expanded=False):
        st.caption(
            "Net financing cost = Total mortgage cost - Net investment earnings. "
            "Retained surplus is reported separately."
        )
        columns = st.columns(2)
        columns[0].metric("Applied to mortgage", f"{totals.applied_repayment:,.2f} PLN")
        columns[1].metric("Retained surplus", f"{totals.retained_surplus:,.2f} PLN", help=RETAINED_SURPLUS_HELP)
        timing = f" · Completed in month {investment.completion_month}" if investment is not None else ""
        st.caption(
            f"Gross deposit interest: {totals.gross_interest:,.2f} PLN · Deposit tax: {totals.tax:,.2f} PLN{timing}"
        )
        if result.investments and investment is None:
            deposits = deposit_outcomes_frame(result)
            st.dataframe(
                _display_frame(
                    deposits,
                    {
                        "investment_index": "Entry",
                        "opening_month": "Planned opening month",
                        "completion_month": "Payout month",
                        "initial_amount": "Capital (PLN)",
                        "gross_interest": "Gross deposit interest (PLN)",
                        "tax": "Deposit tax (PLN)",
                        "net_earnings": "Net investment earnings (PLN)",
                        "applied_repayment": "Applied to mortgage (PLN)",
                        "retained_surplus": "Retained surplus (PLN)",
                    },
                ),
                hide_index=True,
                width="stretch",
            )
            st.download_button("Download deposit outcomes", deposits.write_csv(), "investment-deposits.csv", "text/csv")
        terms = investment_ledger_frame(result)
        if not terms.is_empty():
            ledger = _display_frame(
                terms,
                {
                    "investment_index": "Entry",
                    "opening_month": "Opening month",
                    "maturity_month": "Maturity month",
                    "opening_balance": "Opening balance (PLN)",
                    "gross_interest": "Gross deposit interest (PLN)",
                    "tax": "Deposit tax (PLN)",
                    "closing_balance": "Closing balance (PLN)",
                },
            )
            st.dataframe(ledger, hide_index=True, width="stretch")
            st.download_button("Download investment ledger", terms.write_csv(), "investment-ledger.csv", "text/csv")
        if len(result.investment_candidates) > 1:
            immediate = next(c for c in result.investment_candidates if c.term_count == 0)
            winner = result.investment_candidates[0]
            with st.expander(
                f"Recommended: {winner.term_count} deposit terms, completing in month {winner.repayment_month}.",
                expanded=False,
            ):
                st.caption(
                    f"Net financing savings versus immediate repayment: "
                    f"{immediate.net_financing_cost - winner.net_financing_cost:,.2f} PLN."
                )
                candidates = _display_frame(
                    investment_candidates_frame(result),
                    {
                        "recommended": "Recommended",
                        "term_count": "Terms",
                        "repayment_month": "Completion month",
                        "net_financing_cost": "Net financing cost (PLN)",
                        "total_mortgage_cost": "Total mortgage cost (PLN)",
                        "ending_balance": "Ending debt (PLN)",
                        "net_earnings": "Net investment earnings (PLN)",
                        "retained_surplus": "Retained surplus (PLN)",
                    },
                )
                st.dataframe(
                    candidates,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Net financing cost (PLN)": st.column_config.NumberColumn(help=NET_FINANCING_COST_HELP),
                        "Total mortgage cost (PLN)": st.column_config.NumberColumn(help=MORTGAGE_COST_HELP),
                        "Net investment earnings (PLN)": st.column_config.NumberColumn(help=INVESTMENT_EARNINGS_HELP),
                        "Retained surplus (PLN)": st.column_config.NumberColumn(help=RETAINED_SURPLUS_HELP),
                    },
                )
                st.download_button(
                    "Download repayment candidates", candidates.write_csv(), "investment-candidates.csv", "text/csv"
                )


def _display_frame(frame: pl.DataFrame, labels: dict[str, str]) -> pl.DataFrame:
    return frame.drop("scenario").with_columns(pl.col(pl.String).cast(pl.Float64)).rename(labels)
