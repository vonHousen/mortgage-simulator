"""Optional local defaults for Streamlit overpayment scenarios."""

from pydantic import BaseModel, ConfigDict, ValidationError

from mortgage_simulator.settings import AppSettings
from mortgage_simulator.simulation.models import MortgageTerms, OverpaymentScenario, SimulationRequest


class ScenarioFileConfig(BaseModel):
    """Validated contents of the optional local scenario configuration file."""

    model_config = ConfigDict(frozen=True)

    scenarios: tuple[OverpaymentScenario, ...]


def load_local_scenarios(settings: AppSettings, terms: MortgageTerms) -> tuple[OverpaymentScenario, ...]:
    """Load and validate optional local scenario defaults.

    Args:
        settings: Environment-backed settings containing the selected path and baseline identity.
        terms: Complete mortgage terms used to validate scenario payment months.

    Returns:
        Validated overpayment scenarios in file order.

    Raises:
        OSError: If the configured path exists but cannot be read.
        ValueError: If the JSON document or its scenarios are invalid.
    """
    path = settings.scenarios.config_path
    if not path.exists():
        return ()
    try:
        local_config = ScenarioFileConfig.model_validate_json(path.read_bytes(), extra="forbid")
        SimulationRequest(
            terms=terms,
            scenarios=(OverpaymentScenario(name=settings.scenarios.baseline_name), *local_config.scenarios),
        )
    except ValidationError as error:
        raise ValueError(f"invalid local scenario configuration at {path}: {error}") from error
    return local_config.scenarios
