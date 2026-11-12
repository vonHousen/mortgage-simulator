"""Session-backed deposit editor on the overpayment scenarios page."""

from decimal import Decimal
from typing import cast

import polars as pl
import streamlit as st
from pydantic import ValidationError

from mortgage_simulator.simulation.models import DepositInvestment, InvestmentMode, MortgageTerms

INVESTMENTS_KEY = "scenario_investments"
DRAFT_KEY = "investment_draft"


def get_investments() -> dict[str, DepositInvestment]:
    """Return applied deposit settings keyed by scenario name."""
    return cast(dict[str, DepositInvestment], st.session_state[INVESTMENTS_KEY])


def render_investment_controls(names: list[str], terms: MortgageTerms) -> bool:
    """Render deposit management for scenario names and terms; return whether edits are pending."""
    investments = get_investments()
    with st.container(border=True):
        st.subheader("Invest before overpaying")
        st.caption("Invest a lump sum, renew after tax, then use the balance to repay your mortgage.")
        unknown = set(investments) - set(names)
        if unknown:
            st.error("Investment refers to a renamed or removed scenario: " + ", ".join(sorted(unknown)))
        if investments:
            st.dataframe(
                pl.DataFrame(
                    [
                        {
                            "Scenario": name,
                            "Capital (PLN)": float(item.initial_amount),
                            "Annual gross rate (%)": float(item.annual_rate * 100),
                            "Term (months)": item.term_months,
                            "Mode": item.mode.value,
                            "Terms before repayment": item.term_count,
                        }
                        for name, item in investments.items()
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Add an investment to compare overpaying now with investing first.")
        available = [name for name in names if name not in investments]
        selected = st.selectbox("Investment to manage", list(investments), disabled=not investments)
        with st.container(horizontal=True):
            if st.button("Add investment", disabled=not available):
                _open_draft(available[0], None)
            if st.button("Edit investment", disabled=selected is None):
                assert selected is not None
                _open_draft(selected, investments[selected])
            if st.button("Remove investment", disabled=selected is None):
                assert selected is not None
                del investments[selected]
                st.rerun()
        if DRAFT_KEY in st.session_state:
            _render_draft(names, terms)
    return DRAFT_KEY in st.session_state or bool(set(investments) - set(names))


def _open_draft(name: str, investment: DepositInvestment | None) -> None:
    st.session_state[DRAFT_KEY] = name
    st.session_state["deposit_scenario"] = name
    st.session_state["deposit_capital"] = float(investment.initial_amount) if investment else 10000.0
    st.session_state["deposit_start"] = investment.start_month if investment else 1
    st.session_state["deposit_rate"] = float(investment.annual_rate * 100) if investment else 0.0
    st.session_state["deposit_term"] = investment.term_months if investment else 3
    st.session_state["deposit_mode"] = investment.mode.value if investment else "manual"
    st.session_state["deposit_count"] = (investment.term_count or 0) if investment else 1


def _render_draft(names: list[str], terms: MortgageTerms) -> None:
    st.markdown("**Investment settings**")
    original = cast(str, st.session_state[DRAFT_KEY])
    choices = [name for name in names if name == original or name not in get_investments()]
    if original not in choices:
        choices.insert(0, original)
    name = st.selectbox("Scenario for investment", choices, key="deposit_scenario", persist_state="session")
    left, right = st.columns(2)
    with left:
        capital = st.number_input(
            "Initial capital (PLN)", min_value=0.01, step=1000.0, key="deposit_capital", persist_state="session"
        )
        start = st.number_input(
            "Investment start month", min_value=1, step=1, key="deposit_start", persist_state="session"
        )
    with right:
        rate = st.number_input(
            "Annual gross deposit rate (%)", min_value=0.0, step=0.1, key="deposit_rate", persist_state="session"
        )
        term = st.number_input(
            "Deposit term (months)", min_value=1, step=1, key="deposit_term", persist_state="session"
        )
        st.caption(f"{term // 12} years, {term % 12} months. Interest credited only at maturity.")
    mode = st.segmented_control(
        "Repayment timing",
        ["manual", "automatic"],
        key="deposit_mode",
        required=True,
        format_func=str.title,
        persist_state="session",
    )
    count = st.number_input(
        "Terms before repayment (0 = immediate)", min_value=0, step=1, key="deposit_count", disabled=mode == "automatic"
    )
    if mode == "manual":
        maturity = start + count * term
        month_index = terms.first_payment_date.year * 12 + terms.first_payment_date.month - 1 + maturity - 1
        year, month = divmod(month_index, 12)
        st.caption(
            f"Planned repayment: month {maturity} ({year:04d}-{month + 1:02d}-{terms.first_payment_date.day:02d})."
        )
    else:
        st.caption("Compare immediate repayment and every maturity within the horizon. Minimize Total mortgage cost.")
    st.caption("19% tax at each maturity. If the mortgage ends sooner, finish the current term without renewing.")
    with st.container(horizontal=True):
        if st.button("Apply investment", type="primary"):
            try:
                item = DepositInvestment(
                    initial_amount=Decimal(str(capital)),
                    start_month=start,
                    annual_rate=Decimal(str(rate)) / 100,
                    term_months=term,
                    mode=InvestmentMode(mode or "manual"),
                    term_count=count if mode == "manual" else None,
                )
                if start + (item.term_count or 0) * term > terms.analysis_horizon_months:
                    raise ValueError("Investment start and maturity must fit within the analysis horizon.")
                if name not in names:
                    raise ValueError("Choose an existing scenario.")
            except (ValidationError, ValueError) as error:
                st.error(str(error))
            else:
                get_investments().pop(original, None)
                get_investments()[name] = item
                del st.session_state[DRAFT_KEY]
                st.rerun()
        if st.button("Cancel"):
            del st.session_state[DRAFT_KEY]
            st.rerun()
