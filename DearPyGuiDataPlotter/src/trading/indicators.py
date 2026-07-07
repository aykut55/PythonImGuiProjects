class Indicators:
    @staticmethod
    def sma(data: list[float], period: int) -> list[float]:
        if period <= 0 or len(data) < period:
            return []
        result = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(0.0)
            else:
                window = data[i - period + 1:i + 1]
                result.append(sum(window) / period)
        return result

    @staticmethod
    def ema(data: list[float], period: int) -> list[float]:
        if period <= 0 or len(data) < period:
            return []
        multiplier = 2.0 / (period + 1)
        result = [0.0] * len(data)
        smaFirst = sum(data[:period]) / period
        result[period - 1] = smaFirst
        for i in range(period, len(data)):
            result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
        return result

    @staticmethod
    def macd(data: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
        emaFast = Indicators.ema(data, fast)
        emaSlow = Indicators.ema(data, slow)
        if not emaFast or not emaSlow:
            return [], [], []
        macdLine = [emaFast[i] - emaSlow[i] for i in range(len(data))]
        signalLine = Indicators.ema(macdLine, signal)
        histogram = [macdLine[i] - signalLine[i] if signalLine[i] else 0.0 for i in range(len(data))]
        return macdLine, signalLine, histogram

    @staticmethod
    def rsi(data: list[float], period: int = 14) -> list[float]:
        if len(data) < period + 1:
            return []
        result = [0.0] * len(data)
        gains = []
        losses = []
        for i in range(1, len(data)):
            delta = data[i] - data[i - 1]
            gains.append(delta if delta > 0 else 0.0)
            losses.append(-delta if delta < 0 else 0.0)
        avgGain = sum(gains[:period]) / period
        avgLoss = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            if avgLoss == 0:
                result[i + 1] = 100.0
            else:
                rs = avgGain / avgLoss
                result[i + 1] = 100.0 - (100.0 / (1.0 + rs))
            avgGain = (avgGain * (period - 1) + gains[i]) / period
            avgLoss = (avgLoss * (period - 1) + losses[i]) / period
        return result

    @staticmethod
    def stochastic(high: list[float], low: list[float], close: list[float],
                   kPeriod: int = 14, dPeriod: int = 3) -> tuple:
        if len(close) < kPeriod:
            return [], []
        stochK = [0.0] * len(close)
        stochD = [0.0] * len(close)
        for i in range(kPeriod - 1, len(close)):
            highest = max(high[i - kPeriod + 1:i + 1])
            lowest = min(low[i - kPeriod + 1:i + 1])
            if highest - lowest == 0:
                stochK[i] = 50.0
            else:
                stochK[i] = ((close[i] - lowest) / (highest - lowest)) * 100.0
        for i in range(kPeriod + dPeriod - 2, len(close)):
            window = stochK[i - dPeriod + 1:i + 1]
            stochD[i] = sum(window) / dPeriod
        return stochK, stochD
