# Hazir: gm, pm, pool, tsr, dpg, Panel, PanelData, StockDataReader, FilterMode, IndicatorManager

import json
import math
import os
import sys
from datetime import datetime

import numpy as np


# Full pipeline template:
#   Stage1: CSV/DataManager oku, indikator/sinyal hesapla, binary bundle yaz.
#   Stage2/3: Mevcut default.py viewer template'ini kullanarak bundle'i oku ve ciz.
#
# Bu dosya default_full_pipeline.py yerine gecmez; yeni template denemesi icin
# ayridir. Eski tam script referans olarak korunur.

SCRIPT_DIR = getattr(gm.scriptPanel, "_scripts_dir", os.path.join(os.getcwd(), "DearPyGuiDataPlotter", "scripts"))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
INPUTS_DIR = os.path.join(PROJECT_DIR, "inputs")
VIEWER_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "default.py")

EXPORT_BUNDLE_NAME = "full_pipeline_bundle.npz"
EXPORT_VIEW_NAME = "full_pipeline_bundle.view.json"
EXPORT_INPUT_NAME = "input.json"

# Calisma modu secimi:
#
# 1) Normal template akisi:
#    Oku -> hesapla -> .npz/.view/input yaz -> default.py ile ciz
#    WRITE_BUNDLE_ON_RUN = True
#    RUN_VIEWER_AFTER_EXPORT = True
#    DRAW_DIRECT_WITHOUT_BUNDLE = False
#
# 2) Sadece bundle uret:
#    Oku -> hesapla -> .npz/.view/input yaz -> cizim yapma
#    WRITE_BUNDLE_ON_RUN = True
#    RUN_VIEWER_AFTER_EXPORT = False
#    DRAW_DIRECT_WITHOUT_BUNDLE = False
#
# 3) Disk yazmadan direkt ciz:
#    Oku -> hesapla -> bundle yazma -> bu script bellekten cizsin
#    WRITE_BUNDLE_ON_RUN = False
#    RUN_VIEWER_AFTER_EXPORT = False
#    DRAW_DIRECT_WITHOUT_BUNDLE = True
#
# Not: DRAW_DIRECT_WITHOUT_BUNDLE=True iken WRITE_BUNDLE_ON_RUN de True olsa
# bile export blogu calismaz; 2M data icin gereksiz disk yazimi atlanir.
WRITE_BUNDLE_ON_RUN = True
RUN_VIEWER_AFTER_EXPORT = True
DRAW_DIRECT_WITHOUT_BUNDLE = False

# Data secimi:
#   0 -> C:\data\csvFiles\VIP\01\VIP-X030-T.csv
#   1 -> C:\data\csvFiles\IMKBH\05\THYAO.csv
#   2 -> C:\data\csvFiles\IMKBH\G\THYAO.csv
DATASET_CHOICE = 1
DATASET_CHOICES = {
    0: {"base_dir": r"C:\data\csvFiles", "market": "VIP", "symbol": "VIP-X030-T", "period": "01"},
    1: {"base_dir": r"C:\data\csvFiles", "market": "IMKBH", "symbol": "THYAO", "period": "05"},
    2: {"base_dir": r"C:\data\csvFiles", "market": "IMKBH", "symbol": "THYAO", "period": "G"},
}

EMA_PERIODS = (50, 100, 200)
TRADE_SIGNAL_TAKE_PROFIT_PCT = 0.03
TRADE_SIGNAL_STOP_LOSS_PCT = 0.015

