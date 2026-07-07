import dearpygui.dearpygui as dpg


class PoolPanel:
    """Bagimsiz (standalone) Pool penceresi. DataManager/ScriptPanel gibi
    kullanici acip kapatana kadar ekranda kalir, layout'taki hicbir slotu
    isgal etmez (centerPanel bundan etkilenmez). Onceden LeftMenuPanel'in
    icindeydi; Symbols/Sembol/Grup dallari alt alta sigmadigindan ayri
    pencereye tasindi.

    PoolDataManager'dan besleniyor: Symbols > Sembol > Grup ("Data" /
    "Indicators" / "Levels") > item."""

    TAG = "pool_panel_window"
    TREE_CONTAINER = "pool_panel_tree_container"

    def __init__(self):
        self._visible = False
        self._onCloseCallback = None
        self._poolDataManager = None  # bkz. setPoolDataManager (guiManager tarafindan baglanir)

    def setPoolDataManager(self, poolDataManager):
        self._poolDataManager = poolDataManager

    def build(self, x=0, y=0, width=420, height=600, onClose=None):
        self._onCloseCallback = onClose
        with dpg.window(label="Pool", tag=self.TAG, pos=(x, y),
                        width=width, height=height, show=self._visible,
                        on_close=self._onClose):
            with dpg.child_window(width=-1, height=-1, border=True, tag=self.TREE_CONTAINER):
                pass
        self.refresh()

    def refresh(self):
        """Pool agacini (Symbols > Sembol > Grup > item) yeniden kurar.
        Otomatik cagrilmiyor - script pool.addItem/clear yaptiktan sonra
        elle cagirmasi beklenir (bkz. scripts/default.py fillPool/run)."""
        if not dpg.does_item_exist(self.TREE_CONTAINER):
            return
        dpg.delete_item(self.TREE_CONTAINER, children_only=True)
        if self._poolDataManager is None:
            return
        tree = {}
        for item in self._poolDataManager.iterateAllItems():
            tree.setdefault(item.symbol or "-", {}).setdefault(item.group, []).append(item)
        with dpg.tree_node(label="Symbols", parent=self.TREE_CONTAINER, default_open=True):
            for symbol, groups in tree.items():
                with dpg.tree_node(label=symbol, default_open=True):
                    for group, groupItems in groups.items():
                        with dpg.tree_node(label=group, default_open=True):
                            for item in groupItems:
                                dpg.add_text(item.label)

    def _onClose(self):
        self._visible = False
        if self._onCloseCallback:
            self._onCloseCallback()

    def isVisible(self):
        return self._visible

    def toggle(self):
        self._visible = not self._visible
        if dpg.does_item_exist(self.TAG):
            dpg.configure_item(self.TAG, show=self._visible)

    def show(self):
        self._visible = True
        if dpg.does_item_exist(self.TAG):
            dpg.configure_item(self.TAG, show=True)

    def hide(self):
        self._visible = False
        if dpg.does_item_exist(self.TAG):
            dpg.configure_item(self.TAG, show=False)

    def setGeometry(self, x, y, width, height):
        if dpg.does_item_exist(self.TAG):
            dpg.set_item_pos(self.TAG, (x, y))
            dpg.set_item_width(self.TAG, width)
            dpg.set_item_height(self.TAG, height)
