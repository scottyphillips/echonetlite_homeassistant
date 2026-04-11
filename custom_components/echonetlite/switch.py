"""Support for ECHONETLite switches."""

import asyncio
import logging
from homeassistant.const import CONF_ICON, CONF_SERVICE_DATA, CONF_NAME
from homeassistant.components.switch import SwitchEntity
from .base_entity import EchonetEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import get_name_by_epc_code, get_device_name
from .const import (
    CONF_DISABLED_DEFAULT,
    DOMAIN,
    CONF_ON_VALUE,
    CONF_OFF_VALUE,
    NON_SETUP_SINGLE_ENYITY,
    SWITCH_POWER,
    CONF_ENSURE_ON,
    TYPE_SWITCH,
    TYPE_NUMBER,
    ENL_STATUS,
    CONF_FORCE_POLLING,
)
from pychonet.lib.eojx import EOJX_CLASS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the ECHONETLite switch platform."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        set_enl_status = False
        _enl_op_codes = entity["echonetlite"]._enl_op_codes

        # Configure switch entities by looking up full ENL_OP_CODE dict
        for op_code in list(
            set(entity["instance"]["setmap"])
            - NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())
        ):
            epc_function_data = entity["echonetlite"]._instance.EPC_FUNCTIONS.get(
                op_code, None
            )
            _by_epc_func = (
                type(epc_function_data) == list
                and type(epc_function_data[1]) == dict
                and len(epc_function_data[1]) == 2
            )
            _enl_op_code_dict = _enl_op_codes.get(op_code, {})
            if _by_epc_func or TYPE_SWITCH in _enl_op_code_dict.keys():
                entities.append(
                    EchonetSwitch(
                        entity["echonetlite"],
                        config,
                        _enl_op_code_dict,
                        op_code,
                        
                    )
                )
                if op_code == ENL_STATUS:
                    set_enl_status = True
            if (
                switch_conf := _enl_op_codes.get(op_code, {})
                .get(TYPE_NUMBER, {})
                .get(TYPE_SWITCH)
            ):
                switch_conf.update(_enl_op_codes[op_code].copy())
                entities.append(
                    EchonetSwitch(
                        entity["echonetlite"],
                        config,
                        switch_conf,
                        op_code,
                        
                    )
                )

        # Auto configure of the power switch
        # if (eojgc == 0x01 and eojcc in (0x30, 0x35)) or ( # temporary commented out so I can test on my air conditioner which has 0x01 class group code
        if (eojgc == 0x01 and eojcc == 0x35) or (  # remove line when testing is done
            eojgc == 0x02 and eojcc in (0x90, 0x91)
        ):
            # Home air conditioner, Air cleaner, General Lighting, Single Function Lighting
            continue
        if not set_enl_status and ENL_STATUS in entity["instance"]["setmap"]:
            entities.append(
                EchonetSwitch(
                    entity["echonetlite"],
                    config,
                    {
                        CONF_ICON: "mdi:power-settings",
                        CONF_SERVICE_DATA: SWITCH_POWER,
                    },
                    ENL_STATUS,

                )
            )
    async_add_entities(entities, True)


