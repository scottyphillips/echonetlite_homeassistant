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
from pychonet.HomeAirConditioner import ENL_STATUS
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
# Used when F2 is missing (older firmware) or reports an unknown value.
DEFAULT_ZONE_GROUPING = 0x30
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
AWAY_TO_BYTE = {"off": 0x30, "on": 0x31}
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
# Bound the whole SET + verify sequence so a silent device cannot hold
# the per-host semaphore for minutes (same idea as the Sharp F3 path).
F1_SET_COMMAND_TIMEOUT = 15
F1_SET_OVERALL_TIMEOUT = 45


async def _read_epc(coordinator, epc):
    """GET a single EPC and return its decoded value, or None on failure.

    poll_pychonet_specific() cannot be used for EPCs whose decoded value is
    itself a dict (F1/F0): it would merge that dict into the result as if it
    were {epc: value}.
    """
    for attempt in range(2):
        try:
            value = await coordinator._instance.update([epc])
        except TimeoutError:
            value = None
        if value is not None and value is not False:
            # Tolerate a {epc: value} wrapper as well as a bare value.
            if isinstance(value, dict) and set(value) == {epc}:
                value = value[epc]
            return value
        if attempt == 0:
            await asyncio.sleep(0.3)
    return None


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

    def _base_f1(self, f1=None):
        """Return the F1 dict to start a read-modify-write from."""
        if f1 is None:
            f1 = self.coordinator.data.get(0xF1)
        if not isinstance(f1, dict):
            raise HomeAssistantError("F1 data is unavailable")
        if self._last_sent and time.monotonic() - self._last_sent_at < F1_SETTLE_TIME:
            # The device may not have applied our last write yet.
            return {**f1, **self._last_sent}
        return f1

    def _build_f1(self, overrides, base=None):
        """Apply overrides to the base F1 and encode it as 21 bytes.

        Returns (edt, merged) where merged is the decoded form of edt.
        """
        merged = {**self._base_f1(base), **overrides}

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
                raise HomeAssistantError(f"Unknown zone{zone}ProgramOperation: {program!r}")
            if temp is None or any(u is None for u in unknowns):
                raise HomeAssistantError(f"Incomplete F1 data for zone {zone}")

            edt.extend((
                STATUS_TO_BYTE[status],
                int(temp),
                AIRFLOW_TO_BYTE[airflow],
                *unknowns,
                PROGRAM_OPERATION_TO_BYTE[program],
            ))
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
        waiters = None
        try:
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
        finally:
            # If cancelled (e.g. on unload) before the batch was taken, reset
            # the flag so later calls are not queued forever.
            if self._flush_scheduled:
                self._flush_scheduled = False
                waiters, self._pending, self._waiters = self._waiters, {}, []
            for future in waiters or []:
                if not future.done():
                    future.cancel()

    async def _write(self, overrides):
        coordinator = self.coordinator
        # Power may have been turned off while this batch was waiting.
        if not _main_power_is_on(coordinator):
            raise HomeAssistantError(
                "KAITEKI main power is off; turn it on before changing zones"
            )

        # Share the per-host semaphore with polling so a SET never collides
        # with a poll cycle on the same device.
        semaphore = _host_semaphores.setdefault(coordinator._host, asyncio.Semaphore(1))
        async with semaphore:
            try:
                async with asyncio.timeout(F1_SET_OVERALL_TIMEOUT):
                    await self._write_locked(overrides)
            except TimeoutError as err:
                raise HomeAssistantError("KAITEKI F1 write timed out") from err

    async def _write_locked(self, overrides):
        """Read-modify-write F1. The host semaphore must already be held."""
        coordinator = self.coordinator

        # Start from a fresh GET so changes made on the physical controller
        # since the last poll are not reverted for the other zones.
        base = await _read_epc(coordinator, 0xF1)
        if not isinstance(base, dict):
            raise HomeAssistantError("KAITEKI F1 could not be read before writing")

        edt, merged = self._build_f1(overrides, base)
        _LOGGER.debug("KAITEKI F1 SET overrides=%s edt=%s", overrides, edt.hex())

        for attempt in range(1, F1_SET_RETRIES + 1):
            try:
                async with asyncio.timeout(F1_SET_COMMAND_TIMEOUT):
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

        # Read back until the device reports the values we just wrote.
        # Pass/fail is decided on the overridden keys only: other zones (e.g. a
        # timer switching a zone on -> keep) or unknown* bytes may legitimately
        # change within this window and must not fail an unrelated write.
        seen = False
        confirmed = False
        for _ in range(F1_READBACK_TRIES):
            await asyncio.sleep(F1_READBACK_DELAY)
            actual = await _read_epc(coordinator, 0xF1)
            _LOGGER.debug("KAITEKI F1 readback=%s", actual)
            if not isinstance(actual, dict):
                continue
            seen = True
            coordinator.async_set_updated_data(
                {**(coordinator.data or {}), 0xF1: actual}
            )
            # Full-frame match: the device applied everything, so the
            # _last_sent overlay is no longer needed.
            if all(actual.get(k) == v for k, v in merged.items()):
                self._last_sent = {}
            if all(actual.get(k) == v for k, v in overrides.items()):
                confirmed = True
                break

        if confirmed:
            return

        # Do not re-send values the device did not apply on the next write.
        self._last_sent = {}
        _LOGGER.warning(
            "KAITEKI F1 write was acknowledged but not confirmed by read-back "
            "at %s (expected %s)",
            coordinator._host,
            overrides,
        )
        if not seen:
            # No real data came back: drop the optimistic state.
            coordinator.async_set_updated_data(
                {**(coordinator.data or {}), 0xF1: base}
            )
        raise HomeAssistantError(
            "KAITEKI did not confirm the requested zone settings"
        )


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

        # KAITEKI airflow is carried by 0xF1 rather than the standard
        # ECHONET fan-speed EPC.
        self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
        self._attr_fan_modes = list(AIRFLOW_TO_BYTE)

    def _zone_value(self, suffix):
        """Return a value for the first physical zone in this group."""
        f1 = self.coordinator.data.get(0xF1)
        if not isinstance(f1, dict):
            return None
        return f1.get(f"zone{self.zones[0]}{suffix}")

    @property
    def native_current_temperature(self):
        """Return the room temperature for the representative zone."""
        fa = self.coordinator.data.get(0xFA)
        if not isinstance(fa, dict):
            return super().native_current_temperature
        return fa.get(f"zone{self.zones[0]}Temp")

    @property
    def native_target_temperature(self):
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
        attrs["zone_status"] = self._zone_value("Status")   # on / off / keep
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
        """Turn off this zone group."""
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
    """Return the physical zone layout from F2 zoneGrouping, or None.

    None means "not a KAITEKI unit". For a KAITEKI unit whose F2 is missing or
    unknown, the independent 3-zone layout is used so that the standard
    entity (which cannot decode this unit's raw power value) is never used.
    """
    if not is_kaiteki(coordinator):
        return None
    f2 = coordinator.data.get(0xF2)
    grouping = f2.get("zoneGrouping") if isinstance(f2, dict) else None
    if grouping not in ZONE_GROUPINGS:
        _LOGGER.warning(
            "KAITEKI zoneGrouping unavailable (%r), using default layout", grouping
        )
        grouping = DEFAULT_ZONE_GROUPING
    return ZONE_GROUPINGS[grouping]


