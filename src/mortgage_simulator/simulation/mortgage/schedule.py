"""Mortgage schedule iteration and result assembly."""

from decimal import Decimal

from mortgage_simulator.simulation.models import MonthlyPayment, MortgageTerms, OverpaymentScenario, SimulationResult
from mortgage_simulator.simulation.mortgage.payment import calculate_payment
from mortgage_simulator.simulation.mortgage.summary import summarize

ZERO = Decimal("0")


def calculate_schedule(terms: MortgageTerms, scenario: OverpaymentScenario) -> SimulationResult:
    """Return mortgage payments and summary for the supplied terms and scenario."""
    payments = _calculate_payments(terms, scenario)
    return SimulationResult(scenario_name=scenario.name, payments=payments, summary=summarize(payments, terms))


def _calculate_payments(terms: MortgageTerms, scenario: OverpaymentScenario) -> tuple[MonthlyPayment, ...]:
    opening_balance = terms.principal
    previous_opening_balance = opening_balance
    payments: list[MonthlyPayment] = []
    for month in range(1, terms.analysis_horizon_months + 1):
        payment = calculate_payment(terms, scenario, month, opening_balance, previous_opening_balance)
        payments.append(payment)
        previous_opening_balance = opening_balance
        opening_balance = payment.closing_balance
        if opening_balance == ZERO:
            break
    return tuple(payments)
