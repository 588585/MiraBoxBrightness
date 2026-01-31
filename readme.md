# MiraBoxBrightness

StreamDock 插件：在面板上用旋钮/按钮调整 Windows 显示器亮度。

本仓库包含两部分：
- 插件前端资源：`com.mirabox.streamdock.brightness.sdPlugin\`（manifest、属性面板、图标）
- 插件后端程序：`src\` + `main.py`（Python，WebSocket 事件驱动）

版本：0.0.1
平台：Windows 7+（建议 Win10/Win11）

## 1. 项目目标

MiraBoxBrightness 的目标是做一组“可放到 StreamDock 面板上”的亮度控件。
你可以把它当成一个可编程的亮度遥控器。

目标场景：
- 有多台显示器（内屏 + 外接）
- 想要一键设置“全部亮度”
- 想要用旋钮微调某一块屏幕
- 想要实时显示亮度数字而不是只显示图标

非目标（目前不做）：
- 跨平台（暂仅 Windows）
- 色温、对比度等其它 VCP 功能（当前只做亮度）
- 显示器按名称映射到固定顺序（目前按系统枚举顺序）

---

## 2. 功能清单

核心能力：
- 枚举显示器（外接 DDC/CI + 内屏/部分设备 WMI）
- 获取亮度（0-100%）
- 设置亮度（0-100%）
- 多显示器场景下的“全部亮度”统一控制
- 旋钮交互的“预览值”与“延迟应用”（避免疯狂写硬件）

交互层能力：
- 按键/旋钮上直接显示文本（亮度百分比/屏幕序号）
- 旋钮转动时即时更新显示值
- 转动停止后再批量应用（全局/单屏）
- 支持配置步长、刷新间隔、目标亮度等参数

工程化能力：
- PyInstaller 打包为 `DemoPlugin.exe`
- 运行时动态加载 `src.actions.*` 的各个动作
- 修复“PyInstaller 不加 --clean 时动态导入失效”的问题
- 默认把按键背景图片置为透明，避免图标干扰文本显示

---

## 3. 快速体验（面板端）

你一般不会在命令行直接运行这个插件。
正常流程是：StreamDock 软件负责启动插件可执行文件，并通过 WebSocket 传入参数。

1) 打包得到可执行文件：
- 见第 11 章：`dist\DemoPlugin.exe`

2) 把插件目录安装到 StreamDock 的插件目录：
- 本项目的插件目录是 `com.mirabox.streamdock.brightness.sdPlugin\`
- 目录中包含 `manifest.json`，它会指向 `CodePath: "DemoPlugin.exe"`

3) 在 StreamDock 软件里添加动作：
- 全部亮度(旋钮)
- 单屏亮度(旋钮)
- 显示亮度(单屏)
- 设全部亮度
- 增加全部亮度
- 减少全部亮度

4) 在动作的属性面板里调整参数：
- step（步长）
- refreshMs（刷新间隔）
- value（目标亮度）
- monitorIndex（指定第几块屏）

提示：
- 如果你看到按钮背景仍有图标干扰文本，确认你用的是新版本后端（默认 setImage 透明）。

---

## 4. 代码结构

项目根目录关键文件：
- `main.py`：入口，解析 StreamDock 传入参数，启动插件对象
- `main.spec`：PyInstaller 打包脚本
- `requirements.txt`：Python 依赖
- `src\`：后端核心代码
- `com.mirabox.streamdock.brightness.sdPlugin\`：插件资源与配置

后端目录 `src\`：
- `src\core\`：框架层（WebSocket、Action 抽象、计时器、亮度控制、日志等）
- `src\actions\`：具体动作（按钮/旋钮的业务逻辑）

插件资源目录 `com.mirabox.streamdock.brightness.sdPlugin\`：
- `manifest.json`：动作列表、默认设置、属性面板路径、启动可执行文件
- `propertyInspector\brightness\index.html`：属性面板 UI
- `propertyInspector\brightness\index.js`：属性面板逻辑
- `static\img\icon.svg`：图标

---

## 5. 运行机制（事件流）

总体架构：WebSocket 事件驱动。
StreamDock 会把“动作出现/消失/按下/旋钮旋转/设置变更”等事件发给插件。
插件收到事件后，把它路由到对应的 Action 实例上。

关键概念：
- Action：一个面板上的“控件实例”（按钮或旋钮的一个格子）
- context：StreamDock 用来唯一标识某个格子的 ID
- settings：该格子的配置（来自属性面板）
- global settings：插件级共享状态（例如“全部亮度”“当前选中的屏幕”）

入口流程（简化）：
- `main.py` 解析 `-port -pluginUUID -registerEvent -info`
- 创建 `Plugin(port, uuid, event, info)`
- `Plugin` 连接 WebSocket，注册插件
- 收到 `willAppear` 时创建 Action 并缓存到 `self.actions[context]`
- 收到交互事件（keyUp/dialRotate 等）调用 Action 的对应方法

事件路由位置：
- `src\core\plugin.py` 的 `_on_message`
- 通过 `context` 找到 Action
- 用 `hasattr` 判断 Action 是否实现某个 handler

动作创建位置：
- `src\core\action_factory.py`
- 用 action UUID 最后一段作为 action_name
- 先扫描注册所有 actions
- 再根据 action_name 找到具体 Action 类

---

## 6. 动作（Actions）说明

动作列表与默认 settings 在 `com.mirabox.streamdock.brightness.sdPlugin\manifest.json`。
动作实现位于 `src\actions\`，文件名与 UUID 最后一段一致。

| Action（UUID 最后一段） | 用途 | 控制器 | 关键 settings | 实现文件 |
|---|---|---|---|---|
| all_brightness_dial | 旋钮控制“全部亮度”，延迟批量应用 | Knob/Keypad | step | `src\actions\all_brightness_dial.py` |
| monitor_brightness_dial | 旋钮控制“当前屏”，按下切屏 | Knob/Keypad | step, refreshMs | `src\actions\monitor_brightness_dial.py` |
| show_monitor_brightness | 定时显示指定屏亮度 | Keypad | monitorIndex, refreshMs | `src\actions\show_monitor_brightness.py` |
| set_all_brightness | 一键设定全部亮度到固定值 | Keypad | value | `src\actions\set_all_brightness.py` |
| increase_all_brightness | 一键增加全部亮度并应用 | Keypad | step | `src\actions\increase_all_brightness.py` |
| decrease_all_brightness | 一键减少全部亮度并应用 | Keypad | step | `src\actions\decrease_all_brightness.py` |

共享状态说明：
- all_brightness_dial / set_all_brightness / increase / decrease 共用 `allBrightness`
- monitor_brightness_dial 共用 `selectedMonitorIndex`
- 任意动作更新共享状态后都会 broadcast_refresh，同步更新所有控件的显示

---

## 7. 参数与设置

设置分为两类：
- 动作 settings：每个格子独立（来自属性面板）
- 插件 global settings：跨动作共享（用于同步状态）

### 7.1 动作 settings（来自 manifest 默认值）

step：
- 类型：int
- 用途：旋钮转动时的步长，或按钮增减的步长
- 默认：5

refreshMs：
- 类型：int
- 用途：显示刷新间隔（毫秒）
- 默认：3000
- 下限/上限：由代码 clamp（见 `BrightnessAction._get_refresh_ms`）

value：
- 类型：int
- 用途：set_all_brightness 的目标亮度
- 默认：50

monitorIndex：
- 类型：int（从 1 开始）
- 用途：show_monitor_brightness 指定显示第几块屏
- 默认：1

### 7.2 插件 global settings（跨控件共享）

全局状态集中在 `BrightnessHub`：
- allBrightness：一个 0-100 的共享亮度值
- selectedMonitorIndex：当前“选中的屏幕索引”（从 0 开始）

存储位置：
- 通过 StreamDock 的 global settings 存储
- 插件启动时会请求 `getGlobalSettings`
- 收到 `didReceiveGlobalSettings` 后加载

同步策略：
- 任意控件更新 allBrightness 或 selectedMonitorIndex 后，都会调用 broadcast_refresh
- broadcast_refresh 会对当前所有 Action 调用 refresh_title

---

## 8. 亮度控制后端（DDC/CI 与 WMI）

亮度控制核心在 `src\core\monitor_control.py`。
它做了两条路线：
- DDC/CI（外接显示器常见）
- WMI（内置屏/部分设备）

### 8.1 DDC/CI（dxva2.dll + user32.dll）

枚举流程：
- 调用 `EnumDisplayMonitors` 获取 HMONITOR 列表
- 对每个 HMONITOR 调用 `GetNumberOfPhysicalMonitorsFromHMONITOR`
- 再调用 `GetPhysicalMonitorsFromHMONITOR` 获取物理显示器句柄

读亮度：
- 优先 `GetMonitorBrightness`（高层 API）
- 失败则回退到 `GetVCPFeatureAndVCPFeatureReply`（VCP 0x10）

写亮度：
- 如果拿到了 min/max，会把 0-100 换算为原始范围再 `SetMonitorBrightness`
- 失败则回退 `SetVCPFeature(0x10, percent)`

优势：
- 适合外接显示器
- 调整粒度通常更细

注意：
- 不同显示器的原始亮度范围可能不是 0-100
- 本项目会做百分比换算，尽量保证体验一致

### 8.2 WMI（root\\wmi）

枚举流程：
- PowerShell 执行 `Get-CimInstance -Namespace root\\wmi -ClassName WmiMonitorBrightness`
- 读取 `InstanceName` 列表

读亮度：
- 查询 `WmiMonitorBrightness` 的 `CurrentBrightness`

写亮度：
- 调用 `WmiMonitorBrightnessMethods.WmiSetBrightness(Timeout=0, Brightness=percent)`

优势：
- 常用于内置屏
- 不需要直接调用 dxva2 的物理句柄

注意：
- 某些设备可能只支持离散档位
- 某些系统策略/驱动可能限制 WMI 调用

---

## 9. 全局状态与同步刷新

目标：
- 多个控件共享“全部亮度”
- 多个控件共享“当前选中屏幕”
- 任意一个控件变化时，所有相关控件都要立刻更新显示

核心实现：`BrightnessHub`（`src\core\brightness_hub.py`）。

### 9.1 预览值（preview）与延迟应用（schedule）

为什么需要预览：
- 旋钮滚动时会产生大量 tick
- 每个 tick 都直接写硬件会造成卡顿/延迟/屏幕闪烁

实现方式：
- 旋钮转动：先更新 Hub 内的 preview 值
- 立刻 broadcast_refresh：让 UI 即时显示新数字
- 再 schedule_apply：延迟 180ms/350ms 做一次真正写入

全局应用（全部屏）：
- `schedule_apply_all(delay_ms=350)`
- 定时器触发时调用 `apply_all_now()`

单屏应用（选中屏）：
- `schedule_apply_selected(delay_ms=180, percent=...)`
- 定时器触发时调用 `set_monitor_brightness_now()`

### 9.2 扫描与重试

Hub 里每次设置前会 scan：
- scan 默认带 3 秒节流，避免频繁枚举
- 如果设置失败，会强制 scan(force=True) 再重试一次

这样可以覆盖一些边界情况：
- 显示器刚插拔，还未稳定
- 某个句柄失效
- WMI 列表变化

---

## 10. 属性面板（Property Inspector）

属性面板资源在：
- `com.mirabox.streamdock.brightness.sdPlugin\propertyInspector\brightness\`

`manifest.json` 中每个动作都指向：
- `"PropertyInspectorPath": "./propertyInspector/brightness/index.html"`

典型交互（概念）：
- 面板读取当前 settings 并渲染表单
- 用户修改参数后，面板把新的 settings 发给插件
- 插件收到 `didReceiveSettings` 更新 Action.settings
- Action 触发 refresh_title / 重建 timer

当前项目把 settings 的处理放在各 Action 内部：
- `on_did_receive_settings`
- `_ensure_timer`
- `refresh_title`

---

## 11. 打包发布（PyInstaller）


在项目根目录执行：(不使用clean有bug，ai可能修复了但是还没测试)

```powershell
cd C:\xxxx\MiraBoxBrightness
.\.venv\Scripts\python.exe -m PyInstaller -y --clean main.spec
```


## 12. 常见问题（FAQ）

1) 按键默认背景是图标，干扰显示怎么办？
- 原因：`manifest.json` 的默认 `Image` 会作为背景图。
- 解决：后端在 `Action` 初始化时把 image 设为透明 PNG，覆盖默认图。

2) 为什么有时显示“无显示器”或“--”？
- DDC/CI 不支持或未开启。
- WMI 返回为空或权限/驱动限制。
- 建议：先看日志，确认枚举结果与读写失败原因。

## 13. 命令速查

- 安装依赖：`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
- 打包（clean）：`.\.venv\Scripts\python.exe -m PyInstaller -y --clean main.spec`
- 打包（增量）：`.\.venv\Scripts\python.exe -m PyInstaller -y main.spec`

