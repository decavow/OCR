"""Unit tests for GracefulShutdown (03_worker/app/core/shutdown.py).

Async tests using pytest-asyncio.

Test IDs: GS-001 through GS-005
"""

import asyncio
import signal

import pytest

from app.core.shutdown import GracefulShutdown


# ---- GS-001: Initial state ----

def test_initial_state():
    """GS-001: Fresh GracefulShutdown is not shutting down, event is unset."""
    gs = GracefulShutdown()

    assert gs.is_shutting_down is False
    assert not gs._shutdown_event.is_set()


# ---- GS-002: First signal sets shutdown ----

@pytest.mark.asyncio
async def test_first_signal_sets_shutdown():
    """GS-002: First handle_signal sets is_shutting_down and the event."""
    gs = GracefulShutdown()

    await gs.handle_signal(signal.SIGTERM)

    assert gs.is_shutting_down is True
    assert gs._shutdown_event.is_set()


# ---- GS-003: Second signal is ignored ----

@pytest.mark.asyncio
async def test_second_signal_ignored():
    """GS-003: Second handle_signal when already shutting down is a no-op."""
    gs = GracefulShutdown()

    await gs.handle_signal(signal.SIGTERM)
    assert gs.is_shutting_down is True

    # Second signal should not raise or change state
    await gs.handle_signal(signal.SIGINT)
    assert gs.is_shutting_down is True
    assert gs._shutdown_event.is_set()


# ---- GS-004: wait_for_shutdown waits then returns ----

@pytest.mark.asyncio
async def test_wait_for_shutdown_waits_then_returns():
    """GS-004: wait_for_shutdown blocks until signal is received."""
    gs = GracefulShutdown()

    # Schedule signal delivery after a short delay
    async def send_signal_later():
        await asyncio.sleep(0.05)
        await gs.handle_signal(signal.SIGTERM)

    task = asyncio.create_task(send_signal_later())

    # wait_for_shutdown should block until the signal fires
    await asyncio.wait_for(gs.wait_for_shutdown(), timeout=2.0)

    assert gs.is_shutting_down is True
    await task  # ensure the helper task is cleaned up


# ---- GS-005: Already signaled before wait ----

@pytest.mark.asyncio
async def test_already_signaled_before_wait():
    """GS-005: If signal was already received, wait_for_shutdown returns immediately."""
    gs = GracefulShutdown()

    await gs.handle_signal(signal.SIGTERM)

    # Should return instantly (no blocking)
    await asyncio.wait_for(gs.wait_for_shutdown(), timeout=1.0)

    assert gs.is_shutting_down is True
