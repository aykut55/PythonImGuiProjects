# Hazir: gm, pm, pool, tsr, dpg, Panel, PanelData

import json
import os
import sys
from datetime import datetime

import numpy as np

# Stage2 binary import config. C# tarafindan ayni alanlari tasiyan .npz bundle
# uretildiginde Python tarafi sadece bunu okuyup cizer.
SCRIPT_DIR = getattr(gm.scriptPanel, "_scripts_dir", os.path.join(os.getcwd(), "DearPyGuiDataPlotter", "scripts"))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
INPUTS_DIR = os.path.join(PROJECT_DIR, "inputs")
DEFAULT_BUNDLE_PATH = os.path.join(INPUTS_DIR, "latest_bundle.npz")
INPUT_CONFIG_CANDIDATES = (
    os.path.join(INPUTS_DIR, "input.json"),
    os.path.join(INPUTS_DIR, "src.json"),
)
CREATE_TEST_BUNDLE_ON_RUN = False
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

SHOW_TRADE_SIGNALS = False
SHOW_TRADE_SIGNAL_LINES = True
COLOR_BARS_BY_SIGNAL = True
SHOW_SIGNAL_STEP_PANEL = True

SIGNAL_CODE_TO_TEXT = {
    0: None,
    1: "AL",
    -1: "SAT",
    2: "FLAT",
}


class PreparedData:
    def __init__(self):
        self.meta = {}
        self.xs = []
        self.timestamps = []
        self.open = []
        self.high = []
        self.low = []
        self.close = []
        self.volume = []
        self.size = []
        self.indicatorNames = []
        self.indicatorValues = []
        self.signals = []
        self.signalSteps = []
        self.signalDetails = []


