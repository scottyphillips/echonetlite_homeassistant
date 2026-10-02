"""Vertical vane labels in physical order rather than protocol byte order."""

from pychonet.HomeAirConditioner import AIRFLOW_VERT

OPTION_NUMBERED_VANE_POSITIONS = "numbered_vane_positions"
VERTICAL_LABELS = {
    "auto-vert": "Auto",
    "vert": "Swing",
    "upper": "Position 1",
    "upper-central": "Position 2",
    "central": "Position 3",
    "lower-central": "Position 4",
    "lower": "Position 5",
}


class VanePositionOptions:
    """Translate supported vertical positions without adding horizontal control."""

    def __init__(self, configured, numbered=False):
        self.numbered = numbered
        self.modes = list(configured)
        if numbered:
            self.modes = [m for m in VERTICAL_LABELS if m in self.modes] + [
                m for m in self.modes if m not in VERTICAL_LABELS
            ]
        self.labels = {
            VERTICAL_LABELS.get(mode, mode) if numbered else mode: mode
            for mode in self.modes
        }

    @property
    def options(self):
        """Return positions in display order."""
        return list(self.labels)

    def label_for_value(self, value):
        """Decode static vane readings without sorting their non-monotonic codes."""
        if isinstance(value, int):
            value = next((m for m, code in AIRFLOW_VERT.items() if code == value), None)
        if not self.numbered:
            return value
        return next(
            (label for label, mode in self.labels.items() if mode == value), None
        )

    def mode_for_label(self, label):
        """Accept display labels and existing named commands for supported positions."""
        if label in self.labels:
            return self.labels[label]
        if label in self.modes:
            return label
        raise ValueError(f"Vertical vane position {label!r} is not configured")
