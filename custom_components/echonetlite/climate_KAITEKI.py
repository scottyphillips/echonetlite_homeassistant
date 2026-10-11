"""KAITEKI multi-zone climate entities."""

import logging
import asyncio
import time

from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE
from pychonet.HomeAirConditioner import ENL_HVAC_MODE, ENL_STATUS
from .climate import EchonetClimate
from .connectors import _host_semaphores
from .const import DATA_STATE_ON

_LOGGER = logging.getLogger(__name__)

ZONE_GROUPINGS = {
    # 0x30: zone 1 / zone 2 / zone 3
    # 0x31: zone 1+2 / zone 3
    # 0x32: zone 1+3 / zone 2
    # 0x33: zone 1 / zone 2+3
    # 0x34: zone 1+2+3
    0x30: ((1,), (2,), (3,)),
    0x31: ((1, 2), (3,)),
    0x32: ((1, 3), (2,)),
    0x33: ((1,), (2, 3)),
    0x34: ((1, 2, 3),),
}
STATUS_TO_BYTE = {
    "off": 0x30,
    "on": 0x31,
    "keep": 0x32,
}
AIRFLOW_TO_BYTE = {
    "low": 0x31,
    "high": 0x32,
    "auto": 0x41,
}
PROGRAM_OPERATION_TO_BYTE = {
    "off": 0x30,
    "timer1": 0x31,
    "timer2": 0x32,
    "timer3": 0x33,
}
# Calls arriving within this window are merged into a single F1 frame
# (e.g. an automation touching several zones at once).
F1_COALESCE_DELAY = 0.2
# SET is retried when the device queue is busy (e.g. a poll is in flight).
F1_SET_RETRIES = 3
F1_RETRY_DELAY = 0.5
# Read back until the device reports the values we just wrote.
F1_READBACK_DELAY = 0.5
F1_READBACK_TRIES = 3
# For this long after a write, the values we sent are trusted over a
# (possibly stale) F1 read, so the next read-modify-write cannot revert them.
F1_SETTLE_TIME = 5.0


