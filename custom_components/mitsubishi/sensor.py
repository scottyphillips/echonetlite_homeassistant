"""Support for Mitsubishi HVAC sensors."""
import logging

from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE, CONF_IP_ADDRESS
from homeassistant.helpers.entity import Entity
from homeassistant.util.unit_system import UnitSystem

from .const import (
    ATTR_INSIDE_TEMPERATURE,
    ATTR_OUTSIDE_TEMPERATURE,
    SENSOR_TYPE_TEMPERATURE,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    import mitsubishi_echonet as mit
    """Set up the Mitsubishi ECHONET climate devices."""
    mitsubishi_api = mit.HomeAirConditioner(config.get(CONF_IP_ADDRESS))
    sensors = [ATTR_INSIDE_TEMPERATURE, ATTR_OUTSIDE_TEMPERATURE]
    async_add_entities(
        [
            MitsubishiClimateSensor(mitsubishi_api, sensor, hass.config.units, config.get(CONF_NAME))
            for sensor in sensors
        ]

    )


class MitsubishiClimateSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, api, monitored_state, units: UnitSystem, name=None) -> None:
        """Initialize the sensor."""
        self._api = api
        self._sensor = SENSOR_TYPES.get(monitored_state)
        if name is None:
            name = f"{self._sensor[CONF_NAME]}"
        self._name = f"{name} {monitored_state.replace('_', ' ')}"
        self._device_attribute = monitored_state

        if self._sensor[CONF_TYPE] == SENSOR_TYPE_TEMPERATURE:
            self._unit_of_measurement = units.temperature_unit

    # @property
    # def unique_id(self):
    #    """Return a unique ID."""
    #    return f"{self._api.mac}-{self._device_attribute}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._sensor[CONF_ICON]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""

        if self._device_attribute == ATTR_INSIDE_TEMPERATURE:
            if self._api.roomTemperature == 126 or self._api.roomTemperature == None:
               return 'unavailable'
            else:
               return self._api.roomTemperature

        if self._device_attribute == ATTR_OUTSIDE_TEMPERATURE:
            if self._api.outdoorTemperature == 126 or self._api.outdoorTemperature == None:
               return 'unavailable'
            else:
               return self._api.outdoorTemperature
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def async_update(self):
        """Retrieve latest state."""
        try:
            await self.hass.async_add_executor_job(self._api.update)
            ## self._api.getOutdoorTemperature()
        except KeyError:
           _LOGGER.warning("HA requested an update from HVAC %s but no data was received", self._api.netif)

    # @property
    # def device_info(self):
    #    """Return a device description for device registry."""
    #    return self._api.
