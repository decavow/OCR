"""Contract & flow test conftest — fixtures only."""

import asyncio
import sys
from pathlib import Path

import pytest

# Ensure contract dir is importable (for helpers.py)
CONTRACT_DIR = Path(__file__).parent
if str(CONTRACT_DIR) not in sys.path:
    sys.path.insert(0, str(CONTRACT_DIR))


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
