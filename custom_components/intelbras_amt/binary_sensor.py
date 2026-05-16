"""Binary sensors for Intelbras AMT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_AC_POWER,
    DATA_AUX_OVERLOAD,
    DATA_BATTERY_ABSENT,
    DATA_BATTERY_CONNECTED,
    DATA_BATTERY_LOW,
    DATA_BATTERY_SHORT,
    DATA_COMM_FAILURE,
    DATA_CONNECTED,
    DATA_MAX_ZONES,
    DATA_MODEL_NAME,
    DATA_PARTITIONS,
    DATA_PHONE_LINE_CUT,
    DATA_PROBLEM,
    DATA_SIREN,
    DATA_SIREN_SHORT,
    DATA_SIREN_WIRE_CUT,
    DATA_ZONES_BYPASSED,
    DATA_ZONES_LOW_BATTERY,
    DATA_ZONES_OPEN,
    DATA_ZONES_SHORT_CIRCUIT,
    DATA_ZONES_TAMPER,
    DATA_ZONES_VIOLATED,
    DOMAIN,
    ENTITY_PREFIX,
    MAX_PARTITIONS,
    MAX_ZONES_LOW_BATTERY,
    MAX_ZONES_SHORT_CIRCUIT,
    MAX_ZONES_TAMPER,
    PARTITION_NAMES,
)
from .coordinator import AMTCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    coordinator: AMTCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[BinarySensorEntity] = []

    # Determine max zones from coordinator data
    max_zones = 64
    if coordinator.data:
        max_zones = coordinator.data.get(DATA_MAX_ZONES, 64)

    # Zone sensors (open, violated, bypassed)
    for zone_num in range(1, max_zones + 1):
        entities.append(AMTZoneOpenSensor(coordinator, entry, zone_num))
        entities.append(AMTZoneViolatedSensor(coordinator, entry, zone_num))
        entities.append(AMTZoneBypassedSensor(coordinator, entry, zone_num))

    # Zone tamper sensors (zones 1-18)
    for zone_num in range(1, MAX_ZONES_TAMPER + 1):
        entities.append(AMTZoneTamperSensor(coordinator, entry, zone_num))

    # Zone short-circuit sensors (zones 1-18)
    for zone_num in range(1, MAX_ZONES_SHORT_CIRCUIT + 1):
        entities.append(AMTZoneShortCircuitSensor(coordinator, entry, zone_num))

    # Zone low battery sensors (wireless zones 1-40)
    for zone_num in range(1, MAX_ZONES_LOW_BATTERY + 1):
        entities.append(AMTZoneLowBatterySensor(coordinator, entry, zone_num))

    # Partition sensors
    for partition_idx in range(MAX_PARTITIONS):
        partition_name = PARTITION_NAMES[partition_idx]
        entities.append(AMTPartitionSensor(coordinator, entry, partition_name))

    # Status sensors
    entities.append(AMTACPowerSensor(coordinator, entry))
    entities.append(AMTBatteryConnectedSensor(coordinator, entry))
    entities.append(AMTSirenSensor(coordinator, entry))
    entities.append(AMTProblemSensor(coordinator, entry))

    # Detailed problem sensors
    entities.append(AMTBatteryLowSensor(coordinator, entry))
    entities.append(AMTBatteryAbsentSensor(coordinator, entry))
    entities.append(AMTBatteryShortSensor(coordinator, entry))
    entities.append(AMTAuxOverloadSensor(coordinator, entry))
    entities.append(AMTSirenWireCutSensor(coordinator, entry))
    entities.append(AMTSirenShortSensor(coordinator, entry))
    entities.append(AMTPhoneLineCutSensor(coordinator, entry))
    entities.append(AMTCommFailureSensor(coordinator, entry))

    async_add_entities(entities)


class AMTBinarySensorBase(CoordinatorEntity[AMTCoordinator], BinarySensorEntity):
    """Base class for AMT binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
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


