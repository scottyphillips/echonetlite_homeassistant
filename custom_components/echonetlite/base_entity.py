"""Base entity for ECHONETLite."""

from .const import DOMAIN
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class EchonetEntity(CoordinatorEntity):
    """Base class for ECHONETLite entities."""

    _attr_translation_key = DOMAIN

    def __init__(self, coordinator, config, **kwargs) -> None:
        super().__init__(coordinator)
