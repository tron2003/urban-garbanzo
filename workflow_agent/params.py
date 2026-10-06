"""Parameter resolution: user-supplied > real defaults > bundled sample data."""
from __future__ import annotations

from typing import Any

from .core.registry import WorkflowModule


def resolve_params(module: WorkflowModule, provided: dict[str, Any], allow_samples: bool) -> tuple[dict[str, Any], dict[str, str]]:
    params: dict[str, Any] = {}
    sources: dict[str, str] = {}
    known = {p.name for p in module.params}

    for p in module.params:
        value = provided.get(p.name)
        if value is not None and value != "" and value != []:
            params[p.name] = value
            sources[p.name] = "user"

    user_groups = {p.sample_group for p in module.params if p.name in params and p.sample_group}
    for p in module.params:
        if p.name in params:
            continue
        if p.default is not None:
            params[p.name], sources[p.name] = p.default, "default"
        elif p.sample_default is not None and allow_samples and (p.sample_group is None or p.sample_group not in user_groups):
            params[p.name], sources[p.name] = p.sample_default, "sample"

    # keep unknown keys out: only declared params reach the workflow
    return {k: v for k, v in params.items() if k in known}, {k: v for k, v in sources.items() if k in known}
