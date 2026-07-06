import dearpygui.dearpygui as dpg

from .consolePanel import ConsolePanel
from .menuBar import MenuBar
from .scriptPanel import ScriptPanel


class GuiManager:
    LAYOUT_ROOT = "layout_root"

    MARGIN = 7
    TOP_OFFSET = 40
    TOP_HEIGHT = 100
    BOTTOM_HEIGHT = 60
    LEFT_WIDTH = 200
    RIGHT_WIDTH = 520
    SAFETY_MARGIN = 20
    BOTTOM_LIFT = 20
    RIGHT_INSET = 16
    CONSOLE_HEIGHT = 261
    PANEL_PADDING = (10, 10)
    PANEL_TAGS = ("topPanel", "leftPanel", "centerPanel", "bottomPanel")

    def __init__(self, configManager):
        self.configManager = configManager
        self.menuBar = MenuBar()
        self.scriptPanel = ScriptPanel()
        self.rightSlotPanels = [self.scriptPanel]
        self.consolePanel = ConsolePanel()
        self.consolePanel.attachStdout()
        self.scriptPanel.set_on_open_console(self.consolePanel.show)
        self.isDarkTheme = True
        self.lightTheme = self._buildLightTheme()
        self.panelTheme = self._buildPanelTheme()
        self.menuBar.set_callback(
            on_toggle_theme=self.toggleTheme,
            on_build_layout=self.buildLayout,
            on_destroy_layout=self.destroyLayout,
            on_toggle_script=self.toggleScript,
            on_toggle_console=self.consolePanel.toggle,
            on_command_query=self._onCommandQuery,
        )
        self.commands = [
            ("Toggle Dark/Light Theme", self.toggleTheme),
            ("Build Layout", self.buildLayout),
            ("Destroy Layout", self.destroyLayout),
            ("Toggle Script Panel", self.toggleScript),
            ("Toggle Console Panel", self.consolePanel.toggle),
        ]

    def build(self):
        with dpg.window(label="Ana Pencere", tag="main_window"):
            self.menuBar.build()
            dpg.add_group(tag=self.LAYOUT_ROOT)
        dpg.set_primary_window("main_window", True)
        dpg.bind_item_theme("main_window", self._buildMenuBarHeightTheme())

        consoleGeom = self._computeGeometry()["consolePanel"]
        self.consolePanel.build(*consoleGeom["pos"], consoleGeom["width"], consoleGeom["height"])

        self.buildLayout()

    def buildLayout(self, layoutId=0):
        self.destroyLayout()
        if layoutId == 0:
            self._buildLayoutDefault()
        else:
            raise ValueError(f"Bilinmeyen layoutId: {layoutId}")

    def destroyLayout(self):
        dpg.delete_item(self.LAYOUT_ROOT, children_only=True)
        for tag in (ScriptPanel.TAG, ScriptPanel.OPEN_DIALOG, ScriptPanel.SAVEAS_DIALOG):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)

    def _buildLayoutDefault(self):
        geometry = self._computeGeometry()

        with dpg.child_window(tag="topPanel", parent=self.LAYOUT_ROOT,
                              no_scrollbar=True, **geometry["topPanel"]):
            dpg.add_text("Top Panel")

        with dpg.child_window(tag="leftPanel", parent=self.LAYOUT_ROOT,
                              no_scrollbar=True, **geometry["leftPanel"]):
            dpg.add_text("Left Panel")

        with dpg.child_window(tag="centerPanel", parent=self.LAYOUT_ROOT,
                              **geometry["centerPanel"]):
            dpg.add_text("Center Panel")

        with dpg.child_window(tag="bottomPanel", parent=self.LAYOUT_ROOT,
                              no_scrollbar=True, **geometry["bottomPanel"]):
            dpg.add_text("Bottom Panel")

        for tag in self.PANEL_TAGS:
            dpg.bind_item_theme(tag, self.panelTheme)

        rightGeom = geometry["rightPanel"]
        self.scriptPanel.build(*rightGeom["pos"], rightGeom["width"], rightGeom["height"],
                               on_close=self._relayout)
        dpg.bind_item_theme(ScriptPanel.TAG, self.panelTheme)

        dpg.set_viewport_resize_callback(self._relayout)

    def _computeGeometry(self):
        vpW = dpg.get_viewport_width()
        vpH = dpg.get_viewport_height()

        topY = self.TOP_OFFSET
        middleY = topY + self.TOP_HEIGHT + self.MARGIN
        middleH = vpH - middleY - self.BOTTOM_HEIGHT - 2 * self.MARGIN - self.SAFETY_MARGIN - self.BOTTOM_LIFT
        bottomY = middleY + middleH + self.MARGIN

        appRightEdge = vpW - self.MARGIN - self.RIGHT_INSET
        fullWidth = appRightEdge - self.MARGIN

        centerX = self.MARGIN + self.LEFT_WIDTH + self.MARGIN
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
            panel.set_geometry(*rightGeom["pos"], rightGeom["width"], rightGeom["height"])

        consoleGeom = geometry["consolePanel"]
        self.consolePanel.setGeometry(*consoleGeom["pos"], consoleGeom["width"], consoleGeom["height"])

    def toggleScript(self):
        self.scriptPanel.toggle()
        self._relayout()

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
        return any(panel.is_visible() for panel in self.rightSlotPanels)

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