def get_kaiteki_zone_group(coordinator, zones):
    """Return the zone group shared by all KAITEKI entities of a coordinator."""
    group = getattr(coordinator, "_kaiteki_zone_group", None)
    if group is None or group.grouping != zones:
        group = KaitekiZoneGroup(coordinator, zones)
        coordinator._kaiteki_zone_group = group
    return group


def get_kaiteki_hidden_zone_keys(coordinator, keys):
    """Return the per-zone keys that duplicate a group's representative zone.

    Zones in the same group share one controller, so only the first zone of
    each group is exposed (matches EchonetKaitekiClimate). Returns an empty
    set for units that are not KAITEKI.
    """
    zones = get_kaiteki_zones(coordinator)
    if zones is None:
        return set()
    prefixes = tuple(f"zone{zone}" for group in zones for zone in group[1:])
    if not prefixes:
        return set()
    return {key for key in keys if key.startswith(prefixes)}


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


async def async_set_away_mode(coordinator, option):
    """Write Away Mode (0xF0, byte 2 of 4) keeping the other bytes intact."""
    if option not in AWAY_TO_BYTE:
        raise HomeAssistantError(f"Unsupported Away Mode: {option}")

    semaphore = _host_semaphores.setdefault(coordinator._host, asyncio.Semaphore(1))
    async with semaphore:
        try:
            async with asyncio.timeout(F1_SET_OVERALL_TIMEOUT):
                await _write_away_locked(coordinator, option)
        except TimeoutError as err:
            raise HomeAssistantError("KAITEKI Away Mode write timed out") from err


async def _write_away_locked(coordinator, option):
    """Read-modify-write 0xF0. The host semaphore must already be held."""
    # Start from a fresh GET so the unused bytes are never overwritten with
    # stale values.
    base = await _read_epc(coordinator, 0xF0)
    if not isinstance(base, dict):
        raise HomeAssistantError("KAITEKI Away Mode could not be read before writing")

    values = [
        base.get("unknown1"),
        AWAY_TO_BYTE[option],
        base.get("unknown2"),
        base.get("unknown3"),
    ]
    if not all(isinstance(v, int) for v in values):
        raise HomeAssistantError("Incomplete Away Mode data")
    edt = bytes(values)

    for attempt in range(1, F1_SET_RETRIES + 1):
        try:
            async with asyncio.timeout(F1_SET_COMMAND_TIMEOUT):
                ok = await coordinator._instance.setMessage(
                    0xF0, int.from_bytes(edt, "big"), pdc=len(edt)
                )
        except TimeoutError:
            ok = False
        if ok:
            break
        await asyncio.sleep(F1_RETRY_DELAY)
    else:
        raise HomeAssistantError("KAITEKI did not acknowledge Away Mode")

    # Read back until the device reports the new value.
    for _ in range(F1_READBACK_TRIES):
        await asyncio.sleep(F1_READBACK_DELAY)
        actual = await _read_epc(coordinator, 0xF0)
        if not isinstance(actual, dict):
            continue
        coordinator.async_set_updated_data({**(coordinator.data or {}), 0xF0: actual})
        if actual.get("awayMode") == option:
            return
    _LOGGER.warning(
        "KAITEKI Away Mode write was acknowledged but not confirmed at %s",
        coordinator._host,
    )
    raise HomeAssistantError("KAITEKI did not confirm Away Mode")
