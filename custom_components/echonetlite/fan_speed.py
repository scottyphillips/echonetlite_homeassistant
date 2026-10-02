"""Presentation of configured HVAC speeds without changing protocol values."""

from pychonet.HomeAirConditioner import FAN_SPEED

OPTION_NUMBERED_FAN_SPEEDS = "numbered_fan_speeds"


class FanSpeedOptions:
    """Translate labels and readings using the configured subset of speeds."""

    def __init__(self, configured=None, numbered=False):
        self.numbered = numbered
        self.modes = list(configured or FAN_SPEED)
        self.modes = list(dict.fromkeys(m for m in self.modes if m in FAN_SPEED))
        if numbered:
            self.modes.sort(key=lambda m: -1 if m == "auto" else FAN_SPEED[m])
        self.labels = {}
        level = 0
        for mode in self.modes:
            if numbered and mode != "auto":
                level += 1
                label = f"{level} bar" if level == 1 else f"{level} bars"
            else:
                label = mode
            self.labels[label] = mode

    @property
    def options(self):
        """Return labels in display order."""
        return list(self.labels)

    def label_for_value(self, value):
        """Decode named or raw readings without guessing an unconfigured level."""
        if isinstance(value, int):
            value = next((m for m, code in FAN_SPEED.items() if code == value), None)
        if value not in FAN_SPEED:
            return None
        if not self.numbered:
            return value
        return next(
            (label for label, mode in self.labels.items() if mode == value), None
        )

    def mode_for_label(self, label):
        """Accept displayed labels and existing named commands for enabled speeds."""
        if label in self.labels:
            return self.labels[label]
        if label in self.modes:
            return label
        raise ValueError(f"Fan speed {label!r} is not configured")
