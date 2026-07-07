from .indicators import Indicators


class IndicatorManager:
    """Bir seri uzerinde indikator hesaplayan yonetici.

    Girdi listeleri (xs / open / high / low / close / volume / size) DISARIDAN
    verilir (tek kaynak). Hesaplamalar saf `Indicators` fonksiyonlariyla yapilir;
    boylece indikator mantigi cizim/script'ten ayrisir ve tekrar kullanilabilir.

    Kullanim:
        im = IndicatorManager(xs, opens, highs, lows, closes, volumes, sizes)
        ema8   = im.ema(8)
        rsi14  = im.rsi(14)
        line, signal, hist = im.macd(12, 26, 9)
    """

    def __init__(self, xs=None, opens=None, highs=None, lows=None,
                 closes=None, volumes=None, sizes=None):
        self.xs = xs or []
        self.opens = opens or []
        self.highs = highs or []
        self.lows = lows or []
        self.closes = closes or []
        self.volumes = volumes or []
        self.sizes = sizes or []

    @property
    def length(self):
        return len(self.closes)

    def sma(self, period):
        """Basit hareketli ortalama (close uzerinde)."""
        return Indicators.sma(self.closes, period)

    def ema(self, period):
        """Ustel hareketli ortalama (close uzerinde)."""
        return Indicators.ema(self.closes, period)

    def rsi(self, period=14):
        """RSI (close uzerinde)."""
        return Indicators.rsi(self.closes, period)

    def macd(self, fast=12, slow=26, signal=9):
        """MACD -> (macdLine, signalLine, histogram) (close uzerinde)."""
        return Indicators.macd(self.closes, fast, slow, signal)

    def stochastic(self, kPeriod=14, dPeriod=3):
        """Stochastic -> (%K, %D) (high/low/close uzerinde)."""
        return Indicators.stochastic(self.highs, self.lows, self.closes,
                                     kPeriod, dPeriod)