class AMTZoneOpenSensor(AMTBinarySensorBase):
    """Zone open sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        zone_num: int,
    ) -> None:
        """Initialize the zone sensor."""
        super().__init__(coordinator, entry)
        self._zone_num = zone_num
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_num}_open"
        self._attr_name = f"Zona {zone_num}"

    @property
    def is_on(self) -> bool | None:
        """Return True if zone is open."""
        if not self.coordinator.data:
            return None

        zones_open = self.coordinator.data.get(DATA_ZONES_OPEN, [])
        zone_idx = self._zone_num - 1
        if zone_idx < len(zones_open):
            return zones_open[zone_idx]
        return None


class AMTZoneViolatedSensor(AMTBinarySensorBase):
    """Zone violated sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        zone_num: int,
    ) -> None:
        """Initialize the zone violated sensor."""
        super().__init__(coordinator, entry)
        self._zone_num = zone_num
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_num}_violated"
        self._attr_name = f"Zona {zone_num} Violada"

    @property
    def is_on(self) -> bool | None:
        """Return True if zone is violated."""
        if not self.coordinator.data:
            return None

        zones_violated = self.coordinator.data.get(DATA_ZONES_VIOLATED, [])
        zone_idx = self._zone_num - 1
        if zone_idx < len(zones_violated):
            return zones_violated[zone_idx]
        return None


class AMTZoneBypassedSensor(AMTBinarySensorBase):
    """Zone bypassed sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        zone_num: int,
    ) -> None:
        """Initialize the zone bypassed sensor."""
        super().__init__(coordinator, entry)
        self._zone_num = zone_num
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_num}_bypassed"
        self._attr_name = f"Zona {zone_num} Anulada"

    @property
    def is_on(self) -> bool | None:
        """Return True if zone is bypassed."""
        if not self.coordinator.data:
            return None

        zones_bypassed = self.coordinator.data.get(DATA_ZONES_BYPASSED, [])
        zone_idx = self._zone_num - 1
        if zone_idx < len(zones_bypassed):
            return zones_bypassed[zone_idx]
        return None


class AMTPartitionSensor(AMTBinarySensorBase):
    """Partition armed sensor."""

    _attr_device_class = BinarySensorDeviceClass.LOCK

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        partition_name: str,
    ) -> None:
        """Initialize the partition sensor."""
        super().__init__(coordinator, entry)
        self._partition_name = partition_name
        self._attr_unique_id = f"{entry.entry_id}_partition_{partition_name.lower()}"
        self._attr_name = f"Partição {partition_name}"

    @property
    def is_on(self) -> bool | None:
        """Return True if partition is armed."""
        if not self.coordinator.data:
            return None

        partitions = self.coordinator.data.get(DATA_PARTITIONS, {})
        partition_data = partitions.get(self._partition_name, {})
        return partition_data.get("armed", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}

        partitions = self.coordinator.data.get(DATA_PARTITIONS, {})
        partition_data = partitions.get(self._partition_name, {})
        return {
            "stay": partition_data.get("stay", False),
            "triggered": partition_data.get("triggered", False),
        }


class AMTZoneTamperSensor(AMTBinarySensorBase):
    """Zone tamper sensor."""

    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        zone_num: int,
    ) -> None:
        """Initialize the zone tamper sensor."""
        super().__init__(coordinator, entry)
        self._zone_num = zone_num
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_num}_tamper"
        self._attr_name = f"Zona {zone_num} Tamper"

    @property
    def is_on(self) -> bool | None:
        """Return True if zone has tamper."""
        if not self.coordinator.data:
            return None

        zones_tamper = self.coordinator.data.get(DATA_ZONES_TAMPER, [])
        zone_idx = self._zone_num - 1
        if zone_idx < len(zones_tamper):
            return zones_tamper[zone_idx]
        return None


class AMTZoneShortCircuitSensor(AMTBinarySensorBase):
    """Zone short-circuit sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        zone_num: int,
    ) -> None:
        """Initialize the zone short-circuit sensor."""
        super().__init__(coordinator, entry)
        self._zone_num = zone_num
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_num}_short_circuit"
        self._attr_name = f"Zona {zone_num} Curto-Circuito"

    @property
    def is_on(self) -> bool | None:
        """Return True if zone has short-circuit."""
        if not self.coordinator.data:
            return None

        zones_short = self.coordinator.data.get(DATA_ZONES_SHORT_CIRCUIT, [])
        zone_idx = self._zone_num - 1
        if zone_idx < len(zones_short):
            return zones_short[zone_idx]
        return None


