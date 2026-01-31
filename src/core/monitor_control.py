from __future__ import annotations

import ctypes
import json
import subprocess
import threading
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

from .logger import Logger


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_dxva2 = ctypes.WinDLL("dxva2", use_last_error=True)


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [
        ("hPhysicalMonitor", ctypes.c_void_p),
        ("szPhysicalMonitorDescription", ctypes.c_wchar * 128),
    ]


_MonitorEnumProc = ctypes.WINFUNCTYPE(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.POINTER(_RECT),
    ctypes.c_void_p,
)


_user32.EnumDisplayMonitors.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    _MonitorEnumProc,
    ctypes.c_void_p,
]
_user32.EnumDisplayMonitors.restype = ctypes.c_int

_dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
_dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = ctypes.c_int

_dxva2.GetPhysicalMonitorsFromHMONITOR.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(_PHYSICAL_MONITOR),
]
_dxva2.GetPhysicalMonitorsFromHMONITOR.restype = ctypes.c_int

_dxva2.DestroyPhysicalMonitors.argtypes = [ctypes.c_uint32, ctypes.POINTER(_PHYSICAL_MONITOR)]
_dxva2.DestroyPhysicalMonitors.restype = ctypes.c_int

_dxva2.GetMonitorBrightness.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_uint32),
]
_dxva2.GetMonitorBrightness.restype = ctypes.c_int

_dxva2.SetMonitorBrightness.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
_dxva2.SetMonitorBrightness.restype = ctypes.c_int

_dxva2.GetVCPFeatureAndVCPFeatureReply.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ubyte,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_uint32),
]
_dxva2.GetVCPFeatureAndVCPFeatureReply.restype = ctypes.c_int

_dxva2.SetVCPFeature.argtypes = [ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_uint32]
_dxva2.SetVCPFeature.restype = ctypes.c_int


def _clamp_int(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _safe_percent_from_raw(current: int, min_v: int, max_v: int) -> int:
    if max_v <= min_v:
        return 0
    pct = int(round((current - min_v) * 100.0 / (max_v - min_v)))
    return _clamp_int(pct, 0, 100)


def _raw_from_percent(percent: int, min_v: int, max_v: int) -> int:
    percent = _clamp_int(int(percent), 0, 100)
    if max_v <= min_v:
        return min_v
    raw = int(round(min_v + (max_v - min_v) * (percent / 100.0)))
    return _clamp_int(raw, min_v, max_v)


def _ps_single_quote(s: str) -> str:
    return s.replace("'", "''")


def _run_powershell_json(script: str, timeout_s: float = 2.5) -> Any:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    stdout = (completed.stdout or "").strip()
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "").strip() or "PowerShell execution failed")
    if not stdout:
        return None
    return json.loads(stdout)


@dataclass
class MonitorInfo:
    name: str
    backend: str


class MonitorBackend:
    def get_info(self) -> MonitorInfo:
        raise NotImplementedError

    def get_brightness_percent(self) -> Optional[int]:
        raise NotImplementedError

    def set_brightness_percent(self, percent: int) -> bool:
        raise NotImplementedError

    def close(self) -> None:
        return None


class DdcCiMonitor(MonitorBackend):
    def __init__(self, handle: int, description: str):
        self._handle = ctypes.c_void_p(handle)
        self._description = description.strip() or "DDC/CI"
        self._lock = threading.RLock()

    def get_info(self) -> MonitorInfo:
        return MonitorInfo(name=self._description, backend="ddcci")

    def _get_brightness_raw(self) -> Optional[Tuple[int, int, int]]:
        min_v = ctypes.c_uint32()
        cur_v = ctypes.c_uint32()
        max_v = ctypes.c_uint32()
        ok = _dxva2.GetMonitorBrightness(self._handle, ctypes.byref(min_v), ctypes.byref(cur_v), ctypes.byref(max_v))
        if ok:
            return int(min_v.value), int(cur_v.value), int(max_v.value)

        cur = ctypes.c_uint32()
        maxv = ctypes.c_uint32()
        ok = _dxva2.GetVCPFeatureAndVCPFeatureReply(
            self._handle,
            ctypes.c_ubyte(0x10),
            None,
            ctypes.byref(cur),
            ctypes.byref(maxv),
        )
        if ok:
            return 0, int(cur.value), int(maxv.value)
        return None

    def get_brightness_percent(self) -> Optional[int]:
        with self._lock:
            raw = self._get_brightness_raw()
            if not raw:
                return None
            min_v, cur_v, max_v = raw
            return _safe_percent_from_raw(cur_v, min_v, max_v)

    def set_brightness_percent(self, percent: int) -> bool:
        with self._lock:
            raw = self._get_brightness_raw()
            if raw:
                min_v, _cur_v, max_v = raw
                new_raw = _raw_from_percent(percent, min_v, max_v)
                ok = _dxva2.SetMonitorBrightness(self._handle, ctypes.c_uint32(new_raw))
                if ok:
                    return True

            percent = _clamp_int(int(percent), 0, 100)
            ok = _dxva2.SetVCPFeature(self._handle, ctypes.c_ubyte(0x10), ctypes.c_uint32(percent))
            return bool(ok)

    def close(self) -> None:
        return None


