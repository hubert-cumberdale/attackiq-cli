import pytest

from attackiq_cli.joiner.join import (
    Assessment,
    Scenario,
    join_assessments_to_scenarios,
    validate_scenario_techniques,
)


def test_validate_scenario_technique_fails_on_malformed() -> None:
    scenarios = [
        Scenario(
            scenario_id="1",
            name="Scenario One",
            technique="BAD",
            supported_platforms="Windows",
            capabilities="",
        )
    ]

    with pytest.raises(ValueError):
        validate_scenario_techniques(scenarios, fail_on_malformed=True)


def test_join_assessments_requires_scenario_id() -> None:
    assessments = [Assessment(assessment_id="1", name="Assessment", scenario_id="")]
    scenarios = [
        Scenario(
            scenario_id="1",
            name="Scenario One",
            technique="T1003",
            supported_platforms="Windows",
            capabilities="",
        )
    ]

    with pytest.raises(ValueError):
        join_assessments_to_scenarios(
            assessments,
            scenarios,
            fail_on_missing_scenario=True,
        )

