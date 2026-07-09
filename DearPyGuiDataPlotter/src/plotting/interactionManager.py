import dearpygui.dearpygui as dpg


class InteractionManager:
    """Merkezi etkilesim/event yoneticisi.

    bkz. docs/ref3EventSystemAnalysis.md - kapsam adim adim buraya eklenecek.

    Su an uc parca var:
      1) Panel/plot kayit defteri (register/unregister, bkz. panelManager.py)
      2) Ref3'teki PlotController.ensure_handlers() ile AYNI global mouse/
         klavye handler'lari (hover, wheel zoom, sol/orta/sag surukleme,
         sag/orta/sol tik, cift tik, key press/release) - SADECE event
         URETIYOR (_emit/_emitKeyEvent -> _lastEvent + _eventLog kuyrugu).
         "src'deki event'i yakalayip bagli diger kontrollere uygulama"
         kurgusu (onTick icinde) HENUZ yazilmadi - bilerek NO-OP. Shift ile
         Y kilidi / Space ile adjust-Y de bu yuzden BILINCLI disarida
         birakildi (bunlar event URETMEZ, dogrudan diger plotlari
         DEGISTIRIR - yani "uygulama" kurgusunun bir parcasi, sonraki adim).
      3) Event YAKALAMA (_emit, list.append) ile BASMA (onTick/flushEventLog,
         konsola I/O) BILINCLI ayrildi - ardisik wheel/click event'lerinde
         her event'te hemen print yapmak frame'i yavaslatiyordu. hover event'i
         AYRICA hic _eventLog'a eklenmez (log=False) - cok yuksek frekansta
         tetiklenip diger event'leri log'da bogar, ama _lastEvent/getLastEvent
         ile HER ZAMAN okunabilir.

    Event'in SAHIBI (hangi panel) kendi hit-test'imizle DEGIL, PanelManager'in
    zaten var olan 'aktif panel' takibinden (bkz. setPanelManager,
    panelManager.getActivePanelId) okunur - topPanelGroupBox1'deki 'Active
    Panel' gostergesiyle AYNI kaynak, iki yerde ayni sorun COZULMEZ."""

    HANDLER_REGISTRY_TAG = "interaction_manager_handler_registry"
    X_AXIS_BAND = 40.0  # Ref3'teki plot_controller.py ile ayni: alt serit (X ekseni etiketleri)
    Y_AXIS_BAND = 55.0  # sol serit (Y ekseni etiketleri)

    def __init__(self):
        self._panels = {}  # panelId -> {"panelId", "plotId", "xAxis", "yAxis"}
        self._panelManager = None  # bkz. setPanelManager - event sahibi PanelManager'in aktif panelinden okunur
        self._lastEvent = None
        self._rightSelectionPanelId = None
        self._middlePanPanelId = None
        self._eventSequence = 0  # her _emit/_emitKeyEvent'te 1 artan, event'leri siraya koymak icin
        self._eventLog = []  # emit() ANINDA basilmayan, kuyruklanan event'ler (bkz. onTick/flushEventLog)
        self.PRINT_FORMATTED = False  # True -> satir-sutun tablo, False -> tek satir (bkz. _printEvent)

    def setPrintFormatted(self, formatted):
        self.PRINT_FORMATTED = bool(formatted)

    def setPanelManager(self, panelManager):
        """Event'in sahibini (hangi panel) PanelManager'in ZATEN var olan
        'aktif panel' takibinden (getActivePanelId) okumak icin gerekli.
        Boylece topPanelGroupBox1'deki 'Active Panel' gostergesiyle AYNI
        kaynak kullanilir - burada AYRI bir hit-test kurulmadi."""
        self._panelManager = panelManager

    # ------------------------------------------------------------- kayit
    def registerPanel(self, panelId, plotId, xAxis, yAxis):
        """Bir panel/plot cifti olusturulup PanelManager'a eklendiginde cagrilir."""
        self._panels[panelId] = {
            "panelId": panelId,
            "plotId": plotId,
            "xAxis": xAxis,
            "yAxis": yAxis,
        }

    def unregisterPanel(self, panelId):
        """Bir panel silindiginde cagrilir."""
        self._panels.pop(panelId, None)

    def getLastEvent(self):
        return self._lastEvent

    # ------------------------------------------------------------- yasam dongusu
    def ensureHandlers(self):
        """Global mouse handler'larini (idempotent) kurar - Ref3'teki
        PlotController.ensure_handlers() ile ayni handler seti."""
        if dpg.does_item_exist(self.HANDLER_REGISTRY_TAG):
            return
        with dpg.handler_registry(tag=self.HANDLER_REGISTRY_TAG):
            dpg.add_mouse_move_handler(callback=self._onMouseMove)
            dpg.add_mouse_wheel_handler(callback=self._onMouseWheel)
            dpg.add_mouse_drag_handler(button=dpg.mvMouseButton_Left, threshold=1.0,
                                      callback=self._onLeftMouseDrag)
            dpg.add_mouse_drag_handler(button=dpg.mvMouseButton_Middle, threshold=1.0,
                                      callback=self._onMiddleMouseDrag)
            dpg.add_mouse_drag_handler(button=dpg.mvMouseButton_Right, threshold=1.0,
                                      callback=self._onRightMouseDrag)
            dpg.add_mouse_down_handler(button=dpg.mvMouseButton_Right,
                                     callback=self._onRightMouseDown)
            dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Right,
                                         callback=self._onRightMouseRelease)
            dpg.add_mouse_down_handler(button=dpg.mvMouseButton_Middle,
                                     callback=self._onMiddleMouseDown)
            dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Middle,
                                         callback=self._onMiddleMouseRelease)
            dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Left,
                                       callback=self._onLeftMouseClick)
            dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Middle,
                                       callback=self._onMiddleMouseClick)
            dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Right,
                                       callback=self._onRightMouseClick)
            dpg.add_mouse_double_click_handler(button=dpg.mvMouseButton_Left,
                                              callback=self._onMouseDoubleClick)
            # key parametresi VERILMEDI -> DPG HERHANGI bir tusa basilinca/
            # birakilinca tetikler (appData = tus kodu). Su an SADECE event
            # URETIYOR (Shift/Space gibi tuslara ozel bir "uygulama" - Y
            # kilidi/adjust-Y - HENUZ baglanmadi, bkz. sinif docstring'i).
            dpg.add_key_press_handler(callback=self._onKeyPress)
            dpg.add_key_release_handler(callback=self._onKeyRelease)

    def onTick(self):
        """Her frame (merkezi render dongusunden) cagrilir. Su an SADECE
        kuyruklanan event log'unu basiyor (bkz. flushEventLog) - ileride
        _lastEvent'i (src) yakalayip bagli diger kontrollere uygulama
        kurgusu da BURAYA eklenecek."""
        self.flushEventLog()

    def flushEventLog(self):
        """_eventLog'da BIRIKEN (emit aninda basilmayan) event'leri simdi
        basar ve kuyrugu bosaltir. Event YAKALAMA (_emit/_emitKeyEvent,
        sadece list.append) ile BASMA (burada, konsola/Console panele I/O)
        BILINCLI olarak ayrildi: hizli ardisik wheel/click event'lerinde
        her event'te hemen print yapmak frame'i yavaslatip DPG/GLFW
        tarafinda ardisik event'lerin TEK bir delta'ya birlesip (coalesce)
        KAYBOLMASINA yol aciyordu - artik yakalama an'inda hicbir I/O yok,
        basma toplu ve frame'in sonunda oldugu icin girdi isleme bloklanmiyor."""
        if not self._eventLog:
            return
        for event in self._eventLog:
            fields = self.KEY_EVENT_PRINT_FIELDS if "keyCode" in event else self.EVENT_PRINT_FIELDS
            self._printEvent(event, fields, formatted=self.PRINT_FORMATTED)
        self._eventLog.clear()

    # ------------------------------------------------------------- handler'lar
    def _onMouseMove(self, sender, appData):
        """Hover event'inin uretim kaynagi - log=False: _lastEvent'e yazilir
        (getLastEvent() ile okunabilir) ama _eventLog'a EKLENMEZ, yani
        flushEventLog() bunu YAZDIRMAZ. mouse_move her piksel hareketinde
        tetiklendigi icin (cok yuksek frekans) konsola basmak hem gereksiz
        hem de diger event'leri bogar."""
        self._emit("hover", self._getPanelUnderMouse(), sender, appData, log=False)

    def _onMouseWheel(self, sender, appData):
        panelInfo = self._getPanelUnderMouse()
        if panelInfo is None:
            return
        scope = self._getZoomScope(panelInfo)
        direction = "in" if appData > 0 else "out"
        self._emit(f"zoom_{scope}_{direction}", panelInfo, sender, appData)

    def _onLeftMouseDrag(self, sender, appData):
        self._emit(self._panActionFromDelta("pan"), self._getPanelUnderMouse(), sender, appData)

    def _onMiddleMouseDrag(self, sender, appData):
        panelInfo = self._panels.get(self._middlePanPanelId) or self._getPanelUnderMouse()
        self._emit(self._panActionFromDelta("middle_pan"), panelInfo, sender, appData)

    def _onRightMouseDrag(self, sender, appData):
        self._emit("box_zoom_drag", self._getPanelUnderMouse(), sender, appData)

    def _onRightMouseDown(self, sender, appData):
        panelInfo = self._getPanelUnderMouse()
        self._rightSelectionPanelId = panelInfo["panelId"] if panelInfo else None
        self._emit("right_press", panelInfo, sender, appData)

    def _onRightMouseRelease(self, sender, appData):
        panelInfo = self._panels.get(self._rightSelectionPanelId) or self._getPanelUnderMouse()
        self._emit("right_release", panelInfo, sender, appData)
        if self._rightSelectionPanelId is not None:
            self._emit("box_selection", panelInfo, sender, appData)
        self._rightSelectionPanelId = None

    def _onMiddleMouseDown(self, sender, appData):
        panelInfo = self._getPanelUnderMouse()
        self._middlePanPanelId = panelInfo["panelId"] if panelInfo else None
        self._emit("middle_button_down", panelInfo, sender, appData)

    def _onMiddleMouseRelease(self, sender, appData):
        panelInfo = self._panels.get(self._middlePanPanelId)
        self._emit("middle_button_release", panelInfo, sender, appData)
        self._middlePanPanelId = None

    def _onMiddleMouseClick(self, sender, appData):
        self._emit("middle_click", self._getPanelUnderMouse(), sender, appData)

    def _onRightMouseClick(self, sender, appData):
        self._emit("right_click", self._getPanelUnderMouse(), sender, appData)

    def _onLeftMouseClick(self, sender, appData):
        self._emit("click", self._getPanelUnderMouse(), sender, appData)

    def _onMouseDoubleClick(self, sender, appData):
        self._emit("double_click", self._getPanelUnderMouse(), sender, appData)

    def _onKeyPress(self, sender, appData):
        if self._isRealKeyboardKey(appData):
            self._emitKeyEvent("key_press", appData)

    def _onKeyRelease(self, sender, appData):
        if self._isRealKeyboardKey(appData):
            self._emitKeyEvent("key_release", appData)

    def _isRealKeyboardKey(self, keyCode):
        """DPG'nin (modern Dear ImGui) BIRLESIK ImGuiKey enum'unda mouse
        tuslari/tekeri/gamepad de klavye tuslariyla AYNI ID uzayinda -
        `key` filtresi VERMEDEN kurulan add_key_press/release_handler bu
        yuzden mouse scroll/click'te de tetikleniyor (ornegin sol tik ->
        MouseLeft, tekerlek -> MouseWheelY, hepsi 630'dan (son isimlendirilen
        gercek klavye tusu, mvKey_Browser_Forward) SONRAKI kodlarda). Bu
        sozde-tuslari elemek icin sadece isimlendirilmis klavye araligini
        (<= mvKey_Browser_Forward) gecerli sayiyoruz."""
        return keyCode is not None and keyCode <= dpg.mvKey_Browser_Forward

    # ------------------------------------------------------------- event uretimi
    def _emit(self, action, panelInfo, sender, appData, log=True):
        if panelInfo is None:
            return
        x, y = self._getPlotMousePos()
        event = {
            "eventId": self._nextEventId(),
            "action": action,
            "panelId": panelInfo["panelId"],
            "plotId": panelInfo["plotId"],
            "xAxis": panelInfo["xAxis"],
            "yAxis": panelInfo["yAxis"],
            "region": self._getHoveredRegion(panelInfo),
            "sender": sender,
            "appData": appData,
            "frame": dpg.get_frame_count(),
            "x": x,
            "y": y,
            "xBar": None if x is None else int(round(x)),
            "yBar": None if y is None else int(round(y)),
            "xAxisLimits": self._getAxisLimits(panelInfo["xAxis"]),
            "yAxisLimits": self._getAxisLimits(panelInfo["yAxis"]),
            "screenRect": self._getItemScreenRect(panelInfo["plotId"]),
        }
        self._lastEvent = event
        if log:
            self._eventLog.append(event)

    def _emitKeyEvent(self, action, keyCode):
        """Mouse event'lerinden farkli: bir panele/plota BAGLI DEGIL (klavye
        etkilesimi mouse'un hangi panelde oldugundan bagimsizdir), bu yuzden
        panelInfo/x/y/eksen alanlari yok - sadece tus kodu + frame."""
        event = {
            "eventId": self._nextEventId(),
            "action": action,
            "keyCode": keyCode,
            "frame": dpg.get_frame_count(),
        }
        self._lastEvent = event
        self._eventLog.append(event)

    # Basilirken hangi alan hangi sirada gorunecek (satir-sutun hizali tablo).
    EVENT_PRINT_FIELDS = (
        "eventId", "action", "panelId", "plotId", "region", "frame",
        "x", "y", "xBar", "yBar",
        "xAxisLimits", "yAxisLimits", "screenRect",
    )
    KEY_EVENT_PRINT_FIELDS = ("eventId", "action", "keyCode", "frame")

    def _nextEventId(self):
        self._eventSequence += 1
        return self._eventSequence

    def _printEvent(self, event, fields, formatted=True):
        """formatted=True -> her alan kendi satirinda, hizali satir-sutun
        tablo. formatted=False -> tek satirda, kisa ozet."""
        if formatted:
            label = "InteractionManager event"
            print(f"[{label}] " + "-" * (40 - len(label)))
            for field in fields:
                print(f"  {field:<12}: {event.get(field)}")
        else:
            summary = ", ".join(f"{field}={event.get(field)}" for field in fields)
            print(f"[InteractionManager] {summary}")

    def _getAxisLimits(self, axis):
        if not dpg.does_item_exist(axis):
            return None
        try:
            limits = dpg.get_axis_limits(axis)
        except (KeyError, SystemError, Exception):
            return None
        if limits is None or len(limits) < 2:
            return None
        return float(limits[0]), float(limits[1])

    def _getItemScreenRect(self, item):
        if not dpg.does_item_exist(item):
            return None
        try:
            minPos = dpg.get_item_rect_min(item)
            maxPos = dpg.get_item_rect_max(item)
        except (KeyError, SystemError, Exception):
            return None
        return tuple(minPos), tuple(maxPos)

    def _getPlotMousePos(self):
        """Mouse'un GUNCEL plot-veri koordinatlarini (x,y) dondurur - Ref3'teki
        RangeController/PlotController._get_plot_mouse_pos ile ayni. Mouse bir
        plot uzerinde degilse (veya DPG henuz hesaplamadiysa) (None, None)."""
        try:
            pos = dpg.get_plot_mouse_pos()
        except SystemError:
            return None, None
        if pos is None or len(pos) < 2:
            return None, None
        return float(pos[0]), float(pos[1])

    def _panActionFromDelta(self, prefix):
        deltaX, deltaY = self._getMouseDragDelta()
        if abs(deltaX) >= abs(deltaY):
            direction = "right" if deltaX > 0 else "left"
        else:
            direction = "bottom" if deltaY > 0 else "up"
        return f"{prefix}_{direction}"

    def _getMouseDragDelta(self):
        try:
            delta = dpg.get_mouse_drag_delta()
        except SystemError:
            return 0.0, 0.0
        if isinstance(delta, (list, tuple)) and len(delta) >= 2:
            return float(delta[0]), float(delta[1])
        return 0.0, 0.0

    def _getZoomScope(self, panelInfo):
        return {"xAxis": "x", "yAxis": "y", "plot": "xy"}[self._getRectRegion(panelInfo)]

    def _getRectRegion(self, panelInfo):
        """Mouse'un panelin plot rect'inde HANGI SERITTE oldugunu (alt=xAxis,
        sol=yAxis, ortadaki govde=plot) SADECE rect+mouse pos ile bulur.
        is_item_hovered(xAxis/yAxis) KULLANILMAZ - mvPlotAxis item'lari
        "hovered" durumunu HIC TAKIP ETMIYOR, KeyError firlatiyordu (bkz.
        eski _isItemHovered fix'i) - bu daha basit rect yontemi hem crash
        riskini ortadan kaldirir hem de zoom scope ile ayni mantigi kullanir."""
        plotId = panelInfo["plotId"]
        try:
            minX, minY = dpg.get_item_rect_min(plotId)
            maxX, maxY = dpg.get_item_rect_max(plotId)
            mouseX, mouseY = dpg.get_mouse_pos(local=False)
        except (KeyError, SystemError, Exception):
            return "plot"
        if mouseY >= maxY - self.X_AXIS_BAND:
            return "xAxis"
        if mouseX <= minX + self.Y_AXIS_BAND:
            return "yAxis"
        return "plot"

    def _getHoveredRegion(self, panelInfo):
        return self._getRectRegion(panelInfo)

    def _getPanelUnderMouse(self):
        """Event'in sahibi paneli PanelManager'in ZATEN var olan 'aktif panel'
        takibinden okur (bkz. setPanelManager/panelManager.getActivePanelId) -
        burada AYRI bir hit-test/is_item_hovered dongusu KURULMADI. Boylece
        topPanelGroupBox1'deki 'Active Panel' gostergesiyle AYNI kaynak
        kullanilir, iki yerde ayni "kim aktif" sorusu COZULMEZ."""
        if self._panelManager is None:
            return None
        panelId = self._panelManager.getActivePanelId()
        if panelId is None:
            return None
        return self._panels.get(panelId)
