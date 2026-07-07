import numpy as np


class PanelData:
    DATA_TYPES = {"line", "candle", "bar", "histogram", "volume"}

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
