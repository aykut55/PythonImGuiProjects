import os
from datetime import datetime

import dearpygui.dearpygui as dpg

from ..trading.stockDataReader import StockDataReader, FilterMode


class DataManager:
    """Bagimsiz (standalone) Data Manager penceresi.

    Bir kok dizini tarar (Scan), altindaki market/period/symbol yapisini bir
    agac + combo'lara doldurur; secilen sembol/periyodun CSV'sini okur (Read).

    NOT: Bu surumde KENDI BASINA calisir. Okunan veriyi baska GUI kontrollerine
    (panel cizimi, data pool, sol agac) BASMAZ; Read yalnizca dosyayi okuyup
    ozetini konsola yazar. Ileride panel/data pool entegrasyonu acilinca
    _readFile icindeki STANDALONE blogu aktif edilecek.
    """

    TAG = "data_manager_window"
    FILE_DIALOG = "dm_file_dialog"
    TREE_HANDLER = "dm_tree_click_handler"
    KEY_HANDLER = "dm_read_mode_key_handler"

    READ_MODE_ITEMS = [
        "Full Data",
        "First N Data",
        "Last N Data",
        "Index Range",
        "Start Date",
        "Stop Date",
        "Date Range",
    ]

    # Pencerenin ic icerik genisligi (config'teki width=520'den padding dusulmus).
    WINDOW_CONTENT_WIDTH = 500

    # Read Mode alaninin explicit layout sabitleri (bkz. build()).
    READ_MODE_LABEL_WIDTH = 65
    READ_MODE_COMBO_WIDTH = 100
    READ_MODE_N_WIDTH = 120
    READ_MODE_DT_WIDTH = 130
    READ_MODE_GAP = 8
    READ_MODE_TOP_PAD = 10
    READ_MODE_ROW_HEIGHT = 26
    READ_MODE_META_HEIGHT = 90

    # Path satirindaki hizli secim butonlari.
    QUICK_THYAO_WIDTH = 140
    QUICK_VIP_WIDTH = 170

    # First N Data / Last N Data / Index Range AYNI n1 kutusunu (dm_read_n1_input)
    # paylasir; mod degistiginde kutu tek oldugu icin deger karisir (First N'e
    # 5000 yaz, Last N'e gec 7000 yaz, First N'e don -> 7000 gorunur). Bunu
    # onlemek icin her modun kendi degerini ayri hafizada (_modeValues) tutup
    # mod degisiminde SADECE o modun kutusunu geri yukluyoruz.
    MODE_FIELD_TAGS = {
        "n1": "dm_read_n1_input",
        "n2": "dm_read_n2_input",
        "dt1": "dm_read_dt1_input",
        "dt2": "dm_read_dt2_input",
    }
    MODE_FIELDS = {
        "First N Data": ("n1",),
        "Last N Data": ("n1",),
        "Index Range": ("n1", "n2"),
        "Start Date": ("dt1",),
        "Stop Date": ("dt2",),
        "Date Range": ("dt1", "dt2"),
    }

    def __init__(self):
        self._visible = False
        self._onCloseCallback = None
        # Tarama durumu: {market: {symbol: {period, ...}}}
        self._markets = {}
        self._currentMarket = "All"
        self._currentFilter = ""
        self._currentPeriod = "All"
        self._periodMap = {}   # {period_tag: (symbol, period)}
        self._reader = None    # son basarili okumanin StockDataReader'i
        self._readSource = None  # "manual" (UI Read dugmesi) | "script" (readData() cagrisi) - bkz. getReadSource
        self._fullPath = ""    # secili/okunan sembolun tam CSV yolu
        self._symbol = ""      # son okunan sembol (path'ten de turetilir)
        self._period = ""      # son okunan periyot (intraday karari icin)
        # Setter ile kurulan secim (setSembolBaseDir/Market/Name/FileName/Periyod) -> tam yol.
        self._selBaseDir = ""   # kok dizin; bos ise dm_dir_input kullanilir
        self._selMarket = ""
        self._selSymbol = ""    # sembol adi (uzantisiz), or. 'THYAO'
        self._selFilename = ""  # dosya adi (uzantili), or. 'THYAO.csv'
        self._selPeriod = ""
        self._metaBarCount = 0
        self._metaStartDate = ""
        self._metaStopDate = ""
        self._editRow1Y = 0    # Read Mode alaninda Edit1/Edit2 satir y'leri (build() doldurur)
        self._editRow2Y = 0
        self._editX = 0        # Edit1/Edit2 sutun x'i (build() doldurur)
        self._lastReadMode = "Full Data"
        self._modeValues = {}  # {modeName: {"n1": ..., "n2": ..., "dt1": ..., "dt2": ...}}

    # ---- build ------------------------------------------------------------
    def build(self, x=0, y=0, width=520, height=820, onClose=None):
        self._onCloseCallback = onClose

        with dpg.window(label="Data Manager", tag=self.TAG, pos=(x, y),
                        width=width, height=height, show=self._visible,
                        on_close=self._onClose):
            dpg.add_text("Data Manager")
            dpg.add_separator()

            dpg.add_text("Directory:")
            with dpg.group(horizontal=True):
                dpg.add_input_text(tag="dm_dir_input", width=350,
                                   default_value="C:\\data\\csvFiles\\")
                dpg.add_button(label="...", width=30,
                               callback=lambda: dpg.show_item(self.FILE_DIALOG))
                dpg.add_button(label="Scan", width=50, tag="dm_scan_btn",
                               callback=self._onScan)

            dpg.add_separator()

            dpg.add_text("Filter:")
            with dpg.group(horizontal=True):
                dpg.add_text("Market")
                dpg.add_combo(tag="dm_market_combo", width=150, items=[],
                              callback=self._onMarketChanged)
                dpg.add_text("Period")
                dpg.add_combo(tag="dm_period_combo", width=60, items=[],
                              callback=self._onPeriodChanged)

            dpg.add_separator()

            with dpg.group(horizontal=True):
                dpg.add_input_text(tag="dm_symbol_input", width=160, hint="Symbol filter...",
                                   callback=self._onSymbolInput)
                dpg.add_text("Symbol")
                dpg.add_combo(tag="dm_symbol_combo", width=110, items=[],
                              callback=self._onSymbolChanged)
                dpg.add_text(tag="dm_symbol_count", default_value="")
            dpg.add_separator()
            with dpg.child_window(width=-1, height=-230, border=True):
                dpg.add_tree_node(tag="dm_stock_tree", label="Symbols", default_open=True)

            # 1. satir: Path (secili sembolun tam yolu) + hizli secim butonlari
            # Read Mode alanindaki gibi: butonlar pos=(x,y) ile EXPLICIT yerlestirilir.
            # VIP satirin en saginda (row1); THYAO onun tam altinda (row2), ayni x.
            vipX = self.WINDOW_CONTENT_WIDTH - self.QUICK_VIP_WIDTH
            thyaoX = vipX
            pathRow1Y, pathRow2Y = 0, self.READ_MODE_ROW_HEIGHT
            with dpg.child_window(width=-1, height=2 * self.READ_MODE_ROW_HEIGHT,
                                  border=False, no_scrollbar=True):
                dpg.add_text("Path:", pos=(0, pathRow1Y + 4))
                dpg.add_text("Not Selected...", tag="dm_full_path_label",
                            wrap=vipX - 45, pos=(45, pathRow1Y + 4))
                dpg.add_button(label="Select VIP-X030-T 1Dk", width=self.QUICK_VIP_WIDTH,
                               pos=(vipX, pathRow1Y), callback=self._quickSelectVipX0301Dk)
                dpg.add_button(label="Select THYAO 5Dk", width=self.QUICK_THYAO_WIDTH,
                               pos=(thyaoX, pathRow2Y), callback=self._quickRead)
                dpg.add_button(label="Read MetaData", width=120,
                               pos=(0, pathRow2Y), callback=self._onReadMetadata)

            dpg.add_separator()

            # Read Mode alani: her kontrol pos=(x,y) ile EXPLICIT yerlestirilir
            # (auto-layout/olcum/dongu YOK). n1/dt1 AYNI sutunda (Edit1), n2/dt2
            # AYNI sutunda (Edit2) - n1/n2 ile dt1/dt2 hicbir modda ayni anda
            # gorunmez (bkz. _onReadModeChanged), o yuzden sutunu paylasabilirler.
            labelX, comboX = 8, self.READ_MODE_LABEL_WIDTH + 8
            edit1X = comboX + self.READ_MODE_COMBO_WIDTH + self.READ_MODE_GAP
            row1Y = self.READ_MODE_TOP_PAD
            row2Y = row1Y + self.READ_MODE_ROW_HEIGHT
            row3Y = row2Y + self.READ_MODE_ROW_HEIGHT
            row4Y = row3Y + self.READ_MODE_ROW_HEIGHT
            row5Y = row4Y + self.READ_MODE_ROW_HEIGHT
            self._editRow1Y, self._editRow2Y = row1Y, row2Y
            self._editX = edit1X
            boxHeight = -8  # pencerenin alt cizgisine kadar (kucuk bir pay birakarak) uzat
            leftBoxWidth = edit1X + max(self.READ_MODE_N_WIDTH, self.READ_MODE_DT_WIDTH) + self.READ_MODE_GAP
            readClearX = (leftBoxWidth - 80) // 2  # Read/Clear container'in ortasinda

            # Iki ayri, kenarlikli ("iki kutu yan yana") child_window: solda Read
            # Mode + combo + edit kutulari + Read/Clear, saginda MetaData metni.
            with dpg.group(horizontal=True):
                with dpg.child_window(width=leftBoxWidth, height=boxHeight, border=True):
                    dpg.add_text("Read Mode", pos=(labelX, row1Y))
                    dpg.add_combo(
                        tag="dm_read_mode_combo",
                        width=self.READ_MODE_COMBO_WIDTH,
                        pos=(comboX, row1Y),
                        items=self.READ_MODE_ITEMS,
                        default_value="Full Data",
                        callback=self._onReadModeChanged,
                    )
                    dpg.add_input_int(tag="dm_read_n1_input", width=self.READ_MODE_N_WIDTH,
                                      pos=(edit1X, row1Y), default_value=0)
                    dpg.add_input_text(tag="dm_read_dt1_input", width=self.READ_MODE_DT_WIDTH,
                                       pos=(edit1X, row1Y), default_value="")
                    dpg.add_input_int(tag="dm_read_n2_input", width=self.READ_MODE_N_WIDTH,
                                      pos=(edit1X, row2Y), default_value=0)
                    dpg.add_input_text(tag="dm_read_dt2_input", width=self.READ_MODE_DT_WIDTH,
                                       pos=(edit1X, row2Y), default_value="")

                    dpg.add_button(label="Read", width=80, pos=(readClearX, row4Y), callback=self._onRead)
                    dpg.add_button(label="Clear", width=80, pos=(readClearX, row5Y), callback=self._onClear)

                with dpg.child_window(width=-1, height=boxHeight, border=True):
                    dpg.add_text("", tag="dm_metadata_text",
                                wrap=self.WINDOW_CONTENT_WIDTH - leftBoxWidth - 24, pos=(0, 0))

            self._onReadModeChanged()

        with dpg.file_dialog(directory_selector=True, show=False,
                             tag=self.FILE_DIALOG, width=600, height=400,
                             callback=self._onDirSelected):
            pass

        with dpg.item_handler_registry(tag=self.TREE_HANDLER):
            # activated bazen tree yapraginda atesLENMEZ; clicked ile de yakala.
            # Ikisi de atesLENirse callback idempotent (ayni degerleri set eder).
            dpg.add_item_activated_handler(callback=self._onTreeLeafClick)
            dpg.add_item_clicked_handler(callback=self._onTreeLeafClick)

        # Combo odaklanmisken Up/Down: DPG'nin acik combo popup'inda ok tuslari
        # native olarak item degistirmiyor (global Nav widget atlamaya calisiyor,
        # 'Read' butonuna gidiyordu). Odak dm_read_mode_combo'daysa listede
        # manuel bir onceki/sonraki degere geciyoruz.
        with dpg.handler_registry(tag=self.KEY_HANDLER):
            dpg.add_key_press_handler(key=dpg.mvKey_Down, callback=self._onReadModeArrowKey, user_data=1)
            dpg.add_key_press_handler(key=dpg.mvKey_Up, callback=self._onReadModeArrowKey, user_data=-1)

    def _onReadModeArrowKey(self, sender, appData, userData):
        if not (dpg.does_item_exist("dm_read_mode_combo") and dpg.is_item_focused("dm_read_mode_combo")):
            return
        current = dpg.get_value("dm_read_mode_combo")
        if current not in self.READ_MODE_ITEMS:
            return
        idx = self.READ_MODE_ITEMS.index(current)
        newIdx = max(0, min(len(self.READ_MODE_ITEMS) - 1, idx + userData))
        if newIdx == idx:
            return
        dpg.set_value("dm_read_mode_combo", self.READ_MODE_ITEMS[newIdx])
        self._onReadModeChanged()

    def _onClose(self):
        self._visible = False
        if self._onCloseCallback:
            self._onCloseCallback()

    # ---- scan / tree / combos --------------------------------------------
    def _onDirSelected(self, sender, appData):
        dirPath = appData.get("file_path_name", "")
        dpg.set_value("dm_dir_input", dirPath)

    def _onScan(self):
        dirPath = dpg.get_value("dm_dir_input")
        if not dirPath:
            return
        self._markets.clear()
        dpg.delete_item("dm_stock_tree", children_only=True)
        if not os.path.isdir(dirPath):
            return
        totalSymbols = set()
        for entry in sorted(os.listdir(dirPath)):
            marketPath = os.path.join(dirPath, entry)
            if not os.path.isdir(marketPath):
                continue
            marketSymbols = {}
            for period in os.listdir(marketPath):
                periodPath = os.path.join(marketPath, period)
                if not os.path.isdir(periodPath):
                    continue
                for f in os.listdir(periodPath):
                    name, ext = os.path.splitext(f)
                    if ext.lower() in (".csv", ".txt", ".dat"):
                        if name not in marketSymbols:
                            marketSymbols[name] = set()
                        marketSymbols[name].add(period)
                        totalSymbols.add(name)
            self._markets[entry] = marketSymbols
        marketItems = [f"All ({len(totalSymbols)})"]
        for m in sorted(self._markets.keys()):
            count = len(self._markets[m])
            marketItems.append(f"{m} ({count})")
        dpg.configure_item("dm_market_combo", items=marketItems)
        dpg.set_value("dm_market_combo", marketItems[0])
        self._currentFilter = ""
        self._currentPeriod = "All"
        dpg.configure_item("dm_period_combo", items=["All"])
        dpg.set_value("dm_period_combo", "All")
        self._populateTree("All")
        self._updateSymbolCombo()

    def _getSymbols(self, market: str):
        if market == "All":
            result = {}
            for m, syms in self._markets.items():
                for s, periods in syms.items():
                    if s not in result:
                        result[s] = set()
                    result[s].update(periods)
            return result
        return self._markets.get(market, {})

    def _populateTree(self, market: str, filterText: str = "", period: str = "All"):
        dpg.delete_item("dm_stock_tree", children_only=True)
        self._periodMap.clear()
        pid = 0
        symbolMap = self._getSymbols(market)
        symbols = sorted(symbolMap.keys())
        if filterText:
            symbols = [s for s in symbols if s.upper().startswith(filterText.upper())]
        showPeriods = bool(filterText) or market != "All"
        if market == "All" and not filterText:
            for m in sorted(self._markets.keys()):
                tag = f"dm_dir_{m}"
                dpg.add_tree_node(label=m, parent="dm_stock_tree", tag=tag, default_open=False, open_on_double_click=False)
                for sym in sorted(self._markets[m].keys()):
                    symTag = f"dm_sym_{m}_{sym}"
                    dpg.add_tree_node(label=sym, parent=tag, leaf=True, tag=symTag, selectable=True)
                    dpg.bind_item_handler_registry(symTag, self.TREE_HANDLER)
        elif market == "All" and filterText:
            for m in sorted(self._markets.keys()):
                marketSyms = self._markets[m]
                matches = [s for s in sorted(marketSyms.keys())
                           if s.upper().startswith(filterText.upper())]
                if not matches:
                    continue
                tag = f"dm_dir_{m}"
                dpg.add_tree_node(label=m, parent="dm_stock_tree", tag=tag, default_open=True, open_on_double_click=False)
                for sym in matches:
                    periods = marketSyms.get(sym, set())
                    if period != "All":
                        periods = {p for p in periods if p == period}
                    numP = sorted([p for p in periods if p.isdigit()], key=int)
                    strP = sorted([p for p in periods if not p.isdigit()])
                    sortedPeriods = numP + strP
                    symTag = f"dm_sym_{m}_{sym}"
                    dpg.add_tree_node(label=sym, parent=tag, tag=symTag, default_open=True, selectable=True)
                    dpg.bind_item_handler_registry(symTag, self.TREE_HANDLER)
                    for p in sortedPeriods:
                        pid += 1
                        pTag = f"dm_period_{pid}"
                        self._periodMap[pTag] = (sym, p)
                        dpg.add_tree_node(label=p, parent=symTag, leaf=True, tag=pTag, selectable=True)
                        dpg.bind_item_handler_registry(pTag, self.TREE_HANDLER)
        else:
            for sym in symbols:
                periods = symbolMap.get(sym, set())
                if period != "All":
                    periods = {p for p in periods if p == period}
                numPeriods = sorted([p for p in periods if p.isdigit()], key=int)
                strPeriods = sorted([p for p in periods if not p.isdigit()])
                sortedPeriods = numPeriods + strPeriods
                if showPeriods and sortedPeriods:
                    symTag = f"dm_sym_{sym}"
                    dpg.add_tree_node(label=sym, parent="dm_stock_tree", tag=symTag, default_open=True, selectable=True, open_on_double_click=False)
                    dpg.bind_item_handler_registry(symTag, self.TREE_HANDLER)
                    for p in sortedPeriods:
                        pid += 1
                        pTag = f"dm_period_{pid}"
                        self._periodMap[pTag] = (sym, p)
                        dpg.add_tree_node(label=p, parent=symTag, leaf=True, tag=pTag, selectable=True)
                        dpg.bind_item_handler_registry(pTag, self.TREE_HANDLER)
                else:
                    symTag = f"dm_sym_{sym}"
                    dpg.add_tree_node(label=sym, parent="dm_stock_tree", leaf=True, tag=symTag, selectable=True)
                    dpg.bind_item_handler_registry(symTag, self.TREE_HANDLER)

    def _resolveClickedNode(self, *cands):
        """Tiklanan node'u sender/appData icinden cozer. DPG handler tipine/surumune
        gore tiklanan item sender ya da appData (veya [button, item] listesi) olabilir."""
        for c in cands:
            if c is None:
                continue
            if isinstance(c, (list, tuple)):
                r = self._resolveClickedNode(*reversed(c))
                if r is not None:
                    return r
                continue
            try:
                alias = dpg.get_item_alias(c) if isinstance(c, int) else c
            except Exception:
                alias = None
            if isinstance(alias, str) and (alias in self._periodMap
                                           or alias.startswith("dm_sym")
                                           or alias.startswith("dm_period")):
                return alias
        return None

    def _onTreeLeafClick(self, sender, appData):
        tag = self._resolveClickedNode(sender, appData)
        if tag is None:
            return
        mapped = self._periodMap.get(tag)
        if mapped:
            symbol, period = mapped
            dpg.set_value("dm_symbol_input", symbol)
            self._setPeriods(symbol)
            # Periyot yapragina tiklandi: combo'yu o periyoda getir ki path dogru olsun
            # (_setPeriods combo'yu "All"a resetler).
            dpg.set_value("dm_period_combo", period)
            self._currentPeriod = period
            self._updatePathLabel()
        else:
            # Sembol node'u (periyot degil): label = sembol adi.
            label = dpg.get_item_label(tag)
            if not label:
                return
            dpg.set_value("dm_symbol_input", label)
            self._setPeriods(label)

    def _updateSymbolCombo(self, filterText: str = ""):
        value = dpg.get_value("dm_market_combo")
        market = value.split(" (")[0] if value else "All"
        if market == "All":
            symbols = []
            seen = set()
            for m in sorted(self._markets.keys()):
                for sym in sorted(self._markets[m].keys()):
                    if sym not in seen:
                        symbols.append(sym)
                        seen.add(sym)
        else:
            symbols = sorted(self._getSymbols(market).keys())
        if filterText:
            symbols = [s for s in symbols if s.upper().startswith(filterText.upper())]
        dpg.configure_item("dm_symbol_combo", items=symbols)
        dpg.set_value("dm_symbol_count", f"({len(symbols)})")
        if symbols:
            dpg.set_value("dm_symbol_combo", symbols[0])
            self._setPeriods(symbols[0])

    def _onMarketChanged(self):
        value = dpg.get_value("dm_market_combo")
        market = value.split(" (")[0] if value else "All"
        if market:
            self._currentMarket = market
            self._currentFilter = ""
            self._currentPeriod = "All"
            dpg.set_value("dm_symbol_input", "")
            dpg.configure_item("dm_period_combo", items=["All"])
            dpg.set_value("dm_period_combo", "All")
            self._populateTree(market)
            self._updateSymbolCombo()

    def _onSymbolChanged(self, sender, appData):
        symbol = appData
        if symbol and symbol != self._currentFilter:
            self._currentFilter = symbol
            dpg.set_value("dm_symbol_input", symbol)
            self._populateTree(self._currentMarket, symbol, self._currentPeriod)
            self._setPeriods(symbol)

    def _onSymbolInput(self, sender, appData):
        text = appData
        if text == self._currentFilter:
            return
        self._currentFilter = text
        self._populateTree(self._currentMarket, text, self._currentPeriod)
        self._updateSymbolCombo(text)
        if not text:
            value = dpg.get_value("dm_market_combo")
            market = value.split(" (")[0] if value else "All"
            self._populateTree(market)
            self._updateSymbolCombo("")
            dpg.configure_item("dm_period_combo", items=["All"])
            dpg.set_value("dm_period_combo", "All")

    def _onPeriodChanged(self):
        period = dpg.get_value("dm_period_combo")
        if period == self._currentPeriod:
            return
        self._currentPeriod = period
        self._populateTree(self._currentMarket, self._currentFilter, period)
        self._updatePathLabel()

    def _setPeriods(self, symbol: str):
        value = dpg.get_value("dm_market_combo")
        market = value.split(" (")[0] if value else "All"
        symbolMap = self._getSymbols(market)
        periods = symbolMap.get(symbol, set())
        numPeriods = sorted([p for p in periods if p.isdigit()], key=int)
        strPeriods = sorted([p for p in periods if not p.isdigit()])
        items = ["All"] + numPeriods + strPeriods
        dpg.configure_item("dm_period_combo", items=items)
        dpg.set_value("dm_period_combo", "All")
        self._updatePathLabel()

    def _updatePathLabel(self):
        """Secili sembol/market/period'den tam CSV yolunu hesaplar ve label'a yazar.
        Her secim degisikliginde cagrilir; _onRead ile ayni yol mantigini kullanir."""
        if not dpg.does_item_exist("dm_full_path_label"):
            return
        path = self._selectedFilePath()
        if not path:
            dpg.set_value("dm_full_path_label", "Not Selected...")
            return
        self._fullPath = path
        dpg.set_value("dm_full_path_label", path)

    def _selectedFilePath(self):
        dirPath = dpg.get_value("dm_dir_input") if dpg.does_item_exist("dm_dir_input") else ""
        value = dpg.get_value("dm_market_combo") if dpg.does_item_exist("dm_market_combo") else ""
        market = value.split(" (")[0] if value else self._currentMarket
        symbol = (
            (dpg.get_value("dm_symbol_combo") if dpg.does_item_exist("dm_symbol_combo") else "")
            or (dpg.get_value("dm_symbol_input") if dpg.does_item_exist("dm_symbol_input") else "")
            or self._currentFilter
        )
        period = (
            (dpg.get_value("dm_period_combo") if dpg.does_item_exist("dm_period_combo") else "")
            or self._currentPeriod
            or "All"
        )
        if not symbol:
            return ""
        # Market "All" ise gercek market'i bul (yol gercek dosyaya isaret etsin).
        if market == "All":
            for m, syms in self._markets.items():
                if any(s.upper() == symbol.upper() for s in syms):
                    market = m
                    break
        return os.path.join(dirPath, market, period, f"{symbol}.csv")

    # ---- read (standalone: sadece oku + konsola bas) ----------------------
    def _quickRead(self):
        """'Read THYAO 5dk': Scan'e bas -> filtre kutusuna THYAO yaz -> period 05 sec.
        (Okumaz; sadece secimi hazirlar. Okumak icin Read'e basilir.)"""
        self._quickSelectSymbol("IMKBH", "THYAO", "05")

    def _quickSelectVipX0301Dk(self):
        """VIP-X030-T 1dk secimini hazirlar. Okumak icin Read'e basilir."""
        self._quickSelectSymbol("VIP", "VIP-X030-T", "01")

    def _quickSelectSymbol(self, market, symbol, period):
        self._onScan()
        if dpg.does_item_exist("dm_market_combo"):
            items = dpg.get_item_configuration("dm_market_combo").get("items") or []
            marketValue = next((item for item in items if str(item).split(" (")[0] == market), market)
            dpg.set_value("dm_market_combo", marketValue)
            self._onMarketChanged()

        dpg.set_value("dm_symbol_input", symbol)
        self._onSymbolInput(None, symbol)

        if dpg.does_item_exist("dm_symbol_combo"):
            items = dpg.get_item_configuration("dm_symbol_combo").get("items") or []
            if symbol in items:
                dpg.set_value("dm_symbol_combo", symbol)
                self._onSymbolChanged(None, symbol)

        if dpg.does_item_exist("dm_period_combo"):
            items = dpg.get_item_configuration("dm_period_combo").get("items") or []
            if period in items:
                dpg.set_value("dm_period_combo", period)
                self._onPeriodChanged()

    def _onReadModeChanged(self, sender=None, appData=None, userData=None):
        mode = dpg.get_value("dm_read_mode_combo") if dpg.does_item_exist("dm_read_mode_combo") else "Full Data"

        # Cikilan moddaki kutu degerlerini hafizaya al (n1/dt1/dt2 birden fazla
        # mod tarafindan PAYLASILDIGI icin, yoksa deger karisir).
        self._saveModeValues(self._lastReadMode)

        showN1 = mode in ("First N Data", "Last N Data", "Index Range")
        showN2 = mode == "Index Range"
        showDt1 = mode in ("Start Date", "Date Range")
        showDt2 = mode in ("Stop Date", "Date Range")

        if dpg.does_item_exist("dm_read_n1_input"):
            dpg.configure_item("dm_read_n1_input", show=showN1)
        if dpg.does_item_exist("dm_read_n2_input"):
            dpg.configure_item("dm_read_n2_input", show=showN2)
        if dpg.does_item_exist("dm_read_dt1_input"):
            dpg.configure_item("dm_read_dt1_input", show=showDt1)
        if dpg.does_item_exist("dm_read_dt2_input"):
            dpg.configure_item("dm_read_dt2_input", show=showDt2)
            # Stop Date TEK basina gorunurse Edit1 satirinda (Last N Data gibi);
            # Date Range'de dt1 ile birlikte gorundugunde Edit2 satirinda kalir.
            dt2Y = self._editRow1Y if mode == "Stop Date" else self._editRow2Y
            dpg.set_item_pos("dm_read_dt2_input", [self._editX, dt2Y])

        # Girilen moda ait hafizadaki degeri geri yukle (varsa). Read/Read
        # MetaData BU FONKSIYONU cagirmaz; sadece mod degisince calisir, o
        # yuzden kullanicinin baska bir modda girdigi deger asla ezilmez.
        self._restoreModeValues(mode)
        self._lastReadMode = mode

    def _saveModeValues(self, mode):
        fields = self.MODE_FIELDS.get(mode, ())
        if not fields:
            return
        values = self._modeValues.setdefault(mode, {})
        for field in fields:
            tag = self.MODE_FIELD_TAGS[field]
            if dpg.does_item_exist(tag):
                values[field] = dpg.get_value(tag)

    def _restoreModeValues(self, mode):
        values = self._modeValues.get(mode)
        if not values:
            return
        for field, value in values.items():
            tag = self.MODE_FIELD_TAGS[field]
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, value)

    def _onClear(self):
        """'Clear': okunan datayi hafizadan siler, reader objesini birakir.
        Yol/secim alanlarini ve Path label'i temizler."""
        self._reader = None
        self._readSource = None
        self._fullPath = ""
        self._symbol = ""
        self._period = ""
        self._selBaseDir = ""
        self._selMarket = ""
        self._selSymbol = ""
        self._selFilename = ""
        self._selPeriod = ""
        if dpg.does_item_exist("dm_full_path_label"):
            dpg.set_value("dm_full_path_label", "Not Selected...")
        self._setMetadataText("")
        print("Data temizlendi (reader silindi).")

    def _onRead(self):
        """UI Read dugmesi: combo/tree secimlerinden yolu kurar ve okur."""
        filePath = self._selectedFilePath()
        if not filePath:
            print("No symbol selected")
            return None
        self._decomposeFullPath(filePath)
        print(f"Symbol : {self._selSymbol}")
        print(f"Market : {self._selMarket}")
        print(f"Period : {self._selPeriod}")
        self._readSource = "manual"
        return self._readFile(filePath)

    def _onReadMetadata(self):
        filePath = self._selectedFilePath()
        if not filePath:
            text = "No symbol selected"
            print(text)
            self._setMetadataText(text)
            return None
        return self._readMetadataFile(filePath)

    def _readMetadataFile(self, filePath):
        self._decomposeFullPath(filePath)
        if dpg.does_item_exist("dm_full_path_label"):
            dpg.set_value("dm_full_path_label", filePath)
        if not os.path.isfile(filePath):
            text = f"File not found:\n{filePath}"
            print(text)
            self._setMetadataText(text)
            return None

        reader = StockDataReader()
        meta = reader.readMetaData(filePath)
        self._applyMetadataDefaults(meta)
        self._seedReadModeInputs()
        lines = [
            f"Path   : {filePath}",
            f"Market : {self._selMarket}",
            f"Symbol : {self._selSymbol}",
            f"Period : {self._selPeriod}",
            f"Bars   : {self._metaBarCount or '...'}",
            f"Start  : {self._metaStartDate or '...'}",
            f"Stop   : {self._metaStopDate or '...'}",
        ]
        text = "\n".join(lines)
        print(text)
        self._setMetadataText(text)
        return meta

    def _setMetadataText(self, text):
        if dpg.does_item_exist("dm_metadata_text"):
            dpg.set_value("dm_metadata_text", text)

    def _applyMetadataDefaults(self, meta):
        self._metaBarCount = self._metadataInt(meta, "BarCount")
        self._metaStartDate = self._metadataDate(meta, start=True)
        self._metaStopDate = self._metadataDate(meta, start=False)

    def _seedReadModeInputs(self):
        """Read MetaData sonrasi HER moda kendi sensible varsayilanini
        hafizaya (_modeValues) yazar: First N/Last N -> 1000, Index Range ->
        0..BarCount-1 (tum dosya), Start/Stop/Date Range -> metadata'nin
        baslangic/bitis tarihleri. Su an secili modun kutulari hemen
        guncellenir; digerleri o moda gecilince hafizadan yuklenir. SADECE
        Read MetaData'dan cagrilir - duz Read veya combo mod degisimi bunu
        ASLA tetiklemez (kullanicinin sonradan girdigi degeri korumak icin)."""
        barCount = int(self._metaBarCount or 0)
        self._modeValues = {
            "First N Data": {"n1": 1000},
            "Last N Data": {"n1": 1000},
            "Index Range": {"n1": 0, "n2": max(0, barCount - 1)},
            "Start Date": {"dt1": self._metaStartDate},
            "Stop Date": {"dt2": self._metaStopDate},
            "Date Range": {"dt1": self._metaStartDate, "dt2": self._metaStopDate},
        }
        currentMode = dpg.get_value("dm_read_mode_combo") if dpg.does_item_exist("dm_read_mode_combo") else ""
        self._restoreModeValues(currentMode)

    def _metadataInt(self, meta, wantedKey):
        if not meta:
            return 0
        for key, value in meta.items():
            if key == wantedKey:
                try:
                    return int(str(value).strip())
                except ValueError:
                    return 0
        return 0

    def _metadataDate(self, meta, start=True):
        if not meta:
            return ""
        needles = ("baş", "bas", "lang", "start") if start else ("biti", "stop", "end")
        for key, value in meta.items():
            normalized = key.lower()
            if any(n in normalized for n in needles) and "tarih" in normalized:
                return str(value).strip()
        for key, value in meta.items():
            normalized = key.lower()
            if any(n in normalized for n in needles):
                return str(value).strip()
        return ""

    def _selectedReadFilter(self):
        modeName = dpg.get_value("dm_read_mode_combo") if dpg.does_item_exist("dm_read_mode_combo") else "Full Data"
        n1 = self._getIntValue("dm_read_n1_input", 0)
        n2 = self._getIntValue("dm_read_n2_input", 0)
        dt1 = self._parseDatetimeValue("dm_read_dt1_input")
        dt2 = self._parseDatetimeValue("dm_read_dt2_input")

        if modeName == "First N Data":
            return FilterMode.FirstN, n1, 0, None, None
        if modeName == "Last N Data":
            return FilterMode.LastN, n1, 0, None, None
        if modeName == "Index Range":
            return FilterMode.IndexRange, n1, n2, None, None
        if modeName == "Start Date":
            return FilterMode.AfterDateTime, 0, 0, dt1, None
        if modeName == "Stop Date":
            return FilterMode.BeforeDateTime, 0, 0, dt2, None
        if modeName == "Date Range":
            return FilterMode.DateTimeRange, 0, 0, dt1, dt2
        return FilterMode.All, 0, 0, None, None

    def _getIntValue(self, tag, default):
        if not dpg.does_item_exist(tag):
            return default
        try:
            return int(dpg.get_value(tag))
        except (TypeError, ValueError):
            return default

    def _parseDatetimeValue(self, tag):
        if not dpg.does_item_exist(tag):
            return None
        value = str(dpg.get_value(tag) or "").strip()
        if not value:
            return None
        formats = (
            "%Y.%m.%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
            "%Y.%m.%d",
            "%Y-%m-%d",
            "%d.%m.%Y",
        )
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass
        print(f"Invalid date: {value}")
        return None

    def _readFile(self, filePath):
        """Verilen tam yoldaki CSV'yi okur; StockDataReader dondurur (yoksa None).
        _onRead ile readData'nin ortak cekirdegi. Once yolu parcalarina ayirip
        TUM secim alanlarini (_sel* + _symbol/_period + _fullPath) doldurur."""
        self._decomposeFullPath(filePath)
        if dpg.does_item_exist("dm_full_path_label"):
            dpg.set_value("dm_full_path_label", filePath)
        print(f"Path   : {filePath}")
        print()
        if not os.path.isfile(filePath):
            print(f"File not found: {filePath}")
            return None

        reader = StockDataReader()
        try:
            reader.readMetaData(filePath)
            self._applyMetadataDefaults(reader.metaData)
            for key in ["GrafikPeriyot", "BarCount", "Başlangiç Tarihi", "Bitiş Tarihi"]:
                if key in reader.metaData:
                    print(f"{key:<17} : {reader.metaData[key]}")
            print()
            print("Veri Okunuyor...")
            mode, n1, n2, dt1, dt2 = self._selectedReadFilter()
            reader.readDataWithPandas(filePath, mode=mode, n1=n1, n2=n2, dt1=dt1, dt2=dt2)
            print()
            print("Veri Okundu")
            print(f"{'BarCount':<17} : {reader.data.length}")
            print(f"{'ElapsdTime':<17} : {reader.elapsedMs} ms\n")

            # --- STANDALONE: asagisi baska GUI kontrollerini gunceller, KAPALI ---
            # Ileride panel/data pool entegrasyonu acilinca bu blok aktif edilecek.

            # Okunan reader'i sakla + dondur (script/entegrasyon icin).
            self._reader = reader
            return reader
        except Exception as e:
            print(f"Read error: {e}")
            return None

    # ---- public API (script / entegrasyon icin) --------------------------
    def hasReader(self):
        """DataManager daha once basariyla veri okuduysa True."""
        return self._reader is not None

    def getReader(self):
        """Son basarili okumanin StockDataReader'i (yoksa None)."""
        return self._reader

    def getSembolFullPath(self):
        """Secili/okunan sembolun tam CSV yolu."""
        return self._fullPath

    def getSembolBaseDir(self):
        """Secili/okunan kok dizin (or. r'C:\\data\\csvFiles')."""
        return self._selBaseDir

    def getSembolMarket(self):
        """Secili/okunan market (or. 'IMKBH')."""
        return self._selMarket

    def getSembolName(self):
        """Secili/okunan sembol adi (uzantisiz, or. 'THYAO')."""
        return self._selSymbol

    def getSembolFileName(self):
        """Secili/okunan dosya adi (uzantili, or. 'THYAO.csv')."""
        return self._selFilename

    def getSembolPeriyod(self):
        """Secili/okunan periyot (or. '05','60','G')."""
        return self._selPeriod

    def getSembolDataCount(self):
        """Son okunan verinin bar sayisi (reader yoksa 0)."""
        return self._reader.data.length if self._reader else 0

    def getPeriod(self):
        """Son okunan periyot (or. '05','60','G'). intraday = period.isdigit()."""
        return self._period

    def getSymbol(self):
        """Son okunan sembol adi."""
        return self._symbol

    def isIntraday(self):
        """Son okunan periyot dakika/saatlik mi (rakamsal periyot = intraday)."""
        return self._period.isdigit()

    def setReader(self, reader):
        """Disaridan okunan StockDataReader'i dp'ye atar (or. USE_DIRECT_READ modu).
        Boylece getReader/hasReader/getSembolDataCount tutarli olur."""
        self._reader = reader

    def setSembolFullPath(self, path):
        """Okunacak sembolun tam CSV yolunu ayarlar (label'a da yansitir)."""
        self._fullPath = path
        if dpg.does_item_exist("dm_full_path_label"):
            dpg.set_value("dm_full_path_label", path)

    # --- parcali secim setter'lari: gerekli parcalar dolunca tam yol kurulur ---
    def setSembolBaseDir(self, baseDir):
        """Yol kurarken kullanilacak kok dizini ayarlar (or. r'C:\\data\\csvFiles').
        Bos birakilirsa DataManager'in dm_dir_input alani kullanilir."""
        self._selBaseDir = baseDir
        self._applySelectionPath()

    def setSembolMarket(self, market):
        """Okunacak sembolun market'ini ayarlar (or. 'IMKBH')."""
        self._selMarket = market
        self._applySelectionPath()

    def setSembolName(self, name):
        """Okunacak sembol adini (UZANTISIZ) ayarlar (or. 'THYAO').
        Yol kurarken sonuna '.csv' eklenir; setSembolFileName verilmisse o oncelikli."""
        self._selSymbol = name
        self._symbol = name          # getSymbol ile tutarli
        self._applySelectionPath()

    def setSembolFileName(self, filename):
        """Okunacak dosya adini (UZANTILI) ayarlar (or. 'THYAO.csv').
        Verilirse yol kurarken oldugu gibi kullanilir (setSembolName'i ezer)."""
        self._selFilename = filename
        self._symbol = os.path.splitext(filename)[0]
        self._applySelectionPath()

    def setSembolPeriyod(self, period):
        """Okunacak sembolun periyodunu ayarlar (or. '05','60','G')."""
        self._period = period        # getPeriod / isIntraday ile tutarli
        self._selPeriod = period
        self._applySelectionPath()

    def _applySelectionPath(self):
        """Market + (FileName veya Name) + Periyod doluysa tam yolu kurar ->
        self._fullPath (+ label). FileName oncelikli; yoksa Name+'.csv'.
        dir, DataManager'in dm_dir_input alanindan alinir."""
        filename = self._selFilename or (f"{self._selSymbol}.csv" if self._selSymbol else "")
        if self._selMarket and filename and self._selPeriod:
            dirPath = self._selBaseDir or (
                dpg.get_value("dm_dir_input") if dpg.does_item_exist("dm_dir_input") else "")
            self.setSembolFullPath(
                os.path.join(dirPath, self._selMarket, self._selPeriod, filename))

    def readData(self, filePath=None):
        """CSV'yi okur; StockDataReader dondurur (yoksa None).
        - filePath VERILIRSE: yol parcalanip TUM secim alanlari doldurulur
          (FullPath/BaseDir/Market/Name/FileName/Periyod), sonra okunur.
        - filePath VERILMEZSE: onceden set edilmis yolu (self._fullPath) okur
          (once setSembolFullPath(...) ya da setSembolMarket/Name/Periyod(...))."""
        if filePath is None:
            filePath = self._fullPath
        self._readSource = "script"
        return self._readFile(filePath)   # _readFile zaten decompose eder

    def getReadSource(self):
        """Su anki reader'in nereden geldigini dondurur: 'manual' (UI Read
        dugmesi) | 'script' (readData() cagrisi) | None (henuz okuma yok).
        Script'lerin kendi ONCEKI Run'undan kalma bir reader'i mi yoksa
        kullanicinin ELLE Data Manager'dan okudugu bir reader'i mi gordugunu
        ayirt etmek icin (bkz. scripts/default.py App.run())."""
        return self._readSource

    def _decomposeFullPath(self, filePath):
        """Tam yolu (.../BASE/MARKET/PERIOD/SYMBOL.csv) parcalarina ayirir ve tum
        secim/okuma alanlarini doldurur (_sel* + _symbol/_period + _fullPath)."""
        periodDir = os.path.dirname(filePath)          # .../MARKET/PERIOD
        marketDir = os.path.dirname(periodDir)          # .../MARKET
        baseDir = os.path.dirname(marketDir)            # .../BASE
        filename = os.path.basename(filePath)           # SYMBOL.csv
        symbol = os.path.splitext(filename)[0]          # SYMBOL
        period = os.path.basename(periodDir)            # PERIOD
        self._selBaseDir = baseDir
        self._selMarket = os.path.basename(marketDir)
        self._selPeriod = period
        self._selFilename = filename
        self._selSymbol = symbol
        self._symbol = symbol
        self._period = period
        self.setSembolFullPath(filePath)                # _fullPath + label

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
