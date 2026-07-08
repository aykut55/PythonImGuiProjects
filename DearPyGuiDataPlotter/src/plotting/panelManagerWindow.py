import math

import dearpygui.dearpygui as dpg

from .panel import Panel


class PanelManagerWindow:
    """Bagimsiz Panel Manager penceresi (Ref3'teki panelManagerWindow.py'den
    camelCase'e cevrilerek tasindi). PoolPanel/DataManager gibi kullanici acip
    kapatana kadar ekranda kalir, layout'ta hicbir slotu isgal etmez.

    Ref3'teki hali de zaten bir iskeletti: kontroller (panel ekle/sil,
    hide/show, order, data ops/hide/order, global data actions, view/range,
    pan) cizilir ama HICBIR EVENT BAGLI DEGILDI (RightPanel callback'leri
    None, pencerenin kendi callback satirlari yorumluydu). Bu port bunu
    adim adim gercek islevle dolduruyor:
      - Col1 (Add/Delete Panel), Col2 (Hide/Show Panel), Col3 (Panel Order),
        Data Ops/Hide-Show/Order ve Global Data Actions artik setPanelManager
        ile baglanan gercek PanelManager modelini okuyup degistiriyor. Data
        Ops'taki sinyal ureteci (Sin/Cos/.../Zigzag) gercek veri kaynagi
        degil - Panel Manager'i gercek veri olmadan test edebilmek icin
        Ref3'ten aynen tasindi.
      - View-Range / Pan Controls HALA placeholder/EVENT YOK - sirasi
        geldiginde eklenecek.

    Kullanim (guiManager tarafindan): setPanelManager(panelManager) +
    build(...) + menu 'Panel Manager' -> toggle().
    """

    TAG = "panel_manager_window"
    COL1_CONTAINER = "panel_manager_window_col1"
    COL2_CONTAINER = "panel_manager_window_col2"
    COL3_CONTAINER = "panel_manager_window_col3"
    DATA_OPS_CONTAINER = "panel_manager_window_data_ops"
    DATA_HIDE_SHOW_CONTAINER = "panel_manager_window_data_hide_show"
    DATA_ORDER_CONTAINER = "panel_manager_window_data_order"

    def __init__(self):
        self._visible = False
        self._onCloseCallback = None
        self._panelManager = None  # bkz. setPanelManager (guiManager tarafindan baglanir)
        self._lastPanelsSignature = None  # sync()'in "degisti mi" kontrolu icin
        self._panelOrderLabelMap = {}  # panel_order_listbox etiketi ("Panel {id}: {name}") -> panelId (bkz. _refreshPanelOrderListbox)
        self._dataPanelLabelMap = {}  # data_panel_combo/data_hide_panel_combo/data_order_panel_combo ortak etiket->panelId haritasi
        self._dataOrderLabelMap = {}  # data_order_listbox etiketi ("{dataId}: {name}") -> dataId
        self._dataIdCounters = {}  # panelId -> Data Ops'ta sonraki sentetik data id (bkz. _nextDataId)

    def setPanelManager(self, panelManager):
        self._panelManager = panelManager

    def build(self, x=0, y=0, width=700, height=1010, onClose=None):
        self._onCloseCallback = onClose

        with dpg.window(label="Panel Manager", tag=self.TAG, pos=(x, y),
                        width=width, height=height, show=self._visible,
                        on_close=self._onClose):
            with dpg.group(horizontal=True):
                dpg.add_text("Panel Manager")
                dpg.add_button(label="Read Panels", callback=self._onReadPanels)
            dpg.add_separator()

            with dpg.group(horizontal=True):
                with dpg.child_window(width=185, height=400, border=True, tag=self.COL1_CONTAINER):
                    self._buildCol1()
                with dpg.child_window(width=170, height=400, border=True, tag=self.COL2_CONTAINER):
                    self._buildCol2()
                with dpg.child_window(width=160, height=400, border=True, tag=self.COL3_CONTAINER):
                    self._buildCol3()

            with dpg.group(horizontal=True):
                with dpg.child_window(width=300, height=260, border=True, tag=self.DATA_OPS_CONTAINER):
                    self._buildDataOps()
                with dpg.child_window(width=170, height=260, border=True, tag=self.DATA_HIDE_SHOW_CONTAINER):
                    self._buildDataHideShow()
                with dpg.child_window(width=185, height=260, border=True, tag=self.DATA_ORDER_CONTAINER):
                    self._buildDataOrder()

            with dpg.child_window(width=-1, height=95, border=True):
                dpg.add_text("Global Data Actions")
                dpg.add_separator()
                with dpg.group(horizontal=True):
                    # Ref1'de de iki buton ayni islevi (_on_clear_all_data)
                    # yapiyordu - burada da ikisi ayni callback'e bagli.
                    dpg.add_button(label="Clear All Data", width=130, callback=self._onClearAllData)
                    dpg.add_button(label="Delete All Data", width=130, callback=self._onClearAllData)
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Hide All Data", width=130, callback=self._onHideAllDataGlobal)
                    dpg.add_button(label="Show All Data", width=130, callback=self._onShowAllDataGlobal)

            with dpg.child_window(width=-1, height=100, border=True):
                dpg.add_text("View / Range Controls")
                dpg.add_separator()
                viewModes = ["FitToScreen (Normal)", "FitToScreen (Wide)",
                             "FitToScreen (Ultra)", "Full Data", "Last N Data",
                             "First N Data", "Range"]
                with dpg.group(horizontal=True):
                    dpg.add_combo(tag="view_mode_combo", items=viewModes,
                                  default_value=viewModes[2], width=160)
                    # EVENT YOK. DPG: callback=self._onViewModeChanged
                    dpg.add_button(label="Apply", width=80)
                    # EVENT YOK. DPG: callback=self._onApplyView
                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="view_n_input", label="N",
                                       default_value="1000", width=80, show=False)
                    dpg.add_input_text(tag="view_n2_input", label="N2",
                                       default_value="2000", width=80, show=False)

            with dpg.child_window(width=-1, height=100, border=True):
                dpg.add_text("Pan Controls")
                dpg.add_separator()
                panModes = ["VisibleScreenWidth", "1 Bar", "10 Bar", "100 Bar",
                            "1000 Bar", "UserDefined"]
                with dpg.group(horizontal=True):
                    dpg.add_text("Pan Step")
                    dpg.add_combo(tag="pan_mode_combo", items=panModes,
                                  default_value=panModes[0], width=150)
                    # EVENT YOK. DPG: callback=self._onPanModeChanged
                    dpg.add_input_text(tag="pan_step_input", default_value="100",
                                       width=70, show=False)
                with dpg.group(horizontal=True):
                    # EVENT YOK. DPG: callback=lambda: self._onPan("home"/"left"/"right"/"end")
                    dpg.add_button(label="|< Basa", width=70)
                    dpg.add_button(label="<< Sol", width=70)
                    dpg.add_button(label="Sag >>", width=70)
                    dpg.add_button(label="Son >|", width=70)
                    dpg.add_text("", tag="pan_position_text")

    # --------------------------------------------------------- col1/col2 UI
    def _buildCol1(self):
        """Add/Delete Panel. Panel(id, name, caption) dogrudan kurulup
        panelManager.addPanel(panel) ile kaydediliyor (createPanel id'yi
        otomatik atadigi icin, formdaki elle-girilen ID'yi kullanabilmek
        icin Panel dogrudan insa edildi)."""
        dpg.add_text("Add New Panel")
        dpg.add_separator()
        dpg.add_input_int(label="ID", tag="new_panel_id", default_value=0, min_value=0, width=80)
        dpg.add_input_text(label="Name", tag="new_panel_name", default_value="Plot1", width=80)
        dpg.add_input_text(label="Caption", tag="new_panel_caption", default_value="", width=80)
        dpg.add_input_int(label="Width", tag="new_panel_width", default_value=-1, width=80)
        dpg.add_input_int(label="Height", tag="new_panel_height", default_value=300, width=80)
        dpg.add_spacer(height=6)
        dpg.add_button(label="Add Panel", callback=self._onAddPanel)

        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_text("Delete Panel")
        dpg.add_separator()
        dpg.add_combo(tag="delete_panel_combo", items=[], label="Panel ID", width=80)
        dpg.add_spacer(height=6)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Delete Panel", width=80, callback=self._onDeletePanel)
            dpg.add_button(label="Delete All", width=80, callback=self._onDeleteAllPanels)

    def _buildCol2(self):
        """Hide/Show Panel. Collapse/Expand All plot yuksekligini degistirdigi
        icin plot_controller'a ihtiyac duymuyor, baglandi. Adjust All Y ise
        gercekten bir plot etkilesim katmani (visible-x'e gore y-fit) istedigi
        icin bilerek EVENT YOK birakildi."""
        dpg.add_text("Hide / Show Panel")
        dpg.add_separator()
        dpg.add_text("Visible Panels")
        dpg.add_combo(tag="visible_panel_combo", items=[], label="Panel ID", width=80)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Hide", callback=self._onHidePanel)
            dpg.add_button(label="Hide All", callback=self._onHideAllPanels)
        dpg.add_spacer(height=6)
        dpg.add_text("Hidden Panels")
        dpg.add_combo(tag="hidden_panel_combo", items=[], label="Panel ID", width=80)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Show", callback=self._onShowPanel)
            dpg.add_button(label="Show All", callback=self._onShowAllPanels)
        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_text("All Plots")
        dpg.add_button(label="Collapse All Plots", width=-1, callback=self._onCollapseAllPlots)
        dpg.add_button(label="Expand All Plots", width=-1, callback=self._onExpandAllPlots)
        dpg.add_button(label="Adjust All Y", width=-1)
        # EVENT YOK. DPG: callback=self._onFitAllPlotsY (visible-x'e gore y-fit -
        # plot etkilesim katmani gerektiriyor, henuz yok)

    def _buildCol3(self):
        """Panel Order. Listbox etiketleri "Panel {id}: {name}" (Ref1 ile
        ayni format) - id'yi geri cikarmak icin string parse yerine
        _panelOrderLabelMap kullanilir (bkz. _refreshPanelOrderListbox)."""
        dpg.add_text("Panel Order")
        dpg.add_separator()
        dpg.add_listbox(tag="panel_order_listbox", items=[], width=150, num_items=8)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Up", width=50, callback=self._onMovePanelUp)
            dpg.add_button(label="Down", width=50, callback=self._onMovePanelDown)
        dpg.add_button(label="Apply", width=150, callback=self._onApplyPanelOrder)
        dpg.add_button(label="Reset Order", width=150, callback=self._onResetPanelOrder)

    # ------------------------------------------------------------ data ops UI
    def _buildDataOps(self):
        """Data Operations. Sin/Cos/Line/Square/Zigzag ureteci gercek veri
        DEGIL - panel/data akisini gercek StockData olmadan test etmek
        icin Ref3'ten aynen tasindi (bkz. _generateSignal)."""
        dpg.add_text("Data Operations")
        dpg.add_separator()
        dpg.add_combo(tag="data_panel_combo", items=[], label="Panel", width=120,
                      callback=lambda s, a: self._onDataPanelChanged())
        with dpg.group(horizontal=True):
            dpg.add_combo(tag="data_signal_combo", items=["Sin", "Cos", "Line", "Square", "Zigzag"],
                          label="Signal", default_value="Sin", width=120)
            dpg.add_spacer(width=10)
            dpg.add_button(label="Add All Data", callback=self._onAddDataAll)
        dpg.add_input_float(tag="signal_amplitude", label="Amplitude",
                            default_value=1.0, min_value=0.0, max_value=100.0,
                            format="%.2f", step=0.1, width=120)
        dpg.add_input_float(tag="signal_frequency", label="Frequency",
                            default_value=1.0, min_value=0.0, max_value=100.0,
                            format="%.2f", step=0.1, width=120)
        dpg.add_input_float(tag="signal_level", label="Level",
                            default_value=0.0, min_value=-100.0, max_value=100.0,
                            format="%.2f", step=0.1, width=120)
        dpg.add_spacer(height=6)
        dpg.add_button(label="Add Data", callback=self._onAddData)
        dpg.add_spacer(height=6)
        dpg.add_combo(tag="data_id_combo", items=[], label="Data ID", width=120)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Delete Data", width=90, callback=self._onDeleteData)
            dpg.add_button(label="Delete All", width=90, callback=self._onDeleteAllPanelData)

    def _buildDataHideShow(self):
        dpg.add_text("Data Hide / Show")
        dpg.add_separator()
        dpg.add_combo(tag="data_hide_panel_combo", items=[], label="Panel", width=100,
                      callback=lambda s, a: self._onDataHidePanelChanged())
        dpg.add_text("Visible Data")
        dpg.add_combo(tag="visible_data_combo", items=[], label="Data ID", width=100)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Hide Data", callback=self._onHideVisibleData)
            dpg.add_button(label="Hide All", callback=self._onHideAllPanelData)
        dpg.add_spacer(height=6)
        dpg.add_text("Hidden Data")
        dpg.add_combo(tag="hidden_data_combo", items=[], label="Data ID", width=100)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Show Data", callback=self._onShowHiddenData)
            dpg.add_button(label="Show All", callback=self._onShowAllHiddenData)

    def _buildDataOrder(self):
        """Data Order. Listbox etiketleri "{dataId}: {name}" -
        _dataOrderLabelMap ile geri id'ye cevrilir (Panel Order'daki
        _panelOrderLabelMap ile ayni desen)."""
        dpg.add_text("Data Order")
        dpg.add_separator()
        dpg.add_combo(tag="data_order_panel_combo", items=[], label="Panel", width=130,
                      callback=lambda s, a: self._onDataOrderPanelChanged())
        dpg.add_listbox(tag="data_order_listbox", items=[], width=-1, num_items=7)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Up", width=55, callback=self._onMoveDataUp)
            dpg.add_button(label="Down", width=55, callback=self._onMoveDataDown)
        dpg.add_button(label="Apply", width=-1, callback=self._onApplyDataOrder)
        dpg.add_button(label="Reset Order", width=-1, callback=self._onResetDataOrder)

    def _refreshPanelCombos(self):
        """delete_panel_combo/visible_panel_combo/hidden_panel_combo'yu
        panelManager'daki GUNCEL panel listesinden yeniden doldurur."""
        if self._panelManager is None:
            return
        panels = list(self._panelManager.iterateAllPanels())
        allIds = [str(p.id) for p in panels]
        visibleIds = [str(p.id) for p in panels if p.getVisible()]
        hiddenIds = [str(p.id) for p in panels if not p.getVisible()]
        if dpg.does_item_exist("delete_panel_combo"):
            dpg.configure_item("delete_panel_combo", items=allIds)
        if dpg.does_item_exist("visible_panel_combo"):
            dpg.configure_item("visible_panel_combo", items=visibleIds)
        if dpg.does_item_exist("hidden_panel_combo"):
            dpg.configure_item("hidden_panel_combo", items=hiddenIds)

    def _refreshPanelOrderListbox(self):
        """panel_order_listbox'i panelManager.getPanelOrder() sirasindan
        yeniden doldurur + label->id haritasini gunceller."""
        if self._panelManager is None:
            return
        items = []
        self._panelOrderLabelMap = {}
        for panelId in self._panelManager.getPanelOrder():
            panel = self._panelManager.getPanel(panelId)
            if panel is None:
                continue
            label = f"Panel {panel.id}: {panel.name}"
            items.append(label)
            self._panelOrderLabelMap[label] = panel.id
        if dpg.does_item_exist("panel_order_listbox"):
            dpg.configure_item("panel_order_listbox", items=items)

    def _selectedPanelOrderId(self):
        if not dpg.does_item_exist("panel_order_listbox"):
            return None
        return self._panelOrderLabelMap.get(dpg.get_value("panel_order_listbox"))

    # -------------------------------------------------------- data ops refresh
    def _panelLabel(self, panel):
        return f"Panel {panel.id}: {panel.name}"

    def _refreshDataPanelCombos(self):
        """data_panel_combo/data_hide_panel_combo/data_order_panel_combo -
        Data Ops/Hide-Show/Order'in ortak 'hangi panel' secicileri - GUNCEL
        panel listesinden doldurulur. Secili deger listede kalmadiysa ilk
        panele dusurulur (Ref1'deki _refresh_data_panel_combo ile ayni)."""
        if self._panelManager is None:
            return
        panels = list(self._panelManager.iterateAllPanels())
        labels = [self._panelLabel(p) for p in panels]
        self._dataPanelLabelMap = {self._panelLabel(p): p.id for p in panels}
        for tag in ("data_panel_combo", "data_hide_panel_combo", "data_order_panel_combo"):
            if not dpg.does_item_exist(tag):
                continue
            dpg.configure_item(tag, items=labels)
            if labels and dpg.get_value(tag) not in labels:
                dpg.set_value(tag, labels[0])
            elif not labels:
                dpg.set_value(tag, "")

    def _selectedDataPanelId(self, comboTag):
        if not dpg.does_item_exist(comboTag):
            return None
        return self._dataPanelLabelMap.get(dpg.get_value(comboTag))

    def _refreshDataIdCombo(self):
        """Data Ops'taki data_id_combo'yu data_panel_combo'da secili panelin
        GUNCEL data listesinden doldurur."""
        panel = self._selectedDataPanel("data_panel_combo")
        ids = [str(d.id) for d in panel.iterateAllData()] if panel else []
        if dpg.does_item_exist("data_id_combo"):
            dpg.configure_item("data_id_combo", items=ids)
            dpg.set_value("data_id_combo", ids[-1] if ids else "")

    def _refreshDataHideShowCombos(self):
        """visible_data_combo/hidden_data_combo'yu data_hide_panel_combo'da
        secili panelin data'sinin GUNCEL gorunurlugune (PanelData.isVisible)
        gore ikiye bolup doldurur."""
        panel = self._selectedDataPanel("data_hide_panel_combo")
        visible = [str(d.id) for d in panel.iterateAllData() if d.isVisible] if panel else []
        hidden = [str(d.id) for d in panel.iterateAllData() if not d.isVisible] if panel else []
        if dpg.does_item_exist("visible_data_combo"):
            dpg.configure_item("visible_data_combo", items=visible)
            dpg.set_value("visible_data_combo", visible[0] if visible else "")
        if dpg.does_item_exist("hidden_data_combo"):
            dpg.configure_item("hidden_data_combo", items=hidden)
            dpg.set_value("hidden_data_combo", hidden[0] if hidden else "")

    def _refreshDataOrderListbox(self):
        """data_order_listbox'i data_order_panel_combo'da secili panelin
        GUNCEL dataList sirasindan doldurur + label->dataId haritasini
        gunceller."""
        panel = self._selectedDataPanel("data_order_panel_combo")
        items = []
        self._dataOrderLabelMap = {}
        if panel is not None:
            for d in panel.iterateAllData():
                label = f"{d.id}: {d.name}"
                items.append(label)
                self._dataOrderLabelMap[label] = d.id
        if dpg.does_item_exist("data_order_listbox"):
            dpg.configure_item("data_order_listbox", items=items)

    def _selectedDataPanel(self, comboTag):
        pid = self._selectedDataPanelId(comboTag)
        return self._panelManager.getPanel(pid) if (self._panelManager and pid is not None) else None

    def _selectedDataOrderId(self):
        if not dpg.does_item_exist("data_order_listbox"):
            return None
        return self._dataOrderLabelMap.get(dpg.get_value("data_order_listbox"))

    def _selectDataOrderId(self, dataId):
        for label, did in self._dataOrderLabelMap.items():
            if did == dataId:
                dpg.set_value("data_order_listbox", label)
                return

    def _nextDataId(self, panelId):
        """Data Ops'un sentetik sinyal verileri icin panel basina artan bir
        id uretir (panelId*100+1'den baslar, model/scriptten gelen mevcut
        id'lerle CAKISMAYACAK sekilde ilerletilir). Ref1'deki
        _next_panel_data_id ile ayni fikir."""
        panel = self._panelManager.getPanel(panelId) if self._panelManager else None
        existing = {d.id for d in panel.iterateAllData()} if panel else set()
        nextId = self._dataIdCounters.get(panelId, panelId * 100 + 1)
        while nextId in existing:
            nextId += 1
        self._dataIdCounters[panelId] = nextId + 1
        return nextId

    def _generateSignal(self, signalType, xs):
        amp = dpg.get_value("signal_amplitude")
        freq = dpg.get_value("signal_frequency")
        lvl = dpg.get_value("signal_level")
        if signalType == "Sin":
            return [amp * math.sin(x * freq) for x in xs]
        if signalType == "Cos":
            return [amp * math.cos(x * freq) for x in xs]
        if signalType == "Line":
            return [lvl for _ in xs]
        if signalType == "Square":
            return [amp if math.sin(x * freq) >= 0 else -amp for x in xs]
        if signalType == "Zigzag":
            return [amp * (((x * freq) % (2 * math.pi)) / (2 * math.pi) * 2 - 1) for x in xs]
        return xs

    # ----------------------------------------------------------- toplu yenile
    def _refreshAll(self):
        """Col1/Col2/Col3 + Data Ops/Hide-Show/Order'in TAMAMINI tek cagriyla
        yeniler - 'Read Panels' butonu ve HERHANGI bir mutasyon callback'i
        bunu cagirir (Ref1'in refresh_ui() deseniyle ayni: kismi refresh
        yerine hepsini birden tazelemek, panel silinince data combo'larinin
        bayat kalmasi gibi capraz baglantili unutulmalari onler)."""
        self._refreshPanelCombos()
        self._refreshPanelOrderListbox()
        self._refreshDataPanelCombos()
        self._refreshDataIdCombo()
        self._refreshDataHideShowCombos()
        self._refreshDataOrderListbox()

    def _panelsSignature(self):
        """sync()'in 'degisti mi' kontrolu icin: panel gorunurlugu + gorunum
        sirasi + HER panelin data listesi (id+visible). Data listesi de
        dahil oldugundan script'ten eklenen/silinen/gizlenen data da bir
        sonraki frame'de yakalanir."""
        if self._panelManager is None:
            return None
        panels = list(self._panelManager.iterateAllPanels())
        visibility = tuple(sorted((p.id, p.getVisible()) for p in panels))
        order = tuple(self._panelManager.getPanelOrder())
        dataSignature = tuple(
            (p.id, tuple((d.id, d.isVisible) for d in p.iterateAllData()))
            for p in panels
        )
        return (visibility, order, dataSignature)

    # ------------------------------------------------------------ callback'ler
    def _onAddPanel(self):
        if self._panelManager is None:
            return
        panelId = dpg.get_value("new_panel_id")
        name = dpg.get_value("new_panel_name")
        caption = dpg.get_value("new_panel_caption")
        panel = Panel(panelId, name, caption)
        panel.setWidth(dpg.get_value("new_panel_width"))
        panel.setHeight(dpg.get_value("new_panel_height"))
        self._panelManager.addPanel(panel)
        self._refreshAll()

    def _onDeletePanel(self):
        sel = dpg.get_value("delete_panel_combo")
        if self._panelManager is None or not sel:
            return
        self._panelManager.deletePanel(int(sel))
        self._refreshAll()

    def _onDeleteAllPanels(self):
        if self._panelManager is None:
            return
        self._panelManager.deleteAllPanels()
        self._refreshAll()

    def _onHidePanel(self):
        sel = dpg.get_value("visible_panel_combo")
        if self._panelManager is None or not sel:
            return
        self._panelManager.hidePanel(int(sel))
        self._refreshAll()

    def _onHideAllPanels(self):
        if self._panelManager is None:
            return
        self._panelManager.hideAllPanels()
        self._refreshAll()

    def _onShowPanel(self):
        sel = dpg.get_value("hidden_panel_combo")
        if self._panelManager is None or not sel:
            return
        self._panelManager.showPanel(int(sel))
        self._refreshAll()

    def _onShowAllPanels(self):
        if self._panelManager is None:
            return
        self._panelManager.showAllPanels()
        self._refreshAll()

    def _onCollapseAllPlots(self):
        if self._panelManager is None:
            return
        self._panelManager.collapseAllPanels()

    def _onExpandAllPlots(self):
        if self._panelManager is None:
            return
        self._panelManager.expandAllPanels()

    def _onMovePanelUp(self):
        panelId = self._selectedPanelOrderId()
        if self._panelManager is None or panelId is None:
            return
        self._panelManager.swapPanelUp(panelId)
        self._refreshPanelOrderListbox()

    def _onMovePanelDown(self):
        panelId = self._selectedPanelOrderId()
        if self._panelManager is None or panelId is None:
            return
        self._panelManager.swapPanelDown(panelId)
        self._refreshPanelOrderListbox()

    def _onApplyPanelOrder(self):
        if self._panelManager is None:
            return
        self._panelManager.applyPanelOrder()

    def _onResetPanelOrder(self):
        if self._panelManager is None:
            return
        self._panelManager.resetPanelOrder()
        self._refreshPanelOrderListbox()

    # ---------------------------------------------------------- data ops CB
    def _onDataPanelChanged(self):
        self._refreshDataIdCombo()

    def _onAddData(self):
        panel = self._selectedDataPanel("data_panel_combo")
        if panel is None:
            return
        signal = dpg.get_value("data_signal_combo")
        xs = [i * 0.1 for i in range(200)]
        ys = self._generateSignal(signal, xs)
        dataId = self._nextDataId(panel.id)
        panel.addData(dataId, name=f"{signal}_{dataId}", dataType="line", xs=xs, ys=ys)
        self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    def _onAddDataAll(self):
        """TUM panellere, Data Ops'ta secili sinyal/parametrelerle bir data
        ekler (Ref1'in _on_add_data_all'i her zaman sabit Sin+Cos ekliyordu;
        burada tek bir tutarli davranis icin secili sinyal kullaniliyor)."""
        if self._panelManager is None:
            return
        signal = dpg.get_value("data_signal_combo")
        xs = [i * 0.1 for i in range(200)]
        ys = self._generateSignal(signal, xs)
        for panel in self._panelManager.iterateAllPanels():
            dataId = self._nextDataId(panel.id)
            panel.addData(dataId, name=f"{signal}_{dataId}", dataType="line", xs=xs, ys=ys)
            self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    def _onDeleteData(self):
        panel = self._selectedDataPanel("data_panel_combo")
        dataSel = dpg.get_value("data_id_combo")
        if panel is None or not dataSel:
            return
        panel.deleteData(int(dataSel))
        self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    def _onDeleteAllPanelData(self):
        panel = self._selectedDataPanel("data_panel_combo")
        if panel is None:
            return
        panel.deleteAllData()
        self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    # ------------------------------------------------------- data hide/show CB
    def _onDataHidePanelChanged(self):
        self._refreshDataHideShowCombos()

    def _onHideVisibleData(self):
        panel = self._selectedDataPanel("data_hide_panel_combo")
        dataSel = dpg.get_value("visible_data_combo")
        if panel is None or not dataSel:
            return
        panel.hideData(int(dataSel))
        self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    def _onShowHiddenData(self):
        panel = self._selectedDataPanel("data_hide_panel_combo")
        dataSel = dpg.get_value("hidden_data_combo")
        if panel is None or not dataSel:
            return
        panel.showData(int(dataSel))
        self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    def _onHideAllPanelData(self):
        panel = self._selectedDataPanel("data_hide_panel_combo")
        if panel is None:
            return
        panel.hideAllData()
        self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    def _onShowAllHiddenData(self):
        panel = self._selectedDataPanel("data_hide_panel_combo")
        if panel is None:
            return
        panel.showAllData()
        self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    # ----------------------------------------------------------- data order CB
    def _onDataOrderPanelChanged(self):
        self._refreshDataOrderListbox()

    def _onMoveDataUp(self):
        panel = self._selectedDataPanel("data_order_panel_combo")
        dataId = self._selectedDataOrderId()
        if panel is None or dataId is None:
            return
        panel.swapDataUp(dataId)
        self._refreshDataOrderListbox()
        self._selectDataOrderId(dataId)

    def _onMoveDataDown(self):
        panel = self._selectedDataPanel("data_order_panel_combo")
        dataId = self._selectedDataOrderId()
        if panel is None or dataId is None:
            return
        panel.swapDataDown(dataId)
        self._refreshDataOrderListbox()
        self._selectDataOrderId(dataId)

    def _onApplyDataOrder(self):
        """dataList'teki YENI sirayi plota yansitir (drawPanelData y_axis'i
        temizleyip panel.dataList sirasiyla yeniden cizer)."""
        panel = self._selectedDataPanel("data_order_panel_combo")
        if panel is None:
            return
        self._panelManager.drawPanelData(panel.id)

    def _onResetDataOrder(self):
        panel = self._selectedDataPanel("data_order_panel_combo")
        if panel is None:
            return
        panel.resetDataOrder()
        self._panelManager.drawPanelData(panel.id)
        self._refreshDataOrderListbox()

    def _onReadPanels(self):
        """'Read Panels' butonu: baska bir yerden (or. Script Panel) degismis
        olabilecek panel/data listesini zorla yeniden okur."""
        self._refreshAll()

    # ------------------------------------------------------- global data CB
    def _onClearAllData(self):
        """TUM panellerdeki TUM data'yi siler (Data Ops'taki 'panel basina'
        Delete All'in aksine, panel secimi gerekmez)."""
        if self._panelManager is None:
            return
        for panel in self._panelManager.iterateAllPanels():
            panel.deleteAllData()
            self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    def _onHideAllDataGlobal(self):
        if self._panelManager is None:
            return
        for panel in self._panelManager.iterateAllPanels():
            panel.hideAllData()
            self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    def _onShowAllDataGlobal(self):
        if self._panelManager is None:
            return
        for panel in self._panelManager.iterateAllPanels():
            panel.showAllData()
            self._panelManager.drawPanelData(panel.id)
        self._refreshAll()

    # ------------------------------------------------------------- periyodik
    def sync(self):
        """Panel + data listesini (bkz. _panelsSignature) modelle
        (panelManager) OTOMATIK senkronlar - LeftMenuPanel'deki desenle
        ayni: sadece degisiklik varsa kontrolleri yeniden doldurur (sinyal
        ayni ise gereksiz configure_item cagrisi yapmaz)."""
        signature = self._panelsSignature()
        if signature != self._lastPanelsSignature:
            self._lastPanelsSignature = signature
            self._refreshAll()

    def render(self):
        """GuiManager.render() tarafindan her frame cagrilir. sync()'e
        delege ediyor (bkz. sync())."""
        self.sync()

    def _onClose(self):
        self._visible = False
        if self._onCloseCallback:
            self._onCloseCallback()

    # ---- visibility -------------------------------------------------------
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
