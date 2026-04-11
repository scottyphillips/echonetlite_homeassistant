"""Base entity for ECHONETLite."""

from .const import DOMAIN
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class EchonetEntity(CoordinatorEntity):
    """Base class for ECHONETLite entities."""

    _attr_translation_key = DOMAIN

    def __init__(self, coordinator, config, **kwargs) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self):
        """Return device information for this entity."""
        from pychonet.lib.eojx import EOJX_CLASS
        
        return {
            "identifiers": {
                (DOMAIN, self.coordinator._uid, self.coordinator._eojgc, self.coordinator._eojcc, self.coordinator._eojci)
            },
            "name": self.coordinator._entry_title if hasattr(self.coordinator, '_entry_title') else getattr(self, '_device_name', 'Device'),
            "manufacturer": self.coordinator._manufacturer,
            "model": EOJX_CLASS[self.coordinator._eojgc][self.coordinator._eojcc],
        }

    def _build_unique_id(self, suffix: str | None = None, include_device_info: bool = False) -> str:
        """Build unique ID with optional suffix.
        
        Args:
            suffix: Optional string to append after uidi/uid (e.g., epc_code).
            include_device_info: If True, use full device info fallback format.
            
        Returns:
            Formatted unique_id string.
        """
        if self.coordinator._uidi:
            base = self.coordinator._uidi
            return f"{base}-{suffix}" if suffix else base
        
        # Fallback to full identifier chain
        parts = [self.coordinator._uid, self.coordinator._eojgc, self.coordinator._eojcc, self.coordinator._eojci]
        if include_device_info:
            result = "-".join(str(p) for p in parts)
        else:
            result = self.coordinator._uid
        
        return f"{result}-{suffix}" if suffix else result