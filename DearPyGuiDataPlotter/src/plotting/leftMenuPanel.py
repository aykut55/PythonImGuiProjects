import dearpygui.dearpygui as dpg


class LeftMenuPanel:
    """Sol navigasyon penceresi. Ref3'teki LeftMenu karsiligi: "Panels" agaci
    (panel -> panele atanmis data'lar) + "Pool" agaci (Sembol > Grup > item,
    PoolDataManager'dan besleniyor).

    ScriptPanel gibi bagimsiz bir pencere ama guiManager tarafindan
    leftPanel slotuna gomulu gosterilir: gorunurse centerPanel sagdan
    daralir, kapanirsa centerPanel sola genisler."""

    TAG = "left_menu_panel"
    TREE_CONTAINER = "left_menu_tree_container"
    TREE_ROOT = "left_menu_tree_root"
    POOL_CONTAINER = "left_menu_pool_container"

    def __init__(self):
        self._visible = True  # ScriptPanel gibi acilista gorunur
        self._onCloseCallback = None
        self._panelManager = None  # bkz. setPanelManager (guiManager tarafindan baglanir)
        self._poolDataManager = None  # bkz. setPoolDataManager (guiManager tarafindan baglanir)
        self._lastTreeSignature = None  # sync()'in "degisti mi" kontrolu icin

    def setPanelManager(self, panelManager):
        self._panelManager = panelManager

    def setPoolDataManager(self, poolDataManager):
        self._poolDataManager = poolDataManager

    def build(self, x, y, width, height, onClose=None):
        self._onCloseCallback = onClose
        with dpg.window(label="Left Menu", tag=self.TAG, pos=(x, y),
                        width=width, height=height, show=self._visible,
                        on_close=self._onClose):
            dpg.add_text("Panels")
            dpg.add_separator()
            with dpg.child_window(width=-1, height=-180, border=True, tag=self.TREE_CONTAINER):
                pass
            dpg.add_separator()
            dpg.add_text("Pool")
            with dpg.child_window(width=-1, height=-1, border=True, tag=self.POOL_CONTAINER):
                pass
        self.buildTree()

    def buildTree(self):
        """Panels agacini (panel adi -> data adi/id) yeniden kurar. Her
        frame DEGIL, sadece model degistiginde (script/left menu aksiyonu)
        cagrilmasi beklenir - her frame cagrilirsa tree'nin acik/kapali
        durumu (expand state) surekli sifirlanir."""
        if not dpg.does_item_exist(self.TREE_CONTAINER):
            return
        dpg.delete_item(self.TREE_CONTAINER, children_only=True)
        if self._panelManager is None:
            return
        with dpg.tree_node(label="Panels", parent=self.TREE_CONTAINER,
                           tag=self.TREE_ROOT, default_open=True):
            for panel in self._panelManager.iterateAllPanels():
                with dpg.tree_node(label=panel.name, default_open=True):
                    for data in panel.iterateAllData():
                        dpg.add_text(f"{data.name} ({data.id}) [{data.dataType}]")

    def buildPool(self):
        """Pool agacini (Symbols > Sembol > Grup > item) yeniden kurar.
        buildTree() gibi her frame DEGIL, model degistiginde cagrilmasi
        beklenir. Birden fazla sembolun verisi/indikatorleri ayni anda
        pool'da olabilir - Symbols kok node'u onlari ayirt eder."""
        if not dpg.does_item_exist(self.POOL_CONTAINER):
            return
        dpg.delete_item(self.POOL_CONTAINER, children_only=True)
        if self._poolDataManager is None:
            return
        tree = {}
        for item in self._poolDataManager.iterateAllItems():
            tree.setdefault(item.symbol or "-", {}).setdefault(item.group, []).append(item)
        with dpg.tree_node(label="Symbols", parent=self.POOL_CONTAINER, default_open=True):
            for symbol, groups in tree.items():
                with dpg.tree_node(label=symbol, default_open=True):
                    for group, groupItems in groups.items():
                        with dpg.tree_node(label=group, default_open=True):
                            for item in groupItems:
                                dpg.add_text(item.label)

    def refresh(self):
        """buildTree() + buildPool() - tum sol menuyu tek cagriyla yeniler."""
        self.buildTree()
        self.buildPool()

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

    def _treeSignature(self):
        """Panels agacinin GUNCEL sekli icin ucuz bir "parmak izi": panel
        id'leri + her panelin data id'leri. Bu degismeden buildTree()'yi
        tekrar cagirmaya gerek yok (gereksiz rebuild = expand/collapse
        durumunun sifirlanmasi demek)."""
        if self._panelManager is None:
            return None
        return tuple(
            (p.id, tuple(d.id for d in p.iterateAllData()))
            for p in self._panelManager.iterateAllPanels()
        )

    def sync(self):
        """Panels agacini modelle (panelManager) OTOMATIK senkronlar - panel
        ya da data eklenince/silinince bir sonraki frame'de kendiliginden
        yansir. Pool ise BILEREK otomatik degil: panelden bagimsiz kalici
        bir havuz olmasi gerekiyor (panel silinse de pool'daki veri
        kaybolmamali) - pool.addItem/removeItem + buildPool() ile elle
        yonetilir (script/kullanici aksiyonu)."""
        signature = self._treeSignature()
        if signature != self._lastTreeSignature:
            self._lastTreeSignature = signature
            self.buildTree()

    def render(self):
        """GuiManager.render() tarafindan her frame cagrilir. sync()'e
        delege ediyor (bkz. sync() - sadece degisiklik varsa rebuild eder)."""
        self.sync()
