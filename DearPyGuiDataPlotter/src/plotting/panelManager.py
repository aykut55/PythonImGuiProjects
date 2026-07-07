import time

import dearpygui.dearpygui as dpg

from .panel import Panel


class PanelManager:
    def __init__(self):
        self._panels = {}
        self._nextId = 0
        self._container = None  # panellerin cizilecegi DPG container tag'i (bkz. setContainer)
        self._drawnPanelIds = set()  # drawPanel ile UI'si kurulmus panel id'leri (bkz. sync)
        self._lastRenderPrint = 0.0  # render() heartbeat print throttle (bkz. render)

    def createPanel(self, name, caption="", parent="", alignment=None):
        """Otomatik id ile YALNIZCA bir Panel olusturur, DONDURUR - panelManager'a
        EKLEMEZ (kayit icin addPanel(panel) gerekir; iki adim ayri tutuluyor)."""
        panelId = self._nextId
        self._nextId += 1
        return Panel(panelId, name, caption, parent, alignment)

    def addPanel(self, panel):
        """Bir paneli (createPanel'den gelen ya da dogrudan Panel(...) ile
        kurulmus) panelManager'a kaydeder. Ileride id catismasini onlemek
        icin _nextId'i panel.id'nin onune gecirir."""
        self._panels[panel.id] = panel
        if panel.id >= self._nextId:
            self._nextId = panel.id + 1
        return panel

    def getPanel(self, panelId):
        return self._panels.get(panelId)

    def getPanelId(self, name):
        """Panel ismiyle arayip id dondurur (yoksa None). Panel objesi zaten
        elindeyse buna gerek yok, dogrudan panel.id kullan.
        Ornek: pm.getPanelId("OHLC")."""
        panel = self.findPanel(name)
        return panel.id if panel else None

    def findPanel(self, key):
        """Esnek panel arama: int ise id ile, str ise isim ile. Bulamazsa None."""
        if isinstance(key, str):
            return next((p for p in self._panels.values() if p.name == key), None)
        return self._panels.get(key)

    def deletePanel(self, panelId):
        """Bir paneli siler (Ref3'teki gibi panel_{id} child_window/_panel_order
        YOK - bizde henuz UI/cizim katmani yok, sadece model temizlenir)."""
        panel = self._panels.get(panelId)
        if panel is None:
            return
        panel.deleteAllData()
        del self._panels[panelId]

    def removePanel(self, panelId):
        """deletePanel ile ayni (isim tercihi icin ikinci ad)."""
        self.deletePanel(panelId)

    def getAllPanels(self):
        return list(self._panels.values())

    def iterateAllPanels(self):
        for panel in self._panels.values():
            yield panel

    def deleteAllPanels(self):
        """Henuz cizim/UI katmani yok; sadece modeli temizler (Ref3'teki gibi
        panel_{id} child_window silme/_panel_order YOK - bizde henuz yok)."""
        for panel in self._panels.values():
            panel.deleteAllData()
        self._panels.clear()
        self._nextId = 0

    # ----------------------------------------------------------------- cizim
    def setContainer(self, tag):
        """Panellerin cizilecegi DPG container'inin tag'ini ayarlar (or.
        guiManager'daki 'centerPanel')."""
        self._container = tag

    def getContainer(self):
        return self._container

    def drawPanel(self, panelId):
        """Tek bir paneli (id ile) cizer - (bos) plot UI'sini kurar. Veri
        cizimi (redrawPanelData) HENUZ YOK. Toplu cizim icin script kendi
        dongusunu kurar: `for p in pm.iterateAllPanels(): pm.drawPanel(p.id)`
        (bilerek 'drawPanels' gibi coklu-eylem metodu YOK - API tekil
        eylemlerden olusuyor, coklu islemi script kendisi orgutler)."""
        panel = self._panels.get(panelId)
        if panel is None:
            return
        self._buildPanelUi(panel)
        self._drawnPanelIds.add(panelId)

    def _buildPanelUi(self, panel, width=None, height=None):
        """Panelin plot UI'sini (child_window + plot + legend + eksenler)
        olusturur. Zaten varsa no-op. Veri CIZMEZ. Tag semasi Ref3 ile ayni:
        panel_{id} / plot_{id} / x_axis_{id} / y_axis_{id}."""
        tag = f"panel_{panel.id}"
        if dpg.does_item_exist(tag):
            return
        w = width if width is not None else panel.width
        h = height if height is not None else panel.height

        if self._container and dpg.does_item_exist(self._container):
            dpg.push_container_stack(self._container)
            dpg.add_child_window(tag=tag, width=w, height=h, no_scrollbar=True)
            dpg.pop_container_stack()
        else:
            dpg.add_child_window(tag=tag, width=w, height=h, no_scrollbar=True)

        plotTag = dpg.add_plot(label=panel.caption, height=-1, width=-1, parent=tag,
                               tag=f"plot_{panel.id}", no_mouse_pos=True)
        dpg.add_plot_legend(parent=plotTag, location=dpg.mvPlot_Location_SouthEast)
        dpg.add_plot_axis(dpg.mvXAxis, label="", tag=f"x_axis_{panel.id}", parent=plotTag)
        dpg.add_plot_axis(dpg.mvYAxis, label="y", tag=f"y_axis_{panel.id}", parent=plotTag)

    def hidePanel(self, panelId):
        """Paneli gizler (model: panel.visible=False + varsa UI'da show=False)."""
        panel = self._panels.get(panelId)
        if panel is None:
            return
        panel.setVisible(False)
        tag = f"panel_{panel.id}"
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, show=False)

    def showPanel(self, panelId):
        """Paneli gosterir (model: panel.visible=True + varsa UI'da show=True)."""
        panel = self._panels.get(panelId)
        if panel is None:
            return
        panel.setVisible(True)
        tag = f"panel_{panel.id}"
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, show=True)

    def hideAllPanels(self):
        for panelId in self._panels:
            self.hidePanel(panelId)

    def showAllPanels(self):
        for panelId in self._panels:
            self.showPanel(panelId)

    # ------------------------------------------------------------- periyodik
    def sync(self):
        """Model <-> UI senkronu: daha once drawPanel ile cizilmis ama artik
        modelde (self._panels) olmayan (deletePanel/deleteAllPanels ile
        silinmis) panellerin DPG item'ini (panel_{id}) temizler."""
        orphanIds = self._drawnPanelIds - self._panels.keys()
        for panelId in orphanIds:
            tag = f"panel_{panelId}"
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
            self._drawnPanelIds.discard(panelId)

    def render(self):
        """Periyodik cagrilmasi beklenen metod (or. her frame / bir timer'dan).
        Su an icinde sync() calisiyor + saniyede bir heartbeat print'i var
        (render'in gercekten periyodik tetiklendigini dogrulamak icin)."""
        self.sync()
        now = time.time()
        if now - self._lastRenderPrint >= 1.0:
            self._lastRenderPrint = now
            print(f"[PanelManager.render] tick @ {now:.1f}  panels={len(self._panels)}")
