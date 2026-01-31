from __future__ import annotations

from typing import Any, Dict, Optional

from .action import Action
from .brightness_hub import BrightnessHub, get_brightness_hub


def clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        v = int(value)
    except Exception:
        return int(default)
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


class BrightnessAction(Action):
    @property
    def hub(self) -> BrightnessHub:
        return get_brightness_hub(self.plugin)

    def on_did_receive_global_settings(self, settings: dict):
        self.hub.load_global_settings(settings)
        self.refresh_title()

    def on_did_receive_settings(self, settings: dict):
        self.settings = settings or {}
        self.refresh_title()

    def refresh_title(self) -> None:
        return None

    def _get_step(self, default_step: int = 5) -> int:
        return clamp_int((self.settings or {}).get("step"), 1, 50, default_step)

    def _get_refresh_ms(self, default_ms: int = 3000) -> int:
        return clamp_int((self.settings or {}).get("refreshMs"), 250, 60000, default_ms)

