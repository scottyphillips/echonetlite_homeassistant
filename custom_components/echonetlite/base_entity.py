"""Base entity for ECHONETLite."""

from .const import DOMAIN
from . import get_device_name
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class EchonetEntity(CoordinatorEntity):
    """Base class for ECHONETLite entities."""

    _attr_translation_key = DOMAIN

    def __init__(self, coordinator, config, **kwargs) -> None:
        super().__init__(coordinator)
        name = get_device_name(coordinator, config)
        self._attr_name = name
        self._device_name = name

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
            "manufacturer": self.coordinator._manufacturer
            + (
                " " + self.coordinator._host_product_code
                if self.coordinator._host_product_code
                else ""
            ),
            "model": EOJX_CLASS[self.coordinator._eojgc][self.coordinator._eojcc],
        }

    def _build_unique_id(self, suffix: str | None = None) -> str:
        """Build unique ID with optional suffix.

        Uses uidi (unique device identifier) if available - the modern approach.
        Falls back to uid-based chain for older devices without uidi support.

        Args:
            suffix: Optional string to append (e.g., epc_code).

        Returns:
            Formatted unique_id string with or without suffix.
        """
        if self.coordinator._uidi:
            # Modern approach: use unique device identifier
            return (
                f"{self.coordinator._uidi}-{suffix}"
                if suffix
                else self.coordinator._uidi
            )

        # Legacy fallback: build from uid + EOJ classification chain
        return (
            f"{self.coordinator._uid}-{self.coordinator._eojgc}-"
            f"{self.coordinator._eojcc}-{self.coordinator._eojci}-{suffix}"
            if suffix
            else self.coordinator._uid
        )

    def _build_final_unique_id(
        self, base_id: str, extra_suffixes: list | None = None
    ) -> str:
        """Append dynamic suffixes to a base unique_id.

        Used for sensors with dict_key or accessor_index that create multiple
        entities from a single EPC code (e.g., multi-element arrays).

        Args:
            base_id: The base unique_id to append suffixes to.
            extra_suffixes: List of string values to append with dashes.

        Returns:
            Final formatted unique_id with all suffixes applied.
        """
        if not extra_suffixes:
            return base_id

        return f"{base_id}-{'-'.join(str(s) for s in extra_suffixes)}"
