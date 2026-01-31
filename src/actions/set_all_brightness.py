from src.core.brightness_action_base import BrightnessAction, clamp_int


class SetAllBrightness(BrightnessAction):
    def __init__(self, action: str, context: str, settings: dict, plugin):
        super().__init__(action, context, settings or {}, plugin)
        self.refresh_title()

    def _get_target(self) -> int:
        return clamp_int((self.settings or {}).get("value"), 0, 100, 50)

    def refresh_title(self) -> None:
        value = self._get_target()
        self.set_title(self.plugin.t("set_to", value=value))

    def on_key_up(self, payload: dict):
        value = self._get_target()
        self.hub.set_all_brightness_preview(value)
        self.hub.save_global_settings()
        ok_count = self.hub.apply_all_now()
        self.hub.broadcast_refresh()
        if ok_count > 0:
            self.show_ok()
        else:
            self.show_alert()
