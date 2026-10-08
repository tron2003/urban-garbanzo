"""Central settings. Everything is overridable through environment variables or a .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Tiny .env reader (avoids a python-dotenv dependency). Real env vars win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _bool(value: Optional[str], default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float(value: Optional[str], default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


@dataclass
class Settings:
    base_dir: Path = BASE_DIR
    workflow_excel: Path = BASE_DIR / "data" / "AI_Agent_Workflow_Assessment.xlsx"
    data_dir: Path = BASE_DIR / "data"
    output_dir: Path = BASE_DIR / "outputs"
    log_file: Path = BASE_DIR / "logs" / "execution_log.csv"

    # LLM
    llm_provider: str = "none"          # none | openai | openai_compatible
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout: float = 60.0
    llm_reasoning: str = "off"          # OpenRouter: off = ask the model not to think (default) | default = provider default

    # Behaviour
    allow_sample_defaults: bool = True
    tool_max_retries: int = 2
    tool_retry_backoff_s: float = 0.2
    router_min_score: float = 0.10
    router_ambiguity_margin: float = 0.12
    router_override_score: float = 0.35      # heuristic score that overrides an LLM 'no matching workflow'
    today: Optional[date] = None        # injectable for deterministic tests

    # Business thresholds (the Excel Decision_Logic text states the defaults)
    price_diff_threshold_pct: float = 10.0
    failure_rate_threshold_pct: float = 10.0
    slow_workflow_threshold_ms: float = 5000.0
    slow_step_threshold_ms: float = 2000.0
    restock_target_multiplier: float = 2.0

    def current_date(self) -> date:
        return self.today or date.today()

    def resolve(self, value: str | Path) -> Path:
        """Resolve a user/Excel-supplied path relative to the project root."""
        p = Path(str(value)).expanduser()
        return p if p.is_absolute() else (self.base_dir / p)

    @classmethod
    def from_env(cls, base_dir: Optional[Path] = None) -> "Settings":
        base = Path(base_dir) if base_dir else BASE_DIR
        _load_dotenv(base / ".env")
        env = os.environ.get

        provider = (env("LLM_PROVIDER") or "").strip().lower()
        base_url = env("LLM_BASE_URL") or ""
        if not provider:                       # auto-detect from whatever is configured
            if base_url:
                provider = "openai_compatible"
            elif env("OPENAI_API_KEY"):
                provider = "openai"
            elif env("OPENROUTER_API_KEY"):
                provider = "openrouter"
            else:
                provider = "none"
        # the generic LLM_API_KEY wins; otherwise only the key that belongs to the chosen provider is used,
        # so an OpenAI key is never sent to OpenRouter / a local server by accident
        key_env = {"openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY", "vllm": "VLLM_API_KEY"}.get(provider)
        api_key = env("LLM_API_KEY") or (env(key_env) if key_env else "") or ""

        return cls(
            base_dir=base,
            workflow_excel=Path(env("WORKFLOW_EXCEL") or base / "data" / "AI_Agent_Workflow_Assessment.xlsx"),
            data_dir=base / "data",
            output_dir=Path(env("OUTPUT_DIR") or base / "outputs"),
            log_file=Path(env("EXECUTION_LOG_FILE") or base / "logs" / "execution_log.csv"),
            llm_provider=provider,
            llm_base_url=base_url,
            llm_api_key=api_key,
            llm_model=env("LLM_MODEL") or "",
            llm_timeout=_float(env("LLM_TIMEOUT_SECONDS"), 60.0),
            llm_reasoning=(env("LLM_REASONING") or "off").strip().lower(),
            allow_sample_defaults=_bool(env("ALLOW_SAMPLE_DEFAULTS"), True),
            price_diff_threshold_pct=_float(env("PRICE_DIFF_THRESHOLD_PCT"), 10.0),
            failure_rate_threshold_pct=_float(env("FAILURE_RATE_THRESHOLD_PCT"), 10.0),
            slow_workflow_threshold_ms=_float(env("SLOW_WORKFLOW_THRESHOLD_MS"), 5000.0),
            slow_step_threshold_ms=_float(env("SLOW_STEP_THRESHOLD_MS"), 2000.0),
            restock_target_multiplier=_float(env("RESTOCK_TARGET_MULTIPLIER"), 2.0),
        )
