"""Investment ledgers, comparisons, and downloads."""

import polars as pl
import streamlit as st

from mortgage_simulator.app.presentation.result_metrics import (
    INVESTMENT_EARNINGS_HELP,
    MORTGAGE_COST_HELP,
    NET_FINANCING_COST_HELP,
    RETAINED_SURPLUS_HELP,
)
from mortgage_simulator.simulation.models import SimulationResult


def render_investment_results(result: SimulationResult) -> None:
    """Display the selected result's investment metrics and downloadable ledgers."""
    investment = result.investment
    if investment is None:
        return
    with st.expander("Investment outcome", expanded=False):
        st.caption(
            "Net financing cost = Total mortgage cost - Net investment earnings. "
            "Retained surplus is reported separately."
        )
        columns = st.columns(2)
        columns[0].metric("Applied to mortgage", f"{investment.applied_repayment:,.2f} PLN")
        columns[1].metric("Retained surplus", f"{investment.retained_surplus:,.2f} PLN", help=RETAINED_SURPLUS_HELP)
        st.caption(
            f"Gross deposit interest: {investment.gross_interest:,.2f} PLN · Deposit tax: {investment.tax:,.2f} PLN · "
            f"Completed in month {investment.completion_month}"
        )
        if investment.terms:
            ledger = pl.DataFrame(
                [
                    {
                        "Maturity month": term.maturity_month,
                        "Opening balance (PLN)": float(term.opening_balance),
                        "Gross deposit interest (PLN)": float(term.gross_interest),
                        "Deposit tax (PLN)": float(term.tax),
                        "Closing balance (PLN)": float(term.closing_balance),
                    }
                    for term in investment.terms
                ]
            )
            st.dataframe(ledger, hide_index=True, width="stretch")
            st.download_button("Download investment ledger", ledger.write_csv(), "investment-ledger.csv", "text/csv")
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
                candidates = pl.DataFrame(
                    [
                        {
                            "Recommended": index == 0,
                            "Terms": candidate.term_count,
                            "Completion month": candidate.repayment_month,
                            "Net financing cost (PLN)": float(candidate.net_financing_cost),
                            "Total mortgage cost (PLN)": float(candidate.total_mortgage_cost),
                            "Ending debt (PLN)": float(candidate.ending_balance),
                            "Net investment earnings (PLN)": float(candidate.investment.net_earnings),
                            "Retained surplus (PLN)": float(candidate.investment.retained_surplus),
                        }
                        for index, candidate in enumerate(result.investment_candidates)
                    ]
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