class AMTZoneLowBatterySensor(AMTBinarySensorBase):
    """Wireless zone low battery sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        zone_num: int,
    ) -> None:
        """Initialize the zone low battery sensor."""
        super().__init__(coordinator, entry)
        self._zone_num = zone_num
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_num}_low_battery"
        self._attr_name = f"Zona {zone_num} Bateria Fraca"

    @property
    def is_on(self) -> bool | None:
        """Return True if wireless zone has low battery."""
        if not self.coordinator.data:
            return None

        zones_low_batt = self.coordinator.data.get(DATA_ZONES_LOW_BATTERY, [])
        zone_idx = self._zone_num - 1
        if zone_idx < len(zones_low_batt):
            return zones_low_batt[zone_idx]
        return None


class AMTACPowerSensor(AMTBinarySensorBase):
    """AC power sensor."""

    _attr_device_class = BinarySensorDeviceClass.PLUG
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Energia AC"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the AC power sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ac_power"

    @property
    def is_on(self) -> bool | None:
        """Return True if AC power is connected."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_AC_POWER, False)


class AMTBatteryConnectedSensor(AMTBinarySensorBase):
    """Battery connected sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Bateria Conectada"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the battery connected sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_battery_connected"

    @property
    def is_on(self) -> bool | None:
        """Return True if battery is connected."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_BATTERY_CONNECTED, False)


class AMTSirenSensor(AMTBinarySensorBase):
    """Siren sensor."""

    _attr_device_class = BinarySensorDeviceClass.SOUND
    _attr_name = "Sirene"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the siren sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_siren"

    @property
    def is_on(self) -> bool | None:
        """Return True if siren is active."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_SIREN, False)


class AMTProblemSensor(AMTBinarySensorBase):
    """Problem sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Problema"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the problem sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_problem"

    @property
    def is_on(self) -> bool | None:
        """Return True if there is a problem."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_PROBLEM, False)


class AMTBatteryLowSensor(AMTBinarySensorBase):
    """Battery low sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Bateria Fraca"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the battery low sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_battery_low"

    @property
    def is_on(self) -> bool | None:
        """Return True if battery is low."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_BATTERY_LOW, False)


class AMTBatteryAbsentSensor(AMTBinarySensorBase):
    """Battery absent sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Bateria Ausente"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the battery absent sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_battery_absent"

    @property
    def is_on(self) -> bool | None:
        """Return True if battery is absent."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_BATTERY_ABSENT, False)


class AMTBatteryShortSensor(AMTBinarySensorBase):
    """Battery short-circuit sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Bateria em Curto"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the battery short sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_battery_short"

    @property
    def is_on(self) -> bool | None:
        """Return True if battery has short-circuit."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_BATTERY_SHORT, False)


class AMTAuxOverloadSensor(AMTBinarySensorBase):
    """Auxiliary output overload sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Sobrecarga Aux"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the aux overload sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_aux_overload"

    @property
    def is_on(self) -> bool | None:
        """Return True if aux output is overloaded."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_AUX_OVERLOAD, False)


class AMTSirenWireCutSensor(AMTBinarySensorBase):
    """Siren wire cut sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Fio Sirene Cortado"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the siren wire cut sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_siren_wire_cut"

    @property
    def is_on(self) -> bool | None:
        """Return True if siren wire is cut."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_SIREN_WIRE_CUT, False)


class AMTSirenShortSensor(AMTBinarySensorBase):
    """Siren short-circuit sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Sirene em Curto"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the siren short sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_siren_short"

    @property
    def is_on(self) -> bool | None:
        """Return True if siren has short-circuit."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_SIREN_SHORT, False)


class AMTPhoneLineCutSensor(AMTBinarySensorBase):
    """Phone line cut sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Linha Telefonica Cortada"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the phone line cut sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_phone_line_cut"

    @property
    def is_on(self) -> bool | None:
        """Return True if phone line is cut."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_PHONE_LINE_CUT, False)


class AMTCommFailureSensor(AMTBinarySensorBase):
    """Communication failure sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Falha de Comunicacao"

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the communication failure sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_comm_failure"

    @property
    def is_on(self) -> bool | None:
        """Return True if there is a communication failure."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(DATA_COMM_FAILURE, False)
