import time

import dearpygui.dearpygui as dpg

from .panel import Panel


class PanelManager:
    def __init__(self):
        self._panels = {}
        self._nextId = 0
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
        baglar ki panel.draw()/drawData()/sync()/render() calisabilsin."""
        self._panels[panel.id] = panel
        panel._manager = self
        if panel.id >= self._nextId:
            self._nextId = panel.id + 1
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
        """Bir paneli siler (Ref3'teki gibi panel_{id} child_window/_panel_order
        YOK - bizde henuz UI/cizim katmani yok, sadece model temizlenir)."""
        panel = self._panels.get(panelId)
        if panel is None:
            return
        panel.deleteAllData()
        del self._panels[panelId]

    def removePanel(self, panelId):
        """deletePanel ile ayni (isim tercihi icin ikinci ad)."""
        self.deletePanel(panelId)

    def getAllPanels(self):
        return list(self._panels.values())

    def iterateAllPanels(self):
        for panel in self._panels.values():
            yield panel

    def deleteAllPanels(self):
        """Henuz cizim/UI katmani yok; sadece modeli temizler (Ref3'teki gibi
        panel_{id} child_window silme/_panel_order YOK - bizde henuz yok)."""
        for panel in self._panels.values():
            panel.deleteAllData()
        self._panels.clear()
        self._nextId = 0

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
        self.updateXAxisTicks(panelId)

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
        """Panelin plot UI'sini (child_window + plot + legend + eksenler)
        olusturur. Zaten varsa no-op. Veri CIZMEZ. Tag semasi Ref3 ile ayni:
        panel_{id} / plot_{id} / x_axis_{id} / y_axis_{id}."""
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

        plotTag = dpg.add_plot(label=panel.caption, height=-1, width=-1, parent=tag,
                               tag=f"plot_{panel.id}", no_mouse_pos=True)
        dpg.add_plot_legend(parent=plotTag, location=dpg.mvPlot_Location_SouthEast)
        dpg.add_plot_axis(dpg.mvXAxis, label="", tag=f"x_axis_{panel.id}", parent=plotTag)
        dpg.add_plot_axis(dpg.mvYAxis, label="y", tag=f"y_axis_{panel.id}", parent=plotTag)

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
        _lastAxisTicksSignature sayesinde gercek DPG cagrisi yapilmaz)."""
        self.sync()
        if self._xAxisMode == "datetime":
            self.updateXAxisTicks()
        now = time.time()
        if now - self._lastRenderPrint >= 1.0:
            self._lastRenderPrint = now
            print(f"[PanelManager.render] tick @ {now:.1f}  panels={len(self._panels)}")
