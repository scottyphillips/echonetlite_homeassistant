"""KAITEKI per-zone program operation select entities."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .base_entity import EchonetEntity
from .climate_KAITEKI import (
    PROGRAM_OPERATION_TO_BYTE,
    get_kaiteki_zone_group,
    get_kaiteki_zones,
    _main_power_is_on,
)

_LOGGER = logging.getLogger(__name__)


class EchonetKaitekiProgramSelect(EchonetEntity, SelectEntity):
    """Select the program operation (off/timer1-3) of one KAITEKI zone group."""

    _attr_options = list(PROGRAM_OPERATION_TO_BYTE)
    _attr_icon = "mdi:timer-cog-outline"

    def __init__(self, coordinator, config, zones, zone_group):
        super().__init__(coordinator, config)
        self.zones = tuple(zones)
        self.zone_group = zone_group

        zone_name = "+".join(str(zone) for zone in self.zones)
        self._attr_name = f"{self._device_name} Zone {zone_name} Program Operation"
        self._attr_unique_id = self._build_unique_id(f"zone-{zone_name}-program")

    @property
    def current_option(self):
        """Return the program operation of the first zone in this group."""
        f1 = self.coordinator.data.get(0xF1)
        if not isinstance(f1, dict):
            return None
        value = f1.get(f"zone{self.zones[0]}ProgramOperation")
        return value if value in PROGRAM_OPERATION_TO_BYTE else None

    async def async_select_option(self, option: str) -> None:
        """Write the selected program operation to every zone in the group."""
        if option not in PROGRAM_OPERATION_TO_BYTE:
            raise HomeAssistantError(f"Unsupported program operation: {option}")
        # The unit acknowledges F1 writes but silently ignores program operation
        # changes while the main power (0x80) is off.
        if not _main_power_is_on(self.coordinator):
            raise HomeAssistantError(
                "Program operation can only be changed while the main power is on"
            )
        overrides = {f"zone{zone}ProgramOperation": option for zone in self.zones}
        await self.zone_group.async_set_f1(overrides)


def create_kaiteki_select_entities(coordinator, config):
    """Create KAITEKI select entities from F2 zoneGrouping.

    Returns an empty list for air conditioners that are not KAITEKI units.
    """
    zones = get_kaiteki_zones(coordinator)
    if zones is None:
        return []

    zone_group = get_kaiteki_zone_group(coordinator, zones)
    return [
        EchonetKaitekiProgramSelect(coordinator, config, physical_zones, zone_group)
        for physical_zones in zones
    ]
