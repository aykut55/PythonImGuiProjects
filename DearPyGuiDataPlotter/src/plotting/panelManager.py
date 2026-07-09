import math
import time

import dearpygui.dearpygui as dpg

from .panel import Panel


class PanelManager:
    COLLAPSED_PANEL_HEIGHT = 30  # collapseAllPanels'in kuculttugu sabit yukseklik (bkz. expandAllPanels)

    def __init__(self):
        self._panels = {}
        self._nextId = 0
        self._panelOrder = []  # GORUNUM sirasi (Panel Order kontrolleriyle degistirilebilir; olusturulma sirasindan bagimsiz, bkz. swapPanelUp/Down/resetPanelOrder)
        self._container = None  # panellerin cizilecegi DPG container tag'i (bkz. setContainer)
        self._drawnPanelIds = set()  # drawPanel ile UI'si kurulmus panel id'leri (bkz. sync)
        self._lastRenderPrint = 0.0  # render() heartbeat print throttle (bkz. render)
        self._xAxisMode = "bar"  # "bar" (varsayilan, ham bar no) | "datetime" (bkz. setXAxisMode)
        self._dateTimeFormat = None  # datetime modunda strftime deseni (None -> isIntraday'e gore otomatik, bkz. setXAxisMode)
        self._lastAxisTicksSignature = {}  # {panelId: hesaplanan ticks tuple'i} - gereksiz set_axis_ticks cagrisini (flicker sebebi) onlemek icin
        self._minTickStep = 7  # datetime modunda etiketler en az kac barda bir ("5-10 barda bir", ortasi)
        self._maxTicksOnScreen = 40  # ust sinir (guvenlik/performans) - genelde asil sinirlayici _maxTicksForWidth
        self._axisCharPxWidth = 9  # datetime etiketindeki karakter basina kabaca piksel genislik tahmini
        self._axisTickPadding = 24  # iki etiket arasi minimum bosluk (piksel) - DPG'nin kendi fontunu olcemedigimiz icin guvenli/muhafazakar tahmin
        self._dayChangeFormat = "%d.%m.%Y\n%H:%M:%S"  # saat-bazli (tarihsiz) formatlarda gun degisen bar'a ozel format (bkz. _buildDatetimeTicks)
        self._dayBoundaryScanCap = 5000  # gun degisimi taramasi (O(bar)) bu barsInRange'i asarsa YAPILMAZ - performans/guvenlik
        self._dayChangeMarkersEnabled = False  # gun degisimini x eksende AYRICA isaretleme (kod hazir, gorunumu karistirdigi icin simdilik KAPALI - bkz. _buildDatetimeTicks)
        self._debugAxisTicks = False  # True ise DPG'ye gonderilen (label, bar_no) tick'leri konsola basar (bkz. setDebugAxisTicks) - ekrandaki ile karsilastirip dogrulamak icin
        self._infoPanelMode = "always"  # hidden | hover | active | always (bkz. setInfoPanelMode)
        self._infoActivePanelId = None  # "active" modunda hangi panelin hover_text'i gosterilecek (bkz. setActiveInfoPanel)
        self._infoLastIndex = {}  # {panelId: son cozulen index} - mouse panelden cikinca son degeri korur
        self._infoSharedIndex = None  # "always"/"active" modunda TUM panellerin ortak gosterecegi index (bir plot'un uzerine gelince paylasilir)
        self._crossHairMode = "all"  # hidden | single | all - varsayilan "all": infoPanel gibi TUM panellerde surekli (bkz. setCrossHairMode)
        self._crossHairPersist = True  # varsayilan True: mouse plot'tan cikinca crosshair SON pozisyonda kalir, gizlenmez - infoPanel'in "always" modu gibi surekli gorunur (bkz. setCrossHairPersist)
        self._crossHairLastPos = None  # (kaynakPanelId, x, y) - persist ve "all" modunun paylastigi son bilinen konum
        self._activeUpdateMode = "hover"  # hover | click - "aktif panel" hangi etkilesimle degisecek (bkz. setActiveUpdateMode)
        self._activePanelId = None  # su an "aktif" sayilan panelin id'si (bkz. updateActivePanel/_onPlotClicked)
        self._interactionManager = None  # bkz. setInteractionManager (guiManager tarafindan baglanir)
        self._lastReadPlotParams = None  # Read Params (src) ile yakalanan son kaynak plot/eksen durumu

    def setInteractionManager(self, interactionManager):
        self._interactionManager = interactionManager

    def createPanel(self, name, caption="", parent="", alignment=None):
        """Otomatik id ile YALNIZCA bir Panel olusturur, DONDURUR - panelManager'a
        EKLEMEZ (kayit icin addPanel(panel) gerekir; iki adim ayri tutuluyor)."""
        panelId = self._nextId
        self._nextId += 1
        return Panel(panelId, name, caption, parent, alignment)

    def addPanel(self, panel):
        """Bir paneli (createPanel'den gelen ya da dogrudan Panel(...) ile
        kurulmus) panelManager'a kaydeder. Ileride id catismasini onlemek
        icin _nextId'i panel.id'nin onune gecirir. panel._manager'i buraya
        baglar ki panel.draw()/drawData()/sync()/render() calisabilsin.
        _panelOrder'in sonuna eklenir (gorunum sirasi = ekleme sirasi,
        Panel Order kontrolleriyle sonradan degistirilebilir)."""
        self._panels[panel.id] = panel
        panel._manager = self
        if panel.id >= self._nextId:
            self._nextId = panel.id + 1
        if panel.id not in self._panelOrder:
            self._panelOrder.append(panel.id)
        return panel

    def getPanel(self, panelId):
        return self._panels.get(panelId)

    def getPanelId(self, name):
        """Panel ismiyle arayip id dondurur (yoksa None). Panel objesi zaten
        elindeyse buna gerek yok, dogrudan panel.id kullan.
        Ornek: pm.getPanelId("OHLC")."""
        panel = self.findPanel(name)
        return panel.id if panel else None

    def findPanel(self, key):
        """Esnek panel arama: int ise id ile, str ise isim ile. Bulamazsa None."""
        if isinstance(key, str):
            return next((p for p in self._panels.values() if p.name == key), None)
        return self._panels.get(key)

    def deletePanel(self, panelId):
        """Bir paneli modelden siler + _panelOrder'dan cikarir (cizili
        panel_{id} child_window'u varsa sync() bir sonraki cagrisinda
        yetim UI olarak temizler, bkz. sync())."""
        panel = self._panels.get(panelId)
        if panel is None:
            return
        panel.deleteAllData()
        del self._panels[panelId]
        if panelId in self._panelOrder:
            self._panelOrder.remove(panelId)
        if self._interactionManager is not None:
            self._interactionManager.unregisterPanel(panelId)

    def removePanel(self, panelId):
        """deletePanel ile ayni (isim tercihi icin ikinci ad)."""
        self.deletePanel(panelId)

    def getAllPanels(self):
        return list(self._panels.values())

    def iterateAllPanels(self):
        for panel in self._panels.values():
            yield panel

    def deleteAllPanels(self):
        """Modeldeki TUM panelleri (+ _panelOrder'i) temizler. Cizili
        panel_{id} child_window'lari sync() bir sonraki cagrisinda yetim
        UI olarak temizlenir."""
        for panel in self._panels.values():
            panel.deleteAllData()
        if self._interactionManager is not None:
            for panelId in self._panels.keys():
                self._interactionManager.unregisterPanel(panelId)
        self._panels.clear()
        self._panelOrder.clear()
        self._nextId = 0

    # -------------------------------------------------------- panel sirasi
    def getPanelOrder(self):
        """Panellerin GUNCEL gorunum sirasini (id listesi) dondurur."""
        return list(self._panelOrder)

    def swapPanelUp(self, panelId):
        """panelId'yi gorunum sirasinda bir yukari (bir onceki index'e) tasir."""
        if panelId not in self._panelOrder:
            return
        idx = self._panelOrder.index(panelId)
        if idx > 0:
            self._panelOrder[idx], self._panelOrder[idx - 1] = \
                self._panelOrder[idx - 1], self._panelOrder[idx]

    def swapPanelDown(self, panelId):
        """panelId'yi gorunum sirasinda bir asagi tasir."""
        if panelId not in self._panelOrder:
            return
        idx = self._panelOrder.index(panelId)
        if idx < len(self._panelOrder) - 1:
            self._panelOrder[idx], self._panelOrder[idx + 1] = \
                self._panelOrder[idx + 1], self._panelOrder[idx]

    def applyPanelOrder(self):
        """_panelOrder'daki sirayla panel_{id} child_window'larini
        setContainer ile verilen container icinde yeniden diziyor
        (dpg.move_item varsayilan olarak container'in EN SONUNA tasir;
        sirayla tekrarlaninca istenen sira olusur). Container/en az 2
        panel yoksa no-op."""
        if not self._container or len(self._panelOrder) < 2:
            return
        for panelId in self._panelOrder:
            tag = f"panel_{panelId}"
            if dpg.does_item_exist(tag):
                dpg.move_item(tag, parent=self._container)

    def resetPanelOrder(self):
        """Gorunum sirasini panellerin OLUSTURULMA (ekleme) sirasina
        dondurup uygular."""
        self._panelOrder = list(self._panels.keys())
        self.applyPanelOrder()

    # ----------------------------------------------------------------- cizim
    def setContainer(self, tag):
        """Panellerin cizilecegi DPG container'inin tag'ini ayarlar (or.
        guiManager'daki 'centerPanel')."""
        self._container = tag

    def getContainer(self):
        return self._container

    def drawPanel(self, panelId):
        """Tek bir paneli (id ile) cizer - (bos) plot UI'sini kurar. Veriyi
        CIZMEZ (bkz. drawPanelData). Toplu cizim icin script kendi dongusunu
        kurar: `for p in pm.iterateAllPanels(): pm.drawPanel(p.id)`
        (bilerek 'drawPanels' gibi coklu-eylem metodu YOK - API tekil
        eylemlerden olusuyor, coklu islemi script kendisi orgutler)."""
        panel = self._panels.get(panelId)
        if panel is None:
            return
        self._buildPanelUi(panel)
        self._drawnPanelIds.add(panelId)
        if self._interactionManager is not None:
            self._interactionManager.registerPanel(
                panelId, f"plot_{panelId}", f"x_axis_{panelId}", f"y_axis_{panelId}")

    def drawPanelData(self, panelId):
        """Panelin dataList'indeki (candle/bar/line) serilerini + levels
        (hline/vline) cizgilerini plot'a basar. Tekrar cagrilabilir (once
        y_axis'in tum eski cizimlerini siler). Zaman ekseni tick'leri/LOD
        YOK - ham veriyle cizer. drawPanel'den SONRA cagrilmali (once kabuk
        kurulmali: panel_{id}/y_axis_{id} var olmali)."""
        panel = self._panels.get(panelId)
        yTag = f"y_axis_{panelId}"
        if panel is None or not dpg.does_item_exist(yTag):
            return
        dpg.delete_item(yTag, children_only=True)
        for d in panel.dataList:
            if not d.isVisible:
                continue
            if d.dataType == "candle" and d.open and d.high and d.low and d.close:
                xs = d.xs if d.xs else list(range(len(d.open)))
                dpg.add_candle_series(xs, d.open, d.close, d.low, d.high, label=d.name,
                                      tag=f"candle_{panelId}_{d.id}",
                                      parent=yTag, tooltip=False)
            elif d.dataType == "bar" and d.volume:
                xs = d.xs if d.xs else list(range(len(d.volume)))
                dpg.add_bar_series(xs, d.volume, label=f"{d.name} Vol",
                                   tag=f"bar_{panelId}_{d.id}", parent=yTag)
            else:
                dpg.add_line_series(d.xs, d.ys, label=d.name,
                                    tag=f"line_{panelId}_{d.id}", parent=yTag)
        self._drawLevels(panelId, panel)
        self._applyAxisPadding(panelId, panel)
        self.updateXAxisTicks(panelId)

    def _applyAxisPadding(self, panelId, panel,
                         xMarginRatio=0.02, yMarginRatio=0.08):
        """Panelin GORUNUR TUM datalarindan x/y eksen limitlerini hesaplayip
        (min-max araligina bir pay ekleyerek) dpg.set_axis_limits ile
        uygular - boylece ilk/son bar ya da en yuksek/dusuk deger plot
        cercevesine YAPISMAZ (panellerin kendi aralarinda birakilan bosluk
        gibi, verinin de kenarlardan biraz payi olsun istendi). Gorunur
        data yoksa (hepsi silinmis/gizlenmis) kilit kaldirilir
        (set_axis_limits_auto) ki eksen eski/bayat bir araliga KILITLI
        KALMASIN.

        NOT: dpg.set_axis_limits çağrısı DPG'de ekseni pan/zoom'a KAPALI hale
        getirip o araliga KILITLER (set_axis_limits_auto cagrilana kadar).
        Sadece bir kerelik "guzel cerceveleme" istedigimiz icin (kilitli
        kalsin istemiyoruz), limit BIR FRAME uygulanip dpg.split_frame() ile
        beklenir, sonra set_axis_limits_auto ile kilit hemen kaldirilir -
        kullanici o andan itibaren serbestce zoom/pan yapabilir. Bir sonraki
        drawPanelData (veri degisikligi/hide-show/order) cagrisinda görünüm
        yeniden bu dolgulu hale doner."""
        xTag = f"x_axis_{panelId}"
        yTag = f"y_axis_{panelId}"
        if not dpg.does_item_exist(xTag) or not dpg.does_item_exist(yTag):
            return

        xMin = xMax = yMin = yMax = None
        for d in panel.dataList:
            if not d.isVisible:
                continue
            xs = d.xs if d.xs else (list(range(len(d.open))) if d.open else None)
            if xs:
                xMin = xs[0] if xMin is None else min(xMin, xs[0])
                xMax = xs[-1] if xMax is None else max(xMax, xs[-1])
            if d.dataCount:
                yMin = d.minY if yMin is None else min(yMin, d.minY)
                yMax = d.maxY if yMax is None else max(yMax, d.maxY)

        appliedX = False
        if xMin is None or xMax is None:
            dpg.set_axis_limits_auto(xTag)
        else:
            xPad = max(1.0, (xMax - xMin) * xMarginRatio)
            dpg.set_axis_limits(xTag, xMin - xPad, xMax + xPad)
            appliedX = True

        appliedY = False
        if yMin is None or yMax is None:
            dpg.set_axis_limits_auto(yTag)
        else:
            yRange = yMax - yMin
            yPad = yRange * yMarginRatio if yRange > 0 else max(1.0, abs(yMax) * yMarginRatio)
            dpg.set_axis_limits(yTag, yMin - yPad, yMax + yPad)
            appliedY = True

        if appliedX or appliedY:
            dpg.split_frame()
            if appliedX:
                dpg.set_axis_limits_auto(xTag)
            if appliedY:
                dpg.set_axis_limits_auto(yTag)

    def _drawLevels(self, panelId, panel):
        """panel.levels'daki yatay/dikey seviye cizgilerini inf_line_series
        ile cizer (legend'da gorunur sonsuz cizgi). y_axis'e baglidir, o
        yuzden drawPanelData'nin y_axis temizligiyle birlikte yeniden cizilir."""
        yTag = f"y_axis_{panelId}"
        if not dpg.does_item_exist(yTag):
            return
        for i, lvl in enumerate(panel.levels):
            tag = f"level_{panelId}_{i}"
            v = lvl["value"]
            label = lvl["label"] or (str(int(v)) if v == int(v) else str(v))
            series = dpg.add_inf_line_series(
                [v], horizontal=(not lvl["vertical"]), label=label,
                tag=tag, parent=yTag)
            color = lvl.get("color")
            if color:
                themeTag = f"{tag}_theme"
                if dpg.does_item_exist(themeTag):
                    dpg.delete_item(themeTag)
                with dpg.theme(tag=themeTag):
                    with dpg.theme_component(dpg.mvInfLineSeries):
                        dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
                        if lvl.get("thickness"):
                            dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight,
                                                float(lvl["thickness"]), category=dpg.mvThemeCat_Plots)
                dpg.bind_item_theme(series, themeTag)

    # ---------------------------------------------------------- y adjust
    def adjustYAxis(self, panelId=None, yMarginRatio=0.08, xLimits=None):
        """Verilen panelin mevcut gorunur X araligindaki visible datalarina gore
        Y eksen limitini gunceller. X eksenine dokunmaz."""
        panelId = self.getActivePanelId() if panelId is None else panelId
        panel = self._panels.get(panelId)
        yTag = f"y_axis_{panelId}"
        if panel is None or not dpg.does_item_exist(yTag):
            return False

        yRange = self._visibleYRangeForPanel(panelId, xLimits=xLimits)
        if yRange is None:
            dpg.fit_axis_data(yTag)
            return True

        yMin, yMax = yRange
        ySpan = yMax - yMin
        yPad = ySpan * yMarginRatio if ySpan > 0 else max(1.0, abs(yMax) * yMarginRatio)
        dpg.set_axis_limits(yTag, yMin - yPad, yMax + yPad)
        dpg.split_frame()
        dpg.set_axis_limits_auto(yTag)
        return True

    def adjustAllYAxes(self, yMarginRatio=0.08):
        """Tum gorunur panellerde adjustYAxis uygular. Donen deger: basarili
        adjust edilen panel sayisi."""
        count = 0
        for panel in self._panels.values():
            if not panel.getVisible():
                continue
            if self.adjustYAxis(panel.id, yMarginRatio=yMarginRatio):
                count += 1
        return count

    def resetPanelView(self, panelId=None, xMarginRatio=0.02, yMarginRatio=0.08):
        """Paneli native fit davranisiyla full-data gorunumune resetler."""
        panelId = self.getActivePanelId() if panelId is None else panelId
        panel = self._panels.get(panelId)
        xTag = f"x_axis_{panelId}"
        yTag = f"y_axis_{panelId}"
        if panel is None or not dpg.does_item_exist(xTag) or not dpg.does_item_exist(yTag):
            return False

        dpg.fit_axis_data(xTag)
        dpg.fit_axis_data(yTag)
        return True

    def resetAllPanelViews(self, xMarginRatio=0.02, yMarginRatio=0.08):
        """Tum gorunur panelleri full-data gorunumune resetler."""
        count = 0
        for panel in self._panels.values():
            if not panel.getVisible():
                continue
            if self.resetPanelView(panel.id, xMarginRatio=xMarginRatio,
                                   yMarginRatio=yMarginRatio):
                count += 1
        return count

    def readPanelPlotParams(self, panelId=None, plotId=None):
        """Aktif/kaynak panelin plot eksen parametrelerini okur ve hafizada tutar."""
        panelId = self.getActivePanelId() if panelId is None else panelId
        panel = self._panels.get(panelId)
        plotTag = plotId or f"plot_{panelId}"
        xTag = f"x_axis_{panelId}"
        yTag = f"y_axis_{panelId}"
        if panel is None or not dpg.does_item_exist(plotTag):
            return None

        params = {
            "panelId": panelId,
            "plotId": plotTag,
            "xAxis": xTag,
            "yAxis": yTag,
            "xAxisLimits": self._axisLimits(xTag),
            "yAxisLimits": self._axisLimits(yTag),
            "frame": dpg.get_frame_count(),
        }
        self._lastReadPlotParams = params
        return params

    def getLastReadPlotParams(self):
        return self._lastReadPlotParams

    def isPanelReadyForSourceParams(self, panelId):
        """Panel GUI tarafinda cizilip gorunur hale geldiyse True doner."""
        panel = self._panels.get(panelId)
        plotTag = f"plot_{panelId}"
        xTag = f"x_axis_{panelId}"
        yTag = f"y_axis_{panelId}"
        if panel is None or not panel.getVisible():
            return False
        if not (dpg.does_item_exist(plotTag)
                and dpg.does_item_exist(xTag)
                and dpg.does_item_exist(yTag)):
            return False
        try:
            return dpg.is_item_visible(plotTag)
        except (KeyError, SystemError, Exception):
            return False

    def applySourceParamsToPanel(self, panelId, params=None, yMarginRatio=0.08):
        """Kaynak plot parametrelerini hedef panele uygular.

        X araligi kaynakla aynilanir; Y ise hedef panelin o X araliginda
        gorunen kendi datalarina gore yeniden fit edilir.
        """
        params = params or self._lastReadPlotParams
        panel = self._panels.get(panelId)
        if panel is None or params is None:
            return False
        if panelId == params.get("panelId"):
            return True
        if not self.isPanelReadyForSourceParams(panelId):
            return False

        xLimits = params.get("xAxisLimits")
        xTag = f"x_axis_{panelId}"
        appliedX = False
        if xLimits is not None:
            dpg.set_axis_limits(xTag, xLimits[0], xLimits[1])
            appliedX = True
        self.adjustYAxis(panelId, yMarginRatio=yMarginRatio, xLimits=xLimits)
        if appliedX:
            dpg.split_frame()
            dpg.set_axis_limits_auto(xTag)
        return True

    def applySourceXAxisToPanel(self, panelId, params=None):
        """Kaynak plot'un X araligini hedef panele uygular; Y eksenine dokunmaz."""
        params = params or self._lastReadPlotParams
        panel = self._panels.get(panelId)
        if panel is None or params is None:
            return False
        if panelId == params.get("panelId"):
            return True
        if not self.isPanelReadyForSourceParams(panelId):
            return False

        xLimits = params.get("xAxisLimits")
        if xLimits is None:
            return False

        xTag = f"x_axis_{panelId}"
        dpg.set_axis_limits(xTag, xLimits[0], xLimits[1])
        dpg.split_frame()
        dpg.set_axis_limits_auto(xTag)
        return True

    def _visibleYRangeForPanel(self, panelId, xLimits=None):
        panel = self._panels.get(panelId)
        xLimits = xLimits or self._axisLimits(f"x_axis_{panelId}")
        if panel is None or xLimits is None:
            return None
        xMin, xMax = xLimits
        yMin = yMax = None
        for data in panel.dataList:
            if not data.isVisible:
                continue
            dataRange = self._visibleYRangeForData(data, xMin, xMax)
            if dataRange is None:
                continue
            lo, hi = dataRange
            yMin = lo if yMin is None else min(yMin, lo)
            yMax = hi if yMax is None else max(yMax, hi)
        if yMin is None or yMax is None:
            return None
        return yMin, yMax

    def _visibleYRangeForData(self, data, xMin, xMax):
        xs = data._fullXs if data._fullXs is not None else data.xs
        if data.dataType == "candle" and data.low and data.high:
            lows = data._fullLow if data._fullLow is not None else data.low
            highs = data._fullHigh if data._fullHigh is not None else data.high
            if len(xs) == 0:
                xs = range(len(lows))
        elif data.dataType in ("bar", "volume") and data.volume:
            highs = data._fullVolume if data._fullVolume is not None else data.volume
            lows = [0.0] * len(highs)
            if len(xs) == 0:
                xs = range(len(highs))
        else:
            values = data._fullYs if data._fullYs is not None else data.ys
            lows = highs = values
            if len(xs) == 0:
                xs = range(len(values))

        yMin = yMax = None
        for i in range(min(len(xs), len(lows), len(highs))):
            x = xs[i]
            if x < xMin or x > xMax:
                continue
            lo, hi = lows[i], highs[i]
            if not self._isFiniteNumber(lo) or not self._isFiniteNumber(hi):
                continue
            yMin = lo if yMin is None else min(yMin, lo)
            yMax = hi if yMax is None else max(yMax, hi)
        if yMin is None or yMax is None:
            return None
        return yMin, yMax

    def _axisLimits(self, axis):
        if not dpg.does_item_exist(axis):
            return None
        try:
            limits = dpg.get_axis_limits(axis)
        except (KeyError, SystemError, Exception):
            return None
        if limits is None or len(limits) < 2:
            return None
        return float(limits[0]), float(limits[1])

    def _isFiniteNumber(self, value):
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    # ---------------------------------------------------------- x ekseni
    def setXAxisMode(self, mode, dateTimeFormat=None):
        """X ekseninde bar numarasi (varsayilan) yerine tarih/saat gostermek
        icin. mode: 'bar' (x_axis'in kendi sayisal tick'leri) | 'datetime'
        (PanelData.timestamps + isIntraday'den, GORUNUR ARALIGA (zoom/pan)
        gore uretilen seyrek etiketler, bkz. _buildDatetimeTicks). Cagirinca
        TUM cizili panellerin x eksenini aninda gunceller; datetime modundayken
        render() de her frame gorunur araligi izleyip tick'leri tazeler (bkz.
        render/_lastAxisTicksSignature) - boylece zoom/pan yaptikca bar modunda
        oldugu gibi tick'ler guncel kalir.

        dateTimeFormat: datetime modunda kullanilacak strftime deseni, or:
          "%d.%m.%Y %H:%M:%S"  -> tarih + saat (tek satir)
          "%d.%m.%Y\\n%H:%M:%S" -> tarih + saat (iki satir)
          "%H:%M:%S"            -> yalnizca saat
          "%d.%m.%Y"            -> yalnizca tarih
          "auto"                -> isIntraday'e gore YALNIZCA saat (intraday,
                                    saniyesiz "%H:%M") veya YALNIZCA tarih
                                    (gunluk/haftalik/aylik)
        None (varsayilan) birakilirsa her panelin PanelData.isIntraday'ine
        gore otomatik secilir (intraday: tarih+saat iki satir, degilse
        sadece tarih) - "auto"'dan farki, intraday'de tarihi de gostermesi."""
        if mode not in ("bar", "datetime"):
            raise ValueError("xAxisMode 'bar' ya da 'datetime' olmali")
        self._xAxisMode = mode
        self._dateTimeFormat = dateTimeFormat
        self._lastAxisTicksSignature.clear()
        self.updateXAxisTicks()

    def setDebugAxisTicks(self, enabled: bool):
        """True ise datetime modunda DPG'ye gonderilen HER tick listesini
        (panel, gorunur bar araligi, (label, bar_no) ciftleri) konsola basar
        - ekranda gorunen ile karsilastirip hesaplanan tarihin dogru bar'a
        mi denk geldigini dogrulamak icin (bkz. updateXAxisTicks)."""
        self._debugAxisTicks = bool(enabled)

    def getXAxisMode(self):
        return self._xAxisMode

    def updateXAxisTicks(self, panelId=None):
        """x_axis_{id} tick etiketlerini guncel moda (bkz. setXAxisMode) gore
        yeniden kurar. panelId verilmezse TUM cizili panelleri gunceller.
        Hesaplanan ticks ICERIGI bir onceki cagridakiyle AYNIYSA set_axis_ticks
        hic CAGRILMAZ (bkz. _lastAxisTicksSignature) - flicker'in asil sebebi
        her frame ayni/neredeyse-ayni tick'leri tekrar tekrar DPG'ye basmakti."""
        panelIds = [panelId] if panelId is not None else list(self._panels)
        for pid in panelIds:
            axis = f"x_axis_{pid}"
            if not dpg.does_item_exist(axis):
                continue
            if self._xAxisMode == "bar":
                # Guard YOK (bilerek): setXAxisMode her mod degisiminde
                # _lastAxisTicksSignature'i temizliyor, bu yuzden "onceden
                # set edilmis mi" bilgisi kayboluyor - guard olsaydi eski
                # datetime tick'leri eksende donuk kalabilirdi. reset_axis_ticks
                # ucuz/idempotent, bar modunda zaten her frame CAGRILMIYOR
                # (render() sadece datetime modunda updateXAxisTicks cagirir).
                dpg.reset_axis_ticks(axis)
                self._lastAxisTicksSignature[pid] = None
                continue
            panel = self._panels.get(pid)
            if panel is None:
                continue
            data = self._pickTimestampData(panel)
            if data is None or not data.timestamps:
                dpg.reset_axis_ticks(axis)
                continue
            n = len(data.timestamps)
            lo, hi = self._xAxisLimits(pid, n)
            ticks = tuple(self._buildDatetimeTicks(pid, data, lo, hi, n))
            if self._lastAxisTicksSignature.get(pid) == ticks:
                continue
            self._lastAxisTicksSignature[pid] = ticks
            if ticks:
                if self._debugAxisTicks:
                    print(f"[xAxisTicks] panel={pid} lo={lo:.1f} hi={hi:.1f} ticks={ticks}")
                dpg.set_axis_ticks(axis, ticks)
            else:
                dpg.reset_axis_ticks(axis)

    def _pickTimestampData(self, panel):
        """Panelin dataList'inde timestamps'i dolu olan ILK PanelData'yi
        bulur (datetime tick'leri onun timestamps/isIntraday'inden uretilir
        - panel icindeki tum seriler ayni x eksenini paylasiyor)."""
        for d in panel.dataList:
            if d.timestamps:
                return d
        return None

    def _xAxisLimits(self, panelId, n):
        """x_axis_{panelId}'in SU AN GORUNEN (zoom/pan sonrasi) bar araligini
        dondurur (0..n-1'e kirpilmis). Eksen henuz cizilmediyse/limit
        alinamiyorsa tam araliga (0, n-1) duser."""
        axis = f"x_axis_{panelId}"
        if dpg.does_item_exist(axis):
            try:
                limits = dpg.get_axis_limits(axis)
                if limits:
                    lo, hi = limits
                    return max(0, lo), min(n - 1, hi)
            except Exception:
                pass
        return 0, n - 1

    def _buildDatetimeTicks(self, panelId, data, xMin, xMax, n):
        """[xMin, xMax] GORUNUR bar araligi icin SABIT bir bar-adiminda
        (bkz. _chooseTickStep) etiket yerlestirir: i % step == 0 olan MUTLAK
        bar index'leri isaretlenir. 'N tick'i araliga esit yay' yontemi
        (interpolasyon) zoom sirasinda xMin/xMax'in her karede az miktarda
        kaymasiyla FARKLI bar'lari secip duruyordu - hem flicker hem de
        label overlap'ine sebep oluyordu. Mutlak index'e sabit adimla
        hizalanan bu yontemde pan/zoom sirasinda ayni step suruyorsa
        ISARETLI bar'lar SABIT kalir, sadece pencereye girip/cikan uclar
        degisir. isIntraday=True ise 'gun.ay.yil\\nsaat:dakika:saniye',
        degilse sadece 'gun.ay.yil' formati kullanilir (Ref3'teki gosterimin
        karsiligi)."""
        left = max(0, int(xMin))
        right = min(n - 1, int(xMax) + 1)
        if left > right or left >= n:
            return []
        if self._dateTimeFormat is None:
            fmt = "%d.%m.%Y\n%H:%M:%S" if data.isIntraday else "%d.%m.%Y"
        elif self._dateTimeFormat == "auto":
            fmt = "%H:%M" if data.isIntraday else "%d.%m.%Y"
        else:
            fmt = self._dateTimeFormat
        step = self._chooseTickStep(panelId, right - left + 1, data, fmt)
        start = (left // step) * step
        if start < left:
            start += step
        indices = set(range(start, right + 1, step))

        # Gun degisimi: fmt'de tarih bilgisi YOKSA (or. "auto"/intraday ->
        # sadece saat) hangi gunde oldugumuzu kaybederiz - bir onceki bar'dan
        # FARKLI tarihli bar'lari (gunun ilk bar'i) yakalayan kod hazir
        # (bkz. _dayBoundaryIndices) ama x eksenindeki gosterimi simdilik
        # KAPALI (_dayChangeMarkersEnabled=False) - gorunumu karistirdigi
        # icin kullanici isteyince acilacak, bu arada altyapi duruyor.
        dayIndices = set()
        if self._dayChangeMarkersEnabled and data.isIntraday and not self._fmtHasDateToken(fmt):
            dayIndices = self._dayBoundaryIndices(data, left, right, n)
            if len(dayIndices) > 20:
                dayIndices = set()
            indices |= dayIndices

        ticks = []
        for i in sorted(indices):
            if i >= n:
                continue
            ts = data.timestamps[i]
            if not hasattr(ts, "strftime"):
                continue
            curFmt = self._dayChangeFormat if i in dayIndices else fmt
            ticks.append((ts.strftime(curFmt), float(i)))
        return ticks

    def _fmtHasDateToken(self, fmt):
        """fmt strftime deseninde TARIH bileseni (gun/ay/yil vb.) var mi?
        Yoksa (or. '%H:%M:%S') gun degisimini ayrica isaretlemek gerekir
        (bkz. _buildDatetimeTicks)."""
        return any(tok in fmt for tok in ("%d", "%m", "%Y", "%y", "%j", "%b", "%B", "%a", "%A", "%x"))

    def _dayBoundaryIndices(self, data, left, right, n):
        """[left, right] icinde bir ONCEKI bar'dan FARKLI tarihli (gunun ilk
        bar'i olan) index'leri dondurur. Performans icin barsInRange
        _dayBoundaryScanCap'i asarsa taranmaz (bos set doner) - asiri
        zoom-out'ta her frame O(bar) tarama yapilmasin diye."""
        if right - left + 1 > self._dayBoundaryScanCap or right <= left:
            return set()
        boundaries = set()
        prevDate = None
        for i in range(max(0, left), min(n, right + 1)):
            ts = data.timestamps[i]
            if not hasattr(ts, "date"):
                continue
            d = ts.date()
            if prevDate is not None and d != prevDate:
                boundaries.add(i)
            prevDate = d
        return boundaries

    def _chooseTickStep(self, panelId, barsInRange, data, fmt):
        """Etiketler MUTLAK bar index'ine sabit bir adimla yerlestirilir
        (i % step == 0). Adim, bar modunda DPG'nin kendi sayisal tick'lerinin
        NEDEN guzel davrandigini taklit etmek icin plot'un GERCEK piksel
        genisligine ve etiketin tahmini piksel genisligine gore secilir
        (bkz. _maxTicksForWidth) - boylece eksen 'bogulmuyor'. Varsayilan
        alt sinir _minTickStep (~7, kullanicinin istedigi '5-10 barda bir')
        - genis plot + kisa etiket kombinasyonunda daha sik etiket YERINE
        bu tabanda kalinir; dar plot/uzun etiket kombinasyonunda step
        ikiye katlanarak buyur."""
        step = self._minTickStep
        maxTicks = self._maxTicksForWidth(panelId, data, fmt)
        while barsInRange / step > maxTicks:
            step *= 2
        return step

    def _maxTicksForWidth(self, panelId, data, fmt):
        """Plot'un gercek piksel genisligine (bkz. _plotWidthPx) ve etiketin
        tahmini piksel genisligine (bkz. _estimateLabelPixelWidth) gore
        ekrana sigacak MAKSIMUM tick sayisini hesaplar - _maxTicksOnScreen
        ile de guvenlik/performans amacli ustten sinirlanir."""
        plotWidth = self._plotWidthPx(panelId)
        labelWidth = self._estimateLabelPixelWidth(data, fmt)
        fit = int(plotWidth / labelWidth)
        return max(3, min(self._maxTicksOnScreen, fit))

    def _plotWidthPx(self, panelId):
        """plot_{panelId}'in SU ANKI piksel genisligi. Henuz cizilmediyse/
        olculemiyorsa (or. setXAxisMode ilk kez script icinde, frame henuz
        render edilmeden cagrildiysa) makul bir varsayilana duser - bir
        sonraki frame'de render() zaten dogru genislikle yeniden hesaplar."""
        tag = f"plot_{panelId}"
        if dpg.does_item_exist(tag):
            try:
                size = dpg.get_item_rect_size(tag)
                if size and size[0] > 0:
                    return size[0]
            except Exception:
                pass
        return 900

    def _estimateLabelPixelWidth(self, data, fmt):
        """Bir tick etiketinin kabaca kac piksel genislik kaplayacagini
        tahmin eder: gercek bir timestamp'i fmt ile strftime'layip (coklu
        satirsa) EN UZUN satirin karakter sayisini piksel/karakter tahminiyle
        (_axisCharPxWidth) carpar + iki etiket arasi bosluk payi
        (_axisTickPadding) ekler. DPG'nin gercek font metriklerini
        olcemiyoruz (kolay erisilebilir bir API yok) - bilerek muhafazakar
        (fazla tahmin eden) bir deger kullaniyoruz ki overlap yerine
        gerekirse gereginden az tick gostersin."""
        sample = data.timestamps[0] if data.timestamps else None
        text = sample.strftime(fmt) if hasattr(sample, "strftime") else fmt
        longest = max((len(line) for line in text.split("\n")), default=len(text))
        return longest * self._axisCharPxWidth + self._axisTickPadding

    def _buildPanelUi(self, panel, width=None, height=None):
        """Panelin plot UI'sini (child_window + plot + legend + eksenler +
        info-panel hover_text + ham mouse-pos metni + crosshair) olusturur.
        Zaten varsa no-op. Veri CIZMEZ. Tag semasi Ref3 ile ayni: panel_{id} /
        plot_{id} / x_axis_{id} / y_axis_{id} / hover_text_{id} /
        mouse_pos_text_{id} / crosshair_v_{id} / crosshair_h_{id}."""
        tag = f"panel_{panel.id}"
        if dpg.does_item_exist(tag):
            return
        w = width if width is not None else panel.width
        h = height if height is not None else panel.height

        if self._container and dpg.does_item_exist(self._container):
            dpg.push_container_stack(self._container)
            dpg.add_child_window(tag=tag, width=w, height=h, no_scrollbar=True)
            dpg.pop_container_stack()
        else:
            dpg.add_child_window(tag=tag, width=w, height=h, no_scrollbar=True)

        # no_mouse_pos: DPG'nin sag-alt ham (x,y) okumasini gizler - onun
        # yerine hover_text_{id} (updateInfoOverlays) + mouse_pos_text_{id}
        # (updateMousePosOverlays, plotun sag-ust kosesinde sabit) kullanilir.
        plotTag = dpg.add_plot(label=panel.caption, height=-1, width=-1, parent=tag,
                               tag=f"plot_{panel.id}", no_mouse_pos=True)
        dpg.add_plot_legend(parent=plotTag, location=dpg.mvPlot_Location_SouthEast)
        dpg.add_plot_axis(dpg.mvXAxis, label="", tag=f"x_axis_{panel.id}", parent=plotTag)
        dpg.add_plot_axis(dpg.mvYAxis, label="y", tag=f"y_axis_{panel.id}", parent=plotTag)
        dpg.add_text("", tag=f"hover_text_{panel.id}", parent=tag,
                    pos=(80, 40), color=(210, 210, 220, 255), show=False)
        dpg.add_text("", tag=f"mouse_pos_text_{panel.id}", parent=tag,
                    pos=(0, 8), color=(210, 210, 220, 255), show=False)
        # Crosshair (dikey+yatay drag_line, Ref3'teki plot_controller.py'deki
        # register_plot ile ayni stil): no_inputs -> kullanici suruklemez,
        # sadece imlec konumunu gostermek icin kullanilir. Cizim/gosterme
        # panel_id BAZINDA updateCrossHairOverlays()'te yapilir.
        dpg.add_drag_line(tag=f"crosshair_v_{panel.id}", parent=plotTag,
                          default_value=0.0, color=(255, 255, 0, 160),
                          thickness=1, vertical=True, no_inputs=True,
                          no_fit=True, show=False)
        dpg.add_drag_line(tag=f"crosshair_h_{panel.id}", parent=plotTag,
                          default_value=0.0, color=(255, 255, 0, 160),
                          thickness=1, vertical=False, no_inputs=True,
                          no_fit=True, show=False)

        # DPG'nin yerlesik cift-tikla-fit'i (fit_button, varsayilan sol tik)
        # TIGHT (payisiz) bir sinira resetliyor - bizim _applyAxisPadding
        # dolgusunu ezip gecirdigi icin cift tiklamayi yakalayip PADDING'i
        # geri uyguluyoruz (bkz. _onPlotDoubleClicked). Ayni registry'ye tek
        # tiklama handler'i da eklendi - "click" modunda aktif paneli secer
        # (bkz. _onPlotClicked/setActiveUpdateMode).
        registryTag = f"plot_dclick_registry_{panel.id}"
        if dpg.does_item_exist(registryTag):
            dpg.delete_item(registryTag)
        with dpg.item_handler_registry(tag=registryTag):
            dpg.add_item_double_clicked_handler(callback=self._onPlotDoubleClicked,
                                               user_data=panel.id)
            dpg.add_item_clicked_handler(callback=self._onPlotClicked,
                                        user_data=panel.id)
        dpg.bind_item_handler_registry(plotTag, registryTag)

    def _onPlotDoubleClicked(self, sender=None, appData=None, userData=None):
        """DPG'nin cift-tikla-fit'i (native, tight/payisiz) bu FRAME icinde
        uygulanir; biz bir frame BEKLEYIP (split_frame) ustune kendi
        dolgulu (_applyAxisPadding) araligimizi yeniden yaziyoruz - boylece
        kullanici cift tikladiginda hala "full data + pay" gorunumu alir,
        cipliak/payisiz fit degil."""
        panelId = userData
        panel = self._panels.get(panelId)
        if panel is None:
            return
        dpg.split_frame()
        self._applyAxisPadding(panelId, panel)

    def hidePanel(self, panelId):
        """Paneli gizler (model: panel.visible=False + varsa UI'da show=False)."""
        panel = self._panels.get(panelId)
        if panel is None:
            return
        panel.setVisible(False)
        tag = f"panel_{panel.id}"
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, show=False)

    def showPanel(self, panelId):
        """Paneli gosterir (model: panel.visible=True + varsa UI'da show=True)."""
        panel = self._panels.get(panelId)
        if panel is None:
            return
        panel.setVisible(True)
        tag = f"panel_{panel.id}"
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, show=True)

    def hideAllPanels(self):
        for panelId in self._panels:
            self.hidePanel(panelId)

    def showAllPanels(self):
        for panelId in self._panels:
            self.showPanel(panelId)

    def collapseAllPanels(self):
        """GORUNUR tum panelleri ince bir baslik seridine kuculttur.
        panel.height DEGISMEZ (model dokunulmaz) - sadece cizili
        panel_{id} child_window'unun DPG yuksekligi degisir, bu yuzden
        expandAllPanels eski haline geri getirebilir."""
        for panelId, panel in self._panels.items():
            tag = f"panel_{panelId}"
            if dpg.does_item_exist(tag) and dpg.is_item_shown(tag):
                dpg.set_item_height(tag, self.COLLAPSED_PANEL_HEIGHT)

    def expandAllPanels(self):
        """GORUNUR tum panelleri panel.height'a (height<=0 ise 300'e)
        geri genisletir (bkz. collapseAllPanels)."""
        for panelId, panel in self._panels.items():
            tag = f"panel_{panelId}"
            if dpg.does_item_exist(tag) and dpg.is_item_shown(tag):
                h = panel.height if panel.height and panel.height > 0 else 300
                dpg.set_item_height(tag, h)

    # --------------------------------------------------------- info paneli
    def setInfoPanelMode(self, mode: str):
        """Info panelinin (hover_text_{id}) ne zaman gosterilecegini belirler:
          hidden -> hicbir panelde gosterilmez
          hover  -> yalniz o an mouse'un ustunde oldugu plot'ta gosterilir
          active -> yalniz setActiveInfoPanel ile secilen panelde gosterilir
          always -> (varsayilan) TUM panellerde sabit gosterilir
        Ref3'teki set_info_panel_mode ile ayni."""
        mode = str(mode or "").lower()
        if mode not in ("hidden", "hover", "active", "always"):
            raise ValueError("info panel mode must be one of: hidden, hover, active, always")
        self._infoPanelMode = mode

    def getInfoPanelMode(self):
        return self._infoPanelMode

    def setInfoPanelsVisible(self, visible: bool):
        """Kisayol: visible=True -> mode 'always', visible=False -> mode 'hover'."""
        self.setInfoPanelMode("always" if visible else "hover")

    def setActiveInfoPanel(self, panelId):
        """mode='active' iken hangi panelin info panelinin gosterilecegini secer."""
        self._infoActivePanelId = panelId

    def setInfoSharedIndex(self, index):
        """mode='always'/'active' iken TUM panellerin ortak gosterecegi bar
        index'ini elle ayarlar (bir plot'un uzerine gelince zaten otomatik
        guncellenir, bu manuel/script kontrolu icindir)."""
        if index is None:
            return
        self._infoSharedIndex = int(index)

    def updateInfoOverlays(self):
        """Info panellerini (hover_text_{id}) secili moda gore gunceller.
        render() tarafindan her frame cagrilir - Ref3'teki update_info_overlays
        ile ayni. Mouse'un ustunde oldugu plot varsa oradaki bar index'i
        _infoSharedIndex'e yazilir (boylece always/active modunda TUM
        panellerdeki readout ayni bar'i gosterir - cross-plot senkron)."""
        hoveredPanelId, hoveredIndex = self._currentHoverInfoIndex()
        if hoveredIndex is not None:
            self._infoSharedIndex = hoveredIndex

        for panelId, panel in self._panels.items():
            plotTag = f"plot_{panelId}"
            textTag = f"hover_text_{panelId}"
            if not dpg.does_item_exist(plotTag) or not dpg.does_item_exist(textTag):
                continue
            if not self._shouldShowInfoPanel(panelId, plotTag, hoveredPanelId):
                dpg.hide_item(textTag)
                continue

            d = self._pickInfoSourceData(panel)
            if d is None:
                dpg.hide_item(textTag)
                continue

            idx = self._resolveInfoIndex(panelId, d, hoveredPanelId, hoveredIndex)
            label = self._buildHoverLabel(panel, d, idx)
            if not label:
                dpg.hide_item(textTag)
                continue
            dpg.set_value(textTag, label)
            dpg.show_item(textTag)

    def updateMousePosOverlays(self):
        """Demo'larda gorulen ham mouse-pos okumasi: mouse hangi plot'un
        uzerindeyse SADECE o panelde, sag-ust kosede SABIT (mouse'u TAKIP
        ETMEZ, sadece deger guncellenir) gosterilir; diger panellerde ve
        mouse hicbir plotta degilken gizli kalir. x ekseni bar index oldugu
        icin "xBar" tam sayi, "yBar" ondalikli yazilir.
        Koseye sabit kalmasi icin panelin GERCEK genisligi (yeniden
        boyutlanabilir oldugu icin) her frame okunup metnin x konumu ona
        gore hesaplanir (sag kenardan RIGHT_MARGIN kadar icerde)."""
        RIGHT_MARGIN = 40  # saga tam yapismasin diye (biraz sola cekildi)
        for panelId in self._panels:
            plotTag = f"plot_{panelId}"
            textTag = f"mouse_pos_text_{panelId}"
            if not dpg.does_item_exist(plotTag) or not dpg.does_item_exist(textTag):
                continue
            if not dpg.is_item_hovered(plotTag):
                dpg.hide_item(textTag)
                continue
            try:
                mx, my = dpg.get_plot_mouse_pos()
            except Exception:
                dpg.hide_item(textTag)
                continue
            dpg.set_value(textTag, f"xBar={round(mx)}  yBar={my:.2f}")
            panelTag = f"panel_{panelId}"
            if dpg.does_item_exist(panelTag):
                panelWidth = dpg.get_item_rect_size(panelTag)[0]
                textWidth = dpg.get_item_rect_size(textTag)[0] or 120
                if panelWidth:
                    dpg.set_item_pos(textTag, (max(4, panelWidth - textWidth - RIGHT_MARGIN), 8))
            dpg.show_item(textTag)

    def setCrossHairMode(self, mode: str):
        """Crosshair'in kapsamini belirler:
          hidden -> hicbir panelde gosterilmez
          single -> SADECE mouse'un ustunde oldugu panelde tam
                    (dikey+yatay) crosshair gosterilir
          all    -> (varsayilan) mouse'un ustunde oldugu panelde tam crosshair, TUM
                    DIGER panellerde ise SADECE dikey cizgi (ayni x/bar) -
                    "ben hangi paneldeysem digerlerine de gorunsun".
                    Yatay (y) cizgi digerlerinde YOK: paneller (OHLC/RSI/
                    MACD gibi) farkli y-olcekleri kullandigi icin ayni y
                    degeri baska panelde anlamsiz olurdu (Ref3'teki
                    plot_controller.py'nin CROSSHAIR_ALL'i da boyle calisir)."""
        mode = str(mode or "").lower()
        if mode not in ("hidden", "single", "all"):
            raise ValueError("crosshair mode must be one of: hidden, single, all")
        self._crossHairMode = mode

    def getCrossHairMode(self):
        return self._crossHairMode

    def setCrossHairPersist(self, persist: bool):
        """True (varsayilan) ise mouse hicbir plot'un ustunde degilken
        crosshair SON bilinen pozisyonda kalir, gizlenmez - infoPanel'in
        "always" modu gibi surekli gorunur. False ise mouse plot'tan
        cikar cikmaz crosshair gizlenir."""
        self._crossHairPersist = bool(persist)

    def getCrossHairPersist(self):
        return self._crossHairPersist

    def updateCrossHairOverlays(self):
        """Crosshair'i _crossHairMode/_crossHairPersist bayraklarina gore
        gunceller - render() tarafindan her frame cagrilir.

        Akis: once mouse'un ustunde oldugu panel + (x,y)'i bul. Bulunduysa
        _crossHairLastPos'a yaz (mode/persist ne olursa olsun GUNCEL tutulur).
        Bulunamadiysa (mouse hicbir plotta degil) persist KAPALIYSA son
        pozisyon unutulur (crosshair gizlenir); ACIKSA son pozisyon
        KORUNUR (crosshair oldugu yerde kalir).

        Sonra o son pozisyona gore her panel: mode='hidden' -> hep gizli;
        panel.getCrossHairVisible()==False -> o panel hep gizli (panel
        bazinda opt-out); mode='single' -> SADECE kaynak panelde tam
        crosshair; mode='all' -> kaynak panelde tam, digerlerinde sadece
        dikey (ayni x/bar, bkz. setCrossHairMode)."""
        if self._crossHairMode == "hidden":
            self._hideAllCrossHairs()
            return

        hoveredPanelId, mx, my = self._currentHoverMousePos()
        if hoveredPanelId is not None:
            self._crossHairLastPos = (hoveredPanelId, mx, my)
        elif not self._crossHairPersist:
            self._crossHairLastPos = None

        pos = self._crossHairLastPos
        if pos is None:
            self._hideAllCrossHairs()
            return
        sourcePanelId, x, y = pos

        for panelId, panel in self._panels.items():
            vTag = f"crosshair_v_{panelId}"
            hTag = f"crosshair_h_{panelId}"
            if not panel.getCrossHairVisible():
                self._hideCrossHairTags(vTag, hTag)
                continue
            if panelId == sourcePanelId:
                self._showCrossHairTags(vTag, hTag, x, y)
            elif self._crossHairMode == "all":
                self._showCrossHairTags(vTag, hTag, x, y=None)
            else:
                self._hideCrossHairTags(vTag, hTag)

    def _currentHoverMousePos(self):
        """Mouse'un ustunde oldugu (varsa) ilk plot'u ve HAM (x,y) plot-
        koordinatini dondurur. Hicbir plot hover degilse (None, None, None)."""
        for panelId in self._panels:
            plotTag = f"plot_{panelId}"
            if not dpg.does_item_exist(plotTag) or not dpg.is_item_hovered(plotTag):
                continue
            try:
                mx, my = dpg.get_plot_mouse_pos()
                return panelId, mx, my
            except Exception:
                return panelId, None, None
        return None, None, None

    def _showCrossHairTags(self, vTag, hTag, x, y=None):
        """Dikey cizgiyi x'e, (y verilmisse) yatay cizgiyi y'ye ayarlayip
        gosterir. y=None ise yatay cizgi GIZLI kalir (bkz. updateCrossHairOverlays
        'all' modundaki digerlerinde-sadece-dikey davranisi)."""
        if dpg.does_item_exist(vTag):
            dpg.set_value(vTag, x)
            dpg.show_item(vTag)
        if dpg.does_item_exist(hTag):
            if y is None:
                dpg.hide_item(hTag)
            else:
                dpg.set_value(hTag, y)
                dpg.show_item(hTag)

    def _hideCrossHairTags(self, vTag, hTag):
        if dpg.does_item_exist(vTag):
            dpg.hide_item(vTag)
        if dpg.does_item_exist(hTag):
            dpg.hide_item(hTag)

    def _hideAllCrossHairs(self):
        for panelId in self._panels:
            self._hideCrossHairTags(f"crosshair_v_{panelId}", f"crosshair_h_{panelId}")

    # ----------------------------------------------------------- aktif panel
    def setActiveUpdateMode(self, mode: str):
        """"Aktif panel" (getActivePanelId) hangi etkilesimle guncellenecek:
          hover -> mouse hangi plot'un uzerindeyse o AN aktif olur (mouse
                   ayrilinca SON aktif panel korunur, "None"e dusmez)
          click -> SADECE kullanici bir plot'a tikladiginda degisir (hover
                   etkisiz)."""
        mode = str(mode or "").lower()
        if mode not in ("hover", "click"):
            raise ValueError("active update mode must be 'hover' or 'click'")
        self._activeUpdateMode = mode

    def getActiveUpdateMode(self):
        return self._activeUpdateMode

    def getActivePanelId(self):
        """Henuz hicbir hover/click ile bir panel aktif olmadiysa (_activePanelId
        hala None) ve en az bir panel varsa, panel siralamasindaki ILK paneli
        varsayilan olarak dondurur - boylece combo/gosterge "None" yerine
        bastan itibaren bir panel secili gorunur. _activePanelId'in kendisi
        DEGISTIRILMEZ (gercek bir hover/click olana kadar hala None) - bu
        SADECE okurken uygulanan bir fallback."""
        if self._activePanelId is None and self._panelOrder:
            return self._panelOrder[0]
        return self._activePanelId

    def updateActivePanel(self):
        """render() tarafindan her frame cagrilir. Sadece 'hover' modunda is
        yapar - mouse'un ustunde oldugu plot'u bulup _activePanelId'i onunla
        gunceller (bulunamazsa - mouse hicbir plotta degil - SON deger
        korunur). 'click' modunda hicbir sey yapmaz, degisiklik SADECE
        _onPlotClicked'tan (kullanici tiklayinca) gelir."""
        if self._activeUpdateMode != "hover":
            return
        for panelId in self._panels:
            plotTag = f"plot_{panelId}"
            if dpg.does_item_exist(plotTag) and dpg.is_item_hovered(plotTag):
                self._activePanelId = panelId
                return

    def _onPlotClicked(self, sender=None, appData=None, userData=None):
        """_buildPanelUi'da her panelin plot'una baglanan tiklama handler'i.
        SADECE 'click' modundayken _activePanelId'i degistirir (hover
        modundayken tiklamanin bir etkisi yok - updateActivePanel zaten
        surekli gunceller)."""
        if self._activeUpdateMode == "click":
            self._activePanelId = userData

    def _currentHoverInfoIndex(self):
        """Mouse'un ustunde oldugu (varsa) ilk plot'u ve o plot'taki bar
        index'ini dondurur. Hicbir plot hover degilse (None, None)."""
        for panelId in self._panels:
            plotTag = f"plot_{panelId}"
            if not dpg.does_item_exist(plotTag) or not dpg.is_item_hovered(plotTag):
                continue
            try:
                mx, _ = dpg.get_plot_mouse_pos()
                return panelId, int(round(mx))
            except Exception:
                return panelId, None
        return None, None

    def _shouldShowInfoPanel(self, panelId, plotTag, hoveredPanelId=None):
        """panel.getInfoPanelVisible()==False ise global _infoPanelMode ne
        olursa olsun gosterilmez (panel bazinda programatik kapatma).
        (Panelin TUM data'si silinmis/gizlenmisse info panel zaten
        _pickInfoSourceData None dondugu icin updateInfoOverlays'de ayrica
        gizlenir - burada tekrar kontrol etmeye gerek yok.)"""
        panel = self._panels.get(panelId)
        if panel is not None and not panel.getInfoPanelVisible():
            return False
        mode = self._infoPanelMode
        if mode == "hidden":
            return False
        if mode == "always":
            return True
        if mode == "active":
            return panelId == self._infoActivePanelId
        return panelId == hoveredPanelId or dpg.is_item_hovered(plotTag)

    def _resolveInfoIndex(self, panelId, data, hoveredPanelId=None, hoveredIndex=None):
        idx = hoveredIndex
        if idx is None and self._infoPanelMode in ("always", "active"):
            idx = self._infoSharedIndex
        if idx is not None:
            idx = self._clampInfoIndex(data, idx)
            self._infoLastIndex[panelId] = idx
            return idx
        if panelId in self._infoLastIndex:
            return self._infoLastIndex[panelId]
        return max(0, self._infoDataLen(data) - 1)

    def _clampInfoIndex(self, data, idx):
        dataLen = self._infoDataLen(data)
        if dataLen <= 0:
            return 0
        return max(0, min(dataLen - 1, int(idx)))

    def _pickInfoSourceData(self, panel):
        """Info panelinde gosterilecek 'ana' PanelData'yi secer: once
        timestamp'i olan gorunur bir seri, yoksa gorunur ILK seri."""
        for cand in panel.dataList:
            if cand.isVisible and cand.timestamps:
                return cand
        for cand in panel.dataList:
            if cand.isVisible:
                return cand
        return None

    def _infoDataLen(self, d):
        if d is None:
            return 0
        candidates = (
            getattr(d, "_fullXs", None),
            getattr(d, "_fullYs", None),
            getattr(d, "_fullClose", None),
            getattr(d, "timestamps", None),
            getattr(d, "xs", None),
            getattr(d, "ys", None),
            getattr(d, "close", None),
        )
        for seq in candidates:
            if seq is not None and len(seq) > 0:
                return len(seq)
        return 0

    def _buildHoverLabel(self, panel=None, d=None, idx=None):
        """Secili PanelData (d) + bar index'ine (idx) gore hover_text_{id}
        icin cok satirli bir readout metni kurar.

        panel.getInfoFields() ile ozel bir alan listesi verilmisse ONU
        kullanir (index/date/time + OHLC/volume/size + dataList'teki isimle
        eslesen herhangi bir seri); verilmemisse (None = auto-detect)
        index/date/(intraday ise time) + OHLC/volume/size/diff/change +
        TUM gorunur line serilerini otomatik listeler. Ref3'teki
        _build_hover_label ile ayni."""
        dataLen = self._infoDataLen(d)
        valid = d is not None and idx is not None and 0 <= idx < dataLen
        hasTimestamp = valid and bool(getattr(d, "timestamps", None)) and idx < len(d.timestamps)
        isIntraday = getattr(d, "isIntraday", True) if d is not None else True

        def attr(name):
            return getattr(d, name, None) if d is not None else None

        def val(seqName, fullName, fmt):
            seq = attr(seqName)
            fullArr = attr(fullName) if fullName else None
            src = fullArr if fullArr is not None else seq
            if not valid or src is None or idx >= len(src):
                return "..."
            v = src[idx]
            try:
                if fmt == "d":
                    return format(int(v), fmt)
                return format(float(v), fmt)
            except (TypeError, ValueError):
                return "..."

        def num(seqName, fullName):
            seq = attr(seqName)
            fullArr = attr(fullName) if fullName else None
            src = fullArr if fullArr is not None else seq
            if not valid or src is None or idx >= len(src):
                return None
            try:
                return float(src[idx])
            except (TypeError, ValueError):
                return None

        def diffVal():
            o = num("open", "_fullOpen")
            c = num("close", "_fullClose")
            if o is None or c is None:
                return "..."
            return f"{c - o:.2f}"

        def changeVal():
            o = num("open", "_fullOpen")
            c = num("close", "_fullClose")
            if o is None or c is None:
                return "..."
            pct = ((c - o) / o * 100.0) if o else 0.0
            return f"{pct:.2f}%"

        def yVal(series):
            fullYs = getattr(series, "_fullYs", None)
            ys = getattr(series, "ys", None)
            src = fullYs if fullYs is not None else ys
            if not valid or src is None or idx >= len(src):
                return "..."
            try:
                return f"{float(src[idx]):.2f}"
            except (TypeError, ValueError):
                return "..."

        idxStr = str(idx) if valid else "..."
        dateStr = "..."
        timeStr = "..."
        if hasTimestamp:
            ts = d.timestamps[idx]
            if hasattr(ts, "strftime"):
                dateStr = ts.strftime("%d.%m.%Y")
                timeStr = ts.strftime("%H:%M")
            else:
                dateStr = str(ts)

        infoFields = panel.getInfoFields() if panel is not None else None
        if infoFields is not None:
            fieldMap = {
                "open": ("Open", ".2f", "open", "_fullOpen"),
                "high": ("High", ".2f", "high", "_fullHigh"),
                "low": ("Low", ".2f", "low", "_fullLow"),
                "close": ("Close", ".2f", "close", "_fullClose"),
                "volume": ("Volume", ".0f", "volume", "_fullVolume"),
                "size": ("Size", "d", "size", None),
            }
            rows = []
            for field in infoFields:
                if field == "index":
                    rows.append(("Index", idxStr))
                elif field == "date":
                    rows.append(("Date", dateStr))
                elif field == "time":
                    if isIntraday:
                        rows.append(("Time", timeStr))
                elif field in fieldMap:
                    label, fmt, seqName, fullName = fieldMap[field]
                    rows.append((label, val(seqName, fullName, fmt)))
                elif panel is not None:
                    for series in panel.dataList:
                        if series.name == field and series.isVisible:
                            rows.append((field, yVal(series)))
                            break
        else:
            rows = [("Index", idxStr), ("Date", dateStr)]
            if isIntraday:
                rows.append(("Time", timeStr))
            rows.append(None)

            hasOhlc = d is not None and bool(getattr(d, "open", None))
            if hasOhlc:
                rows += [
                    ("Open", val("open", "_fullOpen", ".2f")),
                    ("High", val("high", "_fullHigh", ".2f")),
                    ("Low", val("low", "_fullLow", ".2f")),
                    ("Close", val("close", "_fullClose", ".2f")),
                    ("Volume", val("volume", "_fullVolume", ".0f")),
                    ("Size", val("size", None, "d")),
                    None,
                    ("Diff", diffVal()),
                    ("Change", changeVal()),
                    None,
                ]
                if panel is not None:
                    for series in panel.dataList:
                        if series.isVisible and series.dataType == "line":
                            rows.append((series.name, yVal(series)))
            elif panel is not None:
                for series in panel.dataList:
                    if series.isVisible:
                        rows.append((series.name, yVal(series)))

        realRows = [r for r in rows if r is not None]
        if not realRows:
            return ""
        nameW = max(len(name) for name, _ in realRows)
        valW = max(len(str(value)) for _, value in realRows)
        sepLine = "-" * (nameW + 3 + valW + 1)
        return "\n".join(
            sepLine if row is None else f"{row[0]:<{nameW}} : {row[1]}"
            for row in rows
        )

    # ------------------------------------------------------------- periyodik
    def sync(self):
        """Model <-> UI senkronu: daha once drawPanel ile cizilmis ama artik
        modelde (self._panels) olmayan (deletePanel/deleteAllPanels ile
        silinmis) panellerin DPG item'ini (panel_{id}) temizler."""
        orphanIds = self._drawnPanelIds - self._panels.keys()
        for panelId in orphanIds:
            tag = f"panel_{panelId}"
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
            self._drawnPanelIds.discard(panelId)

    def render(self):
        """Periyodik cagrilmasi beklenen metod (or. her frame / bir timer'dan).
        Su an icinde sync() calisiyor + saniyede bir heartbeat print'i var
        (render'in gercekten periyodik tetiklendigini dogrulamak icin).
        datetime x-ekseni modundayken her frame updateXAxisTicks() da
        cagrilir - zoom/pan ile gorunur bar araligi degistikce tick'ler
        bar modundaki gibi dinamik guncellenir (degisiklik yoksa
        _lastAxisTicksSignature sayesinde gercek DPG cagrisi yapilmaz).
        updateInfoOverlays() da her frame cagrilir - hover_text_{id}
        readout'lari mouse/mod degisikligine gore guncel kalir.
        updateMousePosOverlays() ham (x,y) mouse-pos metnini gunceller.
        updateCrossHairOverlays() panel basina crosshair'i gunceller.
        updateActivePanel() 'hover' modundaysa aktif paneli gunceller."""
        self.sync()
        if self._xAxisMode == "datetime":
            self.updateXAxisTicks()
        self.updateInfoOverlays()
        self.updateMousePosOverlays()
        self.updateCrossHairOverlays()
        self.updateActivePanel()
        now = time.time()
        if now - self._lastRenderPrint >= 1.0:
            self._lastRenderPrint = now
            # print(f"[PanelManager.render] tick @ {now:.1f}  panels={len(self._panels)}")
