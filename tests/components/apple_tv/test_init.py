"""Tests for Apple TV connection handling."""

import logging
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from pyatv.exceptions import AuthenticationError, ConnectionFailedError, ProtocolError
import pytest

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant

from .common import create_conf, mrp_service

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            ProtocolError("Failed to set up remote control channel"),
            id="protocol-error",
        ),
        pytest.param(ConnectionFailedError("failed"), id="connection-failed"),
        pytest.param(OSError(113, "No route to host"), id="os-error"),
        pytest.param(ClientError(), id="client-error"),
    ],
)
async def test_reconnect_failure_does_not_log_traceback(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """Expected reconnect failures are logged without a stack trace."""
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.apple_tv")
    scan_result = create_conf("127.0.0.1", "Living Room", mrp_service())
    with (
        patch("homeassistant.components.apple_tv.scan", return_value=[scan_result]),
        patch("homeassistant.components.apple_tv.connect", side_effect=error),
    ):
        mock_atv.listener.connection_lost(ConnectionError("Control connection lost"))
        await hass.async_block_till_done()

    assert "Traceback (most recent call last)" not in caplog.text
    assert "Failed to connect to Living Room" in caplog.text


async def test_reconnect_authentication_error_starts_reauth(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Bad credentials during reconnect start reauth without a stack trace."""
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.apple_tv")
    scan_result = create_conf("127.0.0.1", "Living Room", mrp_service())
    with (
        patch("homeassistant.components.apple_tv.scan", return_value=[scan_result]),
        patch(
            "homeassistant.components.apple_tv.connect",
            side_effect=AuthenticationError("bad credentials"),
        ),
    ):
        mock_atv.listener.connection_lost(ConnectionError("Control connection lost"))
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert "Authentication failed for Living Room" in caplog.text
    assert "Traceback (most recent call last)" not in caplog.text


async def test_reconnect_unexpected_error_logs_traceback(
    hass: HomeAssistant,
    mock_atv: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unexpected reconnect failure is still logged with a stack trace."""
    caplog.set_level(logging.ERROR, logger="homeassistant.components.apple_tv")
    scan_result = create_conf("127.0.0.1", "Living Room", mrp_service())
    with (
        patch("homeassistant.components.apple_tv.scan", return_value=[scan_result]),
        patch(
            "homeassistant.components.apple_tv.connect",
            side_effect=RuntimeError("boom"),
        ),
    ):
        mock_atv.listener.connection_lost(ConnectionError("Control connection lost"))
        await hass.async_block_till_done()

    assert "Failed to connect" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text
