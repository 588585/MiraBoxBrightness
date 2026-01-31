let _ws;
let _uuid;
let _context;
let _action;
let _settings = {};
let _saveTimer = null;

function _send(data) {
  if (_ws && _ws.readyState === 1) {
    _ws.send(JSON.stringify(data));
  }
}

function _saveSettingsDebounced() {
  if (_saveTimer) {
    clearTimeout(_saveTimer);
  }
  _saveTimer = setTimeout(() => {
    _send({
      event: "setSettings",
      context: _uuid,
      payload: _settings,
    });
  }, 80);
}

function _int(v, fallback) {
  const n = Number(v);
  if (!Number.isFinite(n)) return fallback;
  return Math.trunc(n);
}

function _clamp(n, lo, hi) {
  if (n < lo) return lo;
  if (n > hi) return hi;
  return n;
}

function _setVisible(id, visible) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.toggle("hidden", !visible);
}

function _setHint(text) {
  const el = document.getElementById("hint");
  if (el) el.textContent = text || "";
}

function _applyUiModel() {
  const a = _action || "";
  const showStep = a.endsWith("all_brightness_dial") || a.endsWith("monitor_brightness_dial") || a.endsWith("increase_all_brightness") || a.endsWith("decrease_all_brightness");
  const showRefreshMs = a.endsWith("monitor_brightness_dial") || a.endsWith("show_monitor_brightness");
  const showMonitorIndex = a.endsWith("show_monitor_brightness");
  const showValue = a.endsWith("set_all_brightness");

  _setVisible("row-step", showStep);
  _setVisible("row-refreshMs", showRefreshMs);
  _setVisible("row-monitorIndex", showMonitorIndex);
  _setVisible("row-value", showValue);

  if (a.endsWith("all_brightness_dial")) _setHint("旋钮：调整全部亮度；旋转停止后应用。");
  else if (a.endsWith("monitor_brightness_dial")) _setHint("旋钮：调整当前显示器亮度；按下切换显示器。");
  else if (a.endsWith("show_monitor_brightness")) _setHint("定时刷新指定显示器亮度。");
  else if (a.endsWith("set_all_brightness")) _setHint("按下将全部显示器亮度设为目标值。");
  else if (a.endsWith("increase_all_brightness")) _setHint("按下将全部亮度增加一个步长并应用。");
  else if (a.endsWith("decrease_all_brightness")) _setHint("按下将全部亮度减少一个步长并应用。");
  else _setHint("");
}

function _hydrateControls() {
  const stepEl = document.getElementById("step");
  const refreshEl = document.getElementById("refreshMs");
  const monitorEl = document.getElementById("monitorIndex");
  const valueEl = document.getElementById("value");

  if (stepEl) stepEl.value = _int(_settings.step, 5);
  if (refreshEl) refreshEl.value = _int(_settings.refreshMs, 3000);
  if (monitorEl) monitorEl.value = _int(_settings.monitorIndex, 1);
  if (valueEl) valueEl.value = _int(_settings.value, 50);
}

function _wireControls() {
  const stepEl = document.getElementById("step");
  const refreshEl = document.getElementById("refreshMs");
  const monitorEl = document.getElementById("monitorIndex");
  const valueEl = document.getElementById("value");

  if (stepEl) {
    stepEl.addEventListener("input", () => {
      _settings.step = _clamp(_int(stepEl.value, 5), 1, 50);
      _saveSettingsDebounced();
    });
  }
  if (refreshEl) {
    refreshEl.addEventListener("input", () => {
      _settings.refreshMs = _clamp(_int(refreshEl.value, 3000), 250, 60000);
      _saveSettingsDebounced();
    });
  }
  if (monitorEl) {
    monitorEl.addEventListener("input", () => {
      _settings.monitorIndex = _clamp(_int(monitorEl.value, 1), 1, 99);
      _saveSettingsDebounced();
    });
  }
  if (valueEl) {
    valueEl.addEventListener("input", () => {
      _settings.value = _clamp(_int(valueEl.value, 50), 0, 100);
      _saveSettingsDebounced();
    });
  }
}

function connectElgatoStreamDeckSocket(port, uuid, event, app, info) {
  _uuid = uuid;
  try {
    const parsed = JSON.parse(info);
    _action = parsed.action || "";
    _context = parsed.context || "";
  } catch (e) {
    _action = "";
    _context = "";
  }

  _applyUiModel();
  _wireControls();

  _ws = new WebSocket("ws://127.0.0.1:" + port);
  _ws.onopen = () => _send({ event, uuid });
  _ws.onmessage = (e) => {
    let msg;
    try {
      msg = JSON.parse(e.data);
    } catch (err) {
      return;
    }

    if (msg.event === "didReceiveSettings") {
      _settings = (msg.payload && msg.payload.settings) ? msg.payload.settings : {};
      _hydrateControls();
    }
  };

  _ws.onerror = () => {};
}