class EchonetSwitch(EchonetEntity, SwitchEntity):
    """Representation of an ECHONETLite switch."""

    def __init__(self, coordinator, config, options, epc_code, ) -> None:
        """Initialize the switch.

        Args:
            connector: The ECHONETConnector coordinator instance.
            config: The config entry for this device.
            code: The EPC operation code for this switch.
            options: Configuration options for this switch entity.
        """
        # Initialize coordinator first - must call parent before setting other properties
        super().__init__(coordinator, config)

        self._code = epc_code
        self._options = options
        self._eojgc = coordinator._eojgc
        self._eojcc = coordinator._eojcc
        self._eojci = coordinator._eojci
        self._device_name = get_device_name(coordinator, config)

        # Process EPC function data to determine on/off values
        epc_function_data = coordinator._instance.EPC_FUNCTIONS.get(epc_code, None)
        if type(epc_function_data) == list:
            data_keys = list(epc_function_data[1].keys())
            data_items = list(epc_function_data[1].values())
            options.update(
                {
                    CONF_SERVICE_DATA: {
                        "on": data_keys[0],
                        "off": data_keys[1],
                    },
                    CONF_ON_VALUE: data_items[0],
                    CONF_OFF_VALUE: data_items[1],
                }
            )

        # Determine on values for state checking (supports various formats)
        self._on_value = options.get(CONF_ON_VALUE, "on")
        service_data_on = options[CONF_SERVICE_DATA].get(
            "on", options[CONF_SERVICE_DATA].get("OFF", 1)
        )
        self._on_vals = [
            self._on_value,
            service_data_on,
            (
                hex(service_data_on)[2:]
                if isinstance(service_data_on, int)
                else str(service_data_on)
            ),
        ]

        # Determine if this is a number-type switch
        self._from_number = True if options.get(TYPE_NUMBER) else False

        # Build unique_id and name
        self._attr_unique_id = (
            f"{coordinator._uidi}-{self._code}"
            if coordinator._uidi
            else f"{coordinator._uid}-{self._eojgc}-{self._eojcc}-{self._eojci}-{self._code}"
        )
        if self._from_number:
            self._attr_unique_id += "-switch"
            self._attr_name = (
                f"{config.title} {get_name_by_epc_code(self._eojgc, self._eojcc, self._code, None, coordinator._enl_op_codes.get(self._code, {}).get(CONF_NAME))} "
                + options.get(CONF_NAME, "Switch")
            )
        else:
            self._attr_name = f"{config.title} {get_name_by_epc_code(self._eojgc, self._eojcc, self._code, None, coordinator._enl_op_codes.get(self._code, {}).get(CONF_NAME))}"

        # Set icon and enabled default from options
        self._attr_icon = options.get(CONF_ICON)
        self._attr_entity_registry_enabled_default = not bool(
            options.get(CONF_DISABLED_DEFAULT)
        )

    @property
    def device_info(self):
        """Return device information for this entity."""
        coordinator = self.coordinator
        return {
            "identifiers": {
                (
                    DOMAIN,
                    coordinator._uid,
                    self._eojgc,
                    self._eojcc,
                    self._eojci,
                )
            },
            "name": self._device_name,
            "manufacturer": coordinator._manufacturer
            + (
                " " + coordinator._host_product_code
                if coordinator._host_product_code
                else ""
            ),
            "model": EOJX_CLASS[self._eojgc][self._eojcc],
        }

    @property
    def is_on(self) -> bool | None:
        """Return True if switch is on.

        Checks the coordinator's data for the current EPC code value
        and compares against known on-values.
        """
        raw_val = self.coordinator.data.get(self._code)
        if raw_val is None:
            return None
        return raw_val in self._on_vals

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return device-specific state attributes.

        Indicates whether the entity receives push notifications or requires polling.
        """
        _should_poll = self._code not in self.coordinator._ntfPropertyMap
        return {"notify": "No" if _should_poll else "Yes"}

    async def async_turn_on(self, **kwargs) -> None:
        """Turn switch on."""
        coordinator = self.coordinator
        main_sw_code = None

        # Check ensure turn on switch. For some devices this ensures the
        # main switch is switched on first.
        if CONF_ENSURE_ON in self._options:
            main_sw_code = self._options[CONF_ENSURE_ON]

        # Turn on the specified switch
        if main_sw_code is not None and coordinator.data.get(main_sw_code) != "on":
            if not await coordinator._instance.setMessage(
                main_sw_code, SWITCH_POWER["on"]
            ):
                # Can't turn on main switch
                return
            # Wait about 2 seconds until the On state is stabilized on the device side
            await asyncio.sleep(2)

        if main_sw_code is None or coordinator.data.get(main_sw_code) == "on":
            await coordinator._instance.setMessage(
                self._code, self._options[CONF_SERVICE_DATA]["on"]
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn switch off."""
        await self.coordinator._instance.setMessage(
            self._code, self._options[CONF_SERVICE_DATA]["off"]
        )
