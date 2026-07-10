# Hazir: gm, pm, tsr, dpg, Panel, PanelData, StockDataReader, FilterMode, IndicatorManager

import math
import os

# Data secimi:
#   0 -> C:\data\csvFiles\VIP\01\VIP-X030-T.csv
#   1 -> C:\data\csvFiles\IMKBH\05\THYAO.csv
DATASET_CHOICE = 1
DATASET_CHOICES = {
    0: {
        "base_dir": r"C:\data\csvFiles",
        "market": "VIP",
        "symbol": "VIP-X030-T",
        "period": "01",
    },
    1: {
        "base_dir": r"C:\data\csvFiles",
        "market": "IMKBH",
        "symbol": "THYAO",
        "period": "05",
    },
    2: {
        "base_dir": r"C:\data\csvFiles",
        "market": "IMKBH",
        "symbol": "THYAO",
        "period": "G",
    },
}

_dataset = DATASET_CHOICES.get(DATASET_CHOICE, DATASET_CHOICES[1])
BASE_DIR = _dataset["base_dir"]   # kaynak Data Manager varsayilani
MARKET = _dataset["market"]
SYMBOL = _dataset["symbol"]
PERIOD = _dataset["period"]       # 01=1dk 05=5dk 10 15 20 30 (dk) 60=1s 120=2s 240=4s | G=gunluk H=haftalik A=aylik

# (klasor_kodu, etiket)  -> yol: BASE_DIR/MARKET/kod/SYMBOL.csv
# Diskte (IMKBH) THYAO icin mevcut tum periyotlar:
PERIODS = [
    ("01",  "1dk"),
    ("05",  "5dk"),
    ("10",  "10dk"),
    ("15",  "15dk"),
    ("20",  "20dk"),
    ("30",  "30dk"),
    ("60",  "1saat"),
    ("120", "2saat"),
    ("240", "4saat"),
    ("G",   "Gunluk"),
    ("H",   "Haftalik"),
    ("A",   "Aylik"),
]

SHOW_TRADE_SIGNALS = False
SHOW_TRADE_SIGNAL_LINES = True
COLOR_BARS_BY_SIGNAL = True
TRADE_SIGNAL_DRAW_DELAY_FRAMES = 1
TRADE_SIGNAL_TAKE_PROFIT_PCT = 0.03
TRADE_SIGNAL_STOP_LOSS_PCT = 0.015


