from __future__ import annotations

from typing import Any, Literal

GateDecision = Literal["include", "exclude", "unclear"]


def _matches(answer: dict[str, Any], condition: dict[str, Any]) -> bool:
    value = answer.get(condition["field"])
    if "equals" in condition:
        return value == condition["equals"]
    if "in" in condition:
        return value in condition["in"]
    raise ValueError(f"Unsupported gate condition: {condition}")


def gate_answer(answer: dict[str, Any], role_config: dict[str, Any]) -> GateDecision:
    if any(_matches(answer, rule) for rule in role_config.get("unclear_if", [])):
        return "unclear"
    if any(_matches(answer, rule) for rule in role_config.get("exclude_if", [])):
        return "exclude"
    return "include"


def route_round_a(
    answers: dict[str, dict[str, Any]], config: dict[str, Any]
) -> tuple[str, dict[str, GateDecision]]:
    role_configs = config["round_a"]
    decisions = {
        role: gate_answer(answers[role], role_config)
        for role, role_config in role_configs.items()
    }
    route = (
        config["routing"]["round_a_all_include"]
        if all(value == "include" for value in decisions.values())
        else config["routing"]["round_a_otherwise"]
    )
    return route, decisions


def route_adjudicated(answer: dict[str, Any], config: dict[str, Any]) -> tuple[str, GateDecision]:
    decision = gate_answer(answer, config["adjudication"])
    route = config["routing"][f"adjudicated_{decision}"]
    return route, decision
