import dearpygui.dearpygui as dpg

from .consolePanel import ConsolePanel
from .dataManager import DataManager
from .leftMenuPanel import LeftMenuPanel
from .menuBar import MenuBar
from .panel import Panel
from .panelData import PanelData
from .panelManager import PanelManager
from .panelManagerWindow import PanelManagerWindow
from .poolDataManager import PoolDataManager
from .poolPanel import PoolPanel
from .scriptPanel import ScriptPanel
from ..trading.indicatorManager import IndicatorManager
from ..trading.stockDataReader import StockDataReader, FilterMode


class GuiManager:
    LAYOUT_ROOT = "layout_root"

    MARGIN = 7
    TOP_OFFSET = 40
    TOP_HEIGHT = 100
    BOTTOM_HEIGHT = 60
    LEFT_WIDTH = 300
    RIGHT_WIDTH = 520
    SAFETY_MARGIN = 20
    BOTTOM_LIFT = 20
    RIGHT_INSET = 16
    CONSOLE_HEIGHT = 261
    PANEL_PADDING = (10, 10)
    PANEL_TAGS = ("topPanel", "centerPanel", "bottomPanel")
    CENTER_TOP_HEIGHT = 150  # RangeSlider/HScrollBar icin ayrilan ust bant

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
        self.panelManager = PanelManager()
        self.leftMenuPanel.setPanelManager(self.panelManager)
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
        self.scriptPanel.set_globals(gm=self, pm=self.panelManager, pool=self.poolDataManager,
                                     Panel=Panel, PanelData=PanelData,
                                     StockDataReader=StockDataReader, FilterMode=FilterMode,
                                     IndicatorManager=IndicatorManager)
        self._renderLoopStarted = False
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
        self.panelManager.render()
        self.leftMenuPanel.render()
        self.panelManagerWindow.render()

    def sync(self):
        """Model<->UI senkronunu manuel tetiklemek icin (render() zaten her
        frame otomatik yapiyor)."""
        self.panelManager.sync()
        self.leftMenuPanel.sync()
        self.panelManagerWindow.sync()

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
            dpg.add_text("Top Panel")

        with dpg.child_window(tag="centerPanel", parent=self.LAYOUT_ROOT,
                              **geometry["centerPanel"]):
            with dpg.child_window(tag="centerTopPanel", width=-1, show=False,
                                  height=self.CENTER_TOP_HEIGHT, no_scrollbar=True):
                pass
            with dpg.child_window(tag="centerCenterPanel", width=-1, height=-1):
                pass

        with dpg.child_window(tag="bottomPanel", parent=self.LAYOUT_ROOT,
                              no_scrollbar=True, **geometry["bottomPanel"]):
            dpg.add_text("Bottom Panel")

        for tag in self.PANEL_TAGS:
            dpg.bind_item_theme(tag, self.panelTheme)
        dpg.bind_item_theme("centerTopPanel", self.panelTheme)
        dpg.bind_item_theme("centerCenterPanel", self.panelTheme)

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
