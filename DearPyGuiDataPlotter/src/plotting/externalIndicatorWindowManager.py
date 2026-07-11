import math
from bisect import bisect_left, bisect_right

import dearpygui.dearpygui as dpg


class ExternalIndicatorWindowManager:
    LOD_ACTIVATION_THRESHOLD = 6000
    LOD_MAX_POINTS = 3000
    LOD_RANGE_CHANGE_RATIO = 0.08

    """Center panel disinda lightweight indikator pencereleri yonetir.

    Ilk surum one-way sync yapar: kaynak OHLC/aktif panelin X araligi takip
    edilir, external pencerelerin Y ekseni kendi gorunur verisine gore fit edilir.
    """

    def __init__(self, panelManager):
        self._panelManager = panelManager
        self._windows = []
        self._nextId = 1

    def openDefaultIndicatorWindow(self, sourcePanelId=None):
        sourcePanelId = self._resolveSourcePanelId(sourcePanelId)
        if sourcePanelId is None:
            return None
        panel = self._panelManager.getPanel(sourcePanelId)
        if panel is None:
            return None

        series = self._pickDefaultSeries(panel)
        if not series:
            return None
        return self.openIndicatorWindow(sourcePanelId, series,
                                        title=f"Indicators - Panel {sourcePanelId}",
                                        followSource=True)

    def openIndicatorWindow(self, sourcePanelId, series, title=None, followSource=True):
        panel = self._panelManager.getPanel(sourcePanelId)
        if panel is None or not series:
            return None
        windowId = self._nextId
        self._nextId += 1
        windowTag = f"external_indicator_window_{windowId}"
        plotTag = f"external_indicator_plot_{windowId}"
        xAxisTag = f"external_indicator_x_axis_{windowId}"
        yAxisTag = f"external_indicator_y_axis_{windowId}"
        crosshairTag = f"external_indicator_crosshair_v_{windowId}"
        statusTag = f"external_indicator_status_{windowId}"
        followTag = f"external_indicator_follow_{windowId}"
        updateSourceTag = f"external_indicator_update_source_{windowId}"

        normalizedSeries = self._normalizeSeries(series)
        if not normalizedSeries:
            return None

        with dpg.window(label=title or f"Indicators - Panel {sourcePanelId}",
                        tag=windowTag, width=820, height=360):
            with dpg.group(horizontal=True):
                dpg.add_checkbox(label="Follow Source", tag=followTag, default_value=bool(followSource),
                                 callback=self._onFollowChanged, user_data=windowTag)
                dpg.add_button(label="Apply To Src", width=95,
                               callback=self._onApplyToSource, user_data=windowTag)
                dpg.add_checkbox(label="Update Src", tag=updateSourceTag, default_value=False,
                                 callback=self._onUpdateSourceChanged, user_data=windowTag)
                dpg.add_text(f"Source Panel: {sourcePanelId}")
                dpg.add_text("", tag=statusTag)
            with dpg.plot(label="", tag=plotTag, width=-1, height=-1,
                          no_mouse_pos=True):
                dpg.add_plot_axis(dpg.mvXAxis, label="", tag=xAxisTag)
                dpg.add_plot_axis(dpg.mvYAxis, label="y", tag=yAxisTag)
                dpg.add_plot_legend(parent=plotTag, location=dpg.mvPlot_Location_SouthEast)
                for idx, item in enumerate(normalizedSeries):
                    item["tag"] = f"external_indicator_line_{windowId}_{idx}"
                    dpg.add_line_series([], [], label=item["name"], tag=item["tag"],
                                        parent=yAxisTag)
                dpg.add_drag_line(tag=crosshairTag, parent=plotTag,
                                  default_value=0.0, color=(255, 255, 0, 160),
                                  thickness=1, vertical=True, no_inputs=True,
                                  no_fit=True, show=False)

        state = {
            "windowTag": windowTag,
            "plotTag": plotTag,
            "xAxisTag": xAxisTag,
            "yAxisTag": yAxisTag,
            "crosshairTag": crosshairTag,
            "statusTag": statusTag,
            "followTag": followTag,
            "updateSourceTag": updateSourceTag,
            "followSource": bool(followSource),
            "updateSource": False,
            "sourcePanelId": sourcePanelId,
            "series": normalizedSeries,
            "timestamps": self._pickTimestamps(panel),
            "isIntraday": self._pickIntraday(panel),
            "lastXLimits": None,
            "lastSourceUpdateXLimits": None,
            "lastTicks": None,
        }
        self._windows.append(state)
        if state["followSource"]:
            self._syncWindow(state, force=True)
        else:
            self._unlockWindowAxes(state)
        return state

    def _normalizeSeries(self, series):
        out = []
        for item in series:
            name = str(item.get("name") or "Series")
            xs = list(item.get("xs") or [])
            ys = [float(v) if self._finite(v) else math.nan for v in (item.get("ys") or [])]
            n = min(len(xs), len(ys))
            if n <= 0:
                continue
            out.append({"name": name, "xs": xs[:n], "ys": ys[:n]})
        return out

    def _onFollowChanged(self, sender=None, appData=None, userData=None):
        for state in self._windows:
            if state["windowTag"] == userData:
                state["followSource"] = bool(appData)
                state["lastXLimits"] = None
                state["lastTicks"] = None
                if state["followSource"]:
                    state["updateSource"] = False
                    if dpg.does_item_exist(state["updateSourceTag"]):
                        dpg.set_value(state["updateSourceTag"], False)
                    self._syncWindow(state, force=True)
                else:
                    self._unlockWindowAxes(state)
                break

    def _onUpdateSourceChanged(self, sender=None, appData=None, userData=None):
        state = self._findWindowState(userData)
        if state is None:
            return
        state["updateSource"] = bool(appData)
        state["lastSourceUpdateXLimits"] = None
        if state["updateSource"]:
            state["followSource"] = False
            if dpg.does_item_exist(state["followTag"]):
                dpg.set_value(state["followTag"], False)
            self._unlockWindowAxes(state)

    def _onApplyToSource(self, sender=None, appData=None, userData=None):
        state = self._findWindowState(userData)
        if state is None or not dpg.does_item_exist(state["xAxisTag"]):
            return
        try:
            xLimits = dpg.get_axis_limits(state["xAxisTag"])
        except Exception:
            return
        if not xLimits:
            return
        self._applyExternalXToSource(state, (xLimits[0], xLimits[1]), forceFollowers=True)

    def _applyExternalXToSourceIfChanged(self, state):
        if not dpg.does_item_exist(state["xAxisTag"]):
            return
        try:
            xLimits = dpg.get_axis_limits(state["xAxisTag"])
        except Exception:
            return
        if not xLimits:
            return
        xLimits = (xLimits[0], xLimits[1])
        last = state.get("lastSourceUpdateXLimits")
        if last is not None and abs(last[0] - xLimits[0]) < 1e-9 and abs(last[1] - xLimits[1]) < 1e-9:
            return
        if self._applyExternalXToSource(state, xLimits, forceFollowers=True):
            state["lastSourceUpdateXLimits"] = xLimits

    def _applyExternalXToSource(self, state, xLimits, forceFollowers=False):
        result = self._panelManager.setPanelAxisLimits(
            state["sourcePanelId"],
            xLimits=xLimits,
            yLimits=None,
        )
        if result is None:
            return False
        self._panelManager.adjustYAxis(state["sourcePanelId"], xLimits=xLimits)

        # Source'a uygulanan X araligi bundan sonra tum Follow Source acik
        # pencerelere normal render dongusunde yayilir. Aninda gorsel feedback
        # icin burada da force sync yapiyoruz.
        if forceFollowers:
            for other in self._windows:
                if other is not state and other.get("followSource", True):
                    self._syncWindow(other, force=True)
        return True

    def _findWindowState(self, windowTag):
        for state in self._windows:
            if state["windowTag"] == windowTag:
                return state
        return None

    def _resolveSourcePanelId(self, sourcePanelId):
        if sourcePanelId is not None:
            return sourcePanelId

        activeId = self._panelManager.getActivePanelId()
        activePanel = self._panelManager.getPanel(activeId)
        if activePanel is not None and self._pickDefaultSeries(activePanel):
            return activeId

        for panel in self._panelManager.iterateAllPanels():
            if panel.name == "OHLC" and self._pickDefaultSeries(panel):
                return panel.id

        for panel in self._panelManager.iterateAllPanels():
            if self._pickDefaultSeries(panel):
                return panel.id
        return None

    def render(self):
        if not self._windows:
            return

        alive = []
        for state in self._windows:
            if not dpg.does_item_exist(state["windowTag"]):
                continue
            if state.get("followSource", True):
                self._syncWindow(state)
            else:
                self._syncDetachedWindow(state)
                if state.get("updateSource", False):
                    self._applyExternalXToSourceIfChanged(state)
            self._syncCrosshair(state)
            alive.append(state)
        self._windows = alive

    def _syncDetachedWindow(self, state):
        if not dpg.does_item_exist(state["xAxisTag"]):
            return
        try:
            xLimits = dpg.get_axis_limits(state["xAxisTag"])
        except Exception:
            return
        if not xLimits:
            return
        xMin, xMax = xLimits
        if state.get("lastXLimits") is not None and abs(state["lastXLimits"][0] - xMin) < 1e-9 and abs(state["lastXLimits"][1] - xMax) < 1e-9:
            return
        self._updateVisibleSeries(state, xMin, xMax)
        self._updateXAxisTicks(state, xMin, xMax)
        state["lastXLimits"] = (xMin, xMax)
        self._updateStatusText(state, xMin, xMax)

    def _unlockWindowAxes(self, state):
        # set_axis_limits source-follow modunda axis'i kilitler. Follow kapandiginda
        # kullanici external plotta pan/zoom/box-select yapabilsin diye kilidi acariz.
        for axisTag in (state["xAxisTag"], state["yAxisTag"]):
            if dpg.does_item_exist(axisTag):
                dpg.set_axis_limits_auto(axisTag)

    def _pickDefaultSeries(self, panel):
        out = []
        for data in panel.iterateAllData():
            if not data.isVisible or data.dataType != "line":
                continue
            name = data.name or ""
            if not name.upper().startswith("EMA"):
                continue
            xs = list(data.xs or [])
            ys = [float(v) if self._finite(v) else math.nan for v in (data.ys or [])]
            if xs and ys:
                out.append({"name": name, "xs": xs, "ys": ys})
        return out

    def _syncWindow(self, state, force=False):
        if not dpg.does_item_exist(state["xAxisTag"]):
            return
        xLimits = self._panelManager.getXAxisLimits(state["sourcePanelId"])
        if xLimits is None:
            return

        xMin, xMax = xLimits
        last = state.get("lastXLimits")
        if not force and last is not None and abs(last[0] - xMin) < 1e-9 and abs(last[1] - xMax) < 1e-9:
            self._syncAxisOnly(state, xMin, xMax)
            return

        dpg.set_axis_limits(state["xAxisTag"], xMin, xMax)
        self._updateVisibleSeries(state, xMin, xMax)
        dpg.set_axis_limits(state["xAxisTag"], xMin, xMax)
        self._updateXAxisTicks(state, xMin, xMax)
        yLimits = self._visibleYLimits(state["series"], xMin, xMax)
        if yLimits is not None and dpg.does_item_exist(state["yAxisTag"]):
            dpg.set_axis_limits(state["yAxisTag"], yLimits[0], yLimits[1])
        state["lastXLimits"] = (xMin, xMax)
        self._updateStatusText(state, xMin, xMax)

    def _syncAxisOnly(self, state, xMin, xMax):
        if dpg.does_item_exist(state["xAxisTag"]):
            dpg.set_axis_limits(state["xAxisTag"], xMin, xMax)
            self._updateXAxisTicks(state, xMin, xMax)
        self._updateStatusText(state, xMin, xMax)

    def _updateStatusText(self, state, xMin, xMax):
        tag = state.get("statusTag")
        if dpg.does_item_exist(tag):
            dpg.set_value(tag, f"X [{xMin:.2f} - {xMax:.2f}]")

    def _updateVisibleSeries(self, state, xMin, xMax):
        for item in state["series"]:
            if not dpg.does_item_exist(item["tag"]):
                continue
            xs, ys = self._lodSeries(item["xs"], item["ys"], xMin, xMax)
            dpg.set_value(item["tag"], [xs, ys])

    def _lodSeries(self, xs, ys, xMin, xMax):
        if not xs or not ys:
            return [], []
        start = max(0, bisect_left(xs, xMin) - 1)
        end = min(len(xs), bisect_right(xs, xMax) + 1)
        if end <= start:
            return [], []
        count = end - start
        if count <= self.LOD_ACTIVATION_THRESHOLD:
            return xs[start:end], ys[start:end]
        stride = max(1, math.ceil(count / self.LOD_MAX_POINTS))
        return xs[start:end:stride], ys[start:end:stride]

    def _syncCrosshair(self, state):
        tag = state.get("crosshairTag")
        if not tag or not dpg.does_item_exist(tag):
            return
        if self._panelManager.getCrossHairMode() == "hidden":
            dpg.hide_item(tag)
            return
        pos = self._panelManager.getCrossHairLastPos()
        if pos is None:
            dpg.hide_item(tag)
            return
        _, x, _ = pos
        if x is None:
            dpg.hide_item(tag)
            return
        xLimits = self._panelManager.getXAxisLimits(state["sourcePanelId"])
        if xLimits is not None and not (xLimits[0] <= x <= xLimits[1]):
            dpg.hide_item(tag)
            return
        dpg.set_value(tag, x)
        dpg.show_item(tag)

    def _visibleYLimits(self, series, xMin, xMax):
        yMin = yMax = None
        for item in series:
            _, visibleYs = self._lodSeries(item["xs"], item["ys"], xMin, xMax)
            for y in visibleYs:
                if not self._finite(y):
                    continue
                yMin = y if yMin is None else min(yMin, y)
                yMax = y if yMax is None else max(yMax, y)
        if yMin is None or yMax is None:
            return None
        span = yMax - yMin
        pad = span * 0.08 if span > 0 else max(abs(yMax) * 0.05, 1.0)
        return yMin - pad, yMax + pad

    def _pickTimestamps(self, panel):
        for data in panel.iterateAllData():
            if data.timestamps:
                return list(data.timestamps)
        return []

    def _pickIntraday(self, panel):
        for data in panel.iterateAllData():
            if data.timestamps:
                return bool(getattr(data, "isIntraday", True))
        return True

    def _updateXAxisTicks(self, state, xMin, xMax):
        axisTag = state["xAxisTag"]
        if not dpg.does_item_exist(axisTag):
            return
        if self._panelManager.getXAxisMode() != "datetime":
            dpg.reset_axis_ticks(axisTag)
            state["lastTicks"] = None
            return

        timestamps = state.get("timestamps") or []
        if not timestamps:
            dpg.reset_axis_ticks(axisTag)
            state["lastTicks"] = None
            return

        ticks = tuple(self._buildDatetimeTicks(
            timestamps,
            bool(state.get("isIntraday", True)),
            xMin,
            xMax,
            state["plotTag"],
        ))
        if state.get("lastTicks") == ticks:
            return
        state["lastTicks"] = ticks
        if ticks:
            dpg.set_axis_ticks(axisTag, ticks)
        else:
            dpg.reset_axis_ticks(axisTag)

    def _buildDatetimeTicks(self, timestamps, isIntraday, xMin, xMax, plotTag):
        n = len(timestamps)
        left = max(0, int(xMin))
        right = min(n - 1, int(xMax) + 1)
        if left > right or left >= n:
            return []

        fmtConfig = self._panelManager.getXAxisDateTimeFormat()
        if fmtConfig is None:
            fmt = "%d.%m.%Y\n%H:%M:%S" if isIntraday else "%d.%m.%Y"
        elif fmtConfig == "auto":
            fmt = "%H:%M" if isIntraday else "%d.%m.%Y"
        else:
            fmt = fmtConfig

        bars = max(1, right - left + 1)
        maxTicks = self._maxTicksForPlot(plotTag, timestamps, fmt)
        step = 7
        while bars / step > maxTicks:
            step *= 2

        start = (left // step) * step
        if start < left:
            start += step

        ticks = []
        for i in range(start, right + 1, step):
            ts = timestamps[i]
            if hasattr(ts, "strftime"):
                ticks.append((ts.strftime(fmt), float(i)))
        return ticks

    def _maxTicksForPlot(self, plotTag, timestamps, fmt):
        width = 820
        if dpg.does_item_exist(plotTag):
            try:
                size = dpg.get_item_rect_size(plotTag)
                if size and size[0] > 0:
                    width = size[0]
            except Exception:
                pass
        sample = timestamps[0] if timestamps else None
        text = sample.strftime(fmt) if hasattr(sample, "strftime") else fmt
        longest = max((len(line) for line in text.split("\n")), default=len(text))
        labelWidth = longest * 7 + 20
        return max(3, min(12, int(width / max(labelWidth, 1))))

    def _finite(self, value):
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False
