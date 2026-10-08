import os
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from workflow_agent.agent import Agent          # noqa: E402
from workflow_agent.config import Settings      # noqa: E402
from workflow_agent.llm import OfflineLLM       # noqa: E402

# Anything a developer may have in .env / the shell that would change behaviour under test.
CONFIG_VARS = (
    "LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_TIMEOUT_SECONDS", "LLM_REASONING",
    "OPENAI_API_KEY", "OPENROUTER_API_KEY", "VLLM_API_KEY", "OPENROUTER_REFERER", "OPENROUTER_APP_TITLE",
    "WORKFLOW_EXCEL", "EXECUTION_LOG_FILE", "OUTPUT_DIR", "ALLOW_SAMPLE_DEFAULTS",
    "PRICE_DIFF_THRESHOLD_PCT", "FAILURE_RATE_THRESHOLD_PCT", "SLOW_WORKFLOW_THRESHOLD_MS",
    "SLOW_STEP_THRESHOLD_MS", "RESTOCK_TARGET_MULTIPLIER",
)


@pytest.fixture(autouse=True)
def hermetic_env():
    """Tests never see a real API key or model from the machine they run on, and never leak .env values."""
    saved = dict(os.environ)
    for name in CONFIG_VARS:
        os.environ.pop(name, None)
    yield
    os.environ.clear()
    os.environ.update(saved)


def make_settings(tmp_path, **overrides) -> Settings:
    s = Settings()                       # plain defaults: does not read .env or the environment
    s.llm_provider = "none"
    s.output_dir = tmp_path / "outputs"
    s.log_file = tmp_path / "execution_log.csv"
    s.today = date(2026, 10, 7)
    s.tool_retry_backoff_s = 0.0
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def agent(settings):
    """Offline agent (no LLM) writing into a temp dir - fully deterministic."""
    return Agent(settings, llm=OfflineLLM())      # strict: Excel and code must agree