class WmiMonitor(MonitorBackend):
    def __init__(self, instance_name: str):
        self._instance_name = instance_name
        self._lock = threading.RLock()

    def get_info(self) -> MonitorInfo:
        return MonitorInfo(name=self._instance_name, backend="wmi")

    def get_brightness_percent(self) -> Optional[int]:
        with self._lock:
            escaped = _ps_single_quote(self._instance_name)
            script = (
                "$b = Get-CimInstance -Namespace root\\wmi -ClassName WmiMonitorBrightness "
                f"| Where-Object {{$_.InstanceName -eq '{escaped}'}} "
                "| Select-Object -First 1 -Property CurrentBrightness; "
                "if ($null -eq $b) { $null } else { $b.CurrentBrightness } | ConvertTo-Json -Compress"
            )
            try:
                value = _run_powershell_json(script)
                if value is None:
                    return None
                return _clamp_int(int(value), 0, 100)
            except Exception as e:
                Logger.error(f"WMI get brightness failed: {e}")
                return None

    def set_brightness_percent(self, percent: int) -> bool:
        with self._lock:
            percent = _clamp_int(int(percent), 0, 100)
            escaped = _ps_single_quote(self._instance_name)
            script = (
                "$m = Get-CimInstance -Namespace root\\wmi -ClassName WmiMonitorBrightnessMethods "
                f"| Where-Object {{$_.InstanceName -eq '{escaped}'}} | Select-Object -First 1; "
                "if ($null -eq $m) { $false } else { "
                f"Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness -Arguments @{{Timeout=0;Brightness={percent}}} | Out-Null; "
                "$true } | ConvertTo-Json -Compress"
            )
            try:
                value = _run_powershell_json(script, timeout_s=3.5)
                return bool(value)
            except Exception as e:
                Logger.error(f"WMI set brightness failed: {e}")
                return False


class MonitorManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._ddc_handles: List[_PHYSICAL_MONITOR] = []
        self._monitors: List[MonitorBackend] = []

    def close(self) -> None:
        with self._lock:
            self._destroy_ddc_handles()
            self._monitors = []

    def _destroy_ddc_handles(self) -> None:
        if not self._ddc_handles:
            return
        try:
            arr_type = _PHYSICAL_MONITOR * len(self._ddc_handles)
            arr = arr_type(*self._ddc_handles)
            _dxva2.DestroyPhysicalMonitors(ctypes.c_uint32(len(self._ddc_handles)), arr)
        except Exception:
            pass
        finally:
            self._ddc_handles = []

    def scan(self) -> List[MonitorBackend]:
        with self._lock:
            self._destroy_ddc_handles()
            ddc_list: List[MonitorBackend] = []

            hmonitors: List[int] = []

            @_MonitorEnumProc
            def _cb(hmonitor, _hdc, _rect, _lparam):
                hmonitors.append(int(ctypes.cast(hmonitor, ctypes.c_void_p).value or 0))
                return 1

            ok = _user32.EnumDisplayMonitors(None, None, _cb, None)
            if not ok:
                Logger.error(f"EnumDisplayMonitors failed: {ctypes.get_last_error()}")

            for hmon in hmonitors:
                count = ctypes.c_uint32()
                ok = _dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(ctypes.c_void_p(hmon), ctypes.byref(count))
                if not ok or not count.value:
                    continue
                arr_type = _PHYSICAL_MONITOR * int(count.value)
                arr = arr_type()
                ok = _dxva2.GetPhysicalMonitorsFromHMONITOR(ctypes.c_void_p(hmon), count, arr)
                if not ok:
                    continue

                for i in range(int(count.value)):
                    pm = arr[i]
                    self._ddc_handles.append(pm)
                    desc = str(pm.szPhysicalMonitorDescription)
                    ddc_list.append(DdcCiMonitor(int(pm.hPhysicalMonitor), desc))

            wmi_list: List[MonitorBackend] = []
            try:
                script = (
                    "Get-CimInstance -Namespace root\\wmi -ClassName WmiMonitorBrightness "
                    "| Select-Object -Property InstanceName "
                    "| ConvertTo-Json -Compress"
                )
                value = _run_powershell_json(script, timeout_s=2.5)
                instances: Sequence[Any]
                if value is None:
                    instances = []
                elif isinstance(value, list):
                    instances = value
                else:
                    instances = [value]
                for item in instances:
                    name = (item or {}).get("InstanceName")
                    if isinstance(name, str) and name.strip():
                        wmi_list.append(WmiMonitor(name.strip()))
            except Exception:
                wmi_list = []

            self._monitors = [*ddc_list, *wmi_list]
            return list(self._monitors)

    def get_monitors(self) -> List[MonitorBackend]:
        with self._lock:
            return list(self._monitors)

    def get_brightness_percent(self, index: int) -> Optional[int]:
        with self._lock:
            if index < 0 or index >= len(self._monitors):
                return None
            return self._monitors[index].get_brightness_percent()

    def set_brightness_percent(self, index: int, percent: int) -> bool:
        with self._lock:
            if index < 0 or index >= len(self._monitors):
                return False
            return self._monitors[index].set_brightness_percent(percent)

    def set_all_brightness_percent(self, percent: int) -> int:
        with self._lock:
            ok_count = 0
            for m in self._monitors:
                try:
                    if m.set_brightness_percent(percent):
                        ok_count += 1
                except Exception:
                    continue
            return ok_count

