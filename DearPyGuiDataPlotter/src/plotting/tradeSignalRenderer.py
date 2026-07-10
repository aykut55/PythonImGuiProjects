import numpy as np
import dearpygui.dearpygui as dpg

from .panelData import _decimateOhlc


class _DeprecatedTradeSignalRenderer:
    """Bir OHLC panelinin uzerine AL/SAT/FLAT trade sinyallerine gore GORSEL
    bir overlay cizer - PanelManager'in candle/line/bar cizim mantigina
    (drawPanelData/_drawOrUpdateSeries/LOD) DOKUNMAZ, sadece TUKETIR (panel/
    axis tag'lerini panelManager uzerinden okur). Ayri bir class olmasinin
    sebebi: bu is TAMAMEN trade-sinyali/gorsellestirme domain'i, PanelManager
    zaten 1900+ satir - candle/line/bar/LOD genel-amacli cizim altyapisini
    sinyal-ozel bir yorumla KIRLETMEMEK icin RangeSliderBar/PanelManagerWindow
    gibi kendi basina, PanelManager'a bagimli ama ondan BAGIMSIZ bir class.

    3 bagimsiz gorsel katman (flag'lerle acilir/kapanir):
      1) colorBars: candle'lar sinyal DURUMUNA (AL/SAT/FLAT) gore boyanir.
         DPG'nin add_candle_series'i PER-BAR ozel renk desteklemiyor (sadece
         tum seri icin tek bull_color/bear_color) - bu yuzden veri, AYNI
         sinyal durumunda kalan ardisik bar araliklarina ('run') bolunup HER
         run AYRI bir candle_series olarak (bull_color=bear_color=durum
         rengi) cizilir. Orijinal (PanelManager'in yonettigi) tekil candle
         serisi bu sirada GIZLENIR (silinmez - colorBars kapatilinca geri
         gosterilir, LOD guncellemeye devam eder).
      2) showSignals: her sinyal barinda kucuk bir harf (A/S/F) - bkz.
         dpg.add_plot_annotation.
      3) showLevelLines: AL barinin LOW'undan, SAT barinin HIGH'indan
         baslayip bir SONRAKI sinyale kadar uzanan yatay bir seviye cizgisi
         (2 noktali line_series) - FLAT'ta cizgi YOK.

    Runs (state degisim NOKTALARI) TEK SEFERLIK, TAM veri uzerinde hesaplanir
    - draw() script'ten (fillPanels sonrasi) bir kere cagrilmasi beklenir,
    updateLod gibi HER FRAME calisan bir mekanizma DEGILDIR. Cok BUYUK
    (RUN_LOD_MAX_POINTS'i asan) tek bir run'in OHLC'si de panelData.
    _decimateOhlc ile ana LOD sistemindeki AYNI algoritmayla kucultulur.

    LEGEND SORUNU (COZULEMEDI - bkz. setOhlcVisible): Her run AYRI bir
    candle_series oldugu icin legend'de HEPSINE ayni ismi versek (data.name)
    TEKRARLI satirlar gorunurdu - bu yuzden SADECE SON run etiketlenir (bkz.
    _drawColoredRuns). Ama bu da demek ki kullanici legend'deki o TEK satira
    tiklayinca ImPlot SADECE o segmenti gizler/gosterir, DIGER run'lar
    ETKILENMEZ - bunu Python'dan SENKRONIZE ETMENIN bir yolu YOK: dpg.
    get_item_state() candle_series icin SADECE {'ok','pos'} donduruyor,
    legend-tiklamasini yakalayabilecek dpg.is_item_shown (statik configure_
    item degerini okuyor, degismiyor) VE dpg.is_item_visible (candle_series
    turunde KeyError - desteklenmiyor) İKİSİ DE DENENIP calismadigi
    DOGRULANDI - bu bir DPG API SINIRI. Bunun yerine setOhlcVisible/
    toggleOhlcVisible ile ACIKCA (script/console veya baglanacak bir
    checkbox'tan) TUM grubu birden gizleyip/gosterebilirsiniz."""

    LETTER_BY_SIGNAL = {"AL": "A", "SAT": "S", "FLAT": "F"}
    COLOR_BY_SIGNAL = {
        "AL": (40, 200, 90, 255),
        "SAT": (220, 70, 70, 255),
        "FLAT": (220, 220, 220, 255),
    }
    RUN_LOD_MAX_POINTS = 2000  # tek bir run bu kadar bar'i asarsa decimate edilir (bkz. sinif docstring'i)
    MAX_SIGNAL_EVENTS = 20000  # bundan FAZLA sinyal olayi varsa harf/cizgi sayisi asiri buyumesin diye ciziLMEZ (bar boyama yine calisir, konsola UYARI basilir - bkz. draw()) - cok sik sinyal ureten veri setlerinde guvenlik supabi

    def __init__(self, panelManager):
        self._panelManager = panelManager
        self._createdTags = {}  # {(panelId, dataId): [tag, ...]} - bkz. _clear
        self._lastTarget = None  # (panelId, dataId) - en son draw() cagrisinin hedefi, bkz. setActiveOhlcVisible
        self._visible = {}  # {(panelId, dataId): bool}

    def draw(self, panelId, dataId, signals, showSignals=True, showLevelLines=True, colorBars=True):
        """panelId'deki panelin dataId'li (OHLC) serisine signals (data ile
        AYNI uzunlukta, sinyal olmayan barlarda None/"" olan liste, bkz.
        App.generateTradeSignals) listesine gore overlay cizer. Tekrar
        cagrilabilir - onceki cizimler ONCE temizlenir."""
        self._lastTarget = (panelId, dataId)
        panel = self._panelManager.getPanel(panelId)
        data = panel.getData(dataId) if panel is not None else None
        if panel is None or data is None or data.dataType != "candle":
            return
        yTag = f"y_axis_{panelId}"
        plotTag = f"plot_{panelId}"
        if not dpg.does_item_exist(yTag) or not dpg.does_item_exist(plotTag):
            return

        self._clear(panelId, dataId)
        originalTag = f"candle_{panelId}_{dataId}"

        n = min(len(signals), len(data.xs))
        if n == 0:
            return
        runs = self._computeRuns(signals, n)

        if colorBars:
            if dpg.does_item_exist(originalTag):
                dpg.configure_item(originalTag, show=False)
            self._drawColoredRuns(panelId, dataId, data, runs, yTag)
        elif dpg.does_item_exist(originalTag):
            dpg.configure_item(originalTag, show=True)

        signalEvents = [i for i in range(n) if signals[i]]
        print(f"[TradeSignalRenderer] panel={panelId} data={dataId}: "
              f"{len(signalEvents)} sinyal olayi, {len(runs)} run")
        if len(signalEvents) > self.MAX_SIGNAL_EVENTS:
            print(f"[TradeSignalRenderer] UYARI: {len(signalEvents)} sinyal "
                  f"MAX_SIGNAL_EVENTS ({self.MAX_SIGNAL_EVENTS})'i asiyor - "
                  f"harf/cizgi cizilmiyor (bar boyama calismaya devam ediyor).")
            self.setOhlcVisible(panelId, dataId, self._visible.get((panelId, dataId), True))
            return

        if showSignals:
            self._drawSignalLetters(panelId, dataId, data, signals, signalEvents, plotTag)
        if showLevelLines:
            self._drawLevelLines(panelId, dataId, data, runs, n, yTag)
        self.setOhlcVisible(panelId, dataId, self._visible.get((panelId, dataId), True))

    def _computeRuns(self, signals, n):
        """signals[0..n)'i, AYNI durumda kalan ardisik [start, end) bar
        araliklarina ('run') boler. Bir run, kendi ILK bar'inda (sinyalin
        ATESLENDIGI bar) BASLAR, bir SONRAKI sinyal bar'ina KADAR (haric)
        surer. Ilk sinyalden ONCEKI barlar (henuz hic sinyal gelmemis
        prefix) 'run' SAYILMAZ - None state ile ayri dondurulur, bar boyama
        bu prefix'i orijinal (varsayilan yon-bazli) renklerle cizer."""
        runs = []
        currentState = None
        runStart = 0
        for i in range(n):
            s = signals[i]
            if s:
                if currentState is not None:
                    runs.append((currentState, runStart, i))
                elif runStart < i:
                    runs.append((None, runStart, i))  # ilk sinyalden ONCEKI prefix
                currentState = s
                runStart = i
        if runStart < n:
            runs.append((currentState, runStart, n))
        return runs

    def _drawColoredRuns(self, panelId, dataId, data, runs, yTag):
        """Her run KENDI candle_series'i oldugu icin (bkz. sinif docstring'i)
        HEPSINE orijinal serinin adini (data.name) etiket versek legend'de
        AYNI isim kadar run sayisi kadar TEKRARLI satir gorunurdu - bu yuzden
        SADECE SON run (en GUNCEL/aktif segment) etiketlenir, digerleri
        use_internal_label=False + label='' ile legend'e HIC girmez.

        Segmentler y_axis sonuna eklenir. Orijinal candle_series colorBars
        acikken gizli tutuldugu icin ayni anda iki OHLC gorseli gorunmez."""
        lastIdx = len(runs) - 1
        for idx, (state, start, end) in enumerate(runs):
            xs = data.xs[start:end]
            opens = data.open[start:end]
            highs = data.high[start:end]
            lows = data.low[start:end]
            closes = data.close[start:end]
            if len(xs) > self.RUN_LOD_MAX_POINTS:
                xs, opens, highs, lows, closes = _decimateOhlc(
                    np.asarray(xs, dtype=np.float64), np.asarray(opens, dtype=np.float64),
                    np.asarray(highs, dtype=np.float64), np.asarray(lows, dtype=np.float64),
                    np.asarray(closes, dtype=np.float64), self.RUN_LOD_MAX_POINTS)
            tag = f"tradesignal_candle_{panelId}_{dataId}_{idx}"
            color = self.COLOR_BY_SIGNAL.get(state)
            kwargs = {"bull_color": color, "bear_color": color} if color is not None else {}
            if idx == lastIdx:
                kwargs["label"] = data.name
            else:
                kwargs["label"] = ""
                kwargs["use_internal_label"] = False
            dpg.add_candle_series(xs, opens, closes, lows, highs, tag=tag,
                                  parent=yTag, tooltip=False, **kwargs)
            self._track(panelId, dataId, tag)

    def _drawSignalLetters(self, panelId, dataId, data, signals, signalEvents, plotTag):
        for i in signalEvents:
            s = signals[i]
            letter = self.LETTER_BY_SIGNAL.get(s, "?")
            color = self.COLOR_BY_SIGNAL.get(s, (255, 255, 255, 255))
            if s == "AL":
                anchorY, offsetPx = data.low[i], (0, 16)
            elif s == "SAT":
                anchorY, offsetPx = data.high[i], (0, -16)
            else:
                anchorY, offsetPx = data.close[i], (0, 0)
            tag = f"tradesignal_ann_{panelId}_{dataId}_{i}"
            dpg.add_plot_annotation(parent=plotTag, default_value=(data.xs[i], anchorY),
                                    label=letter, color=color, offset=offsetPx,
                                    clamped=False, tag=tag)
            self._track(panelId, dataId, tag)

    def _drawLevelLines(self, panelId, dataId, data, runs, n, yTag):
        for idx, (state, start, end) in enumerate(runs):
            if state not in ("AL", "SAT"):
                continue
            level = data.low[start] if state == "AL" else data.high[start]
            xEnd = data.xs[min(end - 1, n - 1)]
            tag = f"tradesignal_line_{panelId}_{dataId}_{idx}"
            dpg.add_line_series([data.xs[start], xEnd], [level, level],
                                tag=tag, parent=yTag)
            self._applyLineTheme(panelId, dataId, tag, self.COLOR_BY_SIGNAL[state])
            self._track(panelId, dataId, tag)

    def _applyLineTheme(self, panelId, dataId, tag, color):
        themeTag = f"{tag}_theme"
        with dpg.theme(tag=themeTag):
            with dpg.theme_component(dpg.mvLineSeries):
                dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
                dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 2.5, category=dpg.mvThemeCat_Plots)
        dpg.bind_item_theme(tag, themeTag)
        self._track(panelId, dataId, themeTag)

    def _track(self, panelId, dataId, tag):
        self._createdTags.setdefault((panelId, dataId), []).append(tag)

    def _clear(self, panelId, dataId):
        for tag in self._createdTags.pop((panelId, dataId), []):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)

    def clearAll(self):
        for key in list(self._createdTags.keys()):
            self._clear(*key)

    def setOhlcVisible(self, panelId, dataId, visible):
        """OHLC candle gorselini VE ONUNLA BIRLIKTE cizilen HER SEYI (harfler,
        seviye cizgileri) ACIKCA gosterir/gizler - colorBars acikken TUM run
        segmentlerini, kapaliyken orijinal tekil candle_series'i, artiHER
        ZAMAN _createdTags'te izlenen TUM overlay item'larini (tradesignal_
        candle_*, tradesignal_ann_* harfler, tradesignal_line_* seviye
        cizgileri) - candle'lar gizlenirken harf/cizgilerin ekranda YALNIZ
        kalmasi mantiksiz oldugu icin (kullanici bunu bildirdi) hepsi
        BIRLIKTE gizlenir/gosterilir. Tema tag'leri (_theme ile bitenler)
        atlanir - onlarin 'show' diye bir konfigurasyonu yok, sadece renk
        tasiyorlar.

        NEDEN BU METOD VAR: DPG'nin native plot legend'i, bir seriye
        tiklandiginda ImPlot'un o item'i gizlemesini SAGLAR ama bu durumu
        Python'a GERI YANSITMAZ - dpg.get_item_state() candle_series icin
        SADECE {'ok','pos'} donduruyor, 'visible'/'shown' gibi legend-
        tiklamasini izleyebilecek HICBIR alan YOK (bu ARAYUZ SINIRI iki
        farkli API denenip DOGRULANDI: dpg.is_item_shown SADECE bizim
        configure_item ile set ettigimiz STATIK degeri okuyor - legend
        tiklamasini yakalamiyor; dpg.is_item_visible ise candle_series
        turunde KeyError firlatiyor, desteklenmiyor). Yani legend'e tiklayip
        SADECE bir segmenti gizlemek hala mumkun ama bunu diger segmentlere
        YAYAMAYIZ - kullanicinin TUM grafigi gizlemek/gostermek icin bu
        metodu (bir script/console cagrisi veya baglanacak bir checkbox
        uzerinden) ACIKCA cagirmasi gerekiyor."""
        originalTag = f"candle_{panelId}_{dataId}"
        self._visible[(panelId, dataId)] = bool(visible)
        if dpg.does_item_exist(originalTag):
            hasColoredRuns = any(
                tag.startswith(f"tradesignal_candle_{panelId}_{dataId}_")
                for tag in self._createdTags.get((panelId, dataId), [])
            )
            dpg.configure_item(originalTag, show=bool(visible) and not hasColoredRuns)
        for tag in self._createdTags.get((panelId, dataId), []):
            if tag.endswith("_theme"):
                continue
            if dpg.does_item_exist(tag):
                dpg.configure_item(tag, show=visible)

    def toggleOhlcVisible(self, panelId, dataId):
        """setOhlcVisible'in tersine cevirme kolayligi - bkz. orada. Su anki
        durumu, run segmentleri VARSA ilkinden, yoksa orijinal candle
        serisinden okur."""
        prefix = f"tradesignal_candle_{panelId}_{dataId}_"
        candleTags = [t for t in self._createdTags.get((panelId, dataId), [])
                     if t.startswith(prefix)]
        refTag = candleTags[0] if candleTags else f"candle_{panelId}_{dataId}"
        current = dpg.get_item_configuration(refTag).get("show", True) \
            if dpg.does_item_exist(refTag) else True
        self.setOhlcVisible(panelId, dataId, not current)

    def setActiveOhlcVisible(self, visible):
        """setOhlcVisible'i EN SON draw() cagrisinin hedefine (panelId,
        dataId) uygular - GuiManager'daki 'Show OHLC' checkbox'i gibi, HANGI
        panel/data oldugunu bilmesi gerekmeyen genel bir UI kontrolunun
        baglanabilecegi kolaylik metodu."""
        if self._lastTarget is None:
            return
        panelId, dataId = self._lastTarget
        self.setOhlcVisible(panelId, dataId, visible)


