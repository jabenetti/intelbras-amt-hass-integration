"""Switches for Intelbras AMT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_CONNECTED,
    DATA_MODEL_NAME,
    DATA_PGMS,
    DATA_SIREN,
    DOMAIN,
    ENTITY_PREFIX,
    MAX_PGMS,
)
from .coordinator import AMTCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from a config entry."""
    coordinator: AMTCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[SwitchEntity] = []

    # Siren switch
    entities.append(AMTSirenSwitch(coordinator, entry))

    # PGM switches (1-19)
    for pgm_num in range(1, MAX_PGMS + 1):
        entities.append(AMTPGMSwitch(coordinator, entry, pgm_num))

    async_add_entities(entities)


class AMTSwitchBase(CoordinatorEntity[AMTCoordinator], SwitchEntity):
    """Base class for AMT switches."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        model_name = "AMT"
        if self.coordinator.data:
            model_name = self.coordinator.data.get(DATA_MODEL_NAME, "AMT")

        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"{ENTITY_PREFIX.upper()} (porta {self._entry.data[CONF_PORT]})",
            manufacturer="Intelbras",
            model=model_name,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not self.coordinator.data:
            return False
        return self.coordinator.data.get(DATA_CONNECTED, False)


class AMTSirenSwitch(AMTSwitchBase):
    """Siren switch."""

    _attr_name = "Sirene"
    _attr_icon = "mdi:bullhorn"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the siren switch."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_siren_switch"

    @property
    def is_on(self) -> bool | None:
        """Return True if siren is active."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_SIREN, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn siren on."""
        await self.coordinator.async_siren_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn siren off."""
        await self.coordinator.async_siren_off()


class AMTPGMSwitch(AMTSwitchBase):
    """PGM on/off switch."""

    _attr_icon = "mdi:electric-switch"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        pgm_num: int,
    ) -> None:
        """Initialize the PGM switch."""
        super().__init__(coordinator, entry)
        self._pgm_num = pgm_num
        self._attr_unique_id = f"{entry.entry_id}_pgm_{pgm_num}_switch"
        self._attr_name = f"PGM {pgm_num}"

    @property
    def is_on(self) -> bool | None:
        """Return True if PGM is active."""
        if not self.coordinator.data:
            return None

        pgms = self.coordinator.data.get(DATA_PGMS, [])
        pgm_idx = self._pgm_num - 1
        if pgm_idx < len(pgms):
            return pgms[pgm_idx]
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the PGM."""
        await self.coordinator.async_activate_pgm(self._pgm_num)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate the PGM."""
        await self.coordinator.async_deactivate_pgm(self._pgm_num)
