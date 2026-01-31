from src.core.brightness_action_base import BrightnessAction, clamp_int


class MonitorBrightnessDial(BrightnessAction):
    def __init__(self, action: str, context: str, settings: dict, plugin):
        super().__init__(action, context, settings or {}, plugin)
        self._timer_key = f"monitor_brightness_dial_{context}"
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

    def refresh_title(self) -> None:
        self.hub.scan(force=False)
        count = self.hub.get_monitor_count()
        if count <= 0:
            self.set_title("无显示器")
            return
        idx = self.hub.get_selected_monitor_index() % count
        brightness = self.hub.get_monitor_brightness(idx)
        if brightness is None:
            self.set_title(f"{idx + 1}/{count}\n--")
        else:
            self.set_title(f"{idx + 1}/{count}\n{brightness}%")

    def _cycle_monitor(self, delta: int):
        self.hub.scan(force=False)
        self.hub.cycle_selected_monitor(delta)
        self.hub.save_global_settings()
        self.hub.broadcast_refresh()

    def on_key_up(self, payload: dict):
        self._cycle_monitor(1)

    def on_dial_down(self, payload: dict):
        self._cycle_monitor(1)

    def on_dial_rotate(self, payload: dict):
        ticks = payload.get("ticks")
        if ticks is None:
            ticks = payload.get("delta")
        try:
            ticks = int(ticks)
        except Exception:
            ticks = 0

        self.hub.scan(force=False)
        count = self.hub.get_monitor_count()
        if count <= 0:
            self.refresh_title()
            return

        step = self._get_step(default_step=5)
        idx = self.hub.get_selected_monitor_index() % count
        current = self.hub.get_monitor_brightness(idx)
        if current is None:
            current = 50
        new_value = clamp_int(int(current) + ticks * step, 0, 100, int(current))
        self.hub.set_monitor_brightness_preview(idx, new_value)
        self.hub.schedule_apply_selected(delay_ms=180, percent=new_value)
        self.hub.broadcast_refresh()
