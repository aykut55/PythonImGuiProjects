import dearpygui.dearpygui as dpg


class LeftMenuPanel:
    """Sol navigasyon penceresi. Ref3'teki LeftMenu karsiligi: "Panels" agaci
    (panel -> panele atanmis data'lar). Pool artik burada DEGIL - Symbols/
    Sembol/Grup dallari alt alta sigmadigi icin ayri, bagimsiz bir pencereye
    (PoolPanel, DataManager gibi kullanici acip kapatiyor) tasindi.

    ScriptPanel gibi bagimsiz bir pencere ama guiManager tarafindan
    leftPanel slotuna gomulu gosterilir: gorunurse centerPanel sagdan
    daralir, kapanirsa centerPanel sola genisler."""

    TAG = "left_menu_panel"
    TREE_CONTAINER = "left_menu_tree_container"
    TREE_ROOT = "left_menu_tree_root"
    ADD_FROM_POOL_WINDOW = "left_menu_add_from_pool_window"
    ADD_FROM_POOL_LIST = "left_menu_add_from_pool_list"
    ADD_FROM_POOL_TARGET = "left_menu_add_from_pool_target"
    ADD_PANEL_WINDOW = "left_menu_add_panel_window"
    ADD_PANEL_NAME = "left_menu_add_panel_name"
    ADD_PANEL_CAPTION = "left_menu_add_panel_caption"
    ADD_PANEL_HEIGHT = "left_menu_add_panel_height"

    def __init__(self):
        self._visible = True  # ScriptPanel gibi acilista gorunur
        self._onCloseCallback = None
        self._panelManager = None  # bkz. setPanelManager (guiManager tarafindan baglanir)
        self._poolDataManager = None
        self._onAddPoolItemToPanel = None
        self._addPoolTargetPanelId = None
        self._addPoolLabelToId = {}
        self._lastTreeSignature = None  # sync()'in "degisti mi" kontrolu icin

    def setPanelManager(self, panelManager):
        self._panelManager = panelManager

    def setPoolDataManager(self, poolDataManager):
        self._poolDataManager = poolDataManager

    def setAddPoolItemCallback(self, callback):
        self._onAddPoolItemToPanel = callback

    def build(self, x, y, width, height, onClose=None):
        self._onCloseCallback = onClose
        with dpg.window(label="Left Menu", tag=self.TAG, pos=(x, y),
                        width=width, height=height, show=self._visible,
                        on_close=self._onClose):
            dpg.add_text("Panels")
            dpg.add_separator()
            with dpg.child_window(width=-1, height=-1, border=True, tag=self.TREE_CONTAINER):
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
            with dpg.popup(self.TREE_ROOT, mousebutton=dpg.mvMouseButton_Right):
                dpg.add_text("Panels")
                dpg.add_separator()
                dpg.add_menu_item(label="Add Panel...",
                                  callback=self._onAddPanelClicked)
                dpg.add_menu_item(label="Delete All Panels",
                                  callback=self._onDeleteAllPanelsClicked)
            for panel in self._panelManager.iterateAllPanels():
                panelTag = f"left_menu_panel_node_{panel.id}"
                with dpg.tree_node(label=panel.name, tag=panelTag, default_open=True):
                    with dpg.popup(panelTag, mousebutton=dpg.mvMouseButton_Right):
                        dpg.add_text(panel.name)
                        dpg.add_separator()
                        dpg.add_menu_item(
                            label="Add Data From Pool...",
                            callback=self._onAddFromPoolClicked,
                            user_data=panel.id)
                        dpg.add_menu_item(
                            label="Delete Panel",
                            callback=self._onDeletePanelClicked,
                            user_data=panel.id)
                    for data in panel.iterateAllData():
                        dataTag = f"left_menu_data_{panel.id}_{data.id}"
                        dpg.add_text(f"{data.name} ({data.id}) [{data.dataType}]",
                                     tag=dataTag)
                        with dpg.popup(dataTag, mousebutton=dpg.mvMouseButton_Right):
                            dpg.add_text(data.name)
                            dpg.add_separator()
                            dpg.add_menu_item(
                                label="Delete",
                                callback=self._onDeleteDataClicked,
                                user_data=(panel.id, data.id))

    def refresh(self):
        """buildTree() ile ayni - tek isim altinda tutmak icin (script tarafi
        gm.leftMenuPanel.refresh() cagirmaya devam edebilsin)."""
        self.buildTree()

    def _onDeleteDataClicked(self, sender=None, appData=None, userData=None):
        if self._panelManager is None or userData is None:
            return
        panelId, dataId = userData
        panel = self._panelManager.getPanel(panelId)
        if panel is None:
            return
        panel.deleteData(dataId)
        self._panelManager.drawPanelData(panelId)
        self._lastTreeSignature = None
        self.refresh()

    def _onAddFromPoolClicked(self, sender=None, appData=None, userData=None):
        if userData is None:
            return
        self._addPoolTargetPanelId = userData
        self._openAddFromPoolWindow(userData)

    def _onAddPanelClicked(self, sender=None, appData=None, userData=None):
        self._openAddPanelWindow()

    def _openAddPanelWindow(self):
        nextIndex = len(list(self._panelManager.iterateAllPanels())) + 1 if self._panelManager else 1
        if dpg.does_item_exist(self.ADD_PANEL_WINDOW):
            dpg.delete_item(self.ADD_PANEL_WINDOW)

        with dpg.window(label="Add Panel", tag=self.ADD_PANEL_WINDOW,
                        modal=True, width=360, height=210,
                        no_saved_settings=True):
            dpg.add_input_text(label="Name", tag=self.ADD_PANEL_NAME,
                               default_value=f"Panel {nextIndex}", width=220)
            dpg.add_input_text(label="Caption", tag=self.ADD_PANEL_CAPTION,
                               default_value=f"Panel {nextIndex}", width=220)
            dpg.add_input_int(label="Height", tag=self.ADD_PANEL_HEIGHT,
                              default_value=200, min_value=60, width=120)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Add", width=90,
                               callback=self._onAddPanelConfirmed)
                dpg.add_button(label="Cancel", width=90,
                               callback=self._closeAddPanelWindow)

    def _onAddPanelConfirmed(self, sender=None, appData=None, userData=None):
        if self._panelManager is None:
            return
        name = dpg.get_value(self.ADD_PANEL_NAME) if dpg.does_item_exist(self.ADD_PANEL_NAME) else ""
        caption = dpg.get_value(self.ADD_PANEL_CAPTION) if dpg.does_item_exist(self.ADD_PANEL_CAPTION) else ""
        height = dpg.get_value(self.ADD_PANEL_HEIGHT) if dpg.does_item_exist(self.ADD_PANEL_HEIGHT) else 200
        name = (name or "Panel").strip()
        caption = (caption or name).strip()
        panel = self._panelManager.createPanel(name, caption)
        panel.setHeight(max(60, int(height or 200)))
        self._panelManager.addPanel(panel)
        self._panelManager.drawPanel(panel.id)
        self._panelManager.applyPanelOrder()
        self._lastTreeSignature = None
        self.refresh()
        self._closeAddPanelWindow()

    def _closeAddPanelWindow(self, sender=None, appData=None, userData=None):
        if dpg.does_item_exist(self.ADD_PANEL_WINDOW):
            dpg.delete_item(self.ADD_PANEL_WINDOW)

    def _onDeletePanelClicked(self, sender=None, appData=None, userData=None):
        if self._panelManager is None or userData is None:
            return
        self._panelManager.deletePanel(userData)
        self._lastTreeSignature = None
        self.refresh()

    def _onDeleteAllPanelsClicked(self, sender=None, appData=None, userData=None):
        if self._panelManager is None:
            return
        self._panelManager.deleteAllPanels()
        self._lastTreeSignature = None
        self.refresh()

    def _openAddFromPoolWindow(self, panelId):
        panel = self._panelManager.getPanel(panelId) if self._panelManager else None
        items = list(self._poolDataManager.iterateAllItems()) if self._poolDataManager else []
        self._addPoolLabelToId = {}
        labels = []
        for item in items:
            label = f"{item.symbol or '-'} / {item.group} / {item.label} [{item.data.dataType}]"
            if label in self._addPoolLabelToId:
                label = f"{label} #{item.id}"
            self._addPoolLabelToId[label] = item.id
            labels.append(label)

        if dpg.does_item_exist(self.ADD_FROM_POOL_WINDOW):
            dpg.delete_item(self.ADD_FROM_POOL_WINDOW)

        with dpg.window(label="Add From Pool", tag=self.ADD_FROM_POOL_WINDOW,
                        modal=True, width=520, height=360,
                        no_saved_settings=True):
            dpg.add_text(f"Target: {panel.name if panel else panelId}",
                         tag=self.ADD_FROM_POOL_TARGET)
            dpg.add_separator()
            dpg.add_listbox(
                labels,
                tag=self.ADD_FROM_POOL_LIST,
                width=-1,
                num_items=12,
                default_value=labels[0] if labels else "")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Add", width=90,
                               callback=self._onAddSelectedPoolItem)
                dpg.add_button(label="Cancel", width=90,
                               callback=self._closeAddFromPoolWindow)

    def _onAddSelectedPoolItem(self, sender=None, appData=None, userData=None):
        if self._onAddPoolItemToPanel is None or self._addPoolTargetPanelId is None:
            return
        selected = dpg.get_value(self.ADD_FROM_POOL_LIST) if dpg.does_item_exist(self.ADD_FROM_POOL_LIST) else ""
        poolItemId = self._addPoolLabelToId.get(selected)
        if not poolItemId:
            return
        self._onAddPoolItemToPanel(self._addPoolTargetPanelId, poolItemId)
        self._closeAddFromPoolWindow()

    def _closeAddFromPoolWindow(self, sender=None, appData=None, userData=None):
        if dpg.does_item_exist(self.ADD_FROM_POOL_WINDOW):
            dpg.delete_item(self.ADD_FROM_POOL_WINDOW)

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
        yansir."""
        signature = self._treeSignature()
        if signature != self._lastTreeSignature:
            self._lastTreeSignature = signature
            self.buildTree()

    def render(self):
        """GuiManager.render() tarafindan her frame cagrilir. sync()'e
        delege ediyor (bkz. sync() - sadece degisiklik varsa rebuild eder)."""
        self.sync()
