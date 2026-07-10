import numpy as np


class PanelData:
    DATA_TYPES = {"line", "candle", "bar", "histogram", "volume"}
    LOD_MAX_POINTS = 3000  # getLodSlice varsayilani - bkz. orada

    def __init__(self, dataId: int, name: str = "", dataType: str = "line",
                 xs: list = None, ys: list = None, color=None):
        self.id = dataId
        self.name = name
        self.dataType = dataType if dataType in self.DATA_TYPES else "line"
        self.xs = xs or []
        self.ys = ys or []
        self.color = color
        self.isVisible = True
        self.dataCount = 0
        self.minY = 0
        self.maxY = 0
        self.xFormat = "%H:%M:%S"
        self.isIntraday = True
        self.parent = None  # bu PanelData'yi tutan Panel (bkz. setParent/getParent, Panel.addData tarafindan set edilir)

        self.timestamps: list = []
        self.open: list = []
        self.high: list = []
        self.low: list = []
        self.close: list = []
        self.volume: list = []
        self.size: list = []
        self.openInterest: list = []
        self.tradeCount: list = []

        # LOD — full data snapshots (numpy arrays, set via setFullData())
        self._fullXs = None
        self._fullYs = None
        self._fullOpen = None
        self._fullHigh = None
        self._fullLow = None
        self._fullClose = None
        self._fullVolume = None
        self._fullTimestamps = None
        self.fullCount: int = 0
        self.lodCount: int = 0

    def updateStats(self):
        """Recompute dataCount, minY, maxY from the current data. Call manually
        after changing xs/ys or OHLC. Candle range uses low/high, others use ys."""
        self.dataCount = len(self.xs)
        if self.dataType == "candle" and self.low and self.high:
            self.minY = min(self.low)
            self.maxY = max(self.high)
        elif self.ys:
            self.minY = min(self.ys)
            self.maxY = max(self.ys)
        else:
            self.minY = 0
            self.maxY = 0

    def setVisible(self, v: bool):
        self.isVisible = v

    def setParent(self, panel):
        """Bu PanelData'nin ait oldugu Panel'i baglar (Panel.addData tarafindan
        otomatik cagrilir)."""
        self.parent = panel

    def getParent(self):
        """Bu PanelData'nin ait oldugu Panel'i dondurur (baglanmadiysa None)."""
        return self.parent

    def setOhlc(self, openData, highData, lowData, closeData):
        self.dataType = "candle"
        self.open = openData or []
        self.high = highData or []
        self.low = lowData or []
        self.close = closeData or []

    def setVolume(self, volumeData):
        self.volume = volumeData or []

    def setSize(self, sizeData):
        self.size = sizeData or []

    def setOpenInterest(self, oiData):
        self.openInterest = oiData or []

    def setTradeCount(self, tcData):
        self.tradeCount = tcData or []

    def setFullData(self):
        """Snapshot current xs/ys/ohlc/volume into _full* numpy arrays.
        Call once after all attributes are set, before appending to panel."""
        if self.xs:
            self._fullXs = np.asarray(self.xs, dtype=np.float64)
            self.fullCount = len(self.xs)
            self.lodCount = self.fullCount
        if self.ys:
            self._fullYs = np.asarray(self.ys, dtype=np.float64)
        if self.open:
            self._fullOpen = np.asarray(self.open, dtype=np.float64)
            self._fullHigh = np.asarray(self.high, dtype=np.float64)
            self._fullLow = np.asarray(self.low, dtype=np.float64)
            self._fullClose = np.asarray(self.close, dtype=np.float64)
        if self.volume:
            self._fullVolume = np.asarray(self.volume, dtype=np.float64)
        self._fullTimestamps = self.timestamps  # list of datetimes, kept as-is

    def setTimestamps(self, dateTime=None, date=None, time=None, epochTime=None):
        self.timestamps = []
        if dateTime:
            self.timestamps = dateTime
        elif date and time:
            self.timestamps = list(zip(date, time))
        elif epochTime:
            self.timestamps = epochTime

    def getLodSlice(self, xMin, xMax, maxPoints=None):
        """[xMin, xMax] bar-index araligindaki veriyi, DPG/ImPlot'a
        gonderilecek nokta sayisi maxPoints'i asmayacak sekilde dondurur -
        buyuk (2M+ bar gibi) veri setlerinde HER cizimde/zoom-pan'de TAM
        veriyi yollamanin (hem Python->C marshalling hem GPU vertex sayisi)
        yarattigi yavasligi onlemek icin (bkz. PanelManager._drawOrUpdateSeries/
        updateLod). _fullXs/_fullYs/_fullOpen vb. (setFullData ile hazirlanan
        numpy snapshot'lari) kullanir - bunlar YOKSA (veri hic setFullData
        gormemis) None doner.

        [xMin,xMax] araligi np.searchsorted ile (xs'in MONOTONIK ARTAN
        oldugu varsayimiyla - bu projede TUM seriler bar-index sirali, bkz.
        makeCandlePanelData/Panel.addData) O(log n) + O(gorunur dilim)
        surede bulunur, TAM diziyi TARAMAZ.

        Gorunur bar sayisi zaten maxPoints'in altindaysa (TAM detay
        gerekiyorsa) decimation YAPILMAZ, ham dilim oldugu gibi donuyor.
        Fazlaysa: candle icin her 'step' bar'lik kovada open=ILK, high=MAX,
        low=MIN, close=SON degeri alinir (standart OHLC downsampling -
        fitilleri/spike'lari KAYBETMEZ); line/bar/volume icin BASIT stride
        (her step'te bir nokta, + SON nokta hep dahil) - bu seriler
        candle'a gore daha 'duz' oldugu icin peak kaybi gorsel olarak
        onemsiz.

        Donen: {'dataType': 'candle', 'xs':[...], 'opens':[...], 'closes':[...],
        'lows':[...], 'highs':[...]} VEYA {'dataType': 'line'|'bar'|'volume',
        'xs':[...], 'ys':[...]} - butun listeler PYTHON listesi (numpy degil,
        dpg.add_*_series/set_value'ya dogrudan verilebilir). Gorunur veri
        yoksa None."""
        maxPoints = maxPoints or self.LOD_MAX_POINTS
        fullXs = self._fullXs
        if fullXs is None or len(fullXs) == 0:
            return None
        startIdx = max(0, int(np.searchsorted(fullXs, xMin, side="left")))
        endIdx = min(len(fullXs), int(np.searchsorted(fullXs, xMax, side="right")))
        if endIdx <= startIdx:
            return None
        xsSlice = fullXs[startIdx:endIdx]

        if self.dataType == "candle" and self._fullOpen is not None:
            opens = self._fullOpen[startIdx:endIdx]
            highs = self._fullHigh[startIdx:endIdx]
            lows = self._fullLow[startIdx:endIdx]
            closes = self._fullClose[startIdx:endIdx]
            outXs, outOpens, outHighs, outLows, outCloses = _decimateOhlc(
                xsSlice, opens, highs, lows, closes, maxPoints)
            return {"dataType": "candle", "xs": outXs, "opens": outOpens,
                   "highs": outHighs, "lows": outLows, "closes": outCloses}

        if self.dataType in ("bar", "volume") and self._fullVolume is not None:
            vol = self._fullVolume[startIdx:endIdx]
            outXs, outYs = _decimateStride(xsSlice, vol, maxPoints)
            return {"dataType": self.dataType, "xs": outXs, "ys": outYs}

        ys = self._fullYs
        if ys is None:
            return None
        ysSlice = ys[startIdx:endIdx]
        outXs, outYs = _decimateStride(xsSlice, ysSlice, maxPoints)
        return {"dataType": "line", "xs": outXs, "ys": outYs}

    def getLodXY(self, xMin, xMax, maxPoints=None):
        """getLodSlice'in BASITLESTIRILMIS hali - dataType farki GOZETMEDEN
        (candle'da bile _fullYs zaten Close'tur, bkz. makeCandlePanelData:
        panelData.ys = closes) hep TEK bir (xs, ys) LOD dilimi (Python
        listesi ciftı) dondurur. Tam OHLC ayrintisina (fitil/wick) DEGIL,
        SADECE tek bir egriye ihtiyaci olan cagiranlar icin (bkz.
        RangeSliderBar'daki overview 'golge' silüeti,
        PanelManager.getOverviewSeries) - o overview 110px yukseklikte kucuk
        bir plot, gorunur bar sayisindan BAGIMSIZ olarak COK daha az nokta
        (bkz. PanelManager.OVERVIEW_LOD_MAX_POINTS) yeterli. Veri/aralik
        yoksa None."""
        maxPoints = maxPoints or self.LOD_MAX_POINTS
        fullXs = self._fullXs
        fullYs = self._fullYs
        if fullXs is None or fullYs is None or len(fullXs) == 0:
            return None
        startIdx = max(0, int(np.searchsorted(fullXs, xMin, side="left")))
        endIdx = min(len(fullXs), int(np.searchsorted(fullXs, xMax, side="right")))
        if endIdx <= startIdx:
            return None
        xsSlice = fullXs[startIdx:endIdx]
        ysSlice = fullYs[startIdx:endIdx]
        return _decimateStride(xsSlice, ysSlice, maxPoints)