class App:
    """OHLC + EMA/MACD/RSI/Stochastic panellerini kurup dolduran script uygulamasi.
    Ara durum (paneller, reader, indikator sonuclari) self uzerinde tutulur
    ki metodlar birbirine parametre gecirmeden erisebilsin."""

    def __init__(self):
        self.ohlcPanel = None
        self.movAvgPanel = None
        self.macdPanel = None
        self.rsiPanel = None
        self.stochPanel = None

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
        self.signals = []
        self.level0 = []
        self.level30 = []
        self.level50 = []
        self.level70 = []

    def buildPanels(self):
        """5 sabit paneli olusturur, panelManager'a ekler, Y-sync gruplarini kurar."""
        self.ohlcPanel = pm.createPanel("OHLC", "OHLC Verisi")
        self.ohlcPanel.setHeight(400)
        pm.addPanel(self.ohlcPanel)

        self.movAvgPanel = pm.createPanel("MovAvg", "Hareketli Ortalamalar")
        self.movAvgPanel.setHeight(300)
        pm.addPanel(self.movAvgPanel)

        self.macdPanel = pm.createPanel("MACD", "MACD")
        self.macdPanel.setHeight(200)
        pm.addPanel(self.macdPanel)

        self.rsiPanel = pm.createPanel("RSI", "RSI")
        self.rsiPanel.setHeight(200)
        pm.addPanel(self.rsiPanel)

        self.stochPanel = pm.createPanel("Stochastic", "Stochastic %K / %D")
        self.stochPanel.setHeight(200)
        pm.addPanel(self.stochPanel)

        # Y ekseni senkron gruplari
        self.ohlcPanel.setYSyncId(0)
        self.movAvgPanel.setYSyncId(0)
        self.macdPanel.setYSyncId(1)
        self.rsiPanel.setYSyncId(2)
        self.stochPanel.setYSyncId(3)

    def quickReadData(self, market, symbol, period):
        """dataManager'i (Data Manager penceresini) atlayip CSV'yi DOGRUDAN
        StockDataReader ile okur - hizli yol / test icin. Yol: BASE_DIR/market/period/symbol.csv
        (dosya yoksa None doner)."""
        filePath = os.path.join(BASE_DIR, market, period, f"{symbol}.csv")
        if not os.path.isfile(filePath):
            print(f"  [YOK] {filePath}")
            return None
        reader = StockDataReader()
        reader.readMetaData(filePath)
        reader.readDataWithPandas(filePath)
        print(f"  {symbol} [{period}]: {reader.data.length} bar  ({reader.elapsedMs} ms)")
        return reader

    def loadData(self):
        """dataManager'da (Data Manager penceresi) okuma yapildiysa ONU kullanir;
        yoksa dataset secimindeki default path'i dataManager uzerinden okur.
        NOT: run() basinda dp.setReader(None) ile cache TEMIZLENIYOR, boylece
        onceki Run'lardan kalma eski reader DATASET_CHOICE'in onune gecmiyor -
        yine de Data Manager panelinden bu Run icinde ELLE okuma yapilirsa onu
        kullanmaya devam eder (bkz. run())."""
        if self.dp.hasReader():
            print("reader = dp.getReader()")
            self.reader = self.dp.getReader()
        else:
            sembolPath = os.path.join(BASE_DIR, MARKET, PERIOD, f"{SYMBOL}.csv")
            print("reader = dp.readData(sembolPath)")
            self.reader = self.dp.readData(sembolPath)

        print(f"{'SembolFullPath':<15} : {self.dp.getSembolFullPath()}")
        print(f"{'SembolBaseDir':<15} : {self.dp.getSembolBaseDir()}")
        print(f"{'SembolMarket':<15} : {self.dp.getSembolMarket()}")
        print(f"{'SembolName':<15} : {self.dp.getSembolName()}")
        print(f"{'SembolPeriyod':<15} : {self.dp.getSembolPeriyod()}")
        print(f"{'SembolDataCount':<15} : {self.dp.getSembolDataCount()}")
        print()

        # dataManager'dan gelen periyoda gore intraday (rakamsal periyot=dakika/saat
        # -> True; G/H/A -> False). Tum candle/line cizimleri bu intraday'i kullanir.
        self.intraday = self.dp.isIntraday()

    def hasData(self):
        return self.reader is not None and self.reader.data.length > 0

    def computeIndicators(self):
        """IndicatorManager uzerinden EMA/RSI/MACD/Stochastic hesaplar."""
        d            = self.reader.data
        self.xs      = list(range(d.length))
        self.ts      = d.dateTime
        self.opens   = [float(v) for v in d.open]
        self.highs   = [float(v) for v in d.high]
        self.lows    = [float(v) for v in d.low]
        self.closes  = [float(v) for v in d.close]
        self.volumes = [float(v) for v in d.volume]
        self.sizes   = [int(v) for v in d.size]
        self.signals = []

        im = IndicatorManager(self.xs, self.opens, self.highs, self.lows,
                              self.closes, self.volumes, self.sizes)

        self.emas = [(i, f"EMA{p}", im.ema(p)) for i, p in enumerate([50, 100, 200], start=1)]
        self.rsiYs = im.rsi(14)
        self.macdLine, self.macdSignal, self.macdHist = im.macd(12, 26, 9)
        self.stochK, self.stochD = im.stochastic(14, 3)
        self.signals = self.generateTradeSignalsMa(
            self.emas[0][2],
            self.emas[1][2],
            takeProfitPct=TRADE_SIGNAL_TAKE_PROFIT_PCT,
            stopLossPct=TRADE_SIGNAL_STOP_LOSS_PCT,
        )

        # Sabit seviye cizgileri (RSI/Stochastic referanslari icin) - pool'a
        # "Levels" grubunda gidecek (bkz. fillPool).
        n = len(self.xs)
        self.level0 = [0.0] * n
        self.level30 = [30.0] * n
        self.level50 = [50.0] * n
        self.level70 = [70.0] * n

    def generateTradeSignalsRsi(self, rsiYs=None, level30=30.0, level70=70.0, warmup=15):
        """RSI threshold crossing'lerinden OHLC ile ayni uzunlukta sinyal listesi uretir.

        AL: RSI level70'i asagidan yukari keser.
        SAT: RSI level30'u yukaridan asagi keser.
        FLAT: Aktif AL/SAT pozisyonu ters esigi geri kesince kapanir.
        """
        values = rsiYs if rsiYs is not None else self.rsiYs
        signals = [None] * len(values)
        state = None

        def finite(v):
            try:
                return math.isfinite(float(v))
            except (TypeError, ValueError):
                return False

        for i in range(max(1, warmup), len(values)):
            prev = values[i - 1]
            cur = values[i]
            if not finite(prev) or not finite(cur):
                continue
            prev = float(prev)
            cur = float(cur)

            if prev < level70 <= cur:
                signals[i] = "AL"
                state = "AL"
            elif state == "AL" and prev > level70 >= cur:
                signals[i] = "FLAT"
                state = None
            elif prev > level30 >= cur:
                signals[i] = "SAT"
                state = "SAT"
            elif state == "SAT" and prev < level30 <= cur:
                signals[i] = "FLAT"
                state = None

        return signals

    def generateTradeSignalsMa(self, ema1Ys=None, ema2Ys=None, *,
                               takeProfitPct=None, stopLossPct=None,
                               useHighLow=True, warmup=1):
        """Iki EMA serisinin kesismelerinden ve TP/SL kosullarindan sinyal uretir.

        AL: ema1, ema2'yi asagidan yukari keser.
        SAT: ema2, ema1'i asagidan yukari keser. Baska bir ifadeyle ema1,
        ema2'nin altina iner.
        FLAT: pozisyondayken takeProfitPct veya stopLossPct kosulu gerceklesirse uretilir.
        """
        if ema1Ys is None:
            ema1Ys = self.emas[0][2] if len(self.emas) >= 1 else []
        if ema2Ys is None:
            ema2Ys = self.emas[1][2] if len(self.emas) >= 2 else []

        n = min(len(ema1Ys), len(ema2Ys))
        signals = [None] * n
        position = None
        entryPrice = None

        def finite(v):
            try:
                return math.isfinite(float(v))
            except (TypeError, ValueError):
                return False

        for i in range(max(1, warmup), n):
            if position is not None and entryPrice is not None:
                close = self.closes[i] if i < len(self.closes) else None
                high = self.highs[i] if useHighLow and i < len(self.highs) else close
                low = self.lows[i] if useHighLow and i < len(self.lows) else close
                if finite(close) and finite(high) and finite(low):
                    exitSignal = self._tradeExitSignal(
                        position, entryPrice, float(high), float(low),
                        takeProfitPct, stopLossPct)
                    if exitSignal:
                        signals[i] = exitSignal
                        position = None
                        entryPrice = None
                        continue

            prev1, prev2 = ema1Ys[i - 1], ema2Ys[i - 1]
            cur1, cur2 = ema1Ys[i], ema2Ys[i]
            if not (finite(prev1) and finite(prev2) and finite(cur1) and finite(cur2)):
                continue

            prevDiff = float(prev1) - float(prev2)
            curDiff = float(cur1) - float(cur2)

            if prevDiff <= 0 < curDiff:
                signals[i] = "AL"
                position = "AL"
                entryPrice = float(self.closes[i]) if i < len(self.closes) and finite(self.closes[i]) else None
            elif prevDiff >= 0 > curDiff:
                signals[i] = "SAT"
                position = "SAT"
                entryPrice = float(self.closes[i]) if i < len(self.closes) and finite(self.closes[i]) else None

        return signals

    def _tradeExitSignal(self, position, entryPrice, high, low, takeProfitPct, stopLossPct):
        if takeProfitPct is None and stopLossPct is None:
            return None

        if position == "AL":
            stopHit = stopLossPct is not None and low <= entryPrice * (1.0 - stopLossPct)
            takeHit = takeProfitPct is not None and high >= entryPrice * (1.0 + takeProfitPct)
        elif position == "SAT":
            stopHit = stopLossPct is not None and high >= entryPrice * (1.0 + stopLossPct)
            takeHit = takeProfitPct is not None and low <= entryPrice * (1.0 - takeProfitPct)
        else:
            return None

        return "FLAT" if (stopHit or takeHit) else None

    def generateTradeSignalsEma(self, *args, **kwargs):
        return self.generateTradeSignalsMa(*args, **kwargs)

    def fillPanels(self):
        """Hesaplanan veriyi self.*Panel'lere yazar."""
        self.ohlcPanel.deleteAllData()
        self.ohlcPanel.deleteAllLevels()
        self.ohlcPanel.setCandleData(self.reader.data, name=self.dp.getSembolName() or SYMBOL,
                                     intraday=self.intraday)
        for emaId, name, ys in self.emas:
            self.ohlcPanel.addData(emaId, name, "line", self.xs, ys,
                                   timestamps=self.ts, intraday=self.intraday)

        self.movAvgPanel.deleteAllData()
        self.movAvgPanel.deleteAllLevels()
        for emaId, name, ys in self.emas:
            self.movAvgPanel.addData(emaId, name, "line", self.xs, ys,
                                     timestamps=self.ts, intraday=self.intraday)

        self.macdPanel.deleteAllData()
        self.macdPanel.deleteAllLevels()
        macdSeries = ((1, "MACD", self.macdLine), (2, "Signal", self.macdSignal), (3, "Hist", self.macdHist))
        for dataId, name, ys in macdSeries:
            self.macdPanel.addData(dataId, name, "line", self.xs, ys,
                                   timestamps=self.ts, intraday=self.intraday)

        self.rsiPanel.deleteAllData()
        self.rsiPanel.deleteAllLevels()
        self.rsiPanel.addData(1, "RSI14", "line", self.xs, self.rsiYs,
                              timestamps=self.ts, intraday=self.intraday)
        self.rsiPanel.addHline(30, color=(120, 120, 120, 150))
        self.rsiPanel.addHline(70, color=(120, 120, 120, 150), label="Overbought")
        # Sondan 1000. ve 2000. bara dikey cizgi (xs[-N] = sondan N. bar)
        n = len(self.xs)
        if n >= 1000:
            self.rsiPanel.addVline(self.xs[-1000], color=(255, 0, 0, 150), label="-1000")
        if n >= 2000:
            self.rsiPanel.addVline(self.xs[-2000], color=(255, 150, 0, 150), label="-2000")

        self.stochPanel.deleteAllData()
        self.stochPanel.deleteAllLevels()
        for dataId, name, ys in ((1, "%K", self.stochK), (2, "%D", self.stochD)):
            self.stochPanel.addData(dataId, name, "line", self.xs, ys,
                                    timestamps=self.ts, intraday=self.intraday)
        self.stochPanel.addHline(20, color=(120, 120, 120, 150), label="Oversold")
        self.stochPanel.addHline(80, color=(120, 120, 120, 150), label="Overbought")

    def _makeLinePd(self, dataId, name, ys):
        """Kaynak listelerden bir 'line' PanelData kurar (pool icin; panele
        bagli DEGIL)."""
        d = PanelData(dataId, name, "line", self.xs, ys)
        d.setTimestamps(dateTime=self.ts)
        d.isIntraday = self.intraday
        d.updateStats()
        d.setFullData()
        return d

    def fillPool(self):
        """Kaynak veri (candle + ham seriler) + tum hesaplanan indikatorleri
        pool'a gonderir (panele bagli DEGIL - cizilmese de pool'da durur).
        Pool: Sembol > (Data | Indicators) > item, her item id-bazli (pool_N)."""
        pool.clear()
        sym = self.dp.getSembolName() or SYMBOL

        candleData = self.ohlcPanel.getData(0)
        if candleData:
            pool.addItem("OHLC", "Data", candleData, symbol=sym)

        dataSeries = [("Open", self.opens), ("High", self.highs), ("Low", self.lows),
                     ("Close", self.closes), ("Volume", self.volumes), ("Size", self.sizes)]
        for i, (name, ys) in enumerate(dataSeries, start=1):
            pool.addItem(name, "Data", self._makeLinePd(i, name, ys), symbol=sym)

        indSeries = [(name, ys) for _, name, ys in self.emas]
        indSeries += [("MACD", self.macdLine), ("Signal", self.macdSignal), ("Hist", self.macdHist),
                     ("RSI14", self.rsiYs), ("%K", self.stochK), ("%D", self.stochD)]
        for i, (name, ys) in enumerate(indSeries, start=1):
            pool.addItem(name, "Indicators", self._makeLinePd(i, name, ys), symbol=sym)

        levelSeries = [("Level0", self.level0), ("Level30", self.level30),
                      ("Level50", self.level50), ("Level70", self.level70)]
        for i, (name, ys) in enumerate(levelSeries, start=1):
            pool.addItem(name, "Levels", self._makeLinePd(i, name, ys), symbol=sym)

        print(f"Pool'a eklendi: {len(pool.getAllItems())} item")

    def draw(self):
        # pm.drawPanels()/drawAllPanelData() YOK - tekil eylem, script kendi
        # dongusunu kurar. drawPanel: kabuk (child_window+plot+eksenler).
        # drawPanelData: kabugun icine gercek candle/line serilerini basar.
        #
        # DENENDI: bu satir kaldirilip centerTopPanel'in show'u SADECE
        # RangeSliderBar.sync()'e (frame-callback zinciri, bkz. GuiManager.
        # _onRenderTick) birakilmisti - ama sync() panellerin bu dongude
        # cizilmesinden EN AZ BIR REAL FRAME GERIDEN geldigi icin bu daha
        # KOTU bir sekans (once plotlar, sonra container) ortaya cikardi.
        # Panel/RangeSlider'in AYNI anda gorunmesi icin show=True'nun
        # PLOTLARLA AYNI senkron cagri icinde (draw() burada) set edilmesi
        # gerekiyor - RangeSliderBar.sync() ile cift-otorite olsa da
        # (checkbox'lar kapatilirsa bir sonraki frame'de zaten duzeltiliyor)
        # geri eklendi.
        dpg.configure_item("centerTopPanel", show=True)
        for p in pm.iterateAllPanels():
            pm.drawPanel(p.id)
            pm.drawPanelData(p.id)
        if self.signals:
            self.drawTradeSignals()

    def drawTradeSignals(self):
        if not self.ohlcPanel or not self.signals:
            return
        tsr.draw(self.ohlcPanel.id, 0, self.signals,
                 showSignals=SHOW_TRADE_SIGNALS,
                 showLevelLines=SHOW_TRADE_SIGNAL_LINES,
                 colorBars=COLOR_BARS_BY_SIGNAL)

    def scheduleTradeSignals(self, delayFrames=TRADE_SIGNAL_DRAW_DELAY_FRAMES):
        """Trade signal overlay'ini ana plotlar ekrana geldikten birkac frame
        sonra cizer. Boylece ilk panel yukleme hissi OHLC/indikator cizimiyle
        tamamlanir, pahali sinyal overlay'i sonraya kalir."""
        targetPanelId = self.ohlcPanel.id if self.ohlcPanel else None
        targetDataLen = len(self.signals)

        def delayedDraw():
            if targetPanelId is None or pm.getPanel(targetPanelId) is None:
                return
            if len(self.signals) != targetDataLen:
                return
            self.drawTradeSignals()

        gm.deferFrames(delayedDraw, delayFrames)
        print(f"TradeSignalRenderer {delayFrames} frame sonra cizilecek.")

    def run(self):
        pm.setContainer("centerCenterPanel")

        # dp'deki reader ONCEKI Run'un kendi readData() cagrisindan kalmissa
        # (getReadSource()=="script") DATASET_CHOICE'i degistirmenin hicbir
        # etkisi olmuyordu (loadData() dp.hasReader() True oldugu icin hep
        # ESKI veriyi donduruyordu) - o durumda cache'i temizleyip
        # DATASET_CHOICE'in taze okunmasini sagliyoruz. Ama Data Manager
        # panelinden ELLE okudugun bir reader ("manual") ASLA silinmez -
        # loadData() onu kullanmaya devam eder.
        if gm.dataManager.getReadSource() == "script":
            gm.dataManager.setReader(None)

        # Once eskisini SIL ve bunu ekrana BAS (split_frame) - kullanici
        # gercekten "sifirlandigini" hissetsin. Sonra sifirdan kur+ciz.
        dpg.configure_item("centerTopPanel", show=False)
        pm.deleteAllPanels()
        pm.sync()
        pool.clear()
        gm.leftMenuPanel.refresh()
        gm.poolPanel.refresh()
        gm._refreshActivePanelCombo()  # Active Panel combosu da bu anda "None" gostersin
        dpg.split_frame()

        self.buildPanels()
        
        self.loadData()
        if not self.hasData():
            print("Veri okunamadi, cikiliyor.")
            return

        print(f"BarCount: {self.reader.data.length}   Elapsed: {self.reader.elapsedMs} ms")

        self.computeIndicators()
        
        self.fillPanels()

        self.fillPool()

        self.draw()

        # Alternatiflerden SADECE BIRI aktif olmali (setXAxisMode her cagrida
        # bir onceki formatin UZERINE yazar - hepsi ayni anda birakilirsa
        # sonuncusu kazanir, digerlerinin hicbir etkisi olmaz):
        #   pm.setXAxisMode("datetime", "%d.%m.%Y %H:%M:%S")   # tarih + saat, tek satir
        pm.setXAxisMode("datetime")                        # (varsayilan) isIntraday'e gore otomatik, iki satir
        #   pm.setXAxisMode("datetime", "%H:%M:%S")            # sadece saat
        #   pm.setXAxisMode("datetime", "%d.%m.%Y")            # sadece tarih
        #   pm.setXAxisMode("datetime", "auto")                    # isIntraday'e gore: intraday->sadece saat, degilse->sadece tarih

        # topPanel'deki View/Range (Last N Data/First N Data/Range) N/N2
        # kutularinin varsayilanlarini bu Run'daki bar sayisina gore
        # BIR KEZ ilkler (Last/First N -> 1000, Range -> 0..barCount).
        # Sonrasinda kullanicinin girdigi deger combo mod degisiminde
        # KAYBOLMAZ - sadece yeni bir Run (yeniden data yukleme) resetler.
        gm.seedTopViewRangeInputs(len(self.xs))

        gm.leftMenuPanel.refresh()
        gm.poolPanel.refresh()

        print("Paneller olusturuldu:")
        for p in pm.iterateAllPanels():
            print(f"  id={p.id}  name={p.name}  height={p.height}")
            for d in p.iterateAllData():
                print(f"    data id={d.id}  name={d.name}  type={d.dataType}  bars={len(d.xs)}")

        print("Bitti.")

App().run()
