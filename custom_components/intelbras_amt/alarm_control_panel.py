"""Alarm control panel for Intelbras AMT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_ARMED,
    DATA_CONNECTED,
    DATA_MODEL_NAME,
    DATA_PARTITIONS,
    DATA_SIREN,
    DATA_STAY,
    DATA_TRIGGERED,
    DOMAIN,
    ENTITY_PREFIX,
    MAX_PARTITIONS,
    PARTITION_NAMES,
)
from .coordinator import AMTCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up alarm control panel from a config entry."""
    coordinator: AMTCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[AlarmControlPanelEntity] = [
        AMTAlarmControlPanel(coordinator, entry),
    ]

    # Add partition alarm panels
    for partition_idx in range(MAX_PARTITIONS):
        partition_name = PARTITION_NAMES[partition_idx]
        entities.append(AMTPartitionAlarmPanel(coordinator, entry, partition_name))

    async_add_entities(entities)


class AMTAlarmControlPanel(CoordinatorEntity[AMTCoordinator], AlarmControlPanelEntity):
    """AMT Alarm Control Panel."""

    _attr_has_entity_name = True
    _attr_name = "Central"
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    _attr_code_arm_required = True
    _attr_code_format = CodeFormat.NUMBER

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the alarm control panel."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_alarm_panel"

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

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""
        if not self.coordinator.data:
            return None

        if not self.coordinator.data.get(DATA_CONNECTED, False):
            return None

        armed = self.coordinator.data.get(DATA_ARMED, False)
        triggered = self.coordinator.data.get(DATA_TRIGGERED, False)
        siren_on = self.coordinator.data.get(DATA_SIREN, False)

        # Only show TRIGGERED if:
        # - Siren is currently on, OR
        # - Alarm is armed AND triggered bit is set
        if siren_on or (armed and triggered):
            return AlarmControlPanelState.TRIGGERED

        if armed:
            # Check central stay flag OR any partition in stay mode
            stay = self.coordinator.data.get(DATA_STAY, False)
            if not stay:
                # Check if any armed partition is in stay mode
                partitions = self.coordinator.data.get(DATA_PARTITIONS, {})
                for part_data in partitions.values():
                    if part_data.get("armed") and part_data.get("stay"):
                        stay = True
                        break
            if stay:
                return AlarmControlPanelState.ARMED_HOME
            return AlarmControlPanelState.ARMED_AWAY

        return AlarmControlPanelState.DISARMED

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the alarm."""
        await self.coordinator.async_disarm(code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm in stay mode."""
        await self.coordinator.async_arm_stay(code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the alarm."""
        await self.coordinator.async_arm(code)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Trigger the alarm (not supported)."""
        _LOGGER.warning("Trigger is not supported by AMT alarm panels")


class AMTPartitionAlarmPanel(CoordinatorEntity[AMTCoordinator], AlarmControlPanelEntity):
    """AMT Partition Alarm Control Panel."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    _attr_code_arm_required = True
    _attr_code_format = CodeFormat.NUMBER

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        partition_name: str,
    ) -> None:
        """Initialize the partition alarm control panel."""
        super().__init__(coordinator)
        self._entry = entry
        self._partition_name = partition_name
        self._attr_unique_id = f"{entry.entry_id}_partition_{partition_name.lower()}_panel"
        self._attr_name = f"Partição {partition_name}"

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

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the partition."""
        if not self.coordinator.data:
            return None

        if not self.coordinator.data.get(DATA_CONNECTED, False):
            return None

        partitions = self.coordinator.data.get(DATA_PARTITIONS, {})
        partition_data = partitions.get(self._partition_name, {})

        armed = partition_data.get("armed", False)
        triggered = partition_data.get("triggered", False)
        siren_on = self.coordinator.data.get(DATA_SIREN, False)

        # Show TRIGGERED if siren is on or partition is armed and triggered
        if siren_on or (armed and triggered):
            return AlarmControlPanelState.TRIGGERED

        if armed:
            if partition_data.get("stay", False):
                return AlarmControlPanelState.ARMED_HOME
            return AlarmControlPanelState.ARMED_AWAY

        return AlarmControlPanelState.DISARMED

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the partition."""
        await self.coordinator.async_disarm_partition(self._partition_name, code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the partition in stay mode."""
        await self.coordinator.async_arm_stay_partition(self._partition_name, code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the partition."""
        await self.coordinator.async_arm_partition(self._partition_name, code)
