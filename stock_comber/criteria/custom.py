"""User-defined custom criteria.

A custom criterion is a small rule of the form ``{metric} {op} {value}`` applied
to the computed metric bundle. Users define them in ``config["custom"]["criteria"]``
(or pass them to the web API), letting them screen on any metric without code.

Example config:
    custom:
      pass_ratio: 1.0
      criteria:
        - {name: "Cheap", metric: pe_ratio, op: "<=", value: 12}
        - {metric: roe_pct, op: ">=", value: 20}
"""

from __future__ import annotations

import operator
from typing import Any

from .. import metrics
from ..models import Company, CriterionResult, ScreenResult

OPS = {
    "<=": operator.le,
    "<": operator.lt,
    ">=": operator.ge,
    ">": operator.gt,
    "==": operator.eq,
    "!=": operator.ne,
}


def _compare(actual, op, value) -> bool:
    if actual is None:
        return False
    try:
        return OPS[op](actual, value)
    except (KeyError, TypeError):
        return False


def validate_criteria(criteria: list) -> list[str]:
    """Return a list of problems with a custom-criteria list (empty = valid)."""
    problems: list[str] = []
    for i, c in enumerate(criteria):
        if not isinstance(c, dict):
            problems.append(f"custom.criteria[{i}] must be a mapping")
            continue
        if c.get("metric") not in metrics.METRIC_KEYS:
            problems.append(
                f"custom.criteria[{i}].metric must be one of {metrics.METRIC_KEYS}")
        if c.get("op") not in OPS:
            problems.append(
                f"custom.criteria[{i}].op must be one of {sorted(OPS)}")
        try:
            float(c.get("value"))
        except (TypeError, ValueError):
            problems.append(f"custom.criteria[{i}].value must be a number")
    return problems


def evaluate_custom(company: Company, cfg: dict[str, Any]) -> ScreenResult:
    spec = cfg.get("custom", {})
    criteria = spec.get("criteria", []) or []
    m = metrics.compute_metrics(company)
    results: list[CriterionResult] = []
    errors: list[str] = []

    if not criteria:
        errors.append("no custom criteria defined")

    for c in criteria:
        metric = c.get("metric")
        op = c.get("op")
        try:
            value = float(c.get("value"))
        except (TypeError, ValueError):
            errors.append(f"invalid value for {metric!r}")
            continue
        actual = m.get(metric)
        passed = _compare(actual, op, value)
        name = c.get("name") or f"{metric} {op} {value:g}"
        results.append(CriterionResult(
            name=name, passed=passed, actual=actual, threshold=value,
            weight=float(c.get("weight", 1.0)),
            detail=f"{metric} {op} {value:g}"
                   + ("" if actual is not None else " (metric unavailable)"),
        ))

    score = sum(r.weight for r in results if r.passed)
    max_score = sum(r.weight for r in results)
    pass_ratio = spec.get("pass_ratio", 1.0)
    passed = max_score > 0 and (score / max_score) >= pass_ratio

    return ScreenResult(
        ticker=company.ticker, name=company.name, cik=company.cik,
        strategy="custom", passed=passed, score=score, max_score=max_score,
        metrics=m, criteria=results, errors=errors,
    )
