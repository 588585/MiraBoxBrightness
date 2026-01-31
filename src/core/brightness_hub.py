from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .logger import Logger
from .monitor_control import MonitorManager


def _clamp_int(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


@dataclass
class BrightnessState:
    all_brightness: int = 50
    selected_monitor_index: int = 0


class BrightnessHub:
    def __init__(self, plugin):
        self._plugin = plugin
        self._lock = threading.RLock()
        self._manager = MonitorManager()
        self._state = BrightnessState()
        self._last_scan_ts = 0.0
        self._apply_all_timer: Optional[threading.Timer] = None
        self._apply_selected_timer: Optional[threading.Timer] = None
        self._saved_global_loaded = False
        self._brightness_preview: Dict[int, tuple[int, float]] = {}

        try:
            self._plugin.get_global_settings()
        except Exception:
            pass

        self.scan(force=True)
        self._init_all_from_first_monitor_if_needed()

    def scan(self, force: bool = False) -> None:
        with self._lock:
            now = time.time()
            if not force and now - self._last_scan_ts < 3.0:
                return
            self._manager.scan()
            self._last_scan_ts = now

    def _init_all_from_first_monitor_if_needed(self) -> None:
        with self._lock:
            if self._saved_global_loaded:
                return
            try:
                current = self._manager.get_brightness_percent(0)
                if current is not None:
                    self._state.all_brightness = int(current)
            except Exception:
                pass

    def load_global_settings(self, settings: Any) -> None:
        if not isinstance(settings, dict):
            return
        with self._lock:
            all_b = settings.get("allBrightness")
            sel = settings.get("selectedMonitorIndex")
            if isinstance(all_b, (int, float)):
                self._state.all_brightness = _clamp_int(int(all_b), 0, 100)
            if isinstance(sel, (int, float)):
                self._state.selected_monitor_index = max(0, int(sel))
            self._saved_global_loaded = True

    def save_global_settings(self) -> None:
        with self._lock:
            payload = {
                "allBrightness": int(self._state.all_brightness),
                "selectedMonitorIndex": int(self._state.selected_monitor_index),
            }
        try:
            self._plugin.set_global_settings(payload)
        except Exception:
            pass

    def get_all_brightness(self) -> int:
        with self._lock:
            return int(self._state.all_brightness)

    def set_all_brightness_preview(self, percent: int) -> int:
        with self._lock:
            self._state.all_brightness = _clamp_int(int(percent), 0, 100)
            return int(self._state.all_brightness)

    def get_selected_monitor_index(self) -> int:
        with self._lock:
            self._state.selected_monitor_index = max(0, int(self._state.selected_monitor_index))
            return int(self._state.selected_monitor_index)

    def set_selected_monitor_index(self, index: int) -> int:
        with self._lock:
            self._state.selected_monitor_index = max(0, int(index))
            return int(self._state.selected_monitor_index)

    def cycle_selected_monitor(self, delta: int = 1) -> int:
        with self._lock:
            count = len(self._manager.get_monitors())
            if count <= 0:
                self._state.selected_monitor_index = 0
                return 0
            cur = self._state.selected_monitor_index % count
            nxt = (cur + delta) % count
            self._state.selected_monitor_index = nxt
            return int(nxt)

    def get_monitor_count(self) -> int:
        with self._lock:
            return len(self._manager.get_monitors())

    def get_monitor_brightness(self, index: int) -> Optional[int]:
        with self._lock:
            idx = int(index)
            preview = self._brightness_preview.get(idx)
            if preview:
                value, ts = preview
                if time.time() - ts < 1.2:
                    return int(value)
                self._brightness_preview.pop(idx, None)
            return self._manager.get_brightness_percent(idx)

    def set_monitor_brightness_preview(self, index: int, percent: int) -> int:
        with self._lock:
            idx = int(index)
            value = _clamp_int(int(percent), 0, 100)
            self._brightness_preview[idx] = (value, time.time())
            return value

    def set_monitor_brightness_now(self, index: int, percent: int) -> bool:
        self.scan(force=False)
        ok = self._manager.set_brightness_percent(int(index), int(percent))
        if not ok:
            self.scan(force=True)
            ok = self._manager.set_brightness_percent(int(index), int(percent))
        return ok

    def apply_all_now(self) -> int:
        self.scan(force=False)
        target = self.get_all_brightness()
        ok_count = self._manager.set_all_brightness_percent(target)
        if ok_count <= 0:
            self.scan(force=True)
            ok_count = self._manager.set_all_brightness_percent(target)
        return ok_count

    def schedule_apply_all(self, delay_ms: int = 350) -> None:
        with self._lock:
            if self._apply_all_timer:
                try:
                    self._apply_all_timer.cancel()
                except Exception:
                    pass
                self._apply_all_timer = None

            def _run():
                try:
                    self.apply_all_now()
                    self.broadcast_refresh()
                except Exception as e:
                    Logger.error(f"Apply all brightness failed: {e}")

            t = threading.Timer(max(0.05, delay_ms / 1000.0), _run)
            t.daemon = True
            self._apply_all_timer = t
            t.start()

    def schedule_apply_selected(self, delay_ms: int = 180, percent: Optional[int] = None) -> None:
        with self._lock:
            if self._apply_selected_timer:
                try:
                    self._apply_selected_timer.cancel()
                except Exception:
                    pass
                self._apply_selected_timer = None

            idx = self.get_selected_monitor_index()
            if percent is None:
                current = self.get_monitor_brightness(idx)
                if current is None:
                    return
                percent = int(current)
            percent = _clamp_int(int(percent), 0, 100)

            def _run():
                try:
                    self.set_monitor_brightness_now(idx, percent)
                    self.broadcast_refresh()
                except Exception as e:
                    Logger.error(f"Apply selected brightness failed: {e}")

            t = threading.Timer(max(0.05, delay_ms / 1000.0), _run)
            t.daemon = True
            self._apply_selected_timer = t
            t.start()

    def broadcast_refresh(self) -> None:
        try:
            actions = list(getattr(self._plugin, "actions", {}).values())
        except Exception:
            actions = []
        for a in actions:
            try:
                if hasattr(a, "refresh_title"):
                    a.refresh_title()
            except Exception:
                continue


_hub: Optional[BrightnessHub] = None
_hub_lock = threading.Lock()


def get_brightness_hub(plugin) -> BrightnessHub:
    global _hub
    with _hub_lock:
        if _hub is None:
            _hub = BrightnessHub(plugin)
        return _hub
