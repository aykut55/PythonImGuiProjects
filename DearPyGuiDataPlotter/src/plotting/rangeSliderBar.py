import dearpygui.dearpygui as dpg


class RangeSliderBar:
    """guiManager'daki centerTopPanel'e gomulu Range Slider (overview plot +
    surukenebilir secim DORTGENI) + yatay Scroll Bar iskeleti.

    Ref3'teki range_controller.py'den (RangeController) baslangicta SADECE
    GORSEL bilesenler alinmisti. Scroll Bar aktif panelin X eksenine IKI
    YONLU baglandi (bkz. syncScrollToView/_onScrollDragged): plot pan/zoom/
    box-select edilince scroll bar canli takip eder, scroll bar suruklenince
    de plot pan eder (span SABIT kalir). Secim dortgeni de artik AYNI
    sekilde IKI YONLU baglandi (bkz. syncSliderToView/_onSliderRectDragged) -
    ImPlot'un native `drag_rect` item'i (bkz. build()) HEM 4 kenardan resize
    (zoom) HEM de ic kismindan tutup kaydirma (pan) destekliyor, ikisi de
    TEK bir callback'e dusuyor - hangisinin oldugunu ayirt etmeye gerek yok,
    surukleme bittiginde dortgenin GUNCEL (xmin,xmax) degeri ne ise aktif
    panelin X eksenine dogrudan o uygulanir.

    Gorunurluk IKI KATMANLI:
      1) centerTopPanel'in tamami: panelManager'da EN AZ BIR GORUNUR panel
         varsa gosterilir, hicbiri gorunmuyorsa (ya da hic panel yoksa)
         gizlenir (bkz. sync()).
      2) Bunun icindeki Range Slider ve Scroll Bar BAGIMSIZ birer bayrakla
         (Ref3'teki set_slider_visible/set_scrollbar_visible ile ayni
         fikir) ayri ayri gosterilip gizlenebilir - bkz. setSliderVisible/
         setScrollbarVisible/_applyVisibility. Etiket metni bu iki bayraga
         gore DINAMIK: ikisi de gorunurse "Range Slider / Scroll Bar", sadece
         biri gorunurse onun aciklamasi, hicbiri gorunmuyorsa etiket de
         gizlenir (bkz. _updateLabelText)."""

    CONTAINER_TAG = "centerTopPanel"
    OVERVIEW_PLOT_TAG = "range_overview_plot"
    OVERVIEW_X_AXIS_TAG = "range_overview_x_axis"
    OVERVIEW_Y_AXIS_TAG = "range_overview_y_axis"
    RECT_TAG = "range_selection_rect"
    SCROLL_TAG = "range_scroll"
    RANGE_LABEL_TAG = "range_slider_label"
    CONTENT_GROUP_TAG = "range_slider_bar_group"
    SPACING_THEME_TAG = "range_slider_bar_spacing_theme"
    PADDING_THEME_TAG = "range_slider_bar_padding_theme"
    SCROLL_THEME_TAG = "range_scroll_theme"

    CONTAINER_VPADDING = 4  # _applyContainerPaddingTheme'deki (10,2) dikey padding'in TOPLAMI (ust+alt)
    BOTTOM_GAP = 10          # centerTopPanel'in alt kenari ile gorunur icerigin arasinda birakilan sabit pay
    DRAG_Y_ADJUST_STRIDE = 4  # scroll bar suruklenirken kac tik'te bir Y ekseni adjust edilecek (her tik degil - split_frame maliyeti)

    def __init__(self):
        self._panelManager = None  # bkz. setPanelManager (guiManager tarafindan baglanir)
        self._sliderVisible = False    # Range Slider (label+overview plot) gorunur mu.
        # GUI'deki "top_show_sliderange_checkbox"un default_value'su False - DPG
        # default_value verilince callback'i TETIKLEMEDIGI icin buradaki
        # baslangic degeri checkbox'in gorsel varsayilaniyla EL ILE ayni
        # tutulmali, yoksa checkbox gorsel olarak unchecked gorunurken model
        # hala True kalip veri yuklenince overview plot checked'mis gibi
        # gorunmeye devam ediyordu (bkz. panelManager._activeUpdateMode'daki
        # ayni sinif bug).
        self._scrollbarVisible = True  # Scroll Bar gorunur mu
        self._scrollDragActive = False  # bir onceki frame'de scroll bar suruklenirken miydi (bkz. _syncScrollToActivePanel)
        self._scrollDragTickCount = 0  # drag suresince kac _onScrollDragged tetiklendi (bkz. DRAG_Y_ADJUST_STRIDE)
        self._scrollDragPanelId = None  # drag BASLARKEN kilitlenen panelId (bkz. _onScrollDragged/_syncScrollToActivePanel) -
        # kilit acilirken de AYNI id kullanilmali, yoksa drag sirasinda aktif panel
        # degisirse (ornegin drag bitis frame'inde baska bir panele tiklanirsa)
        # yanlis panel unlockXAxis edilir ve gercekten kilitlenen panel x ekseni
        # SONSUZA KADAR manuel/sabit limitte kilitli kalir (zoom/pan'a tepki vermez).
        self._sliderDragActive = False  # bir onceki frame'de secim dortgeni suruklenirken miydi (bkz. _syncSliderToActivePanel)
        self._sliderDragTickCount = 0  # drag suresince kac _onSliderRectDragged tetiklendi (bkz. DRAG_Y_ADJUST_STRIDE)
        self._sliderDragPanelId = None  # scroll bar'daki AYNI kilit-panel eslesmesi sorunu icin (bkz. _scrollDragPanelId) - drag BASLARKEN sabitlenir
        self._sliderDragEventCount = 0  # _onSliderRectDragged her tetiklendiginde artar (bkz. _syncSliderToActivePanel)
        self._sliderDragEventSeen = 0   # en son _syncSliderToActivePanel'in gordugu _sliderDragEventCount degeri -
        # scroll bar'in tersine drag_rect'in dpg.is_item_active DESTEGI GARANTI DEGIL
        # (plot-ici ozel bir item - standart widget degil), o yuzden "suruklemenin
        # halen surdugu" bilgisi is_item_active YERINE "bu frame'den beri en az
        # bir _onSliderRectDragged event'i geldi mi" karsilastirmasiyla tespit
        # edilir - is_item_active desteklemese bile calisir.

    def setPanelManager(self, panelManager):
        self._panelManager = panelManager

    def setSliderVisible(self, visible=None):
        """Range Slider'i (etiket + overview plot) goster/gizle.
        visible=None -> toggle (Ref3'teki set_slider_visible ile ayni)."""
        self._sliderVisible = (not self._sliderVisible) if visible is None else bool(visible)
        self._applyVisibility()

    def setScrollbarVisible(self, visible=None):
        """Scroll Bar'i goster/gizle. visible=None -> toggle."""
        self._scrollbarVisible = (not self._scrollbarVisible) if visible is None else bool(visible)
        self._applyVisibility()

    def build(self, parentTag=CONTAINER_TAG):
        """Range Slider (etiket + overview plot + secim dortgeni) ve Scroll
        Bar'i parentTag icine (varsayilan: centerTopPanel) DIKEY SIRAYLA
        (etiket -> range slider -> scroll bar) cizer. Ucu, araya DPG'nin
        varsayilan item-spacing'inin actigi bosluk kalmasin diye TEK bir
        group icine alinip o group'a ItemSpacing=0 teması baglaniyor (bkz.
        _applySpacingTheme)."""
        with dpg.group(parent=parentTag, tag=self.CONTENT_GROUP_TAG):
            dpg.add_text("Range Slider", tag=self.RANGE_LABEL_TAG)

            with dpg.plot(tag=self.OVERVIEW_PLOT_TAG, label="", height=110, width=-1,
                         no_menus=True, no_box_select=True, no_mouse_pos=True,
                         pan_button=-1, fit_button=-1, box_select_button=-1,
                         context_menu_button=-1, zoom_rate=0):
                dpg.add_plot_axis(dpg.mvXAxis, label="", tag=self.OVERVIEW_X_AXIS_TAG)
                dpg.add_plot_axis(dpg.mvYAxis, label="", tag=self.OVERVIEW_Y_AXIS_TAG)
            # Overview plot artik SEMBOLIK 0..100 (x) / 0..1 (y) bir "fraction
            # uzayi" - gercek veriyle degil, aktif panelin gorunur X penceresinin
            # TOPLAM veri araligindaki ORANIYLA (bkz. syncSliderToView) calisiyor.
            # Kullanici etkilesimi zaten pan_button/fit_button/zoom_rate=0 ile
            # KAPALI, o yuzden bu limitler BIR KERE sabitlenip bir daha
            # DOKUNULMUYOR - dortgenin degerleri hep bu 0..100 uzayina gore
            # yorumlanir.
            dpg.set_axis_limits(self.OVERVIEW_X_AXIS_TAG, 0, 100)
            dpg.set_axis_limits(self.OVERVIEW_Y_AXIS_TAG, 0, 1)

            # ImPlot'un native drag_rect'i: 4 kenardan resize (zoom) VE ic
            # kismindan tutup kaydirma (pan) native olarak destekleniyor -
            # onceki ayri Start/End drag_line + statik shade_series ikilisinin
            # yerine gecti (kullanici dortgeni SURUKLEYEMEDIGINI bildirdi -
            # shade_series zaten interaktif bir item degil).
            dpg.add_drag_rect(tag=self.RECT_TAG, parent=self.OVERVIEW_PLOT_TAG,
                              label="Visible Range", default_value=(0, 0, 100, 1),
                              color=(80, 160, 255, 90), no_fit=True,
                              callback=self._onSliderRectDragged)

            dpg.add_spacer(height=6)
            dpg.add_slider_int(tag=self.SCROLL_TAG, width=-1, height=11,
                               min_value=0, max_value=100, default_value=100,
                               no_input=True, callback=self._onScrollDragged)

        self._applySpacingTheme()
        self._applyContainerPaddingTheme(parentTag)
        self._applyScrollTheme()
        self._applyVisibility()

    def _applyContainerPaddingTheme(self, containerTag):
        """centerTopPanel'in USTUNDEKI bosluk cok genis oldugu (etiket asagi
        itiliyordu) icin GuiManager.panelTheme'in dikey WindowPadding'ini
        (PANEL_PADDING=10) burada 2'ye dusuren, sadece bu container'a ozel
        bir tema baglar. guiManager._buildLayoutDefault() bu build()'i
        panelTheme baglandiktan SONRA cagirir, o yuzden bu tema panelTheme'i
        EZER (son baglanan tema kazanir) - centerTopPanel'in yatay padding'i
        (10) korunur, sadece dikeyi daralir."""
        if not dpg.does_item_exist(self.PADDING_THEME_TAG):
            with dpg.theme(tag=self.PADDING_THEME_TAG):
                with dpg.theme_component(dpg.mvChildWindow):
                    dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 2,
                                        category=dpg.mvThemeCat_Core)
        dpg.bind_item_theme(containerTag, self.PADDING_THEME_TAG)

    def _applyScrollTheme(self):
        """Scroll bar'in gercek kalinligi add_slider_int'e verilen height
        parametresiyle DEGIL, guiManager._buildMenuBarHeightTheme'in main_
        window'dan miras gelen FramePadding=(8,11) temasiyla belirleniyordu
        (centerTopPanel bu temayi override etmiyor) - height=11/14 gibi
        degerler bu yuzden GORSEL olarak hicbir etki yapmiyordu. compactControl
        Theme'deki (DataManager combo'lariyla ayni) desenle, SADECE bu slider'a
        ozel kucuk bir FramePadding baglayip gercekten inceltiyoruz."""
        if not dpg.does_item_exist(self.SCROLL_THEME_TAG):
            with dpg.theme(tag=self.SCROLL_THEME_TAG):
                with dpg.theme_component(dpg.mvSliderInt):
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 4, 2,
                                        category=dpg.mvThemeCat_Core)
        dpg.bind_item_theme(self.SCROLL_TAG, self.SCROLL_THEME_TAG)

    def _applySpacingTheme(self):
        """CONTENT_GROUP_TAG icindeki etiket/plot/scrollbar arasinda DPG'nin
        varsayilan dikey item-spacing'ini (~8px) sifirlar - kullanicinin
        istedigi 'boslukSUZ' dikey yigin budur."""
        if not dpg.does_item_exist(self.SPACING_THEME_TAG):
            with dpg.theme(tag=self.SPACING_THEME_TAG):
                with dpg.theme_component(dpg.mvAll):
                    dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 0, 0,
                                        category=dpg.mvThemeCat_Core)
        dpg.bind_item_theme(self.CONTENT_GROUP_TAG, self.SPACING_THEME_TAG)

    def _applyVisibility(self):
        """setSliderVisible/setScrollbarVisible bayraklarini ilgili DPG
        item'larina uygular - Ref3'teki _apply_visibility ile ayni: Range
        Slider (overview plot) ve Scroll Bar birbirinden BAGIMSIZ gosterilir/
        gizlenir. Etiketin kendisi ikisinden EN AZ BIRI gorunurse gosterilir
        (bkz. _updateLabelText) - o yuzden burada OVERVIEW_PLOT_TAG'e
        RANGE_LABEL_TAG dahil edilmedi."""
        if dpg.does_item_exist(self.OVERVIEW_PLOT_TAG):
            dpg.configure_item(self.OVERVIEW_PLOT_TAG, show=self._sliderVisible)
        if dpg.does_item_exist(self.SCROLL_TAG):
            dpg.configure_item(self.SCROLL_TAG, show=self._scrollbarVisible)
        self._updateLabelText()

    def _updateLabelText(self):
        """Etiketi ikisinin de gorunurluguna gore gunceller: ikisi de
        gorunurse birlesik 'Range Slider / Scroll Bar', sadece biri gorunurse
        ONUN aciklamasi, hicbiri gorunmuyorsa etiket de gizlenir."""
        if not dpg.does_item_exist(self.RANGE_LABEL_TAG):
            return
        if self._sliderVisible and self._scrollbarVisible:
            text = "Range Slider / Scroll Bar"
        elif self._sliderVisible:
            text = "Range Slider"
        elif self._scrollbarVisible:
            text = "Scroll Bar"
        else:
            text = ""
        dpg.set_value(self.RANGE_LABEL_TAG, text)
        dpg.configure_item(self.RANGE_LABEL_TAG, show=bool(text))

    def _anyPanelVisible(self):
        if self._panelManager is None:
            return False
        return any(p.getVisible() for p in self._panelManager.iterateAllPanels())

    # ------------------------------------------------------------- periyodik
    def sync(self):
        """centerTopPanel'in gorunurlugunu panelManager'daki GUNCEL panel
        gorunurluguyle senkronlar - en az bir panel gorunurse gosterilir,
        hicbiri gorunmuyorsa (ya da hic panel yoksa) gizlenir. scripts/
        default.py'de zaten kullanilan `dpg.configure_item("centerTopPanel",
        show=...)` cagrisinin AYNISI - ayri bir "degisti mi" onbellegi
        YOK, dogrudan her cagrida uygulanir.

        Buna EK: Range Slider ve Scroll Bar'in IKISI BIRDEN gizliyse
        (_sliderVisible ve _scrollbarVisible ikisi de False) gosterilecek
        hicbir icerik kalmadigi icin centerTopPanel'in TAMAMI da gizlenir -
        panel(ler) gorunur olsa bile."""
        if dpg.does_item_exist(self.CONTAINER_TAG):
            show = self._anyPanelVisible() and (self._sliderVisible or self._scrollbarVisible)
            dpg.configure_item(self.CONTAINER_TAG, show=show)
        self._syncScrollToActivePanel()
        self._syncSliderToActivePanel()

    def _syncScrollToActivePanel(self):
        """Her frame cagrilir - scroll bar'i aktif panelin O ANKI gorunur X
        araligina gore gunceller. Onceden SADECE pan butonlarindan (guiManager.
        _doPan -> syncScrollToView) tetikleniyordu; mouse ile suruklenerek
        pan yapildiginda veya box-select/wheel-zoom ile X eksen araligi
        DPG'nin kendi ic mekanizmasiyla degistiginde scroll bar HABERSIZ
        kaliyordu. Artik her frame canli okunuyor, TEK istisna: kullanici
        scroll bar'i O AN suruklerken (dpg.is_item_active) burasi calismaz -
        yoksa bir onceki frame'in eski konumu, kullanicinin az once surukledigi
        degeri her frame geri ezerdi.

        Drag BITTIGI (bir onceki frame active, bu frame degil) frame'de: drag
        sirasinda panToFraction(liveOnly=True) tarafindan KILITLI birakilan x
        eksenini unlockXAxis() ile serbest birakir ve Y eksenini SON KEZ adjust
        eder - HER TIK'te degil, ayrica _onScrollDragged icinde DRAG_Y_ADJUST_STRIDE
        tik'te bir de ARA adjust yapiliyor (surukleme suresince Y'nin de gozle
        gorulur sekilde takip etmesi icin, ama her tik'te degil - split_frame
        maliyeti "dalga dalga" kekemelige yol aciyordu).

        unlockXAxis burada getActivePanelId() ILE DEGIL, _scrollDragPanelId
        (drag BASLARKEN _onScrollDragged'in kilitledigi panel) ile cagrilir -
        drag suresince aktif panel degisirse (ör. drag bitis frame'inde baska
        bir panele tiklanirsa) yine de KILITLENEN panel acilir, YANLIS
        (yeni aktif) panel degil."""
        if self._panelManager is None or not dpg.does_item_exist(self.SCROLL_TAG):
            return
        active = dpg.is_item_active(self.SCROLL_TAG)
        if self._scrollDragActive and not active:
            panelId = self._scrollDragPanelId if self._scrollDragPanelId is not None \
                else self._panelManager.getActivePanelId()
            self._panelManager.unlockXAxis(panelId)
            self._panelManager.adjustYAxis(panelId)
            self._scrollDragTickCount = 0
            self._scrollDragPanelId = None
        self._scrollDragActive = active
        if active:
            return
        self.syncScrollToView()

    def syncScrollToView(self, panelId=None):
        """Scroll bar'in degerini panelin GORUNUR X penceresinin TOPLAM veri
        icindeki ORANINA gore gunceller (Ref1'deki _update_pan_indicator ile
        ayni fikir: offset degisince gosterge de degisir). Her frame
        (_syncScrollToActivePanel) VE pan butonlarindan (guiManager._doPan)
        sonra cagrilir.

        SADECE xMax'i (sag kenari) izlemek YANLISTI: Basa'ya basinca xMax =
        dataMin + span oluyordu, span (gorunur genislik) toplam veriye gore
        kucuk degilse bu deger 0'a YAKIN OLMUYOR, scroll bar en basa gitmis
        gibi gorunmuyordu. Bunun yerine pencerenin sol kenarinin (xMin), veri
        kaydirilabilecek TOPLAM mesafe (total - span) icindeki oranini
        (fraction) hesaplayip 0..count araligina olcekliyoruz:
          - Basa: xMin == dataMin -> fraction 0 -> scroll en solda.
          - Sona: xMin == dataMax - span -> fraction 1 -> scroll en sagda.
          - Tum veri gorunuyorsa (span >= total, kaydiracak yer YOK) -> en
            sagda kalir (full-data yuklemede istenen varsayilan konum)."""
        if self._panelManager is None or not dpg.does_item_exist(self.SCROLL_TAG):
            return
        panelId = self._panelManager.getActivePanelId() if panelId is None else panelId
        count = self._panelManager.getPanelDataCount(panelId)
        limits = self._panelManager.getXAxisLimits(panelId)
        dataRange = self._panelManager.getFullXRange(panelId)
        if count <= 0 or limits is None or dataRange is None:
            return
        xMin, xMax = limits
        dataMin, dataMax = dataRange
        total = dataMax - dataMin
        span = xMax - xMin
        denom = total - span
        fraction = 1.0 if denom <= 0 else max(0.0, min(1.0, (xMin - dataMin) / denom))
        dpg.configure_item(self.SCROLL_TAG, max_value=count)
        dpg.set_value(self.SCROLL_TAG, fraction * count)

    def _onScrollDragged(self, sender=None, appData=None):
        """Kullanici scroll bar'i mouse ile suruklediginde (SANIYEDE ONLARCA
        KEZ) cagrilir - syncScrollToView'in TERSI: plot'un GORUNUR X penceresini
        (mevcut genisligi koruyarak) scroll bar'in yeni konumuna gore pan eder
        (bkz. panelManager.panToFraction). liveOnly=True: her tikte split_frame/
        set_axis_limits_auto YAPILMAZ (pahali - "dalga dalga" kekemelige yol
        aciyordu), sadece eksen anlik kaydirilir.

        Y ekseni HER tik'te degil, DRAG_Y_ADJUST_STRIDE tik'te BIR ARA adjust
        edilir - hem surukleme akici kalsin hem de kullanici Y'nin de takip
        ettigini gorsun diye orta yol (drag bitince zaten SON bir adjust daha
        yapiliyor, bkz. _syncScrollToActivePanel).

        Kilitlenen panelId, drag'in ILK tik'inde _scrollDragPanelId'e
        SABITLENIR - sonraki tik'ler (aktif panel bu arada degismis olsa
        bile) hep AYNI panelin eksenini kilitler, boylece
        _syncScrollToActivePanel drag bitince dogru paneli acar (bkz. orada
        eklenen aciklama)."""
        if self._panelManager is None:
            return
        if self._scrollDragPanelId is None:
            self._scrollDragPanelId = self._panelManager.getActivePanelId()
        panelId = self._scrollDragPanelId
        count = self._panelManager.getPanelDataCount(panelId)
        if count <= 0:
            return
        fraction = appData / count
        self._panelManager.panToFraction(panelId, fraction, liveOnly=True)
        self._scrollDragTickCount += 1
        if self._scrollDragTickCount % self.DRAG_Y_ADJUST_STRIDE == 0:
            self._panelManager.adjustYAxis(panelId)

    # ------------------------------------------------------- Range Slider (secim dortgeni)
    def _syncSliderToActivePanel(self):
        """Her frame cagrilir - scroll bar'daki _syncScrollToActivePanel ile
        AYNI desen, TEK fark suruklemenin halen surdugunu tespit yontemi:
        scroll bar standart bir widget oldugu icin dpg.is_item_active
        guvenilir calisiyordu, ama secim dortgeni (drag_rect) plot-ici ozel
        bir item - is_item_active DESTEGI garanti degil. Onun yerine "bu
        cagridan beri en az bir _onSliderRectDragged event'i geldi mi"
        (_sliderDragEventCount degisti mi) kontrolu kullaniliyor.

        Suruklemenin surdugu tespit edilirse burasi calismaz, drag BITTIGI
        (bir onceki cagrida aktifti, bu cagrida degil) anda
        zoomToFractionRange(liveOnly=True) tarafindan kilitli birakilan x
        eksenini unlockXAxis() ile acar + Y'yi SON KEZ adjust eder, digerinde
        canli syncSliderToView() ile dortgenin konumunu gunceller.

        unlockXAxis burada da getActivePanelId() ILE DEGIL, _sliderDragPanelId
        (drag BASLARKEN _onSliderRectDragged'in kilitledigi panel) ile
        cagrilir - ayni sebep: scroll bar'daki kilit/kilit-acma panel
        eslesmezligi hatasi (bkz. _syncScrollToActivePanel)."""
        if self._panelManager is None:
            return
        active = self._sliderDragEventCount != self._sliderDragEventSeen
        self._sliderDragEventSeen = self._sliderDragEventCount
        if self._sliderDragActive and not active:
            panelId = self._sliderDragPanelId if self._sliderDragPanelId is not None \
                else self._panelManager.getActivePanelId()
            self._panelManager.unlockXAxis(panelId)
            self._panelManager.adjustYAxis(panelId)
            self._sliderDragTickCount = 0
            self._sliderDragPanelId = None
        self._sliderDragActive = active
        if active:
            return
        self.syncSliderToView()

    def syncSliderToView(self, panelId=None):
        """Secim dortgeninin degerini panelin GORUNUR X penceresinin TOPLAM
        veri icindeki ORANINA (0..100, bkz. overview eksenlerinin build()'te
        sabitlenen 0..100/0..1 uzayi) gore gunceller - syncScrollToView'in
        secim dortgeni karsiligi."""
        if self._panelManager is None or not dpg.does_item_exist(self.RECT_TAG):
            return
        panelId = self._panelManager.getActivePanelId() if panelId is None else panelId
        limits = self._panelManager.getXAxisLimits(panelId)
        dataRange = self._panelManager.getFullXRange(panelId)
        if limits is None or dataRange is None:
            return
        xMin, xMax = limits
        dataMin, dataMax = dataRange
        total = dataMax - dataMin
        if total <= 0:
            return
        startFrac = max(0.0, min(1.0, (xMin - dataMin) / total)) * 100.0
        endFrac = max(0.0, min(1.0, (xMax - dataMin) / total)) * 100.0
        dpg.set_value(self.RECT_TAG, [startFrac, 0.0, endFrac, 1.0])

    def _onSliderRectDragged(self, sender=None, appData=None):
        """Secim dortgeni mouse ile suruklendiginde (kenardan resize/zoom VEYA
        ic kismindan tutup kaydirma/pan - ImPlot'un drag_rect'i ikisini de
        AYNI callback'e dusurur, hangisi oldugunu ayirt etmeye gerek yok)
        cagrilir - syncSliderToView'in TERSI: dortgenin GUNCEL (xmin,xmax)
        degerini okuyup aktif panelin X eksenini zoomToFractionRange
        (liveOnly=True) ile bu araliga kilitler.

        xmin/xmax MIN_GAP_FRACTION altina cokmesin (span sifirlanmasin) diye
        clamp edilir; y (ymin/ymax) ise SEMBOLIK oldugu icin (gercek bir
        anlami yok) kullanici ust/alt kenari surukleyip bozarsa bile her
        tik'te 0..1'e geri sabitlenir - set_value ile dortgenin kendisine
        de yaziliyor (yoksa gorsel olarak carpiklasir).

        Kilitlenen panelId, scroll bar'daki AYNI desenle drag'in ILK
        tik'inde _sliderDragPanelId'e sabitlenir (bkz. _syncSliderToActivePanel)."""
        if self._panelManager is None:
            return
        self._sliderDragEventCount += 1
        if self._sliderDragPanelId is None:
            self._sliderDragPanelId = self._panelManager.getActivePanelId()
        panelId = self._sliderDragPanelId

        MIN_GAP_FRACTION = 1.0  # 0..100 uzayinda minimum xmin/xmax farki (yaklasik %1)
        rect = dpg.get_value(self.RECT_TAG)
        startVal = max(0.0, min(100.0, rect[0]))
        endVal = max(0.0, min(100.0, rect[2]))
        if endVal - startVal < MIN_GAP_FRACTION:
            endVal = min(100.0, startVal + MIN_GAP_FRACTION)
            startVal = max(0.0, endVal - MIN_GAP_FRACTION)
        dpg.set_value(self.RECT_TAG, [startVal, 0.0, endVal, 1.0])

        self._panelManager.zoomToFractionRange(panelId, startVal / 100.0, endVal / 100.0, liveOnly=True)
        self._sliderDragTickCount += 1
        if self._sliderDragTickCount % self.DRAG_Y_ADJUST_STRIDE == 0:
            self._panelManager.adjustYAxis(panelId)

    def _syncContainerHeight(self):
        """centerTopPanel'in yuksekligini GERCEKTEN gorunen icerige (grup
        icindeki hangi ogeler show=True ise onlarin toplam rect'i) gore
        ayarlar - sabit/tahmini piksel degerleri YOK, dogrudan CONTENT_GROUP_TAG'in
        olculen yuksekligi + BOTTOM_GAP kullanilir. Boylece Range Slider/
        Scroll Bar'dan hangisi gorunuyorsa centerTopPanel'in alt kenari
        onun bir tik altinda kalir."""
        if not (dpg.does_item_exist(self.CONTAINER_TAG) and dpg.does_item_exist(self.CONTENT_GROUP_TAG)):
            return
        contentHeight = dpg.get_item_rect_size(self.CONTENT_GROUP_TAG)[1]
        dpg.configure_item(self.CONTAINER_TAG,
                          height=int(contentHeight + self.CONTAINER_VPADDING + self.BOTTOM_GAP))

    def render(self):
        """GuiManager.render() tarafindan her frame cagrilir. sync()'e ve
        _syncContainerHeight()'e delege ediyor - ikisi de her frame calisir
        (bkz. sync()/_syncContainerHeight())."""
        self.sync()
        self._syncContainerHeight()
