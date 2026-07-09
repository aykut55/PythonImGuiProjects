import dearpygui.dearpygui as dpg

from .consolePanel import ConsolePanel
from .dataManager import DataManager
from .interactionManager import InteractionManager
from .leftMenuPanel import LeftMenuPanel
from .menuBar import MenuBar
from .panel import Panel
from .panelData import PanelData
from .panelManager import PanelManager
from .panelManagerWindow import PanelManagerWindow
from .poolDataManager import PoolDataManager
from .poolPanel import PoolPanel
from .rangeSliderBar import RangeSliderBar
from .scriptPanel import ScriptPanel
from ..trading.indicatorManager import IndicatorManager
from ..trading.stockDataReader import StockDataReader, FilterMode


class GuiManager:
    LAYOUT_ROOT = "layout_root"

    MARGIN = 7
    TOP_OFFSET = 40
    TOP_HEIGHT = 135  # topPanelGroupBox3'teki ayrac+2 buton satiri+durum metni digerlerinden fazla yer istedigi icin artirildi (scrollbar cikiyordu)
    BOTTOM_HEIGHT = 60
    LEFT_WIDTH = 300
    RIGHT_WIDTH = 520
    SAFETY_MARGIN = 20
    BOTTOM_LIFT = 20
    RIGHT_INSET = 16
    CONSOLE_HEIGHT = 261
    PANEL_PADDING = (10, 10)
    PANEL_TAGS = ("topPanel", "centerPanel", "bottomPanel")
    CENTER_TOP_HEIGHT = 190  # RangeSlider/HScrollBar icin ayrilan ust bant (scrollbar kirpilmiyordu, artirildi)

    # top_view_n_input/top_view_n2_input BIRDEN FAZLA mod tarafindan
    # PAYLASILIYOR (DataManager'daki n1/n2 gibi) - hangi modun hangi
    # alani kullandigi + alan->tag eslesmesi (bkz. _saveTopViewModeValues/
    # _restoreTopViewModeValues/seedTopViewRangeInputs).
    TOP_VIEW_MODE_FIELDS = {
        "Last N Data": ("n",),
        "First N Data": ("n",),
        "Range": ("n", "n2"),
    }
    TOP_VIEW_FIELD_TAGS = {"n": "top_view_n_input", "n2": "top_view_n2_input"}

    def __init__(self, configManager):
        self.configManager = configManager
        self.menuBar = MenuBar()
        self.scriptPanel = ScriptPanel()
        self.dataManager = DataManager()
        # DataManager rightSlotPanels'te DEGIL: kullanici onu istedigi yere
        # surukleyebilsin diye, sadece ilk build'de config'teki baslangic
        # konumunu alir; ScriptPanel/ConsolePanel gibi viewport resize'da
        # zorla eski konumuna geri alinmaz (bkz. _relayout).
        self.rightSlotPanels = [self.scriptPanel]
        self.leftMenuPanel = LeftMenuPanel()
        # LeftMenuPanel ScriptPanel'in aynadaki hali: gorunurse centerPanel
        # sagdan daralir (leftPanel slotu isgal edilir), kapanirsa centerPanel
        # sola genisler (bkz. _isLeftSlotOccupied / _computeGeometry).
        self.leftSlotPanels = [self.leftMenuPanel]
        self.consolePanel = ConsolePanel()
        self.consolePanel.attachStdout()
        self.scriptPanel.set_on_open_console(self.consolePanel.show)
        self.scriptPanel.set_on_run_complete(self.sync)
        self.panelManager = PanelManager()
        self.leftMenuPanel.setPanelManager(self.panelManager)
        # InteractionManager: panel/plot olusturulup PanelManager'a eklendiginde
        # register, silindiginde unregister olur (bkz. interactionManager.py).
        # ensureHandlers(): Ref3'teki PlotController ile ayni global mouse
        # handler'lari (wheel/pan/box-select/click/double-click) - SU AN SADECE
        # event URETIYOR (konsola yazdirir), diger kontrollere uygulama YOK.
        self.interactionManager = InteractionManager()
        self.panelManager.setInteractionManager(self.interactionManager)
        # Event sahibi (hangi panel) PanelManager'in ZATEN var olan aktif
        # panel takibinden (getActivePanelId) okunur - bkz. interactionManager.py.
        self.interactionManager.setPanelManager(self.panelManager)
        self.interactionManager.ensureHandlers()
        self.poolDataManager = PoolDataManager()
        # PoolPanel: DataManager gibi bagimsiz/floating bir pencere - hicbir
        # slotu isgal etmez, kullanici acip kapatana kadar ekranda kalir.
        # Symbols/Sembol/Grup dallari alt alta LeftMenuPanel'e sigmadigindan
        # ayri pencereye alindi.
        self.poolPanel = PoolPanel()
        self.poolPanel.setPoolDataManager(self.poolDataManager)
        # PanelManagerWindow: PoolPanel gibi bagimsiz/floating pencere - hicbir
        # slotu isgal etmez. Col1/2/3 + Data Ops/Hide-Show/Order gercek
        # panelManager modeline bagli; Global Data Actions/View-Range/Pan
        # Controls hala placeholder.
        self.panelManagerWindow = PanelManagerWindow()
        self.panelManagerWindow.setPanelManager(self.panelManager)
        # RangeSliderBar: centerTopPanel'e gomulu, SADECE gorsel iskelet
        # (bkz. rangeSliderBar.py) - pan/zoom'a baglanmadi.
        self.rangeSliderBar = RangeSliderBar()
        self.rangeSliderBar.setPanelManager(self.panelManager)
        self.scriptPanel.set_globals(gm=self, pm=self.panelManager, pool=self.poolDataManager,
                                     Panel=Panel, PanelData=PanelData,
                                     StockDataReader=StockDataReader, FilterMode=FilterMode,
                                     IndicatorManager=IndicatorManager)
        self._renderLoopStarted = False
        self._topViewModeValues = {}  # {mode: {field: value}} - bkz. seedTopViewRangeInputs/_saveTopViewModeValues
        self._lastTopViewMode = "FitToScreen (Normal)"  # _onTopViewModeChanged'in "cikilan mod" takibi
        self.isDarkTheme = True
        self.lightTheme = self._buildLightTheme()
        self.panelTheme = self._buildPanelTheme()
        self.menuBar.set_callback(
            on_toggle_theme=self.toggleTheme,
            on_build_layout=self.buildLayout,
            on_destroy_layout=self.destroyLayout,
            on_toggle_script=self.toggleScript,
            on_toggle_console=self.consolePanel.toggle,
            on_toggle_left_menu=self.toggleLeftMenu,
            on_toggle_pool=self.togglePoolPanel,
            on_manage_panels=self.togglePanelManagerWindow,
            on_manage_data=self.toggleDataManager,
            on_command_query=self._onCommandQuery,
        )
        self.commands = [
            ("Toggle Dark/Light Theme", self.toggleTheme),
            ("Build Layout", self.buildLayout),
            ("Destroy Layout", self.destroyLayout),
            ("Toggle Script Panel", self.toggleScript),
            ("Toggle Console Panel", self.consolePanel.toggle),
            ("Toggle Left Menu", self.toggleLeftMenu),
            ("Toggle Pool Panel", self.togglePoolPanel),
            ("Toggle Panel Manager Window", self.togglePanelManagerWindow),
            ("Toggle Data Manager", self.toggleDataManager),
        ]

    def build(self):
        with dpg.window(label="Ana Pencere", tag="main_window"):
            self.menuBar.build()
            dpg.add_group(tag=self.LAYOUT_ROOT)
        dpg.set_primary_window("main_window", True)
        dpg.bind_item_theme("main_window", self._buildMenuBarHeightTheme())

        c = self._panelInitialCoords("consolePanel")
        self.consolePanel.build(c["x"], c["y"], c["width"], c["height"])

        self.buildLayout()
        self._startRenderLoop()

    def _startRenderLoop(self):
        """Render dongusunu baslatir. Tekrar baslatilirsa (build() ikinci kez
        cagrilirsa) ust uste iki zincir olusmasin diye guard var."""
        if self._renderLoopStarted:
            return
        self._renderLoopStarted = True
        self._scheduleRenderLoop()

    def _scheduleRenderLoop(self):
        """self.render()'i her frame'de bir cagiran, kendini yeniden zamanlayan
        surekli dongu. Uygulama acik oldugu surece calisir."""
        dpg.set_frame_callback(dpg.get_frame_count() + 1, self._onRenderTick)

    def _onRenderTick(self):
        # try/except: render() icinde bir hata olursa dongu SESSIZCE durmasin
        # (hatayi konsola yaz, zincire devam et) - normal isleyis bozulmasin.
        try:
            self.render()
        except Exception:
            import traceback
            traceback.print_exc()
        self._scheduleRenderLoop()

    def render(self):
        """Her frame cagrilan ust-seviye render girisi. Su an alt bilesenlere
        delege ediyor; ileride baska bilesenler eklendikce buraya eklenir."""
        self.rangeSliderBar.render()
        self.panelManager.render()
        self.leftMenuPanel.render()
        self.panelManagerWindow.render()
        self._refreshActivePanelCombo()
        self._alignTopViewNRow()
        self.interactionManager.onTick()

    def sync(self):
        """Model<->UI senkronunu manuel tetiklemek icin (render() zaten her
        frame otomatik yapiyor)."""
        self.rangeSliderBar.sync()
        self.panelManager.sync()
        self.leftMenuPanel.sync()
        self.panelManagerWindow.sync()
        self._refreshActivePanelCombo()

    def _onActiveUpdateModeChanged(self, sender=None, appData=None):
        self.panelManager.setActiveUpdateMode((appData or "hover").lower())

    def _onTopViewModeChanged(self, sender=None, appData=None):
        """SADECE gorsel: secili moda gore N/N2 input'larini gosterir/gizler
        (Ref1'deki _on_view_mode_changed ile ayni). Apply butonuna henuz
        BAGLANMADI - x/y eksenine gercekten bir sey uygulamiyor.

        N/N2 kutulari Last N Data/First N Data/Range arasinda PAYLASILIYOR
        (DataManager'daki n1/n2 gibi) - mod degismeden ONCE cikilan modun
        degerini hafizaya alip (_saveTopViewModeValues), yeni modun
        hafizadaki degerini geri yukluyoruz (_restoreTopViewModeValues) ki
        kullanicinin girdigi deger baska bir moda gecince KAYBOLMASIN."""
        self._saveTopViewModeValues(self._lastTopViewMode)
        showN = appData in ("Last N Data", "First N Data", "Range")
        showN2 = appData == "Range"
        dpg.configure_item("top_view_n_input", show=showN)
        dpg.configure_item("top_view_n2_input", show=showN2)
        self._restoreTopViewModeValues(appData)
        self._lastTopViewMode = appData

    def _onTopPanModeChanged(self, sender=None, appData=None):
        """SADECE gorsel: 'UserDefined' secilince adim input'unu gosterir
        (Ref1'deki _on_pan_mode_changed ile ayni). Yon butonlarina henuz
        BAGLANMADI - gercekten pan/kaydirma yapmiyor."""
        dpg.configure_item("top_pan_step_input", show=(appData == "UserDefined"))

    def _onShowSliderRangeChanged(self, sender=None, appData=None):
        self.rangeSliderBar.setSliderVisible(bool(appData))

    def _onShowScrollBarChanged(self, sender=None, appData=None):
        self.rangeSliderBar.setScrollbarVisible(bool(appData))

    def _onShowInfoPanelChanged(self, sender=None, appData=None):
        self.panelManager.setInfoPanelMode("always" if appData else "hidden")

    def _onCrossHairModeChanged(self, sender=None, appData=None):
        self.panelManager.setCrossHairMode((appData or "all").lower())

    def _onReadSrcParams(self, sender=None, appData=None):
        params = self.panelManager.readPanelPlotParams()
        if not params:
            self._setStatusText("Read Params: no active panel")
            return
        self._setStatusText(
            f"Read Params: panel {params['panelId']} x={params['xAxisLimits']} y={params['yAxisLimits']}")

    def _onApplySrcParams(self, sender=None, appData=None):
        if not self.panelManager.getLastReadPlotParams():
            self._setStatusText("Apply Params: read source params first")
            return
        pending = self.interactionManager.scheduleSyncOthers()
        self._setStatusText(f"Apply Params: pending {pending} panel(s)")

    def _onAdjustYAxisSrc(self, sender=None, appData=None):
        panelId = self.panelManager.getActivePanelId()
        ok = self.panelManager.adjustYAxis(panelId)
        self._setStatusText(f"Adjusted Y: panel {panelId}" if ok else "Adjusted Y: no active panel")

    def _onAdjustYAxisAll(self, sender=None, appData=None):
        count = self.panelManager.adjustAllYAxes()
        self._setStatusText(f"Adjusted Y: {count} panels")

    def _onResetViewSrc(self, sender=None, appData=None):
        panelId = self.panelManager.getActivePanelId()
        ok = self.panelManager.resetPanelView(panelId)
        self._setStatusText(f"Reset View: panel {panelId}" if ok else "Reset View: no active panel")

    def _onResetViewAll(self, sender=None, appData=None):
        count = self.panelManager.resetAllPanelViews()
        self._setStatusText(f"Reset View: {count} panels")

    def _onAdjustXAxisAll(self, sender=None, appData=None):
        params = self.panelManager.readPanelPlotParams()
        if not params or not params.get("xAxisLimits"):
            self._setStatusText("Adjust X: no active source X")
            return
        pending = self.interactionManager.scheduleSyncOthers(params, mode="x")
        self._setStatusText(f"Adjust X: pending {pending} panel(s)")

    def _onAdjustAllAxes(self, sender=None, appData=None):
        # scheduleSyncOthers SADECE "diger" panellere uygular (src'ye dokunmaz -
        # zaten kendi parametrelerinde oldugu icin). Ama src'nin Y ekseni
        # kendi GUNCEL gorunur X araligina gore hic adjust edilmemis olabilir
        # (orn. pan sonrasi) - bu yuzden params okumadan ONCE src'nin Y'sini
        # adjust ediyoruz ki hem src'nin kendisi hem diger panellere yayilan
        # deger GUNCEL/dogru olsun.
        panelId = self.panelManager.getActivePanelId()
        self.panelManager.adjustYAxis(panelId)
        params = self.panelManager.readPanelPlotParams(panelId)
        if not params or not params.get("xAxisLimits"):
            self._setStatusText("Adjust All: no active source X")
            return
        pending = self.interactionManager.scheduleSyncOthers(params)
        self._setStatusText(f"Adjust All: pending {pending} panel(s)")

    def _onTopViewApply(self, sender=None, appData=None):
        pass

    def _onPanToStart(self, sender=None, appData=None):
        self._doPan("start")

    def _onPanLeft(self, sender=None, appData=None):
        self._doPan("left")

    def _onPanRight(self, sender=None, appData=None):
        self._doPan("right")

    def _onPanToEnd(self, sender=None, appData=None):
        self._doPan("end")

    def _doPan(self, direction):
        panelId = self.panelManager.getActivePanelId()
        mode = dpg.get_value("top_pan_mode_combo")
        step = dpg.get_value("top_pan_step_input")
        result = self.panelManager.panPanel(panelId, direction=direction, mode=mode, step=step)
        if result is None:
            self._setStatusText("Pan: no active panel")
            return
        xMin, xMax = result
        # Ref1'deki pan_view AYNI: HER pan yonunde (sadece Basa/Sona degil,
        # Sol/Sag'da da) gorunur X araligi degistigi icin Y ekseni de src
        # panele gore hemen adjust edilir (Adjust Y Axis (src) ile ayni
        # cagri) - kullanici ayrica butona basmak zorunda kalmasin.
        self.panelManager.adjustYAxis(panelId)
        # Scroll bar'i da yeni gorunur araliga gore guncelle (Ref1'deki
        # _update_pan_indicator ile ayni fikir).
        self.rangeSliderBar.syncScrollToView(panelId)
        barCount = self.panelManager.getPanelDataCount(panelId)
        offset = max(0, round(xMin))
        end = min(barCount, round(xMax)) if barCount > 0 else round(xMax)
        self._setStatusText(f"[{offset} - {end}] / {barCount}")

    def _setStatusText(self, text):
        if dpg.does_item_exist("bottom_status_text"):
            dpg.set_value("bottom_status_text", text)

    def _saveTopViewModeValues(self, mode):
        fields = self.TOP_VIEW_MODE_FIELDS.get(mode, ())
        if not fields:
            return
        values = self._topViewModeValues.setdefault(mode, {})
        for field in fields:
            tag = self.TOP_VIEW_FIELD_TAGS[field]
            if dpg.does_item_exist(tag):
                values[field] = dpg.get_value(tag)

    def _restoreTopViewModeValues(self, mode):
        values = self._topViewModeValues.get(mode)
        if not values:
            return
        for field, value in values.items():
            tag = self.TOP_VIEW_FIELD_TAGS[field]
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, value)

    def seedTopViewRangeInputs(self, barCount):
        """View/Range moduna gore sensible varsayilanlari yazar: Last N
        Data/First N Data -> 1000, Range -> 0..barCount. DataManager'daki
        _seedReadModeInputs ile AYNI fikir: SADECE data yuklendikten sonra
        BIR KEZ (scripts/default.py'den) cagrilmasi beklenir - duz combo
        mod degisimi bunu ASLA tetiklemez, kullanicinin sonradan girdigi
        deger boylece korunur. Reset/yeniden yukleme = bu yeniden cagrilir."""
        barCount = int(barCount or 0)
        self._topViewModeValues = {
            "Last N Data": {"n": 1000},
            "First N Data": {"n": 1000},
            "Range": {"n": 0, "n2": barCount},
        }
        currentMode = dpg.get_value("top_view_mode_combo") if dpg.does_item_exist("top_view_mode_combo") else ""
        self._restoreTopViewModeValues(currentMode)

    def _alignTopViewNRow(self):
        """top_view_n_row'u (N/N2 kutulari) top_view_mode_combo ile SOLDAN
        hizalar. Her frame GuiManager.render()'dan cagrilir (once bir kerelik
        dpg.set_frame_callback denendi ama GuiManager._scheduleRenderLoop
        de AYNI frame numarasina kendi callback'ini kaydettigi icin DPG'nin
        'frame basina tek callback' kisitlamasinda bizimki eziliyordu - bu
        yuzden zaten her frame calisan render() dongusune tasindi).

        X: top_view_mode_combo'nun GERCEK x konumu (dpg.get_item_pos).
        Y: top_view_row1'in (View / Range + combo + Apply satiri) GERCEK alt
        kenari (pos.y + rect_size.y) + kucuk bir bosluk - boylece satirlar
        UST USTE BINMEZ, N/N2 dogru sekilde bir alt satirda kalir."""
        if not (dpg.does_item_exist("top_view_mode_combo")
                and dpg.does_item_exist("top_view_n_row")
                and dpg.does_item_exist("top_view_row1")):
            return
        comboX = dpg.get_item_pos("top_view_mode_combo")[0]
        row1Y = dpg.get_item_pos("top_view_row1")[1]
        row1H = dpg.get_item_rect_size("top_view_row1")[1]
        dpg.set_item_pos("top_view_n_row", (comboX, row1Y + row1H + 4))

    def _refreshActivePanelCombo(self):
        """active_panel_plot_combo'yu panelManager'daki GUNCEL panel
        listesiyle + panelManager.getActivePanelId() ile GUNCEL aktif
        panelle senkronlar. Combo'ya callback BAGLANMADI - kullanicinin
        elle sectigi bir deger bir sonraki bu cagrida GERI YAZILIR, yani
        bu SADECE bir gosterge, aktif paneli degistirmek icin kullanilamaz
        (Hover/Click modunu bypass etmez)."""
        panels = list(self.panelManager.iterateAllPanels())
        labels = [f"Panel {p.id}: {p.name}" for p in panels] or ["None"]
        activeId = self.panelManager.getActivePanelId()
        activeLabel = next((f"Panel {p.id}: {p.name}" for p in panels if p.id == activeId),
                           "None")
        if dpg.does_item_exist("active_panel_plot_combo"):
            dpg.configure_item("active_panel_plot_combo", items=labels)
            dpg.set_value("active_panel_plot_combo", activeLabel)

    def buildLayout(self, layoutId=0):
        self.destroyLayout()
        if layoutId == 0:
            self._buildLayoutDefault()
        else:
            raise ValueError(f"Bilinmeyen layoutId: {layoutId}")

    def destroyLayout(self):
        dpg.delete_item(self.LAYOUT_ROOT, children_only=True)
        for tag in (ScriptPanel.TAG, ScriptPanel.OPEN_DIALOG, ScriptPanel.SAVEAS_DIALOG,
                   DataManager.TAG, DataManager.FILE_DIALOG, DataManager.TREE_HANDLER,
                   DataManager.KEY_HANDLER, LeftMenuPanel.TAG, PoolPanel.TAG,
                   PanelManagerWindow.TAG):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)

    def _buildLayoutDefault(self):
        geometry = self._computeGeometry()

        with dpg.child_window(tag="topPanel", parent=self.LAYOUT_ROOT,
                              no_scrollbar=True, **geometry["topPanel"]):
            # Ref3'teki drawTopPanel() gibi yan yana grup-box'lar (child_window,
            # border=True) halinde kurgulanacak - once tek kutu (topPanelGroupBox1),
            # gorsel olarak onaylaninca digerleri eklenecek.
            with dpg.group(horizontal=True):
                with dpg.child_window(tag="topPanelGroupBox1", width=350, height=-1, border=True):
                    # Ref3'teki drawTopPanel() 1. satirinin denenen yerlesimi:
                    # "Active Panel [byCombo] [Combobox]" - UCU AYNI satirda.
                    with dpg.group(horizontal=True):
                        dpg.add_text("Active Panel")
                        dpg.add_combo(tag="active_update_mode_combo", items=["Hover", "Click"],
                                     default_value="Click", width=90,
                                     callback=self._onActiveUpdateModeChanged)
                        # callback YOK: bu combo SADECE gosterge - itemlari/
                        # secili degeri her frame _refreshActivePanelCombo()
                        # tarafindan panelManager'daki GERCEK aktif panele
                        # gore yazilir; kullanicinin elle secim yapmasi
                        # aktif paneli DEGISTIRMEZ (Hover/Click'i bypass etmez).
                        dpg.add_combo(tag="active_panel_plot_combo", items=["None"],
                                     default_value="None", width=150)
                    # Ref3'teki drawTopPanel() 4. satiri: View / Range.
                    # SADECE GORSEL - Apply butonu bilerek EVENT YOK (henuz
                    # baglanmadi). Tek istisna: mode combosunun N/N2 input'lari
                    # gosterip gizlemesi (Ref1'deki _on_view_mode_changed ile
                    # ayni davranis) - "combo degisince nasil gorunuyor" testi.
                    #
                    # "View / Range" etiketinin SAGINDA (ayni satirda) combo+Apply;
                    # N/N2 bir ALTTAKI satirda. Konum PIKSEL TAHMINI DEGIL -
                    # her frame combo'nun GERCEK x'i + bu satirin GERCEK
                    # alt kenari olculup otomatik uygulanir (bkz. _alignTopViewNRow,
                    # GuiManager.render()'dan cagrilir).
                    with dpg.group(horizontal=True, tag="top_view_row1"):
                        dpg.add_text("View / Range")
                        topViewModes = ["FitToScreen (Normal)", "FitToScreen (Wide)",
                                       "FitToScreen (Ultra)", "Full Data", "Last N Data",
                                       "First N Data", "Range"]
                        dpg.add_combo(tag="top_view_mode_combo", items=topViewModes,
                                     default_value=topViewModes[0], width=150,
                                     callback=self._onTopViewModeChanged)
                        dpg.add_button(label="Apply", width=60,
                                       callback=self._onTopViewApply)
                    with dpg.group(horizontal=True, tag="top_view_n_row", pos=(0, 0)):
                        dpg.add_input_int(tag="top_view_n_input", label="N", step=0,
                                         default_value=0, width=70, show=False)
                        dpg.add_input_int(tag="top_view_n2_input", label="N2", step=0,
                                         default_value=0, width=70, show=False)

                with dpg.child_window(tag="topPanelGroupBox2", width=340, height=-1, border=True):
                    # Ref3'teki drawTopPanel() 5. satiri: Pan Controls.
                    # SADECE GORSEL - yon butonlarina (|< Basa/<< Sol/Sag >>/
                    # Son >|) bilerek EVENT YOK. Tek istisna: mode combosunun
                    # "UserDefined" secilince adim input'unu gostermesi
                    # (View/Range'deki N/N2 testiyle ayni fikir).
                    with dpg.group(horizontal=True, tag="top_pan_row1"):
                        dpg.add_text("Pan Controls")
                        panModes = ["VisibleScreenWidth", "1 Bar", "10 Bar",
                                   "100 Bar", "1000 Bar", "UserDefined"]
                        dpg.add_combo(tag="top_pan_mode_combo", items=panModes,
                                     default_value=panModes[0], width=150,
                                     callback=self._onTopPanModeChanged)
                        dpg.add_input_int(tag="top_pan_step_input", step=0,
                                         default_value=100, width=70, show=False)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="|< Basa", width=70,
                                       callback=self._onPanToStart)
                        dpg.add_button(label="<< Sol", width=70,
                                       callback=self._onPanLeft)
                        dpg.add_button(label="Sag >>", width=70,
                                       callback=self._onPanRight)
                        dpg.add_button(label="Son >|", width=70,
                                       callback=self._onPanToEnd)

                with dpg.child_window(tag="topPanelGroupBox3", width=330, height=-1, border=True):
                    # Ref3'teki drawTopPanel() 3. satirinin bir kismi: Read Src
                    # Params / Apply Params To Other. Callback'ler BAGLANDI ama
                    # icleri BILEREK BOS (pass) - gercek eksen okuma-yazma
                    # mantigi henuz yok, sadece buton<->method baglantisi hazir.
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Read Params (src)", width=140,
                                       callback=self._onReadSrcParams)
                        dpg.add_button(label="Apply Params (dst)", width=140,
                                       callback=self._onApplySrcParams)
                    # Ref3'teki drawTopPanel() 6. satiri: Adjust Src Y / Adjust
                    # All Y Axes. Callback'ler BAGLANDI ama icleri BILEREK BOS
                    # (pass) - "Adjust All Y" fikri zaten PanelManagerWindow'da
                    # da placeholder olarak var, tag cakismasin diye buradakiler
                    # "top_" onekiyle.
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Adjust Y Axis (src)", width=140,
                                       callback=self._onAdjustYAxisSrc)
                        dpg.add_button(label="Adjust Y Axis (all)", width=140,
                                       callback=self._onAdjustYAxisAll)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Reset Src", width=140,
                                       callback=self._onResetViewSrc)
                        dpg.add_button(label="Adjust X Axes All", width=140,
                                       callback=self._onAdjustXAxisAll)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Reset All", width=140,
                                       callback=self._onResetViewAll)
                        dpg.add_button(label="Adjust All", width=140,
                                       callback=self._onAdjustAllAxes)
                    dpg.add_text("", tag="top_visible_window_text")

                with dpg.child_window(tag="topPanelGroupBox4", width=300, height=-1, border=True):
                    # RangeSliderBar'in (centerTopPanel'e gomulu) iki bagimsiz
                    # gorunurluk bayragini (bkz. rangeSliderBar.py setSliderVisible/
                    # setScrollbarVisible) buradan yonetir. Ikisi de default CHECKED.
                    with dpg.group(horizontal=True):
                        dpg.add_checkbox(label="Show SliderRange", tag="top_show_sliderange_checkbox",
                                         default_value=True, callback=self._onShowSliderRangeChanged)
                        dpg.add_text("CrossHair :")
                        dpg.add_combo(tag="top_crosshair_mode_combo", items=["Hidden", "Single", "All"],
                                     default_value="All", width=70,
                                     callback=self._onCrossHairModeChanged)
                    dpg.add_checkbox(label="Show ScrollBar", tag="top_show_scrollbar_checkbox",
                                     default_value=True, callback=self._onShowScrollBarChanged)
                    # panelManager.setInfoPanelMode ile ayni fikir: checked ->
                    # "always" (tum panellerde sabit gosterilir), unchecked ->
                    # "hidden" (hicbir panelde gosterilmez).
                    dpg.add_checkbox(label="Show InfoPanel(s)", tag="top_show_infopanel_checkbox",
                                     default_value=True, callback=self._onShowInfoPanelChanged)
        dpg.bind_item_theme("topPanelGroupBox1", self._buildCompactControlTheme())
        dpg.bind_item_theme("topPanelGroupBox2", self._buildCompactControlTheme())
        dpg.bind_item_theme("topPanelGroupBox3", self._buildCompactControlTheme())
        dpg.bind_item_theme("topPanelGroupBox4", self._buildCompactControlTheme())

        with dpg.child_window(tag="centerPanel", parent=self.LAYOUT_ROOT,
                              **geometry["centerPanel"]):
            with dpg.child_window(tag="centerTopPanel", width=-1, show=False,
                                  height=self.CENTER_TOP_HEIGHT, no_scrollbar=True):
                pass
            with dpg.child_window(tag="centerCenterPanel", width=-1, height=-1):
                pass

        with dpg.child_window(tag="bottomPanel", parent=self.LAYOUT_ROOT,
                              no_scrollbar=True, **geometry["bottomPanel"]):
            dpg.add_text("", tag="bottom_status_text")

        for tag in self.PANEL_TAGS:
            dpg.bind_item_theme(tag, self.panelTheme)
        dpg.bind_item_theme("centerTopPanel", self.panelTheme)
        dpg.bind_item_theme("centerCenterPanel", self.panelTheme)
        # RangeSliderBar panelTheme'den SONRA cizilip kendi (daha dar) dikey
        # padding temasini centerTopPanel'e baglar - boylece panelTheme'in
        # WindowPadding'i tarafindan EZILMEZ (bkz. rangeSliderBar.py).
        self.rangeSliderBar.build("centerTopPanel")

        s = self._panelInitialCoords("scriptPanel")
        self.scriptPanel.build(s["x"], s["y"], s["width"], s["height"],
                               on_close=self._relayout)
        dpg.bind_item_theme(ScriptPanel.TAG, self.panelTheme)

        d = self._panelInitialCoords("dataManager")
        self.dataManager.build(d["x"], d["y"], d["width"], d["height"],
                               onClose=self._relayout)
        dpg.bind_item_theme(DataManager.TAG, self.panelTheme)

        leftGeom = geometry["leftPanel"]
        self.leftMenuPanel.build(*leftGeom["pos"], leftGeom["width"], leftGeom["height"],
                                 onClose=self._relayout)
        dpg.bind_item_theme(LeftMenuPanel.TAG, self.panelTheme)

        # PoolPanel DataManager gibi bagimsiz/floating: hicbir slotu isgal
        # etmez, sadece ilk build'de config'teki baslangic konumunu alir.
        p = self._panelInitialCoords("poolPanel")
        self.poolPanel.build(p["x"], p["y"], p["width"], p["height"],
                             onClose=self._relayout)
        dpg.bind_item_theme(PoolPanel.TAG, self.panelTheme)

        # PanelManagerWindow da PoolPanel gibi bagimsiz/floating: hicbir
        # slotu isgal etmez, sadece ilk build'de config'teki baslangic
        # konumunu alir.
        pmw = self._panelInitialCoords("panelManagerWindow")
        self.panelManagerWindow.build(pmw["x"], pmw["y"], pmw["width"], pmw["height"],
                                      onClose=self._relayout)
        dpg.bind_item_theme(PanelManagerWindow.TAG, self.panelTheme)

        dpg.set_viewport_resize_callback(self._relayout)

    def _panelInitialCoords(self, panelName):
        panels = self.configManager.get("panels") or {}
        return panels.get(panelName, {}).get("initialCoordinates", {"x": 0, "y": 0, "width": 520, "height": 600})

    def _computeGeometry(self):
        vpW = dpg.get_viewport_width()
        vpH = dpg.get_viewport_height()

        topY = self.TOP_OFFSET
        middleY = topY + self.TOP_HEIGHT + self.MARGIN
        middleH = vpH - middleY - self.BOTTOM_HEIGHT - 2 * self.MARGIN - self.SAFETY_MARGIN - self.BOTTOM_LIFT
        bottomY = middleY + middleH + self.MARGIN

        appRightEdge = vpW - self.MARGIN - self.RIGHT_INSET
        fullWidth = appRightEdge - self.MARGIN

        if self._isLeftSlotOccupied():
            centerX = self.MARGIN + self.LEFT_WIDTH + self.MARGIN
        else:
            centerX = self.MARGIN
        rightX = vpW - self.RIGHT_WIDTH - self.MARGIN - self.RIGHT_INSET

        if self._isRightSlotOccupied():
            centerWidth = rightX - self.MARGIN - centerX
        else:
            centerWidth = appRightEdge - centerX

        scriptHeight = middleH - self.CONSOLE_HEIGHT - self.MARGIN
        consoleY = middleY + scriptHeight + self.MARGIN

        return {
            "topPanel": {"pos": (self.MARGIN, topY), "width": fullWidth, "height": self.TOP_HEIGHT},
            "leftPanel": {"pos": (self.MARGIN, middleY), "width": self.LEFT_WIDTH, "height": middleH},
            "centerPanel": {"pos": (centerX, middleY), "width": centerWidth, "height": middleH},
            "rightPanel": {"pos": (rightX, middleY), "width": self.RIGHT_WIDTH, "height": scriptHeight},
            "consolePanel": {"pos": (rightX, consoleY), "width": self.RIGHT_WIDTH, "height": self.CONSOLE_HEIGHT},
            "bottomPanel": {"pos": (self.MARGIN, bottomY), "width": fullWidth, "height": self.BOTTOM_HEIGHT},
        }

    def _relayout(self, *args):
        if not dpg.does_item_exist("topPanel"):
            return
        geometry = self._computeGeometry()
        for tag in self.PANEL_TAGS:
            rect = geometry[tag]
            dpg.set_item_pos(tag, rect["pos"])
            dpg.set_item_width(tag, rect["width"])
            dpg.set_item_height(tag, rect["height"])

        rightGeom = geometry["rightPanel"]
        for panel in self.rightSlotPanels:
            panel.setGeometry(*rightGeom["pos"], rightGeom["width"], rightGeom["height"])

        leftGeom = geometry["leftPanel"]
        for panel in self.leftSlotPanels:
            panel.setGeometry(*leftGeom["pos"], leftGeom["width"], leftGeom["height"])

        consoleGeom = geometry["consolePanel"]
        self.consolePanel.setGeometry(*consoleGeom["pos"], consoleGeom["width"], consoleGeom["height"])

    def toggleScript(self):
        self.scriptPanel.toggle()
        self._relayout()

    def toggleDataManager(self):
        self.dataManager.toggle()
        self._relayout()

    def toggleLeftMenu(self):
        self.leftMenuPanel.toggle()
        self._relayout()

    def togglePoolPanel(self):
        self.poolPanel.toggle()

    def togglePanelManagerWindow(self):
        self.panelManagerWindow.toggle()

    def _onCommandQuery(self, query):
        if dpg.does_item_exist("commandPaletteResults"):
            dpg.delete_item("commandPaletteResults")

        query = query.strip().lower()
        if not query:
            return

        matches = [(label, action) for label, action in self.commands if query in label.lower()]
        if not matches:
            return

        inputPos = dpg.get_item_rect_min("commandPaletteInput")
        inputHeight = dpg.get_item_rect_size("commandPaletteInput")[1]
        with dpg.window(tag="commandPaletteResults", no_title_bar=True, no_resize=True,
                        no_move=True, no_collapse=True, no_scrollbar=True,
                        pos=(inputPos[0], inputPos[1] + inputHeight + 2),
                        width=260, height=min(200, 24 * len(matches) + 10)):
            for label, action in matches:
                dpg.add_selectable(label=label, callback=self._runCommand(action))

    def _runCommand(self, action):
        def runner(sender=None, appData=None):
            action()
            dpg.set_value("commandPaletteInput", "")
            if dpg.does_item_exist("commandPaletteResults"):
                dpg.delete_item("commandPaletteResults")
        return runner

    def _isRightSlotOccupied(self):
        return any(panel.isVisible() for panel in self.rightSlotPanels)

    def _isLeftSlotOccupied(self):
        return any(panel.isVisible() for panel in self.leftSlotPanels)

    def _buildMenuBarHeightTheme(self):
        with dpg.theme() as menuBarHeightTheme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 11, category=dpg.mvThemeCat_Core)
            with dpg.theme_component(dpg.mvInputText):
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 11, category=dpg.mvThemeCat_Core)
        return menuBarHeightTheme

    def _buildPanelTheme(self):
        with dpg.theme() as panelTheme:
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, *self.PANEL_PADDING, category=dpg.mvThemeCat_Core)
        return panelTheme

    def _buildCompactControlTheme(self):
        """topPanel "main_window" altinda oldugu icin _buildMenuBarHeightTheme'in
        FramePadding=(8,11)'ini (mvAll) MIRAS ALIYOR - combo/buton gibi
        kontroller DataManager'daki (ayri, temasiz bir pencerede olan)
        gibi degil, gereksiz yere UZUN gorunuyordu. Bu tema FramePadding'i
        DPG'nin varsayilanina (4,3) dondurup topPanelGroupBox1 (ve
        cocuklarina) baglaniyor - DataManager'daki combo ile ayni yukseklik.

        mvInputText icin AYRICA ozel bir kural ekliyoruz: main_window'daki
        _buildMenuBarHeightTheme'in mvInputText'e ozel (10,11) kurali, mvAll'dan
        DAHA SPESIFIK oldugu icin mvAll'i EZIP input_text kutularini (top_view_n_input/
        top_view_n2_input) hala kalin gosteriyordu - buraya da ayni derecede
        spesifik bir mvInputText kurali eklemek gerekti (nearest-wins)."""
        with dpg.theme() as compactControlTheme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 4, 3, category=dpg.mvThemeCat_Core)
            with dpg.theme_component(dpg.mvInputText):
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 4, 3, category=dpg.mvThemeCat_Core)
        return compactControlTheme

    def _buildLightTheme(self):
        with dpg.theme() as lightTheme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (240, 240, 240), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (240, 240, 240), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (240, 240, 240), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_MenuBarBg, (225, 225, 225), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Text, (20, 20, 20), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Border, (170, 170, 170), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (255, 255, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (225, 225, 225), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (200, 200, 200), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (225, 225, 225), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (200, 200, 200), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Button, (225, 225, 225), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (205, 205, 205), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (185, 185, 185), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Header, (210, 210, 210), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (190, 190, 190), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (170, 170, 170), category=dpg.mvThemeCat_Core)
        return lightTheme

    def toggleTheme(self):
        if self.isDarkTheme:
            dpg.bind_theme(self.lightTheme)
        else:
            dpg.bind_theme(0)
        self.isDarkTheme = not self.isDarkTheme
