from src.core.brightness_action_base import BrightnessAction, clamp_int


class ShowMonitorBrightness(BrightnessAction):
    def __init__(self, action: str, context: str, settings: dict, plugin):
        super().__init__(action, context, settings or {}, plugin)
        self._timer_key = f"show_monitor_brightness_{context}"
        self._ensure_timer()
        self.refresh_title()

    def on_will_disappear(self):
        try:
            self.plugin.timer.clear_interval(self._timer_key)
        except Exception:
            pass

    def on_did_receive_settings(self, settings: dict):
        self.settings = settings or {}
        self._ensure_timer()
        self.refresh_title()

    def _ensure_timer(self):
        refresh_ms = self._get_refresh_ms(default_ms=3000)
        try:
            self.plugin.timer.clear_interval(self._timer_key)
        except Exception:
            pass
        self.plugin.timer.set_interval(self._timer_key, refresh_ms, self.refresh_title)

    def _get_monitor_index(self, count: int) -> int:
        raw = (self.settings or {}).get("monitorIndex")
        idx = clamp_int(raw, 1, 999, 1) - 1
        if count <= 0:
            return 0
        return idx % count

    def refresh_title(self) -> None:
        self.hub.scan(force=False)
        count = self.hub.get_monitor_count()
        if count <= 0:
            self.set_title("无显示器")
            return
        idx = self._get_monitor_index(count)
        brightness = self.hub.get_monitor_brightness(idx)
        if brightness is None:
            self.set_title(f"屏{idx + 1}\n--")
        else:
            self.set_title(f"屏{idx + 1}\n{brightness}%")

    def on_key_up(self, payload: dict):
        self.refresh_title()

