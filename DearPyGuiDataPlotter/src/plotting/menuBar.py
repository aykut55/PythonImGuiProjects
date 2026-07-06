import dearpygui.dearpygui as dpg


class MenuBar:
    def __init__(self):
        self._on_build_layout = None
        self._on_destroy_layout = None
        self._on_manage_panels = None
        self._on_manage_data = None
        self._on_toggle_script = None
        self._on_toggle_console = None
        self._on_open_all = None
        self._on_collapse_all = None
        self._on_expand_all = None
        self._on_cascade_all = None
        self._on_close_all = None
        self._on_toggle_theme = None
        self._on_command_query = None

    def set_callback(self, on_build_layout=None, on_destroy_layout=None,
                     on_manage_panels=None, on_manage_data=None,
                     on_toggle_script=None, on_toggle_console=None,
                     on_open_all=None, on_collapse_all=None,
                     on_expand_all=None, on_cascade_all=None, on_close_all=None,
                     on_toggle_theme=None, on_command_query=None):
        self._on_build_layout = on_build_layout
        self._on_destroy_layout = on_destroy_layout
        self._on_manage_panels = on_manage_panels
        self._on_manage_data = on_manage_data
        self._on_toggle_script = on_toggle_script
        self._on_toggle_console = on_toggle_console
        self._on_open_all = on_open_all
        self._on_collapse_all = on_collapse_all
        self._on_expand_all = on_expand_all
        self._on_cascade_all = on_cascade_all
        self._on_close_all = on_close_all
        self._on_toggle_theme = on_toggle_theme
        self._on_command_query = on_command_query

    def _show_about(self):
        with dpg.window(label="About", modal=True, width=300, height=100):
            dpg.add_text("DearPyGui Data Plotter v1.0")

    def build(self):
        with dpg.menu_bar():
            with dpg.menu(label="Layout"):
                dpg.add_menu_item(label="Build",
                                  callback=lambda: self._on_build_layout and self._on_build_layout())
                dpg.add_menu_item(label="Destroy",
                                  callback=lambda: self._on_destroy_layout and self._on_destroy_layout())

            with dpg.menu(label="File"):
                dpg.add_menu_item(label="New")
                dpg.add_menu_item(label="Save")
                dpg.add_separator()
                dpg.add_menu_item(label="Exit", callback=lambda: dpg.stop_dearpygui())

            with dpg.menu(label="Edit"):
                dpg.add_menu_item(label="Undo")
                dpg.add_menu_item(label="Redo")

            with dpg.menu(label="View"):
                dpg.add_menu_item(label="Toggle Grid")
                dpg.add_menu_item(label="Zoom Reset")
                dpg.add_separator()
                dpg.add_menu_item(label="Toggle Dark/Light",
                                  callback=lambda: self._on_toggle_theme and self._on_toggle_theme())

            with dpg.menu(label="Panels"):
                dpg.add_menu_item(label="Script Panel",
                                  callback=lambda: self._on_toggle_script and self._on_toggle_script())
                dpg.add_menu_item(label="Console Panel",
                                  callback=lambda: self._on_toggle_console and self._on_toggle_console())
                dpg.add_menu_item(label="Panel Manager",
                                  callback=lambda: self._on_manage_panels and self._on_manage_panels())
                dpg.add_menu_item(label="Data Manager",
                                  callback=lambda: self._on_manage_data and self._on_manage_data())
                dpg.add_separator()
                dpg.add_menu_item(label="Open All",
                                  callback=lambda: self._on_open_all and self._on_open_all())
                dpg.add_menu_item(label="Collapse All",
                                  callback=lambda: self._on_collapse_all and self._on_collapse_all())
                dpg.add_menu_item(label="Expand All",
                                  callback=lambda: self._on_expand_all and self._on_expand_all())
                dpg.add_menu_item(label="Cascade All",
                                  callback=lambda: self._on_cascade_all and self._on_cascade_all())
                dpg.add_menu_item(label="Close All",
                                  callback=lambda: self._on_close_all and self._on_close_all())

            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About", callback=self._show_about)

            dpg.add_spacer(width=20)
            dpg.add_input_text(tag="commandPaletteInput", hint="Komut ara...", width=260,
                               callback=lambda s, a: self._on_command_query and self._on_command_query(a))