class App:
    """Binary hazir veri viewer'i.

    Bu script strateji hesaplamaz. Beklenen akış:
      Stage2: .npz binary bundle oku.
      Stage3: okunan OHLC/indikator/sinyal verisini panel'lere ciz.
    Eski full pipeline scripts/default_full_pipeline.py icinde tutuluyor.
    """

    def __init__(self):
        self.data = None
        self.ohlcPanel = None
        self.signalPanel = None
        self.indicatorPanel = None
        self.inputConfig = {}
        self.bundlePath = None
        self.viewPath = None
        self.view = {}
        self.panelByViewId = {}

    def run(self):
        pm.setContainer("centerCenterPanel")
        
        # 1) UI reset: onceki run'dan kalan panel/plot/pool state'ini temizle.
        self._resetUi()
        
        # 2) Opsiyonel test input uretimi. Gercek C# akisine gecince kapali kalir.
        if CREATE_TEST_BUNDLE_ON_RUN:
            self.createTestBundle()

        # Binary Data View çözümü...
        # 3) Aktif binary bundle ve view description dosyalarini coz.
        self.inputConfig = self.loadInputConfig()
        self.bundlePath = self.resolveBundlePath(self.inputConfig)
        self.viewPath = self.resolveViewPath(self.inputConfig, self.bundlePath)
        self.view = self.loadViewDescription(self.viewPath)

        # 4) View description'a gore panel modelini kur.
        self.stage3BuildPanelsFromView(self.view)

        # 5) Binary datayi oku. Bu asamadan sonra self.data hazir olur.
        prepared = self.stage2LoadPreparedData(self.bundlePath)
        if prepared is None:
            return
        self.data = prepared

        # Panel ve Plotların guide cizdirilmesi...
        # 6) Bos plot kabuklarini ciz. Bu UI'nin once iskeleti gostermesini saglar.
        self.stage3DrawEmptyPlots()
        
        # 7) Datayi panel modeline bas, pool'u doldur, mevcut plotlara data ciz.
        self.stage3FillPanels()
        self.stage3FillPool()
        self.stage3DrawPanelDataOnly()

        # 8) Yan UI'lari ve top controls state'ini tazele.
        gm.seedTopViewRangeInputs(len(self.data.xs) if self.data else 0)
        gm.leftMenuPanel.refresh()
        gm.poolPanel.refresh()
        gm._refreshActivePanelCombo()

        print("Binary viewer hazir:")
        print(f"  bundle : {self.bundlePath or 'not loaded'}")
        print(f"  view   : {self.viewPath or 'not loaded'}")
        print(f"  symbol : {(self.data.meta.get('symbol', '') if self.data else '')}")
        print(f"  bars   : {len(self.data.xs) if self.data else 0}")
        print(f"  ind    : {len(self.data.indicatorNames) if self.data else 0}")
        print("  draw   : empty plot shells")

    def createTestBundle(self):
        import create_test_bundle
        create_test_bundle.main()

    def loadInputConfig(self):
        for configPath in INPUT_CONFIG_CANDIDATES:
            if not os.path.isfile(configPath):
                continue
            config = self._readJsonConfig(configPath)
            if config is not None:
                print(f"Input config: {configPath}")
                return config if isinstance(config, dict) else {"bundle": config}
        print("Input config bulunamadi, default bundle/view kullaniliyor.")
        return {}

    def _readJsonConfig(self, path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                raw = f.read().strip()
            return json.loads(raw) if raw else {}
        except Exception as exc:
            print(f"JSON config okunamadi: {path} ({exc})")
            return None

    def resolveBundlePath(self, inputConfig):
        rawPath = (inputConfig.get("bundle") or inputConfig.get("path") or
                   inputConfig.get("bundle_path") or inputConfig.get("bundlePath") or
                   inputConfig.get("source") or inputConfig.get("file") or
                   DEFAULT_BUNDLE_PATH)
        path = self._resolvePath(rawPath, INPUTS_DIR)
        print(f"Input bundle: {path}")
        return path

    def resolveViewPath(self, inputConfig, bundlePath):
        rawPath = inputConfig.get("view") or inputConfig.get("view_path") or inputConfig.get("viewPath")
        if rawPath:
            path = self._resolvePath(rawPath, INPUTS_DIR)
        else:
            base, _ = os.path.splitext(bundlePath or DEFAULT_BUNDLE_PATH)
            path = base + ".view.json"
        print(f"Input view: {path}")
        return path

    def _resolvePath(self, path, baseDir):
        path = os.path.expandvars(os.path.expanduser(str(path)))
        if not os.path.isabs(path):
            path = os.path.join(baseDir, path)
        return os.path.abspath(path)

    def loadViewDescription(self, viewPath):
        view = self._readJsonConfig(viewPath) if viewPath and os.path.isfile(viewPath) else None
        if isinstance(view, dict) and isinstance(view.get("panels"), list):
            return view
        print("View description bulunamadi/gecersiz, default bos panel layout kullaniliyor.")
        return self.defaultViewDescription()

    def defaultViewDescription(self):
        return {
            "panels": [
                {"id": "ohlc", "name": "OHLC", "caption": "OHLC", "height": 420, "ySyncId": 0},
                {"id": "signals", "name": "Signals", "caption": "Signal Steps", "height": 160, "ySyncId": 1},
                {"id": "indicators", "name": "Indicators", "caption": "Indicators", "height": 260, "ySyncId": 2},
            ]
        }

    def _resetUi(self):
        dpg.configure_item("centerTopPanel", show=False)
        pm.deleteAllPanels()
        pm.sync()
        pool.clear()
        gm.leftMenuPanel.refresh()
        gm.poolPanel.refresh()
        gm._refreshActivePanelCombo()
        if dpg.is_dearpygui_running():
            dpg.split_frame()

    def stage2LoadPreparedData(self, path):
        if not os.path.isfile(path):
            print("Binary bundle bulunamadi:")
            print(f"  {path}")
            print("Beklenen .npz alanlari:")
            print("  meta_json, timestamps, open, high, low, close")
            print("Opsiyonel alanlar:")
            print("  volume, size, indicator_names, indicator_values, signal_codes, signal_steps, signal_details_json")
            return None

        bundle = np.load(path, allow_pickle=False)
        data = PreparedData()
        data.meta = self._readMeta(bundle)
        data.open = self._arrayToFloatList(bundle["open"])
        data.high = self._arrayToFloatList(bundle["high"])
        data.low = self._arrayToFloatList(bundle["low"])
        data.close = self._arrayToFloatList(bundle["close"])
        n = len(data.close)
        data.xs = list(range(n))
        data.timestamps = self._readTimestamps(bundle, n)
        data.volume = self._arrayToFloatList(bundle["volume"]) if "volume" in bundle else [0.0] * n
        data.size = [int(v) for v in bundle["size"].tolist()] if "size" in bundle else [0] * n
        data.indicatorNames, data.indicatorValues = self._readIndicators(bundle, n)
        data.signals = self._readSignals(bundle, n)
        data.signalSteps = self._readSignalSteps(bundle, data.signals, n)
        data.signalDetails = self._readSignalDetails(bundle, n)
        return data

    def _readMeta(self, bundle):
        if "meta_json" not in bundle:
            return {}
        raw = bundle["meta_json"].item() if bundle["meta_json"].shape == () else str(bundle["meta_json"][0])
        try:
            return json.loads(str(raw))
        except Exception:
            return {}

    def _readTimestamps(self, bundle, n):
        if "timestamps" not in bundle:
            return []
        out = []
        for value in bundle["timestamps"].tolist()[:n]:
            try:
                out.append(datetime.fromisoformat(str(value)))
            except Exception:
                out.append(str(value))
        return out

    def _readIndicators(self, bundle, n):
        if "indicator_names" not in bundle or "indicator_values" not in bundle:
            return [], []
        names = [str(x) for x in bundle["indicator_names"].tolist()]
        values = np.asarray(bundle["indicator_values"], dtype=np.float64)
        if values.ndim == 1:
            values = values.reshape(1, -1)
        series = [values[i, :n].tolist() for i in range(min(len(names), values.shape[0]))]
        return names[:len(series)], series

    def _readSignals(self, bundle, n):
        if "signal_codes" not in bundle:
            return [None] * n
        codes = [int(v) for v in bundle["signal_codes"].tolist()[:n]]
        return [SIGNAL_CODE_TO_TEXT.get(code) for code in codes]

    def _readSignalSteps(self, bundle, signals, n):
        if "signal_steps" in bundle:
            return [int(v) for v in bundle["signal_steps"].tolist()[:n]]
        state = 0
        steps = []
        for signal in signals:
            if signal == "AL":
                state = 1
            elif signal == "SAT":
                state = -1
            elif signal == "FLAT":
                state = 0
            steps.append(state)
        return steps

    def _readSignalDetails(self, bundle, n):
        if "signal_details_json" not in bundle:
            return [None] * n
        details = [None] * n
        for raw in bundle["signal_details_json"].tolist():
            if not raw:
                continue
            try:
                item = json.loads(str(raw))
                idx = int(item.get("index", -1))
                if 0 <= idx < n:
                    details[idx] = item
            except Exception:
                continue
        return details

    def _arrayToFloatList(self, arr):
        return np.asarray(arr, dtype=np.float64).tolist()

    def stage3BuildPanels(self):
        self.stage3BuildPanelsFromView(self.view or self.defaultViewDescription())

    def stage3BuildPanelsFromView(self, view):
        self.panelByViewId = {}
        self.ohlcPanel = None
        self.signalPanel = None
        self.indicatorPanel = None

        for panelSpec in view.get("panels", []):
            panel = self._createPanelFromSpec(panelSpec)
            viewId = str(panelSpec.get("id") or panel.name)
            self.panelByViewId[viewId] = panel
            if viewId == "ohlc" or self.ohlcPanel is None:
                if str(panelSpec.get("id", "")).lower() == "ohlc" or panel.name == "OHLC":
                    self.ohlcPanel = panel
            if viewId == "signals" or panel.name == "Signals":
                self.signalPanel = panel
            if viewId == "indicators" or panel.name == "Indicators":
                self.indicatorPanel = panel

        if self.ohlcPanel is None and self.panelByViewId:
            self.ohlcPanel = next(iter(self.panelByViewId.values()))

    def _createPanelFromSpec(self, panelSpec):
        name = str(panelSpec.get("name") or panelSpec.get("id") or "Panel")
        caption = str(panelSpec.get("caption") or name)
        panel = pm.createPanel(name, caption)
        panel.setHeight(int(panelSpec.get("height", 240)))
        pm.addPanel(panel)
        if "ySyncId" in panelSpec:
            panel.setYSyncId(panelSpec.get("ySyncId"))
        elif panelSpec.get("ySyncMode"):
            panel.setYSync(panelSpec.get("ySyncMode"), panelSpec.get("ySyncId"),
                           panelSpec.get("fixedRange"))
        return panel

    def stage3FillPanels(self):
        if self._viewHasSeries():
            self.stage3FillPanelsFromView()
            return

        symbol = self.data.meta.get("symbol", "OHLC")
        intraday = bool(self.data.meta.get("intraday", True))

        self.ohlcPanel.deleteAllData()
        self.ohlcPanel.deleteAllLevels()
        self.ohlcPanel.setCandleData(
            opens=self.data.open,
            highs=self.data.high,
            lows=self.data.low,
            closes=self.data.close,
            volumes=self.data.volume,
            sizes=self.data.size,
            dateTime=self.data.timestamps,
            name=symbol,
            intraday=intraday,
        )
        for idx, (name, ys) in enumerate(zip(self.data.indicatorNames, self.data.indicatorValues), start=1):
            self.ohlcPanel.addData(idx, name, "line", self.data.xs, ys,
                                   timestamps=self.data.timestamps, intraday=intraday)

        if self.signalPanel:
            self.signalPanel.deleteAllData()
            self.signalPanel.deleteAllLevels()
            self.signalPanel.addData(1, "Signal Step", "line", self.data.xs, self.data.signalSteps,
                                     timestamps=self.data.timestamps, intraday=intraday)

        self.indicatorPanel.deleteAllData()
        self.indicatorPanel.deleteAllLevels()
        for idx, (name, ys) in enumerate(zip(self.data.indicatorNames, self.data.indicatorValues), start=1):
            self.indicatorPanel.addData(idx, name, "line", self.data.xs, ys,
                                        timestamps=self.data.timestamps, intraday=intraday)

    def _viewHasSeries(self):
        return any(panelSpec.get("series") for panelSpec in (self.view or {}).get("panels", []))

    def stage3FillPanelsFromView(self):
        symbol = self.data.meta.get("symbol", "OHLC")
        intraday = bool(self.data.meta.get("intraday", True))
        indicatorMap = {
            name: ys
            for name, ys in zip(self.data.indicatorNames, self.data.indicatorValues)
        }

        for panelSpec in (self.view or {}).get("panels", []):
            viewId = str(panelSpec.get("id") or panelSpec.get("name") or "")
            panel = self.panelByViewId.get(viewId)
            if not panel:
                continue

            panel.deleteAllData()
            panel.deleteAllLevels()
            nextDataId = 1

            for seriesSpec in panelSpec.get("series", []):
                source = str(seriesSpec.get("source") or "").lower()
                name = str(seriesSpec.get("name") or "")
                label = str(seriesSpec.get("label") or name)
                dataId = int(seriesSpec.get("dataId", nextDataId))
                nextDataId = max(nextDataId, dataId + 1)

                if source == "ohlc":
                    panel.setCandleData(
                        opens=self.data.open,
                        highs=self.data.high,
                        lows=self.data.low,
                        closes=self.data.close,
                        volumes=self.data.volume,
                        sizes=self.data.size,
                        dateTime=self.data.timestamps,
                        name=symbol,
                        dataId=dataId,
                        intraday=intraday,
                    )
                    continue

                if source == "indicator":
                    ys = indicatorMap.get(name)
                    if ys is None:
                        print(f"View indicator bulunamadi: {name}")
                        continue
                    panel.addData(dataId, label, "line", self.data.xs, ys,
                                  timestamps=self.data.timestamps, intraday=intraday)
                    continue

                if source in ("signalsteps", "signal_steps"):
                    panel.addData(dataId, label or "Signal Step", "line", self.data.xs, self.data.signalSteps,
                                  timestamps=self.data.timestamps, intraday=intraday)
                    continue

                if source in ("open", "high", "low", "close", "volume", "size"):
                    ys = getattr(self.data, source)
                    panel.addData(dataId, label or source.title(), "line", self.data.xs, ys,
                                  timestamps=self.data.timestamps, intraday=intraday)

            self._applyViewLevels(panel, panelSpec)

    def _applyViewLevels(self, panel, panelSpec):
        for levelSpec in panelSpec.get("levels", []):
            orientation = str(levelSpec.get("orientation") or levelSpec.get("type") or "h").lower()
            color = tuple(levelSpec.get("color", (120, 120, 120, 150)))
            thickness = int(levelSpec.get("thickness", 1))
            label = str(levelSpec.get("label", ""))

            if orientation in ("h", "horizontal"):
                if "value" not in levelSpec:
                    continue
                panel.addHline(float(levelSpec["value"]), color=color,
                               thickness=thickness, label=label)
                continue

            if orientation in ("v", "vertical"):
                if "x" in levelSpec:
                    x = float(levelSpec["x"])
                elif "xFromEnd" in levelSpec:
                    offset = int(levelSpec["xFromEnd"])
                    if offset <= 0 or len(self.data.xs) < offset:
                        continue
                    x = self.data.xs[-offset]
                else:
                    continue
                panel.addVline(x, color=color, thickness=thickness, label=label)

    def stage3FillPool(self):
        pool.clear()
        symbol = self.data.meta.get("symbol", "")
        seen = set()
        for panel in pm.iterateAllPanels():
            for item in panel.iterateAllData():
                key = (item.name, item.dataType)
                if key in seen:
                    continue
                seen.add(key)
                if item.dataType == "candle":
                    pool.addItem("OHLC", "Data", item, symbol=symbol)
                elif item.name == "Signal Step":
                    pool.addItem(item.name, "Signals", item, symbol=symbol)
                else:
                    pool.addItem(item.name, "Indicators", item, symbol=symbol)

    def stage3Draw(self):
        # Tek-adim tam cizim: panel kabuklarini olusturur ve datayi basar.
        # Bos plotlari once gosterip sonra data basmak istiyorsan bunu DEGIL,
        # su sirayi kullan:
        #   stage3DrawEmptyPlots()
        #   stage3FillPanels()
        #   stage3FillPool()
        #   stage3DrawPanelDataOnly()
        dpg.configure_item("centerTopPanel", show=True)
        for panel in pm.iterateAllPanels():
            pm.drawPanel(panel.id)
            pm.drawPanelData(panel.id)
        if self.data.signals:
            tsr.draw(self.ohlcPanel.id, 0, self.data.signals,
                     showSignals=SHOW_TRADE_SIGNALS,
                     showLevelLines=SHOW_TRADE_SIGNAL_LINES,
                     colorBars=COLOR_BARS_BY_SIGNAL)
        pm.setXAxisMode("datetime")

    def stage3DrawEmptyPlots(self):
        dpg.configure_item("centerTopPanel", show=True)
        for panel in pm.iterateAllPanels():
            pm.drawPanel(panel.id)

    def stage3DrawPanelDataOnly(self):
        for panel in pm.iterateAllPanels():
            pm.drawPanelData(panel.id)
        if self.data and self.data.signals:
            tsr.draw(self.ohlcPanel.id, 0, self.data.signals,
                     showSignals=SHOW_TRADE_SIGNALS,
                     showLevelLines=SHOW_TRADE_SIGNAL_LINES,
                     colorBars=COLOR_BARS_BY_SIGNAL)
        pm.setXAxisMode("datetime")


App().run()
