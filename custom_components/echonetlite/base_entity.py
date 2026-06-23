"""Base entity for ECHONETLite."""

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from . import get_device_name


class EchonetEntity(Entity):
    """Base class for ECHONETLite entities.

    Previously extended CoordinatorEntity (which requires DataUpdateCoordinator).
    Now uses ECHONETConnector directly, which implements the same listener
    interface (async_add_listener / async_update_listeners) but is polled by
    ECHONETHostCoordinator rather than its own timer. This prevents _waiting
    queue saturation when multiple instances share the same host IP.
    """

    _attr_translation_key = DOMAIN
    _attr_should_poll = False

    def __init__(self, coordinator, config, **kwargs) -> None:
        super().__init__()
        self.coordinator = coordinator
        name = get_device_name(coordinator, config)
        self._attr_name = name
        self._device_name = name

    @property
    def available(self) -> bool:
        """Return True if the coordinator last update was successful."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Register listener when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Request a refresh via the host coordinator."""
        if self.coordinator._host_coordinator is not None:
            await self.coordinator._host_coordinator.async_request_refresh()

    @property
    def device_info(self):
        """Return device information for this entity."""
        from pychonet.lib.eojx import EOJX_CLASS

        return {
            "identifiers": {
                (
                    DOMAIN,
                    self.coordinator._uid,
                    self.coordinator._eojgc,
                    self.coordinator._eojcc,
                    self.coordinator._eojci,
                )
            },
            "name": self._device_name,
            "manufacturer": (self.coordinator._manufacturer or "Unknown")
            + (
                " " + self.coordinator._host_product_code
                if self.coordinator._host_product_code
                else ""
            ),
            "model": EOJX_CLASS[self.coordinator._eojgc][self.coordinator._eojcc],
        }

    def _build_unique_id(self, suffix: str | None = None) -> str:
        """Build unique ID with optional suffix."""
        if self.coordinator._uidi:
            return (
                f"{self.coordinator._uidi}-{suffix}"
                if suffix
                else self.coordinator._uidi
            )
        return (
            f"{self.coordinator._uid}-{self.coordinator._eojgc}-"
            f"{self.coordinator._eojcc}-{self.coordinator._eojci}-{suffix}"
            if suffix
            else self.coordinator._uid
        )

    def _build_final_unique_id(
        self, base_id: str, extra_suffixes: list | None = None
    ) -> str:
        """Append dynamic suffixes to a base unique_id."""
        if not extra_suffixes:
            return base_id
        return f"{base_id}-{'-'.join(str(s) for s in extra_suffixes)}"

    def is_settable(self, epc_code: int) -> bool:
        """Check if an EPC code is settable on this device."""
        return epc_code in list(self.coordinator._setPropertyMap)