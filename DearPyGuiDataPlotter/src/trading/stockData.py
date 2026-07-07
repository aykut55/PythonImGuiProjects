from datetime import datetime, date, time


class StockData:
    def __init__(self):
        self.symbol: str = ""
        self.dateTimeFormat: str = "%Y.%m.%d %H:%M:%S:%f"
        self.dateTime: list[datetime] = []
        self.open: list[float] = []
        self.high: list[float] = []
        self.low: list[float] = []
        self.close: list[float] = []
        self.volume: list[float] = []
        self.size: list[int] = []
        self.openInterest: list[float] = []
        self.macd: list[float] = []
        self.macdSignal: list[float] = []
        self.macdHistogram: list[float] = []
        self.rsi: list[float] = []
        self.stochasticK: list[float] = []
        self.stochasticD: list[float] = []
        self.ema: dict[int, list[float]] = {}
        self.sma: dict[int, list[float]] = {}

    @property
    def length(self):
        return len(self.dateTime)

    @property
    def date(self):
        return [dt.date() for dt in self.dateTime]

    @property
    def time(self):
        return [dt.time() for dt in self.dateTime]

    @property
    def epochTime(self):
        return [dt.timestamp() for dt in self.dateTime]

    @property
    def epochDate(self):
        return [datetime.combine(dt.date(), time()).timestamp() for dt in self.dateTime]

    @property
    def dateTimeStr(self):
        if "%f" in self.dateTimeFormat:
            return [dt.strftime(self.dateTimeFormat)[:-3] for dt in self.dateTime]
        return [dt.strftime(self.dateTimeFormat) for dt in self.dateTime]

    @property
    def dateStr(self):
        return [dt.strftime("%Y.%m.%d") for dt in self.dateTime]

    @property
    def timeStr(self):
        return [dt.strftime("%H:%M:%S:%f")[:-3] for dt in self.dateTime]

    def clear(self):
        self.dateTime.clear()
        self.open.clear()
        self.high.clear()
        self.low.clear()
        self.close.clear()
        self.volume.clear()
        self.size.clear()
        self.openInterest.clear()
        self.macd.clear()
        self.macdSignal.clear()
        self.macdHistogram.clear()
        self.rsi.clear()
        self.stochasticK.clear()
        self.stochasticD.clear()
        self.ema.clear()
        self.sma.clear()

    def setDateTime(self, dateTimeList: list):
        self.dateTime = [dt if isinstance(dt, datetime) else datetime.now()
                         for dt in dateTimeList]

    def setDate(self, dateList: list, timeList: list = None):
        if timeList:
            self.dateTime = [datetime.combine(d, t)
                             for d, t in zip(dateList, timeList)]
        else:
            self.dateTime = [datetime.combine(d, time())
                             for d in dateList]

    def setTime(self, timeList: list):
        if not self.dateTime:
            self.dateTime = [datetime.combine(date.today(), t)
                             for t in timeList]
        else:
            self.dateTime = [datetime.combine(self.dateTime[i].date(), t)
                             if i < len(timeList) else self.dateTime[i]
                             for i, t in enumerate(timeList)]

    def setEpochTime(self, epochList: list):
        self.dateTime = [datetime.fromtimestamp(e) for e in epochList]
