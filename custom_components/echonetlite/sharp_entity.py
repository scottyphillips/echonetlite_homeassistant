"""Shared coordinator-backed entity for proven, model-scoped Sharp fields."""

from .base_entity import EchonetEntity
from .sharp import sharp_field, sharp_value


class SharpFieldEntity(EchonetEntity):
    """Reuse the existing connector; no entity owns a polling loop."""

    def __init__(self, coordinator, config, key):
        super().__init__(coordinator, config)
        _, name, icon = sharp_field(key)
        self._sharp_key = key
        self._attr_unique_id = self._build_unique_id(f"sharp-{key}")
        self._attr_name = f"{config.title} {name}"
        self._attr_icon = icon

    @property
    def available(self):
        return super().available and self.sharp_state is not None

    @property
    def sharp_state(self):
        return sharp_value(self.coordinator.data, self._sharp_key)