SIGNAL_TEXT_TO_CODE = {
    None: 0,
    "AL": 1,
    "SAT": -1,
    "FLAT": 2,
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


class FullPipelineTemplate:
    """Stage1 producer.

    C# tarafindaki gercek akis icin Python tarafinin bekledigi binary format
    burada uretilir. Sonra cizim icin ayni default.py viewer kullanilir.
    """

    def __init__(self):
        self.dp = gm.dataManager
        self.reader = None
        self.intraday = True

        self.xs = []
        self.ts = []
        self.opens = []
        self.highs = []
        self.lows = []
        self.closes = []
        self.volumes = []
        self.sizes = []

        self.emas = []
        self.rsiYs = []
        self.macdLine = []
        self.macdSignal = []
        self.macdHist = []
        self.stochK = []
        self.stochD = []
        self.indicatorSeries = []
        self.signals = []
        self.signalSteps = []
        self.signalDetails = []

        self.bundlePath = os.path.join(INPUTS_DIR, EXPORT_BUNDLE_NAME)
        self.viewPath = os.path.join(INPUTS_DIR, EXPORT_VIEW_NAME)
        self.inputPath = os.path.join(INPUTS_DIR, EXPORT_INPUT_NAME)

    def run(self):
        # 1) Script ortam hazirligi.
        # ScriptPanel icinde __file__ yok; bu yuzden SCRIPT_DIR yukarida
        # gm.scriptPanel uzerinden hesaplandi. Import icin sys.path'e ekliyoruz.
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)

        # 2) DataManager reader cache temizligi.
        # Onceki Run script tarafindan okunan reader'i birakmissa temizle.
        # Data Manager panelinden elle okunmus reader varsa korunur.
        if gm.dataManager.getReadSource() == "script":
            gm.dataManager.setReader(None)

        # 3) Stage1-A: kaynak datayi oku.
        # Oncelik DataManager'da elle yuklenmis reader; yoksa DATASET_CHOICE.
        self.stage1LoadData()
        if not self.hasData():
            print("Veri okunamadi, full pipeline durdu.")
            return

        # 4) Stage1-B: indikatorleri ve trade sinyallerini hesapla.
        # Bu asamadan sonra self.indicatorSeries, self.signals,
        # self.signalSteps ve self.signalDetails hazirdir.
        self.stage1ComputeIndicators()
        self.stage1GenerateSignals()


        # Burada iki ayri calisma yolu var:
        #
        # 1) Bundle/viewer yolu:
        #    WRITE_BUNDLE_ON_RUN=True ve DRAW_DIRECT_WITHOUT_BUNDLE=False
        #    ise bu script .npz + .view.json + input.json uretir.
        #    Cizim isini sonra default.py yapar.
        #
        # 2) Direct memory yolu:
        #    DRAW_DIRECT_WITHOUT_BUNDLE=True ise disk yazilmaz.
        #    Cizim isini bu script, bellekteki self.* listeleriyle yapar.
        #
        # Alttaki iki blok bu iki yolu secmek icin ayrica korunuyor.

        # 5) Stage1-C: opsiyonel binary export.
        # Direct memory modunda 2M data icin gereksiz disk yazmayi atliyoruz.
        # Normal viewer modunda default.py'nin okuyacagi .npz bundle,
        # .view.json ve input.json burada yazilir.
        if WRITE_BUNDLE_ON_RUN and not DRAW_DIRECT_WITHOUT_BUNDLE:
            # -> .npz + .view.json + input.json yazılır
            self.stage1ExportBundle()
            self.stage1WriteViewDescription()
            self.stage1WriteInputConfig()

        # 6) Stage2/Stage3 secimi.
        # A) DRAW_DIRECT_WITHOUT_BUNDLE=True ise disk yazmadan bellekten cizer.
        # B) Aksi halde RUN_VIEWER_AFTER_EXPORT=True ise default.py viewer template'i
        #    input.json -> .npz -> .view.json akisi ile cizim yapar.
        if DRAW_DIRECT_WITHOUT_BUNDLE:
            # -> default.py yok, bellekten direkt çiz
            self.stage3DrawDirectFromMemory()
        elif RUN_VIEWER_AFTER_EXPORT:
            # -> default.py çalışır, bundle/view/input üzerinden çiz
            self.stage2Stage3RunViewerTemplate()
        else:
            # -> çizim yapılmaz, sadece önceki aşamalar çalışmış olur
            print("Cizim atlandi: DRAW_DIRECT_WITHOUT_BUNDLE=False ve RUN_VIEWER_AFTER_EXPORT=False.")

        # 7) Konsol ozeti.
        self.printSummary()

    # ------------------------------------------------------------------
    # Stage1: read + compute + export

    def stage1LoadData(self):
        if self.dp.hasReader():
            print("reader = dp.getReader()")
            self.reader = self.dp.getReader()
        else:
            dataset = DATASET_CHOICES.get(DATASET_CHOICE, DATASET_CHOICES[1])
            filePath = os.path.join(
                dataset["base_dir"],
                dataset["market"],
                dataset["period"],
                f"{dataset['symbol']}.csv",
            )
            print("reader = dp.readData(filePath)")
            print(f"  {filePath}")
            self.reader = self.dp.readData(filePath)

        self.intraday = self.dp.isIntraday()

    def hasData(self):
        return self.reader is not None and self.reader.data.length > 0

    def stage1ComputeIndicators(self):
        data = self.reader.data
        self.xs = list(range(data.length))
        self.ts = list(data.dateTime)
        self.opens = [float(v) for v in data.open]
        self.highs = [float(v) for v in data.high]
        self.lows = [float(v) for v in data.low]
        self.closes = [float(v) for v in data.close]
        self.volumes = [float(v) for v in data.volume]
        self.sizes = [int(v) for v in data.size]

        im = IndicatorManager(
            self.xs,
            self.opens,
            self.highs,
            self.lows,
            self.closes,
            self.volumes,
            self.sizes,
        )
        self.emas = [(f"EMA{period}", im.ema(period)) for period in EMA_PERIODS]
        self.rsiYs = im.rsi(14)
        self.macdLine, self.macdSignal, self.macdHist = im.macd(12, 26, 9)
        self.stochK, self.stochD = im.stochastic(14, 3)
        self.indicatorSeries = list(self.emas)
        self.indicatorSeries += [
            ("MACD", self.macdLine),
            ("MACDSignal", self.macdSignal),
            ("MACDHist", self.macdHist),
            ("RSI14", self.rsiYs),
            ("StochK", self.stochK),
            ("StochD", self.stochD),
        ]

    def stage1GenerateSignals(self):
        emaFast = self.emas[0][1] if len(self.emas) >= 1 else []
        emaSlow = self.emas[1][1] if len(self.emas) >= 2 else []
        self.signals = self.generateTradeSignalsEma(
            emaFast,
            emaSlow,
            takeProfitPct=TRADE_SIGNAL_TAKE_PROFIT_PCT,
            stopLossPct=TRADE_SIGNAL_STOP_LOSS_PCT,
        )
        self.signalSteps = self.generateSignalSteps(self.signals)

    def stage1ExportBundle(self):
        os.makedirs(INPUTS_DIR, exist_ok=True)
        indicatorNames = np.array([name for name, _ in self.indicatorSeries], dtype="<U32")
        indicatorValues = np.asarray([ys for _, ys in self.indicatorSeries], dtype=np.float64)
        detailsJson = np.array(
            [
                json.dumps({"index": i, **detail}, ensure_ascii=False)
                for i, detail in enumerate(self.signalDetails)
                if detail
            ],
            dtype="<U2048",
        )
        meta = {
            "source": "default_full_pipeline_template.py",
            "symbol": self.dp.getSembolName() or DATASET_CHOICES.get(DATASET_CHOICE, DATASET_CHOICES[1])["symbol"],
            "market": self.dp.getSembolMarket(),
            "period": self.dp.getSembolPeriyod(),
            "intraday": bool(self.intraday),
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "emaPeriods": list(EMA_PERIODS),
            "takeProfitPct": TRADE_SIGNAL_TAKE_PROFIT_PCT,
            "stopLossPct": TRADE_SIGNAL_STOP_LOSS_PCT,
        }

        np.savez(
            self.bundlePath,
            meta_json=np.array(json.dumps(meta, ensure_ascii=False)),
            timestamps=np.array([self._timestampToIso(value) for value in self.ts], dtype="<U32"),
            open=np.asarray(self.opens, dtype=np.float64),
            high=np.asarray(self.highs, dtype=np.float64),
            low=np.asarray(self.lows, dtype=np.float64),
            close=np.asarray(self.closes, dtype=np.float64),
            volume=np.asarray(self.volumes, dtype=np.float64),
            size=np.asarray(self.sizes, dtype=np.int64),
            indicator_names=indicatorNames,
            indicator_values=indicatorValues,
            signal_codes=np.asarray([SIGNAL_TEXT_TO_CODE.get(signal, 0) for signal in self.signals], dtype=np.int16),
            signal_steps=np.asarray(self.signalSteps, dtype=np.int16),
            signal_details_json=detailsJson,
        )
        print(f"Bundle yazildi: {self.bundlePath}")

    def stage1WriteViewDescription(self):
        view = self.buildViewDescription()
        self._writeJson(self.viewPath, view)
        print(f"View yazildi: {self.viewPath}")

    def buildViewDescription(self):
        symbol = self.dp.getSembolName() or "OHLC"
        return {
            "version": 1,
            "name": f"{symbol} full pipeline view",
            "panels": [
                {
                    "id": "ohlc",
                    "name": "OHLC",
                    "caption": f"{symbol} OHLC",
                    "height": 400,
                    "ySyncId": 0,
                    "series": [
                        {"source": "ohlc", "name": "OHLC", "dataId": 0},
                        {"source": "indicator", "name": "EMA50", "dataId": 1},
                        {"source": "indicator", "name": "EMA100", "dataId": 2},
                        {"source": "indicator", "name": "EMA200", "dataId": 3},
                    ],
                    "tradeOverlay": {
                        "enabled": True,
                        "showSignals": False,
                        "showLevelLines": True,
                        "colorBars": True,
                    },
                },
                {
                    "id": "signals",
                    "name": "Signals",
                    "caption": "Signal Step",
                    "height": 300,
                    "ySyncMode": "fixedRange",
                    "fixedRange": [-1, 1],
                    "series": [{"source": "signalSteps", "name": "Signal Step", "dataId": 1}],
                },
                {
                    "id": "indicators",
                    "name": "MACD",
                    "caption": "MACD",
                    "height": 200,
                    "ySyncId": 1,
                    "series": [
                        {"source": "indicator", "name": "MACD", "dataId": 1},
                        {"source": "indicator", "name": "MACDSignal", "label": "Signal", "dataId": 2},
                        {"source": "indicator", "name": "MACDHist", "label": "Hist", "dataId": 3},
                    ],
                },
                {
                    "id": "rsi",
                    "name": "RSI",
                    "caption": "RSI",
                    "height": 200,
                    "ySyncMode": "fixedRange",
                    "fixedRange": [0, 100],
                    "series": [
                        {"source": "indicator", "name": "RSI14", "dataId": 1},
                    ],
                    "levels": [
                        {"orientation": "h", "value": 30, "color": [120, 120, 120, 150]},
                        {"orientation": "h", "value": 70, "color": [120, 120, 120, 150], "label": "Overbought"},
                        {"orientation": "v", "xFromEnd": 1000, "color": [255, 0, 0, 150], "label": "-1000"},
                        {"orientation": "v", "xFromEnd": 2000, "color": [255, 150, 0, 150], "label": "-2000"},
                    ],
                },
                {
                    "id": "stochastic",
                    "name": "Stochastic",
                    "caption": "Stochastic %K / %D",
                    "height": 200,
                    "ySyncMode": "fixedRange",
                    "fixedRange": [0, 100],
                    "series": [
                        {"source": "indicator", "name": "StochK", "label": "%K", "dataId": 1},
                        {"source": "indicator", "name": "StochD", "label": "%D", "dataId": 2},
                    ],
                    "levels": [
                        {"orientation": "h", "value": 20, "color": [120, 120, 120, 150], "label": "Oversold"},
                        {"orientation": "h", "value": 80, "color": [120, 120, 120, 150], "label": "Overbought"},
                    ],
                },
            ],
        }

    def stage1WriteInputConfig(self):
        config = {
            "bundle": self.bundlePath,
            "view": self.viewPath,
        }
        self._writeJson(self.inputPath, config)
        print(f"Input config yazildi: {self.inputPath}")

    def stage2Stage3RunViewerTemplate(self):
        if not os.path.isfile(VIEWER_TEMPLATE_PATH):
            print(f"Viewer template bulunamadi: {VIEWER_TEMPLATE_PATH}")
            return
        with open(VIEWER_TEMPLATE_PATH, "r", encoding="utf-8-sig") as f:
            code = f.read()
        exec(compile(code, VIEWER_TEMPLATE_PATH, "exec"), globals())

    # ------------------------------------------------------------------
    # Stage3 direct draw: disk yazmadan, Stage1 sonucunu bellekten ciz.

    def stage3DrawDirectFromMemory(self):
        data = self.buildPreparedDataInMemory()
        view = self.buildViewDescription()
        gm.currentPreparedData = data
        gm.currentView = view
        gm.currentBundlePath = None
        gm.currentViewPath = None

        self._resetUi()
        self.stage3BuildPanelsFromView(view)
        self.stage3DrawEmptyPlots()
        self.stage3FillPanelsFromView(view, data)
        self.stage3FillPoolFromPanels(data)
        self.stage3DrawPanelDataOnly(view, data)

        gm.seedTopViewRangeInputs(len(data.xs))
        gm.leftMenuPanel.refresh()
        gm.poolPanel.refresh()
        gm._refreshActivePanelCombo()
        print("Direct draw tamamlandi: bundle yazmadan bellekten cizildi.")

    def buildPreparedDataInMemory(self):
        data = PreparedData()
        data.meta = {
            "source": "default_full_pipeline_template.py",
            "symbol": self.dp.getSembolName() or DATASET_CHOICES.get(DATASET_CHOICE, DATASET_CHOICES[1])["symbol"],
            "market": self.dp.getSembolMarket(),
            "period": self.dp.getSembolPeriyod(),
            "intraday": bool(self.intraday),
        }
        data.xs = list(self.xs)
        data.timestamps = list(self.ts)
        data.open = list(self.opens)
        data.high = list(self.highs)
        data.low = list(self.lows)
        data.close = list(self.closes)
        data.volume = list(self.volumes)
        data.size = list(self.sizes)
        data.indicatorNames = [name for name, _ in self.indicatorSeries]
        data.indicatorValues = [list(ys) for _, ys in self.indicatorSeries]
        data.signals = list(self.signals)
        data.signalSteps = list(self.signalSteps)
        data.signalDetails = list(self.signalDetails)
        return data

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

    def stage3BuildPanelsFromView(self, view):
        self.panelByViewId = {}
        self.ohlcPanel = None
        for panelSpec in view.get("panels", []):
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
            viewId = str(panelSpec.get("id") or name)
            self.panelByViewId[viewId] = panel
            if viewId == "ohlc" or self.ohlcPanel is None:
                if str(panelSpec.get("id", "")).lower() == "ohlc" or panel.name == "OHLC":
                    self.ohlcPanel = panel
        if self.ohlcPanel is None and self.panelByViewId:
            self.ohlcPanel = next(iter(self.panelByViewId.values()))

    def stage3DrawEmptyPlots(self):
        dpg.configure_item("centerTopPanel", show=True)
        for panel in pm.iterateAllPanels():
            pm.drawPanel(panel.id)

    def stage3FillPanelsFromView(self, view, data):
        symbol = data.meta.get("symbol", "OHLC")
        intraday = bool(data.meta.get("intraday", True))
        indicatorMap = {
            name: ys
            for name, ys in zip(data.indicatorNames, data.indicatorValues)
        }

        for panelSpec in view.get("panels", []):
            viewId = str(panelSpec.get("id") or panelSpec.get("name") or "")
            panel = self.panelByViewId.get(viewId)
            if not panel:
                continue

            panel.deleteAllData()
            panel.deleteAllLevels()
            for seriesSpec in panelSpec.get("series", []):
                source = str(seriesSpec.get("source") or "").lower()
                name = str(seriesSpec.get("name") or "")
                label = str(seriesSpec.get("label") or name)
                dataId = int(seriesSpec.get("dataId", 1))

                if source == "ohlc":
                    panel.setCandleData(
                        opens=data.open,
                        highs=data.high,
                        lows=data.low,
                        closes=data.close,
                        volumes=data.volume,
                        sizes=data.size,
                        dateTime=data.timestamps,
                        name=symbol,
                        dataId=dataId,
                        intraday=intraday,
                    )
                elif source == "indicator":
                    ys = indicatorMap.get(name)
                    if ys is not None:
                        panel.addData(dataId, label, "line", data.xs, ys,
                                      timestamps=data.timestamps, intraday=intraday)
                elif source in ("signalsteps", "signal_steps"):
                    panel.addData(dataId, label or "Signal Step", "line", data.xs, data.signalSteps,
                                  timestamps=data.timestamps, intraday=intraday)

            self._applyViewLevels(panel, panelSpec, data)

    def _applyViewLevels(self, panel, panelSpec, data):
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
                    if offset <= 0 or len(data.xs) < offset:
                        continue
                    x = data.xs[-offset]
                else:
                    continue
                panel.addVline(x, color=color, thickness=thickness, label=label)

    def stage3FillPoolFromPanels(self, data):
        pool.clear()
        symbol = data.meta.get("symbol", "")
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

    def stage3DrawPanelDataOnly(self, view, data):
        for panel in pm.iterateAllPanels():
            pm.drawPanelData(panel.id)
        for panelSpec in view.get("panels", []):
            overlay = panelSpec.get("tradeOverlay") or {}
            if not overlay.get("enabled"):
                continue
            panel = self.panelByViewId.get(str(panelSpec.get("id") or panelSpec.get("name") or ""))
            if panel and data.signals:
                tsr.draw(panel.id, 0, data.signals,
                         showSignals=bool(overlay.get("showSignals", False)),
                         showLevelLines=bool(overlay.get("showLevelLines", True)),
                         colorBars=bool(overlay.get("colorBars", True)))
        pm.setXAxisMode("datetime")

    # ------------------------------------------------------------------
    # Signal helpers

    def generateTradeSignalsEma(self, ema1Ys, ema2Ys, *, takeProfitPct=None, stopLossPct=None,
                                useHighLow=True, warmup=1):
        n = min(len(ema1Ys), len(ema2Ys), len(self.closes))
        signals = [None] * n
        details = [None] * n
        position = None
        entryPrice = None
        entryIndex = None

        for i in range(max(1, warmup), n):
            if position is not None and entryPrice is not None:
                high = self.highs[i] if useHighLow else self.closes[i]
                low = self.lows[i] if useHighLow else self.closes[i]
                exitDetail = self._tradeExitDetail(
                    position,
                    entryPrice,
                    high,
                    low,
                    self.closes[i],
                    takeProfitPct,
                    stopLossPct,
                )
                if exitDetail:
                    signals[i] = "FLAT"
                    pnl = (exitDetail["exitPrice"] - entryPrice) if position == "AL" else (
                        entryPrice - exitDetail["exitPrice"]
                    )
                    details[i] = {
                        "signal": "FLAT",
                        "state": 0,
                        "position": position,
                        "entryIndex": entryIndex,
                        "entryPrice": entryPrice,
                        "exitPrice": exitDetail["exitPrice"],
                        "exitReason": exitDetail["reason"],
                        "pnl": pnl,
                        "pnlPct": pnl / entryPrice if entryPrice else None,
                    }
                    position = None
                    entryPrice = None
                    entryIndex = None
                    continue

            prev1, prev2 = ema1Ys[i - 1], ema2Ys[i - 1]
            cur1, cur2 = ema1Ys[i], ema2Ys[i]
            if not (self._finite(prev1) and self._finite(prev2) and self._finite(cur1) and self._finite(cur2)):
                continue

            prevDiff = float(prev1) - float(prev2)
            curDiff = float(cur1) - float(cur2)
            candidateSignal = None
            if prevDiff <= 0 < curDiff:
                candidateSignal = "AL"
            elif prevDiff >= 0 > curDiff:
                candidateSignal = "SAT"

            if candidateSignal is None:
                continue

            if position is not None:
                details[i] = self._tradeSkipDetail(
                    candidateSignal,
                    i,
                    position,
                    entryIndex,
                    entryPrice,
                    reason="POSITION_OPEN",
                )
                continue

            signals[i] = candidateSignal
            position = candidateSignal
            entryPrice = float(self.closes[i]) if self._finite(self.closes[i]) else None
            entryIndex = i
            details[i] = self._tradeEntryDetail(candidateSignal, i, entryPrice, takeProfitPct, stopLossPct)

        self.signalDetails = details
        return signals

    def generateSignalSteps(self, signals):
        state = 0
        steps = []
        for signal in signals or []:
            if signal == "AL":
                state = 1
            elif signal == "SAT":
                state = -1
            elif signal == "FLAT":
                state = 0
            steps.append(state)
        return steps

    def _tradeEntryDetail(self, signal, index, entryPrice, takeProfitPct, stopLossPct):
        if signal == "AL":
            takeProfit = entryPrice * (1.0 + takeProfitPct) if entryPrice and takeProfitPct is not None else None
            stopLoss = entryPrice * (1.0 - stopLossPct) if entryPrice and stopLossPct is not None else None
            reason = "EMA_CROSS_UP"
        else:
            takeProfit = entryPrice * (1.0 - takeProfitPct) if entryPrice and takeProfitPct is not None else None
            stopLoss = entryPrice * (1.0 + stopLossPct) if entryPrice and stopLossPct is not None else None
            reason = "EMA_CROSS_DOWN"
        return {
            "signal": signal,
            "state": 1 if signal == "AL" else -1,
            "position": signal,
            "entryIndex": index,
            "entryPrice": entryPrice,
            "takeProfitPrice": takeProfit,
            "stopLossPrice": stopLoss,
            "reason": reason,
        }

    def _tradeSkipDetail(self, candidateSignal, index, position, entryIndex, entryPrice, reason):
        return {
            "signal": "SKIP",
            "state": 1 if position == "AL" else -1 if position == "SAT" else 0,
            "candidateSignal": candidateSignal,
            "position": position,
            "entryIndex": entryIndex,
            "entryPrice": entryPrice,
            "reason": reason,
            "index": index,
        }

    def _tradeExitDetail(self, position, entryPrice, high, low, close, takeProfitPct, stopLossPct):
        if takeProfitPct is None and stopLossPct is None:
            return None
        if not all(self._finite(v) for v in (entryPrice, high, low, close)):
            return None

        if position == "AL":
            stopPrice = entryPrice * (1.0 - stopLossPct) if stopLossPct is not None else None
            takePrice = entryPrice * (1.0 + takeProfitPct) if takeProfitPct is not None else None
            stopHit = stopPrice is not None and low <= stopPrice
            takeHit = takePrice is not None and high >= takePrice
        elif position == "SAT":
            stopPrice = entryPrice * (1.0 + stopLossPct) if stopLossPct is not None else None
            takePrice = entryPrice * (1.0 - takeProfitPct) if takeProfitPct is not None else None
            stopHit = stopPrice is not None and high >= stopPrice
            takeHit = takePrice is not None and low <= takePrice
        else:
            return None

        if stopHit:
            return {"reason": "STOP_LOSS", "exitPrice": stopPrice}
        if takeHit:
            return {"reason": "TAKE_PROFIT", "exitPrice": takePrice}
        return None

    # ------------------------------------------------------------------
    # Utility

    def _finite(self, value):
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    def _timestampToIso(self, value):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    def _writeJson(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def printSummary(self):
        print("Full pipeline template:")
        print(f"  bars   : {len(self.closes)}")
        print(f"  bundle : {self.bundlePath if WRITE_BUNDLE_ON_RUN else 'skip'}")
        print(f"  view   : {self.viewPath if WRITE_BUNDLE_ON_RUN else 'skip'}")
        print(f"  viewer : {'run' if RUN_VIEWER_AFTER_EXPORT else 'skip'}")


FullPipelineTemplate().run()
