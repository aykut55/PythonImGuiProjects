# Hazir: gm, pm, dpg, Panel, PanelData, StockDataReader, FilterMode, IndicatorManager

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
        self.signals = []  # al/sat/flat sinyalleri (henuz doldurulmuyor)
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
        yoksa dataset secimindeki default path'i dataManager uzerinden okur."""
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
        self.signals = []  # al/sat/flat sinyalleri (henuz doldurulmuyor)        

        im = IndicatorManager(self.xs, self.opens, self.highs, self.lows,
                              self.closes, self.volumes, self.sizes)

        self.emas = [(i, f"EMA{p}", im.ema(p)) for i, p in enumerate([8, 13, 21], start=1)]
        self.rsiYs = im.rsi(14)
        self.macdLine, self.macdSignal, self.macdHist = im.macd(12, 26, 9)
        self.stochK, self.stochD = im.stochastic(14, 3)

        # Sabit seviye cizgileri (RSI/Stochastic referanslari icin) - pool'a
        # "Levels" grubunda gidecek (bkz. fillPool).
        n = len(self.xs)
        self.level0 = [0.0] * n
        self.level30 = [30.0] * n
        self.level50 = [50.0] * n
        self.level70 = [70.0] * n

    def fillPanels(self):
        """Hesaplanan veriyi self.*Panel'lere yazar."""
        self.ohlcPanel.deleteAllData()
        self.ohlcPanel.deleteAllLevels()
        self.ohlcPanel.setCandleData(self.reader.data, name=SYMBOL, intraday=self.intraday)
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
        for p in pm.iterateAllPanels():
            pm.drawPanel(p.id)
            pm.drawPanelData(p.id)

    def run(self):
        dpg.configure_item("centerTopPanel", show=False)
        pm.setContainer("centerCenterPanel")
        
        # Once eskisini SIL ve bunu ekrana BAS (split_frame) - kullanici
        # gercekten "sifirlandigini" hissetsin. Sonra sifirdan kur+ciz.
        pm.deleteAllPanels()
        pm.sync()
        pool.clear()
        gm.leftMenuPanel.refresh()
        gm.poolPanel.refresh()
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
        #   pm.setXAxisMode("datetime")                        # (varsayilan) isIntraday'e gore otomatik, iki satir
        #   pm.setXAxisMode("datetime", "%H:%M:%S")            # sadece saat
        #   pm.setXAxisMode("datetime", "%d.%m.%Y")            # sadece tarih
        pm.setXAxisMode("datetime", "auto")                    # isIntraday'e gore: intraday->sadece saat, degilse->sadece tarih

        gm.leftMenuPanel.refresh()
        gm.poolPanel.refresh()

        print("Paneller olusturuldu:")
        for p in pm.iterateAllPanels():
            print(f"  id={p.id}  name={p.name}  height={p.height}")
            for d in p.iterateAllData():
                print(f"    data id={d.id}  name={d.name}  type={d.dataType}  bars={len(d.xs)}")

        print("Bitti.")

App().run()
