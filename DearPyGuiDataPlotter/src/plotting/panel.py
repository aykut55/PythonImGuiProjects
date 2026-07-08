from .panelData import PanelData, makeCandlePanelData


class Panel:
    ALIGNMENTS = {
        "top-left", "top", "top-right",
        "left", "center", "right",
        "bottom-left", "bottom", "bottom-right",
    }
    Y_SYNC_MODES = {
        "independent",
        "fitVisibleData",
        "syncGroup",
        "fixedRange",
    }

    def __init__(self, panelId: int, name: str, caption: str = "", parent: str = "",
                 alignment=None):
        self.id = panelId
        self.name = name
        self.caption = caption or name
        self.parent = parent
        self.alignment = alignment
        self.x = 0
        self.y = 0
        self.width = -1
        self.height = 200
        self.visible = True
        self.dataList: list[PanelData] = []
        # Yatay seviye cizgileri (drag_line). Veri DEGIL, plot dekorasyonu.
        # Her oge: {"value", "vertical", "color", "thickness", "label"}. Cizim PanelManager'da.
        self.levels: list[dict] = []
        self._infoFields = None  # None = auto-detect
        self.ySyncMode = "fitVisibleData"
        self.ySyncId = None
        self.yFixedRange = None
        self._manager = None  # addPanel tarafindan set edilir (bkz. sync/render)

    def addData(self, dataId: int, name: str = "", dataType: str = "line",
               xs: list = None, ys: list = None, timestamps=None, intraday: bool = None):
        """Panel-ici bir PanelData olusturur, dataList'e ekler, dondurur (MODEL).

        timestamps verilirse setTimestamps(dateTime=...) ile atanir; intraday
        verilirse isIntraday ayarlanir. Her durumda updateStats() + setFullData()
        cagrilir -> dataCount/minY/maxY dolar ve LOD snapshot'i hazir olur.
        (timestamps/intraday None ise o alanlara dokunulmaz.)
        """
        data = PanelData(dataId, name, dataType, xs, ys)
        data.setParent(self)
        if timestamps is not None:
            data.setTimestamps(dateTime=timestamps)
        if intraday is not None:
            data.isIntraday = intraday
        data.updateStats()
        data.setFullData()
        self.dataList.append(data)
        return data

    def deleteData(self, dataId: int):
        self.dataList = [d for d in self.dataList if d.id != dataId]

    def deleteAllData(self):
        self.dataList.clear()

    def getData(self, dataId: int):
        """Panel-ici id ile bir PanelData dondurur (yoksa None)."""
        return next((d for d in self.dataList if d.id == dataId), None)

    def getDataId(self, name):
        """PanelData ismiyle arayip id dondurur (yoksa None)."""
        data = self.findData(name)
        return data.id if data else None

    def findData(self, key):
        """Esnek PanelData arama: int ise id ile, str ise isim ile. Bulamazsa None."""
        if isinstance(key, str):
            return next((d for d in self.dataList if d.name == key), None)
        return self.getData(key)

    def removeData(self, dataId: int):
        """deleteData ile ayni (isim tercihi icin ikinci ad)."""
        self.deleteData(dataId)

    def getAllData(self):
        return list(self.dataList)

    def iterateAllData(self):
        for data in self.dataList:
            yield data

    def hideData(self, dataId: int):
        data = self.getData(dataId)
        if data:
            data.setVisible(False)

    def showData(self, dataId: int):
        data = self.getData(dataId)
        if data:
            data.setVisible(True)

    def hideAllData(self):
        for data in self.dataList:
            data.setVisible(False)

    def showAllData(self):
        for data in self.dataList:
            data.setVisible(True)

    # --- Data sirasi (Data Order kontrolleri) ---
    def _findDataIndex(self, dataId):
        for i, d in enumerate(self.dataList):
            if d.id == dataId:
                return i
        return None

    def swapDataUp(self, dataId):
        """dataId'li PanelData'yi dataList icinde bir yukari (bir onceki
        index'e) tasir (cizim/legend sirasini degistirir)."""
        idx = self._findDataIndex(dataId)
        if idx is None or idx <= 0:
            return
        self.dataList[idx - 1], self.dataList[idx] = self.dataList[idx], self.dataList[idx - 1]

    def swapDataDown(self, dataId):
        """dataId'li PanelData'yi dataList icinde bir asagi tasir."""
        idx = self._findDataIndex(dataId)
        if idx is None or idx >= len(self.dataList) - 1:
            return
        self.dataList[idx], self.dataList[idx + 1] = self.dataList[idx + 1], self.dataList[idx]

    def resetDataOrder(self):
        """dataList'i data id'sine gore artan sirada duzenler. Ayri bir
        'olusturulma sirasi' kaydi tutulmuyor (panelManager._panelOrder'in
        aksine) - id'ler genelde ekleme sirasiyla artan oldugundan id'ye
        gore sort yeterli (Ref1/Ref3'teki reset_data_order ile ayni)."""
        self.dataList.sort(key=lambda d: d.id)

    # --- Seviye cizgileri (drag_line): veri DEGIL, plot dekorasyonu (MODEL) ---
    def _addLevel(self, value, vertical, color, thickness, label):
        level = {"value": float(value), "vertical": bool(vertical),
                 "color": color, "thickness": thickness, "label": label}
        self.levels.append(level)
        return level

    def addHline(self, y, color=(120, 120, 120, 150), thickness=1, label=""):
        """Yatay seviye cizgisi (y sabit). Cizim PanelManager'da drag_line ile."""
        return self._addLevel(y, vertical=False, color=color, thickness=thickness, label=label)

    def addVline(self, x, color=(120, 120, 120, 150), thickness=1, label=""):
        """Dikey seviye cizgisi (x sabit). Cizim PanelManager'da drag_line ile."""
        return self._addLevel(x, vertical=True, color=color, thickness=thickness, label=label)

    def deleteAllLevels(self):
        self.levels.clear()

    def setCandleData(self, source=None, *, opens=None, highs=None, lows=None,
                      closes=None, volumes=None, sizes=None, dateTime=None,
                      name: str = "", dataId: int = 0, intraday: bool = True):
        """Bu panelin CANDLE datasini ESNEK sekilde ayarlar (MODEL).

        Girdi 3 sekilde (makeCandlePanelData):
          1) source = StockData (reader.data)
          2) source = PanelData (hazir candle) -> oldugu gibi kullanilir
          3) source=None + ayri listeler: opens/highs/lows/closes/volumes/sizes/dateTime

        Panelin onceki TUM datasini temizler, candle PanelData'yi ekler, dondurur.
        DIKKAT: YALNIZCA modeli gunceller; cizim icin PanelManager gerekir
        (pm.setPanel(panel) veya pm.redrawPanelData(panel.id)).
        """
        panelData = makeCandlePanelData(
            source, opens=opens, highs=highs, lows=lows, closes=closes,
            volumes=volumes, sizes=sizes, dateTime=dateTime,
            name=name or self.name, dataId=dataId, intraday=intraday)
        panelData.setParent(self)
        self.deleteAllData()
        self.dataList.append(panelData)
        return panelData

    def setHeight(self, h: int):
        self.height = h

    def setWidth(self, w: int):
        self.width = w

    def setVisible(self, v: bool):
        self.visible = v

    def setName(self, name: str):
        self.name = name

    def setCaption(self, caption: str):
        self.caption = caption

    def setParent(self, parent):
        self.parent = parent

    def setId(self, panelId: int):
        self.id = panelId

    def setYSync(self, mode: str, syncId: int = None,
                fixedRange: tuple = None):
        if mode not in self.Y_SYNC_MODES:
            raise ValueError(f"Unknown ySync mode: {mode}")
        self.ySyncMode = mode
        self.ySyncId = syncId
        self.yFixedRange = fixedRange
        return self

    def setYSyncId(self, syncId: int = None):
        self.ySyncMode = "syncGroup" if syncId is not None else "fitVisibleData"
        self.ySyncId = syncId
        return self

    def setInfoFields(self, fields: list):
        """Set the hover-readout fields for this panel.

        Each item in `fields` can be:
          "index", "date", "time"        — timestamp meta fields
          "open", "high", "low", "close",
          "volume", "size"               — OHLC/volume fields from the primary series
          any other string               — looked up by name in dataList, y-value shown

        Pass None (or call clearInfoFields) to revert to auto-detect.
        """
        self._infoFields = list(fields) if fields is not None else None

    def clearInfoFields(self):
        self._infoFields = None

    def getInfoFields(self):
        return self._infoFields

    def getId(self): return self.id
    def getName(self): return self.name
    def getCaption(self): return self.caption
    def getParent(self): return self.parent
    def getAlignment(self): return self.alignment
    def getX(self): return self.x
    def getY(self): return self.y
    def getWidth(self): return self.width
    def getHeight(self): return self.height
    def getVisible(self): return self.visible

    # --- Cizim (PanelManager gerekli - addPanel ile _manager baglanir) ---
    def draw(self):
        """Bu panelin (bos) plot kabugunu cizer (= pm.drawPanel(self.id))."""
        if self._manager is not None:
            self._manager.drawPanel(self.id)

    def drawData(self):
        """Bu panelin dataList'indeki serileri + levels'i cizer
        (= pm.drawPanelData(self.id))."""
        if self._manager is not None:
            self._manager.drawPanelData(self.id)

    def sync(self):
        """Cizili veriyi guncel dataList ile senkronlar (drawData ile ayni;
        pm.sync()'ten FARKLI - pm.sync() silinen panellerin yetim UI'sini
        temizler, bunun PanelData seviyesinde bir karsiligi yok)."""
        self.drawData()

    def render(self):
        """Bu panelin kabugunun var oldugundan emin olur, sonra verisini
        cizer (draw() + drawData()) - 'paneli tam olarak ekrana bas' icin
        tek cagri."""
        self.draw()
        self.drawData()
