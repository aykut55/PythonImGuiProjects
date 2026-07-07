from datetime import datetime
from enum import Enum
from time import perf_counter
from .stockData import StockData
from .indicators import Indicators


class FilterMode(Enum):
    All = 0
    LastN = 1
    FirstN = 2
    IndexRange = 3
    AfterDateTime = 4
    BeforeDateTime = 5
    DateTimeRange = 6


class StockDataReaderException(Exception):
    pass


class StockDataReader:
    def __init__(self):
        self._data: StockData = StockData()
        self._metaData: dict[str, str] = {}
        self._metaDataLines: list[str] = []
        self._elapsedMs: int = 0

    @property
    def data(self) -> StockData:
        return self._data

    @property
    def metaData(self) -> dict[str, str]:
        return self._metaData

    @property
    def elapsedMs(self) -> int:
        return self._elapsedMs

    def clear(self):
        self._data.clear()
        self._metaData.clear()
        self._metaDataLines.clear()

    def readMetaData(self, filePath: str) -> dict[str, str]:
        self._metaData.clear()
        self._metaDataLines.clear()
        with open(filePath, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped.startswith("#"):
                    break
                self._metaDataLines.append(stripped)
                content = stripped[1:].strip()
                separator = content.find(":")
                if separator > 0:
                    key = content[:separator].strip()
                    val = content[separator + 1:].strip()
                    self._metaData[key] = val
        return self._metaData

    def readData(self, filePath: str,
                 mode: FilterMode = FilterMode.All,
                 n1: int = 0, n2: int = 0,
                 dt1: datetime = None, dt2: datetime = None) -> int:
        self._data.clear()
        start = perf_counter()
        rows = []
        with open(filePath, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("Id"):
                    continue
                parts = stripped.split(";")
                if len(parts) < 8:
                    continue
                try:
                    dt = datetime.strptime(f"{parts[1]} {parts[2]}", "%Y.%m.%d %H:%M:%S")
                    row = {
                        "id": int(parts[0]),
                        "dateTime": dt,
                        "open": float(parts[3]),
                        "high": float(parts[4]),
                        "low": float(parts[5]),
                        "close": float(parts[6]),
                        "volume": float(parts[7]),
                        "size": int(float(parts[8])) if len(parts) > 8 else 0,
                    }
                    rows.append(row)
                except (ValueError, IndexError):
                    continue

        rows = self._applyFilter(rows, mode, n1, n2, dt1, dt2)
        for r in rows:
            self._data.dateTime.append(r["dateTime"])
            self._data.open.append(r["open"])
            self._data.high.append(r["high"])
            self._data.low.append(r["low"])
            self._data.close.append(r["close"])
            self._data.volume.append(r["volume"])
            self._data.size.append(r["size"])
        self._elapsedMs = int((perf_counter() - start) * 1000)
        return self._data.length

    def readDataWithPandas(self, filePath: str,
                           mode: FilterMode = FilterMode.All,
                           n1: int = 0, n2: int = 0,
                           dt1: datetime = None, dt2: datetime = None) -> int:
        import pandas as pd
        self._data.clear()
        start = perf_counter()
        df = pd.read_csv(
            filePath, sep=";", comment="#",
            names=["Id", "Date", "Time", "Open", "High", "Low", "Close", "Volume", "Lot"],
            dtype={"Open": float, "High": float, "Low": float, "Close": float,
                   "Volume": float, "Lot": int},
            skip_blank_lines=True,
        )
        dtCombined = df["Date"] + " " + df["Time"]
        df["DateTime"] = pd.to_datetime(dtCombined, format="%Y.%m.%d %H:%M:%S")

        if mode == FilterMode.LastN and n1 > 0:
            df = df.tail(n1)
        elif mode == FilterMode.FirstN and n1 > 0:
            df = df.head(n1)
        elif mode == FilterMode.IndexRange and 0 <= n1 <= n2 < len(df):
            df = df.iloc[n1:n2 + 1]
        else:
            df = self._applyFilterDataFrame(df, mode, n1, n2, dt1, dt2)

        self._data.open = df["Open"].tolist()
        self._data.high = df["High"].tolist()
        self._data.low = df["Low"].tolist()
        self._data.close = df["Close"].tolist()
        self._data.volume = df["Volume"].tolist()
        self._data.size = df["Lot"].tolist()
        self._data.dateTime = df["DateTime"].tolist()

        self._elapsedMs = int((perf_counter() - start) * 1000)
        return self._data.length

    def _applyFilterDataFrame(self, df, mode, n1, n2, dt1, dt2):
        if mode == FilterMode.All:
            return df
        elif mode == FilterMode.LastN:
            return df.tail(n1) if n1 > 0 else df
        elif mode == FilterMode.FirstN:
            return df.head(n1) if n1 > 0 else df
        elif mode == FilterMode.IndexRange:
            return df.iloc[n1:n2 + 1] if 0 <= n1 <= n2 < len(df) else df.head(0)
        elif mode == FilterMode.AfterDateTime:
            return df[df["DateTime"] >= dt1] if dt1 else df
        elif mode == FilterMode.BeforeDateTime:
            return df[df["DateTime"] <= dt1] if dt1 else df
        elif mode == FilterMode.DateTimeRange:
            return df[(df["DateTime"] >= dt1) & (df["DateTime"] <= dt2)] if dt1 and dt2 else df
        return df

    def _applyFilter(self, rows: list, mode: FilterMode,
                     n1: int, n2: int,
                     dt1: datetime, dt2: datetime) -> list:
        if mode == FilterMode.All:
            return rows
        elif mode == FilterMode.LastN:
            return rows[-n1:] if n1 > 0 else rows
        elif mode == FilterMode.FirstN:
            return rows[:n1] if n1 > 0 else rows
        elif mode == FilterMode.IndexRange:
            if 0 <= n1 <= n2 < len(rows):
                return rows[n1:n2 + 1]
            return []
        elif mode == FilterMode.AfterDateTime:
            return [r for r in rows if r["dateTime"] >= dt1] if dt1 else rows
        elif mode == FilterMode.BeforeDateTime:
            return [r for r in rows if r["dateTime"] <= dt1] if dt1 else rows
        elif mode == FilterMode.DateTimeRange:
            if dt1 and dt2:
                return [r for r in rows if dt1 <= r["dateTime"] <= dt2]
            return rows
        return rows

    def head(self, n: int = 5) -> str:
        header = f"  {'No':>6s} {'Date':<10s} {'Time':<12s} {'Open':>8s} {'High':>8s} {'Low':>8s} {'Close':>8s} {'Volume':>14s} {'Lot':>8s}"
        sep = f"  {'-' * 6} {'-' * 10} {'-' * 12} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 14} {'-' * 8}"
        lines = [header, sep]
        for i in range(min(n, self._data.length)):
            lines.append(
                f"  {i:6d} {self._data.dateStr[i]:10s} {self._data.timeStr[i]:12s} "
                f"{self._data.open[i]:8.2f} {self._data.high[i]:8.2f} "
                f"{self._data.low[i]:8.2f} {self._data.close[i]:8.2f} "
                f"{self._data.volume[i]:14.0f} {self._data.size[i]:8d}")
        return "\n".join(lines)

    def tail(self, n: int = 5) -> str:
        header = f"  {'No':>6s} {'Date':<10s} {'Time':<12s} {'Open':>8s} {'High':>8s} {'Low':>8s} {'Close':>8s} {'Volume':>14s} {'Lot':>8s}"
        sep = f"  {'-' * 6} {'-' * 10} {'-' * 12} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 14} {'-' * 8}"
        lines = [header, sep]
        start = max(0, self._data.length - n)
        for i in range(start, self._data.length):
            lines.append(
                f"  {i:6d} {self._data.dateStr[i]:10s} {self._data.timeStr[i]:12s} "
                f"{self._data.open[i]:8.2f} {self._data.high[i]:8.2f} "
                f"{self._data.low[i]:8.2f} {self._data.close[i]:8.2f} "
                f"{self._data.volume[i]:14.0f} {self._data.size[i]:8d}")
        return "\n".join(lines)

    def calculateSma(self, period: int):
        self._data.sma[period] = Indicators.sma(self._data.close, period)

    def calculateEma(self, period: int):
        self._data.ema[period] = Indicators.ema(self._data.close, period)

    def calculateMacd(self, fast: int = 12, slow: int = 26, signal: int = 9):
        macdLine, signalLine, histogram = Indicators.macd(
            self._data.close, fast, slow, signal)
        self._data.macd = macdLine
        self._data.macdSignal = signalLine
        self._data.macdHistogram = histogram

    def calculateRsi(self, period: int = 14):
        self._data.rsi = Indicators.rsi(self._data.close, period)

    def calculateStochastic(self, kPeriod: int = 14, dPeriod: int = 3):
        k, d = Indicators.stochastic(
            self._data.high, self._data.low, self._data.close, kPeriod, dPeriod)
        self._data.stochasticK = k
        self._data.stochasticD = d