def _decimateOhlc(xs, opens, highs, lows, closes, maxPoints):
    """xs/opens/highs/lows/closes (AYNI uzunlukta numpy array) - maxPoints'i
    asarsa 'step' bar'lik kovalara ayirip her kovayi TEK bir OHLC bar'a
    indirger (open=kovanin ILK acilisi, high=kovanin EN YUKSEGI, low=EN
    DUSUGU, close=kovanin SON kapanisi) - boylece fiyat spike'lari/fitilleri
    KAYBOLMAZ, sadece bar SAYISI azalir. Kalan (step'e tam bolunmeyen)
    kuyruk bar'lari AYRI bir son kova olarak eklenir."""
    n = len(xs)
    if n <= maxPoints:
        return xs.tolist(), opens.tolist(), highs.tolist(), lows.tolist(), closes.tolist()
    step = -(-n // maxPoints)  # ceil division
    usableN = (n // step) * step
    outXs = xs[:usableN:step]
    outOpens = opens[:usableN:step]
    if usableN > 0:
        outHighs = highs[:usableN].reshape(-1, step).max(axis=1)
        outLows = lows[:usableN].reshape(-1, step).min(axis=1)
        outCloses = closes[step - 1:usableN:step]  # her kovanin SON (step-1, 2*step-1, ...) elemani
    else:
        outHighs = highs[:0]
        outLows = lows[:0]
        outCloses = closes[:0]
    outXs = outXs.tolist()
    outOpens = outOpens.tolist()
    outHighs = outHighs.tolist()
    outLows = outLows.tolist()
    outCloses = outCloses.tolist()
    if usableN < n:
        outXs.append(float(xs[usableN]))
        outOpens.append(float(opens[usableN]))
        outHighs.append(float(highs[usableN:].max()))
        outLows.append(float(lows[usableN:].min()))
        outCloses.append(float(closes[-1]))
    return outXs, outOpens, outHighs, outLows, outCloses


def _decimateStride(xs, ys, maxPoints):
    """xs/ys (AYNI uzunlukta numpy array) - maxPoints'i asarsa 'step'lik
    kovalara ayirip her kovadan TEK nokta alan bir decimation. NAIF bir
    "her step'te bir" ORNEKLEME DEGIL: her kovada NaN OLMAYAN bir deger
    VARSA o tercih edilir (yoksa kovanin ILK elemani). Bu, al/sat sinyali
    veya iki indikator kesisimi gibi COGU NaN/bos, SADECE bazi barlarda
    deger tasiyan (ana seriyle AYNI uzunlukta) seyrek serilerde KRITIK:
    naif stride, seyrek isaretlerin coguna hic denk gelmeyip zoom-out'ta
    onlari GORUNMEZ yapardi - "kovada varsa GOSTER" mantigi bunu onler.
    Duz/yogun serilerde (RSI/MACD gibi) davranis DEGISMEZ (kova basi zaten
    finite oldugu icin yine o secilir). SON nokta (xs[-1]/ys[-1]) her zaman
    DAHIL edilir - yoksa hem serinin sag ucu 'kesilmis' gibi gorunur hem de
    tam son bar'daki olasi bir sinyal kaybolabilirdi."""
    n = len(xs)
    if n <= maxPoints:
        return xs.tolist(), ys.tolist()
    step = -(-n // maxPoints)
    usableN = (n // step) * step
    if usableN > 0:
        ysBuckets = ys[:usableN].reshape(-1, step)
        finiteMask = np.isfinite(ysBuckets)
        anyFinite = finiteMask.any(axis=1)
        # argmax: ILK True'nun offset'i - satir TAMAMEN False ise 0 doner,
        # bu da "kovanin ILK elemani" fallback'iyle zaten AYNI davranis.
        firstFiniteOffset = np.argmax(finiteMask, axis=1)
        rowOffsets = np.where(anyFinite, firstFiniteOffset, 0)
        flatIdx = np.arange(usableN // step) * step + rowOffsets
        outXs = xs[flatIdx].tolist()
        outYs = ys[flatIdx].tolist()
    else:
        outXs, outYs = [], []
    if not outXs or outXs[-1] != float(xs[-1]):
        outXs.append(float(xs[-1]))
        outYs.append(float(ys[-1]))
    return outXs, outYs


def makeCandlePanelData(source=None, *, opens=None, highs=None, lows=None,
                        closes=None, volumes=None, sizes=None, dateTime=None,
                        name="", dataId=0, intraday=True):
    """Esnek candle PanelData kurucusu. Girdi 3 sekilde olabilir:

      1) source = StockData (reader.data): .open/.high/.low/.close/.volume/.size/.dateTime
      2) source = PanelData (hazir candle): oldugu gibi DONDURULUR
      3) source=None + ayri listeler: opens/highs/lows/closes/volumes/sizes/dateTime

    Donen: candle tipinde PanelData (Panel/PanelManager bunu dataList'e koyar).
    """
    # 2) Hazir PanelData verildiyse dokunma.
    if isinstance(source, PanelData):
        return source
    # 1) StockData (duck-typed) verildiyse listelerini al.
    if source is not None:
        opens, highs, lows = source.open, source.high, source.low
        closes, volumes, sizes = source.close, source.volume, source.size
        dateTime = source.dateTime
    # 3) (veya) dogrudan verilen listeler kullanilir.
    closes = list(closes or [])
    n = len(closes)
    panelData = PanelData(dataId, name, "candle")
    panelData.xs = list(range(n))
    panelData.ys = closes
    panelData.setOhlc(list(opens or []), list(highs or []), list(lows or []), closes)
    if volumes:
        panelData.setVolume([float(v) for v in volumes])
    if sizes:
        panelData.setSize([int(v) for v in sizes])
    if dateTime:
        panelData.setTimestamps(dateTime=dateTime)
    panelData.isIntraday = intraday
    panelData.xFormat = "%H:%M:%S" if intraday else "%d.%m.%Y"
    panelData.updateStats()
    panelData.setFullData()
    return panelData
