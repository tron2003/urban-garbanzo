"""Convenience launcher:  python main.py "Which products need restocking?"  (same as python -m workflow_agent)"""
import sys

from workflow_agent.cli import entry

if __name__ == "__main__":
    sys.exit(entry())
