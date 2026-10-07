import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from workflow_agent.agent import Agent          # noqa: E402
from workflow_agent.config import Settings      # noqa: E402
from workflow_agent.llm import OfflineLLM       # noqa: E402


def make_settings(tmp_path, **overrides) -> Settings:
    s = Settings.from_env(ROOT)
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
