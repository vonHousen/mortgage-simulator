"""Investment ledgers, comparisons, and downloads."""

import polars as pl
import streamlit as st

from mortgage_simulator.simulation.models import SimulationResult


def render_investment_results(result: SimulationResult) -> None:
    """Display the selected result's investment metrics and downloadable ledgers."""
    investment = result.investment
    if investment is None:
        return
    st.subheader("Investment outcome")
    st.caption("Investment earnings and retained money are separate from Total mortgage cost.")
    columns = st.columns(3)
    columns[0].metric("Net investment earnings", f"{investment.net_earnings:,.2f} PLN")
    columns[1].metric("Applied to mortgage", f"{investment.applied_repayment:,.2f} PLN")
    columns[2].metric("Retained surplus", f"{investment.retained_surplus:,.2f} PLN")
    st.caption(
        f"Gross interest: {investment.gross_interest:,.2f} PLN · Tax: {investment.tax:,.2f} PLN · "
        f"Completed in month {investment.completion_month}"
    )
    if investment.terms:
        ledger = pl.DataFrame(
            [
                {
                    "Maturity month": term.maturity_month,
                    "Opening balance (PLN)": float(term.opening_balance),
                    "Gross interest (PLN)": float(term.gross_interest),
                    "Tax (PLN)": float(term.tax),
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
        st.markdown(
            f"**Recommended: {winner.term_count} deposit terms**, completing in month {winner.repayment_month}."
        )
        st.caption(
            f"Mortgage-cost savings versus immediate repayment: "
            f"{immediate.total_mortgage_cost - winner.total_mortgage_cost:,.2f} PLN."
        )
        candidates = pl.DataFrame(
            [
                {
                    "Recommended": index == 0,
                    "Terms": candidate.term_count,
                    "Completion month": candidate.repayment_month,
                    "Total mortgage cost (PLN)": float(candidate.total_mortgage_cost),
                    "Ending debt (PLN)": float(candidate.ending_balance),
                    "Net investment earnings (PLN)": float(candidate.investment.net_earnings),
                    "Retained surplus (PLN)": float(candidate.investment.retained_surplus),
                }
                for index, candidate in enumerate(result.investment_candidates)
            ]
        )
        st.dataframe(candidates, hide_index=True, width="stretch")
        st.download_button(
            "Download repayment candidates", candidates.write_csv(), "investment-candidates.csv", "text/csv"
        )
