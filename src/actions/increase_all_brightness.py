from src.core.brightness_action_base import BrightnessAction


class IncreaseAllBrightness(BrightnessAction):
    def __init__(self, action: str, context: str, settings: dict, plugin):
        super().__init__(action, context, settings or {}, plugin)
        self.refresh_title()

    def refresh_title(self) -> None:
        step = self._get_step(default_step=5)
        self.set_title(self.plugin.t("inc_all", step=step))

    def on_key_up(self, payload: dict):
        step = self._get_step(default_step=5)
        current = self.hub.get_all_brightness()
        self.hub.set_all_brightness_preview(current + step)
        self.hub.save_global_settings()
        ok_count = self.hub.apply_all_now()
        self.hub.broadcast_refresh()
        if ok_count > 0:
            self.show_ok()
        else:
            self.show_alert()
