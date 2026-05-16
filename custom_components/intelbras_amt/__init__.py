"""Intelbras AMT Alarm integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .server import AMTServer
from .const import (
    CONF_PASSWORD_A,
    CONF_PASSWORD_B,
    CONF_PASSWORD_C,
    CONF_PASSWORD_D,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import AMTCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Intelbras AMT from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create server (listens for panel connections)
    server = AMTServer(
        port=entry.data[CONF_PORT],
        password=entry.data[CONF_PASSWORD],
    )

    # Set partition passwords if configured
    server.set_partition_passwords(
        password_a=entry.data.get(CONF_PASSWORD_A),
        password_b=entry.data.get(CONF_PASSWORD_B),
        password_c=entry.data.get(CONF_PASSWORD_C),
        password_d=entry.data.get(CONF_PASSWORD_D),
    )

    # Start the server
    await server.start()

    # Get scan interval from options or data
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    # Create coordinator
    coordinator = AMTCoordinator(hass, server, scan_interval)

    # Don't wait for first refresh - panel may not be connected yet
    # The coordinator will return disconnected status until panel connects
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info(
        "Intelbras AMT integration started, panel port=%s",
        entry.data[CONF_PORT]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: AMTCoordinator = data["coordinator"]
        await coordinator.async_shutdown()

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
