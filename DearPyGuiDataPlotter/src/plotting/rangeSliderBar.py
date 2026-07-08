import dearpygui.dearpygui as dpg


class RangeSliderBar:
    """guiManager'daki centerTopPanel'e gomulu Range Slider (overview plot +
    Start/End drag-line marker'lari + secili aralik golgesi) + yatay Scroll
    Bar iskeleti.

    Ref3'teki range_controller.py'den (RangeController) SADECE GORSEL
    bilesenler alindi: "Range Slider" etiketi + overview plot + marker'lar +
    shade + scroll slider. Mouse handler'lari, gercek plot pan/zoom'a baglanti
    (visible_range_changed_callback), pan/scroll hesaplari, seri/veri baglama
    BILINCLI OLARAK tasinmadi - "bagla" degil sadece "iskelet" istendi. Butun
    widget'lar sabit/dummy degerlerle cizilir, hicbir callback yoktur.

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
    LEFT_MARKER_TAG = "range_left_line"
    RIGHT_MARKER_TAG = "range_right_line"
    SHADE_TAG = "range_selection_shade"
    SHADE_THEME_TAG = "range_selection_shade_theme"
    SCROLL_TAG = "range_scroll"
    RANGE_LABEL_TAG = "range_slider_label"
    CONTENT_GROUP_TAG = "range_slider_bar_group"
    SPACING_THEME_TAG = "range_slider_bar_spacing_theme"
    PADDING_THEME_TAG = "range_slider_bar_padding_theme"

    def __init__(self):
        self._panelManager = None  # bkz. setPanelManager (guiManager tarafindan baglanir)
        self._sliderVisible = True     # Range Slider (label+overview plot) gorunur mu
        self._scrollbarVisible = True  # Scroll Bar gorunur mu

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
        """Range Slider (etiket + overview plot + Start/End marker + shade) ve
        Scroll Bar'i parentTag icine (varsayilan: centerTopPanel) DIKEY
        SIRAYLA (etiket -> range slider -> scroll bar) cizer. Ucu, araya
        DPG'nin varsayilan item-spacing'inin actigi bosluk kalmasin diye
        TEK bir group icine alinip o group'a ItemSpacing=0 teması
        baglaniyor (bkz. _applySpacingTheme)."""
        with dpg.group(parent=parentTag, tag=self.CONTENT_GROUP_TAG):
            dpg.add_text("Range Slider", tag=self.RANGE_LABEL_TAG)

            with dpg.plot(tag=self.OVERVIEW_PLOT_TAG, label="", height=110, width=-1,
                         no_menus=True, no_box_select=True, no_mouse_pos=True,
                         pan_button=-1, fit_button=-1, box_select_button=-1,
                         context_menu_button=-1, zoom_rate=0):
                dpg.add_plot_axis(dpg.mvXAxis, label="", tag=self.OVERVIEW_X_AXIS_TAG)
                with dpg.plot_axis(dpg.mvYAxis, label="", tag=self.OVERVIEW_Y_AXIS_TAG):
                    dpg.add_shade_series([0, 100], [0, 0], y2=[1, 1],
                                         label="Selected Range", tag=self.SHADE_TAG)
                    self._applyShadeTheme()

            dpg.add_drag_line(tag=self.LEFT_MARKER_TAG, parent=self.OVERVIEW_PLOT_TAG,
                              label="Start", default_value=0,
                              color=(80, 160, 255, 255), thickness=2,
                              vertical=True, no_fit=True)
            dpg.add_drag_line(tag=self.RIGHT_MARKER_TAG, parent=self.OVERVIEW_PLOT_TAG,
                              label="End", default_value=100,
                              color=(80, 160, 255, 255), thickness=2,
                              vertical=True, no_fit=True)

            dpg.add_spacer(height=6)
            dpg.add_slider_int(tag=self.SCROLL_TAG, width=-1, height=14,
                               min_value=0, max_value=100, default_value=100,
                               no_input=True)

        self._applySpacingTheme()
        self._applyContainerPaddingTheme(parentTag)
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

    def _applyShadeTheme(self):
        if not dpg.does_item_exist(self.SHADE_THEME_TAG):
            with dpg.theme(tag=self.SHADE_THEME_TAG):
                with dpg.theme_component(dpg.mvShadeSeries):
                    dpg.add_theme_color(dpg.mvPlotCol_Fill, (80, 160, 255, 35),
                                        category=dpg.mvThemeCat_Plots)
        dpg.bind_item_theme(self.SHADE_TAG, self.SHADE_THEME_TAG)

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
        YOK, dogrudan her cagrida uygulanir."""
        if dpg.does_item_exist(self.CONTAINER_TAG):
            dpg.configure_item(self.CONTAINER_TAG, show=self._anyPanelVisible())

    def render(self):
        """GuiManager.render() tarafindan her frame cagrilir. sync()'e
        delege ediyor (bkz. sync())."""
        self.sync()