class KaitekiZoneGroup:
    def __init__(self, coordinator, grouping):
        self.coordinator = coordinator
        self.grouping = grouping
        self._lock = asyncio.Lock()
        # Overrides and callers waiting for the next F1 write.
        self._pending = {}
        self._waiters = []
        self._flush_scheduled = False
        # Decoded F1 values of the last frame we sent, and when.
        self._last_sent = {}
        self._last_sent_at = 0.0

    def _base_f1(self):
        """Return the F1 dict to start a read-modify-write from."""
        f1 = self.coordinator.data.get(0xF1)
        if not isinstance(f1, dict):
            raise HomeAssistantError("F1 data is unavailable")
        if self._last_sent and time.monotonic() - self._last_sent_at < F1_SETTLE_TIME:
            # The device may not have applied our last write yet.
            return {**f1, **self._last_sent}
        return f1

    def _build_f1(self, overrides):
        """Apply overrides to the base F1 and encode it as 21 bytes.

        Returns (edt, merged) where merged is the decoded form of edt.
        """
        merged = {**self._base_f1(), **overrides}

        edt = bytearray()
        for zone in (1, 2, 3):
            status = merged.get(f"zone{zone}Status")
            temp = merged.get(f"zone{zone}TargetTemp")
            airflow = merged.get(f"zone{zone}AirFlow")
            program = merged.get(f"zone{zone}ProgramOperation")
            unknowns = [merged.get(f"unknown{zone}-{i}") for i in (1, 2, 3)]

            if status not in STATUS_TO_BYTE:
                raise HomeAssistantError(f"Unknown zone{zone}Status: {status!r}")
            if airflow not in AIRFLOW_TO_BYTE:
                raise HomeAssistantError(f"Unknown zone{zone}AirFlow: {airflow!r}")
            if program not in PROGRAM_OPERATION_TO_BYTE:
                raise HomeAssistantError(
                    f"Unknown zone{zone}ProgramOperation: {program!r}"
                )
            if temp is None or any(u is None for u in unknowns):
                raise HomeAssistantError(f"Incomplete F1 data for zone {zone}")

            edt.extend(
                (
                    STATUS_TO_BYTE[status],
                    int(temp),
                    AIRFLOW_TO_BYTE[airflow],
                    *unknowns,
                    PROGRAM_OPERATION_TO_BYTE[program],
                )
            )
        return bytes(edt), merged  # 21 bytes

    async def async_set_f1(self, overrides=None):
        """Queue overrides; calls made close together share one F1 write."""
        # The unit acknowledges F1 writes but silently ignores them while the
        # main power (0x80) is off. Turning the main power on would switch on
        # every zone, so it is left to the user (main power switch) instead.
        if not _main_power_is_on(self.coordinator):
            raise HomeAssistantError(
                "KAITEKI main power is off; turn it on before changing zones"
            )

        overrides = {k: v for k, v in (overrides or {}).items() if v is not None}
        if not overrides:
            return

        future = asyncio.get_running_loop().create_future()
        # Later calls win for the same key.
        self._pending.update(overrides)
        self._waiters.append(future)
        if not self._flush_scheduled:
            self._flush_scheduled = True
            self.coordinator.hass.async_create_task(self._flush())
        await future

    async def _flush(self):
        """Wait briefly for more calls, then write everything in one frame."""
        await asyncio.sleep(F1_COALESCE_DELAY)
        async with self._lock:
            # Calls arriving from now on form the next batch.
            overrides, waiters = self._pending, self._waiters
            self._pending, self._waiters = {}, []
            self._flush_scheduled = False

            error = None
            try:
                await self._write(overrides)
            except Exception as err:  # propagate to every waiting caller
                error = err

            for future in waiters:
                # A caller may have been cancelled while waiting.
                if future.done():
                    continue
                if error is None:
                    future.set_result(None)
                else:
                    future.set_exception(error)

    async def _write(self, overrides):
        coordinator = self.coordinator
        # Power may have been turned off while this batch was waiting.
        if not _main_power_is_on(coordinator):
            raise HomeAssistantError(
                "KAITEKI main power is off; turn it on before changing zones"
            )

        edt, merged = self._build_f1(overrides)
        _LOGGER.debug("KAITEKI F1 SET overrides=%s edt=%s", overrides, edt.hex())

        # Share the per-host semaphore with polling so a SET never collides
        # with a poll cycle on the same device.
        semaphore = _host_semaphores.setdefault(coordinator._host, asyncio.Semaphore(1))
        async with semaphore:
            for attempt in range(1, F1_SET_RETRIES + 1):
                try:
                    ok = await coordinator._instance.setMessage(
                        0xF1, int.from_bytes(edt, "big"), pdc=len(edt)
                    )
                except TimeoutError:
                    ok = False
                _LOGGER.debug("KAITEKI F1 SET ack=%s (attempt %s)", ok, attempt)
                if ok:
                    break
                await asyncio.sleep(F1_RETRY_DELAY)
            else:
                raise HomeAssistantError("KAITEKI did not acknowledge F1")

            self._last_sent = merged
            self._last_sent_at = time.monotonic()
            # Optimistic update so the UI follows immediately.
            coordinator.async_set_updated_data(
                {**(coordinator.data or {}), 0xF1: dict(merged)}
            )

            # Read back until the device reports what we wrote.
            for _ in range(F1_READBACK_TRIES):
                await asyncio.sleep(F1_READBACK_DELAY)
                try:
                    confirmed = await coordinator.poll_pychonet_specific([0xF1])
                except TimeoutError:
                    continue
                _LOGGER.debug("KAITEKI F1 readback=%s", confirmed)
                actual = confirmed.get(0xF1) if confirmed else None
                if not isinstance(actual, dict):
                    continue
                coordinator.async_set_updated_data(
                    {**(coordinator.data or {}), **confirmed}
                )
                if all(actual.get(k) == v for k, v in merged.items()):
                    # Device applied everything; no need to trust the cache.
                    self._last_sent = {}
                    break


