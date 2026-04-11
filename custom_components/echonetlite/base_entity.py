"""Base entity for ECHONETLite."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity


class EchonetEntity(CoordinatorEntity):
    """Base class for ECHONETLite entities."""

    def __init__(self, coordinator, config, **kwargs) -> None:
        super().__init__(coordinator)
