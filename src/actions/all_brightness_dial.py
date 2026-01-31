from src.core.brightness_action_base import BrightnessAction, clamp_int


class AllBrightnessDial(BrightnessAction):
    def __init__(self, action: str, context: str, settings: dict, plugin):
        super().__init__(action, context, settings or {}, plugin)
        self.refresh_title()

    def refresh_title(self) -> None:
        value = self.hub.get_all_brightness()
        #self.set_title(f"全部\n{value}%")
        self.set_title(f"-{value}%\n全部")

    def on_dial_rotate(self, payload: dict):
        ticks = payload.get("ticks")
        if ticks is None:
            ticks = payload.get("delta")
        try:
            ticks = int(ticks)
        except Exception:
            ticks = 0

        step = self._get_step(default_step=5)
        current = self.hub.get_all_brightness()
        new_value = clamp_int(current + ticks * step, 0, 100, current)
        self.hub.set_all_brightness_preview(new_value)
        self.hub.save_global_settings()
        self.hub.broadcast_refresh()
        self.hub.schedule_apply_all(delay_ms=350)

    def on_key_up(self, payload: dict):
        self.refresh_title()

    def on_dial_down(self, payload: dict):
        self.refresh_title()