# Authoritative implementation. The earlier class is kept only because this
# file existed as a debug notebook; this final definition is the one Python
# exports from the module.
class TradeSignalRenderer:
    """Draw trade-signal overlays for one OHLC series.

    Important design choice: colorBars=True does not try to hide the original
    candle series. DearPyGui/ImPlot can keep that native item visually alive in
    some cases, which caused duplicate original + colored candles. Instead the
    original candle item is deleted while colored runs are active. If colorBars
    is later disabled, the original series is rebuilt from PanelManager data.
    """

    LETTER_BY_SIGNAL = {"AL": "A", "SAT": "S", "FLAT": "F"}
    COLOR_BY_SIGNAL = {
        "AL": (40, 200, 90, 255),
        "SAT": (220, 70, 70, 255),
        "FLAT": (225, 225, 225, 255),
    }
    RUN_LOD_MAX_POINTS = 2000
    MAX_SIGNAL_EVENTS = 20000

    def __init__(self, panelManager):
        self._panelManager = panelManager
        self._createdTags = {}
        self._lastTarget = None
        self._visible = {}
        self._colorBarsActive = set()

    def draw(self, panelId, dataId, signals, showSignals=True, showLevelLines=True, colorBars=True):
        self._lastTarget = (panelId, dataId)
        panel, data = self._getPanelData(panelId, dataId)
        if data is None:
            return

        yTag = f"y_axis_{panelId}"
        plotTag = f"plot_{panelId}"
        if not dpg.does_item_exist(yTag) or not dpg.does_item_exist(plotTag):
            return

        self._clear(panelId, dataId)
        n = min(len(signals or []), len(data.xs), len(data.open), len(data.high),
                len(data.low), len(data.close))
        if n <= 0:
            self._restoreOriginal(panelId, dataId)
            return

        runs = self._computeRuns(signals, n)
        if colorBars:
            self._colorBarsActive.add((panelId, dataId))
            self._drawColoredRuns(panelId, dataId, data, runs, yTag)
            self._deleteOriginal(panelId, dataId)
        else:
            self._colorBarsActive.discard((panelId, dataId))
            self._restoreOriginal(panelId, dataId)

        signalEvents = [i for i in range(n) if signals[i]]
        if len(signalEvents) <= self.MAX_SIGNAL_EVENTS:
            if showSignals:
                self._drawSignalLetters(panelId, dataId, data, signals, signalEvents, plotTag)
            if showLevelLines:
                self._drawLevelLines(panelId, dataId, data, runs, n, yTag)
        else:
            print(f"[TradeSignalRenderer] {len(signalEvents)} signals; letters/lines skipped.")

        self.setOhlcVisible(panelId, dataId, self._visible.get((panelId, dataId), True))
        print(f"[TradeSignalRenderer] panel={panelId} data={dataId}: "
              f"{len(signalEvents)} signals, {len(runs)} runs, colorBars={colorBars}")

    def _getPanelData(self, panelId, dataId):
        panel = self._panelManager.getPanel(panelId)
        data = panel.getData(dataId) if panel is not None else None
        if data is None or data.dataType != "candle":
            return panel, None
        return panel, data

    def _originalTag(self, panelId, dataId):
        return f"candle_{panelId}_{dataId}"

    def _deleteOriginal(self, panelId, dataId):
        tag = self._originalTag(panelId, dataId)
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

    def _restoreOriginal(self, panelId, dataId):
        panel, data = self._getPanelData(panelId, dataId)
        yTag = f"y_axis_{panelId}"
        tag = self._originalTag(panelId, dataId)
        if data is None or not dpg.does_item_exist(yTag) or dpg.does_item_exist(tag):
            return
        xs = data.xs if data.xs else list(range(len(data.open)))
        if not xs:
            return
        xMin, xMax = float(xs[0]), float(xs[-1])
        self._panelManager._drawOrUpdateSeries(panelId, data, xMin, xMax, yTag=yTag)

    def _computeRuns(self, signals, n):
        runs = []
        currentState = None
        runStart = 0
        for i in range(n):
            state = signals[i]
            if not state:
                continue
            if currentState is not None:
                runs.append((currentState, runStart, i))
            elif runStart < i:
                runs.append((None, runStart, i))
            currentState = state
            runStart = i
        if runStart < n:
            runs.append((currentState, runStart, n))
        return runs

    def _drawColoredRuns(self, panelId, dataId, data, runs, yTag):
        beforeTag = self._firstSeriesTagAfter(panelId, dataId)
        grouped = self._groupRunBarsByState(data, runs)
        for idx, state in enumerate(("AL", "SAT", "FLAT", None)):
            values = grouped.get(state)
            if not values:
                continue
            xs, opens, highs, lows, closes = values
            if not xs:
                continue

            tag = f"tradesignal_candle_{panelId}_{dataId}_{idx}"
            color = self.COLOR_BY_SIGNAL.get(state)
            kwargs = {"bull_color": color, "bear_color": color} if color else {}
            kwargs["label"] = ""
            kwargs["use_internal_label"] = False
            addKwargs = {"tag": tag, "parent": yTag, "tooltip": False, **kwargs}
            if beforeTag is not None and dpg.does_item_exist(beforeTag):
                addKwargs["before"] = beforeTag
            dpg.add_candle_series(xs, opens, closes, lows, highs, **addKwargs)
            self._track(panelId, dataId, tag)

    def _drawColoredRuns_old(self, panelId, dataId, data, runs, yTag):
        beforeTag = self._firstSeriesTagAfter(panelId, dataId)
        for idx, (state, start, end) in enumerate(runs):
            if end <= start:
                continue
            xs = data.xs[start:end]
            opens = data.open[start:end]
            highs = data.high[start:end]
            lows = data.low[start:end]
            closes = data.close[start:end]
            if len(xs) > self.RUN_LOD_MAX_POINTS:
                xs, opens, highs, lows, closes = _decimateOhlc(
                    np.asarray(xs, dtype=np.float64),
                    np.asarray(opens, dtype=np.float64),
                    np.asarray(highs, dtype=np.float64),
                    np.asarray(lows, dtype=np.float64),
                    np.asarray(closes, dtype=np.float64),
                    self.RUN_LOD_MAX_POINTS,
                )

            tag = f"tradesignal_candle_{panelId}_{dataId}_{idx}"
            color = self.COLOR_BY_SIGNAL.get(state)
            kwargs = {"bull_color": color, "bear_color": color} if color else {}
            kwargs["label"] = ""
            kwargs["use_internal_label"] = False
            addKwargs = {"tag": tag, "parent": yTag, "tooltip": False, **kwargs}
            if beforeTag is not None and dpg.does_item_exist(beforeTag):
                addKwargs["before"] = beforeTag
            dpg.add_candle_series(xs, opens, closes, lows, highs, **addKwargs)
            self._track(panelId, dataId, tag)

    def _groupRunBarsByState(self, data, runs):
        grouped = {}
        for state, start, end in runs:
            if end <= start:
                continue
            bucket = grouped.setdefault(state, ([], [], [], [], []))
            xs, opens, highs, lows, closes = bucket
            runXs = data.xs[start:end]
            runOpens = data.open[start:end]
            runHighs = data.high[start:end]
            runLows = data.low[start:end]
            runCloses = data.close[start:end]
            if len(runXs) > self.RUN_LOD_MAX_POINTS:
                runXs, runOpens, runHighs, runLows, runCloses = _decimateOhlc(
                    np.asarray(runXs, dtype=np.float64),
                    np.asarray(runOpens, dtype=np.float64),
                    np.asarray(runHighs, dtype=np.float64),
                    np.asarray(runLows, dtype=np.float64),
                    np.asarray(runCloses, dtype=np.float64),
                    self.RUN_LOD_MAX_POINTS,
                )
            xs.extend(runXs)
            opens.extend(runOpens)
            highs.extend(runHighs)
            lows.extend(runLows)
            closes.extend(runCloses)
        return grouped

    def _firstSeriesTagAfter(self, panelId, dataId):
        panel = self._panelManager.getPanel(panelId)
        if panel is None:
            return None
        seenTarget = False
        for item in panel.dataList:
            if item.id == dataId:
                seenTarget = True
                continue
            if not seenTarget or not item.isVisible:
                continue
            tag = self._panelManager._seriesTag(panelId, item)
            if dpg.does_item_exist(tag):
                return tag
        return None

    def _drawSignalLetters(self, panelId, dataId, data, signals, signalEvents, plotTag):
        for i in signalEvents:
            state = signals[i]
            if state == "AL":
                y, offset = data.low[i], (0, 16)
            elif state == "SAT":
                y, offset = data.high[i], (0, -16)
            else:
                y, offset = data.close[i], (0, 0)
            tag = f"tradesignal_ann_{panelId}_{dataId}_{i}"
            dpg.add_plot_annotation(
                parent=plotTag,
                default_value=(data.xs[i], y),
                label=self.LETTER_BY_SIGNAL.get(state, "?"),
                color=self.COLOR_BY_SIGNAL.get(state, (255, 255, 255, 255)),
                offset=offset,
                clamped=False,
                tag=tag,
            )
            self._track(panelId, dataId, tag)

    def _drawLevelLines(self, panelId, dataId, data, runs, n, yTag):
        grouped = {"AL": ([], []), "SAT": ([], [])}
        for state, start, end in runs:
            if state not in ("AL", "SAT") or end <= start:
                continue
            level = data.low[start] if state == "AL" else data.high[start]
            xEnd = data.xs[min(end - 1, n - 1)]
            xs, ys = grouped[state]
            xs.extend([data.xs[start], xEnd, float("nan")])
            ys.extend([level, level, float("nan")])

        for state, (xs, ys) in grouped.items():
            if not xs:
                continue
            tag = f"tradesignal_line_{panelId}_{dataId}_{state.lower()}"
            dpg.add_line_series(xs, ys, tag=tag, parent=yTag)
            self._applyLineTheme(panelId, dataId, tag, self.COLOR_BY_SIGNAL[state])
            self._track(panelId, dataId, tag)

    def _applyLineTheme(self, panelId, dataId, tag, color):
        themeTag = f"{tag}_theme"
        with dpg.theme(tag=themeTag):
            with dpg.theme_component(dpg.mvLineSeries):
                dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
                dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 2.5, category=dpg.mvThemeCat_Plots)
        dpg.bind_item_theme(tag, themeTag)
        self._track(panelId, dataId, themeTag)

    def _track(self, panelId, dataId, tag):
        self._createdTags.setdefault((panelId, dataId), []).append(tag)

    def _clear(self, panelId, dataId):
        for tag in self._createdTags.pop((panelId, dataId), []):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)

    def clearAll(self):
        for panelId, dataId in list(self._createdTags.keys()):
            self._clear(panelId, dataId)
            self._restoreOriginal(panelId, dataId)
        self._colorBarsActive.clear()

    def setOhlcVisible(self, panelId, dataId, visible):
        visible = bool(visible)
        self._visible[(panelId, dataId)] = visible

        originalTag = self._originalTag(panelId, dataId)
        if dpg.does_item_exist(originalTag):
            dpg.configure_item(originalTag, show=visible)

        for tag in self._createdTags.get((panelId, dataId), []):
            if tag.endswith("_theme"):
                continue
            if dpg.does_item_exist(tag):
                dpg.configure_item(tag, show=visible)

    def toggleOhlcVisible(self, panelId, dataId):
        self.setOhlcVisible(panelId, dataId, not self._visible.get((panelId, dataId), True))

    def setActiveOhlcVisible(self, visible):
        if self._lastTarget is None:
            return
        self.setOhlcVisible(*self._lastTarget, visible)