class EchonetKaitekiClimate(EchonetClimate):
    """Climate entity representing one KAITEKI zone group."""

    _MODE_B0 = {
        0x42: HVACMode.COOL,
        0x43: HVACMode.HEAT,
        0x44: HVACMode.DRY,
    }

    def __init__(self, coordinator, config, zones, zone_group):
        super().__init__(coordinator, config)
        self.zones = tuple(zones)
        self.zone_group = zone_group

        zone_name = "+".join(str(zone) for zone in self.zones)
        self._attr_name = f"{self._device_name} Zone {zone_name}"
        self._attr_unique_id = self._build_unique_id(f"zone-{zone_name}")
        # KAITEKI airflow is carried by 0xF1, so FAN_MODE must be enabled
        # explicitly even when 0xA0 is not in the set map
        self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

    def _zone_value(self, suffix):
        """Return a value for the first physical zone in this group."""
        f1 = self.coordinator.data.get(0xF1)
        if not isinstance(f1, dict):
            return None
        return f1.get(f"zone{self.zones[0]}{suffix}")

    def update_option_listener(self):
        super().update_option_listener()
        # KAITEKI airflow comes from 0xF1, not from the standard fan EPC
        self._attr_fan_modes = list(AIRFLOW_TO_BYTE)

    @property
    def current_temperature(self):
        """Return the room temperature for the representative zone."""
        fa = self.coordinator.data.get(0xFA)
        if not isinstance(fa, dict):
            return super().current_temperature
        return fa.get(f"zone{self.zones[0]}Temp")

    @property
    def target_temperature(self):
        """Return the target temperature for this zone group."""
        return self._zone_value("TargetTemp")

    @property
    def fan_mode(self):
        """Return the airflow setting for this zone group."""
        return self._zone_value("AirFlow")

    @property
    def zone_program_operation(self):
        """Return the program operation for this zone group."""
        return self._zone_value("ProgramOperation")

    @property
    def zone_status(self):
        return self._zone_value("Status")

    @property
    def is_on(self):
        return self._zone_value("Status") == "on"

    @property
    def hvac_mode(self):
        if self._zone_value("Status") == "on":
            return self._MODE_B0.get(self.coordinator.data.get(0xB0))
        return HVACMode.OFF

    @property
    def hvac_modes(self):
        modes = [HVACMode.OFF]
        current = self._MODE_B0.get(self.coordinator.data.get(0xB0))
        if current is not None:
            modes.append(current)
        return modes

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    @property
    def hvac_action(self):
        status = self._zone_value("Status")
        if status == "keep":
            return HVACAction.IDLE
        if status == "on":
            return {
                0x42: HVACAction.COOLING,
                0x43: HVACAction.HEATING,
                0x44: HVACAction.DRYING,
            }.get(self.coordinator.data.get(0xB0), HVACAction.IDLE)
        return HVACAction.OFF

    @property
    def extra_state_attributes(self):
        attrs = dict(super().extra_state_attributes or {})
        attrs["zone_status"] = self._zone_value("Status")  # on / off / keep
        attrs["zone_program_operation"] = self.zone_program_operation
        return attrs

    async def async_set_temperature(self, **kwargs):
        overrides = {}
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode == HVACMode.OFF:
            return await self.async_turn_off()
        if hvac_mode is not None:
            overrides.update({f"zone{z}Status": "on" for z in self.zones})

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            t = self._normalize_settemp(temperature)
            overrides.update({f"zone{z}TargetTemp": t for z in self.zones})

        if overrides:
            await self.zone_group.async_set_f1(overrides)

    async def async_set_fan_mode(self, fan_mode):
        """Set airflow for this zone group."""
        overrides = {f"zone{zone}AirFlow": fan_mode for zone in self.zones}
        await self.zone_group.async_set_f1(overrides)

    async def async_turn_on(self):
        """Turn on this zone group."""
        overrides = {f"zone{zone}Status": "on" for zone in self.zones}
        await self.zone_group.async_set_f1(overrides)

    async def async_turn_off(self):
        """Turn off this zone group, or park it as keep when a timer is active."""
        # With the main power off every zone is already off
        if not _main_power_is_on(self.coordinator):
            return

        overrides = {f"zone{zone}Status": "off" for zone in self.zones}
        await self.zone_group.async_set_f1(overrides)


# Supported KAITEKI units. These values mirror the quirks directory layout
# (quirks/<manufacturer>/<product code>/0130.py) used by connectors.py.
KAITEKI_MANUFACTURER = "Chofu Seisakusho"
KAITEKI_PRODUCT_CODES = {
    "MC-38",
}


def is_kaiteki(coordinator) -> bool:
    """Whether this coordinator is a supported KAITEKI air conditioner.

    Identification relies on the device class and the manufacturer/product
    code only, because older firmware may lack EPC 0xF2 or report other values.
    """
    return (
        (coordinator._eojgc, coordinator._eojcc) == (0x01, 0x30)
        and coordinator._manufacturer == KAITEKI_MANUFACTURER
        and coordinator._quirk_product_code in KAITEKI_PRODUCT_CODES
    )


def get_kaiteki_zones(coordinator):
    """Return the physical zone layout from F2 zoneGrouping, or None."""
    if not is_kaiteki(coordinator):
        return None
    f2 = coordinator.data.get(0xF2)
    if not isinstance(f2, dict):
        return None
    return ZONE_GROUPINGS.get(f2.get("zoneGrouping"))


def get_kaiteki_zone_group(coordinator, zones):
    """Return the zone group shared by all KAITEKI entities of a coordinator."""
    group = getattr(coordinator, "_kaiteki_zone_group", None)
    if group is None or group.grouping != zones:
        group = KaitekiZoneGroup(coordinator, zones)
        coordinator._kaiteki_zone_group = group
    return group


def create_kaiteki_climate_entities(coordinator, config):
    """Create KAITEKI climate entities from F2 zoneGrouping."""
    zones = get_kaiteki_zones(coordinator)
    if zones is None:
        return []

    zone_group = get_kaiteki_zone_group(coordinator, zones)

    return [
        EchonetKaitekiClimate(
            coordinator,
            config,
            physical_zones,
            zone_group,
        )
        for physical_zones in zones
    ]


def _main_power_is_on(coordinator) -> bool:
    """Whether the main power (0x80) is on.

    The decoded value is "on" when pychonet's super class decoder is used and
    0x30 when the quirk's raw integer decoder is used, so accept both.
    """
    return coordinator.data.get(ENL_STATUS) in (DATA_STATE_ON, 0x30)
