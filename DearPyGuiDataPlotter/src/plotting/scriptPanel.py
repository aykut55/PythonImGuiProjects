import os
import traceback

import dearpygui.dearpygui as dpg


class ScriptPanel:
    """Floating window for running Python against the live app.

    Opens like the Panel Manager (movable window). Write code in the editor and
    press Run; the code is exec'd in a namespace that exposes the app objects
    (app, gm, pm, dpg, Panel, PanelData). The namespace persists across runs so
    state can be built up incrementally.

    Scripts live in <root>/scripts. On first open the 'default.py' script is
    loaded; Open/Save/Save As manage other script files.
    """

    TAG = "script_panel"
    CODE = "script_code"
    FILE_LABEL = "script_file_label"
    OPEN_DIALOG = "script_open_dialog"
    SAVEAS_DIALOG = "script_saveas_dialog"

    FALLBACK_CODE = (
        "# Hazir: app, gm, pm, dpg, Panel, PanelData\n"
    )

    def __init__(self):
        self._namespace = {"dpg": dpg}
        self._visible = True
        self._on_close_cb = None
        self._on_run_complete = None
        self._on_open_console = None
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._scripts_dir = os.path.join(root, "scripts")
        self._current_path = os.path.join(self._scripts_dir, "default.py")

    def set_globals(self, **kwargs):
        """Add/refresh objects available to scripts (e.g. app=App, gm=GuiManager)."""
        self._namespace.update(kwargs)

    def set_on_run_complete(self, callback):
        self._on_run_complete = callback

    def set_on_open_console(self, callback):
        self._on_open_console = callback

    @property
    def namespace(self):
        return self._namespace

    # ---- file helpers -----------------------------------------------------
    def _read_file(self, path) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.FALLBACK_CODE)
            return self.FALLBACK_CODE
        except UnicodeDecodeError:
            # External editor may have saved as Windows Turkish (cp1254) ANSI.
            with open(path, "r", encoding="cp1254", errors="replace") as f:
                return f.read()

    def _load_path(self, path):
        self._current_path = path
        if dpg.does_item_exist(self.CODE):
            dpg.set_value(self.CODE, self._read_file(path))
        self._update_file_label()

    def _update_file_label(self):
        if dpg.does_item_exist(self.FILE_LABEL):
            dpg.set_value(self.FILE_LABEL, os.path.basename(self._current_path))

    # ---- build ------------------------------------------------------------
    def build(self, x, y, width, height, on_close=None):
        self._on_close_cb = on_close
        initial = self._read_file(self._current_path)
        with dpg.window(label="Script Panel", tag=self.TAG, pos=(x, y),
                        width=width, height=height, show=self._visible,
                        on_close=self._on_close):
            with dpg.group(horizontal=True):
                dpg.add_button(label="Run", callback=self._run)
                dpg.add_button(label="Open", callback=lambda: dpg.show_item(self.OPEN_DIALOG))
                dpg.add_button(label="Reopen", callback=self._reopen)
                dpg.add_button(label="Save", callback=self._save)
                dpg.add_button(label="Save As", callback=lambda: dpg.show_item(self.SAVEAS_DIALOG))
                dpg.add_button(label="Console",
                               callback=lambda: self._on_open_console and self._on_open_console())
                dpg.add_text("File:")
                dpg.add_text(os.path.basename(self._current_path), tag=self.FILE_LABEL)
            dpg.add_input_text(tag=self.CODE, multiline=True, width=-1, height=-1,
                               default_value=initial, tab_input=True)

        with dpg.file_dialog(tag=self.OPEN_DIALOG, show=False, directory_selector=False,
                             width=600, height=400, default_path=self._scripts_dir,
                             callback=self._on_open_selected):
            dpg.add_file_extension(".py")
            dpg.add_file_extension(".*")

        with dpg.file_dialog(tag=self.SAVEAS_DIALOG, show=False, directory_selector=False,
                             width=600, height=400, default_path=self._scripts_dir,
                             callback=self._on_saveas_selected):
            dpg.add_file_extension(".py")
            dpg.add_file_extension(".*")

    def _on_close(self):
        # Keep state in sync when the window's X button is used.
        self._visible = False
        if self._on_close_cb:
            self._on_close_cb()

    def is_visible(self):
        return self._visible

    # ---- actions ----------------------------------------------------------
    def _run(self):
        code = dpg.get_value(self.CODE)
        try:
            exec(code, self._namespace)
        except Exception:
            print(traceback.format_exc())
        if self._on_run_complete:
            try:
                self._on_run_complete()
            except Exception:
                print(traceback.format_exc())

    def _reopen(self):
        # Reload the active file from disk (e.g. after editing it externally).
        self._load_path(self._current_path)
        print(f"Yeniden yuklendi: {self._current_path}")

    def _save(self):
        self._save_to(self._current_path)

    def _save_to(self, path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(dpg.get_value(self.CODE))
            self._current_path = path
            self._update_file_label()
            print(f"Kaydedildi: {path}")
        except Exception:
            print(traceback.format_exc())

    def _on_open_selected(self, sender, app_data):
        path = app_data.get("file_path_name")
        if path:
            self._load_path(path)

    def _on_saveas_selected(self, sender, app_data):
        path = app_data.get("file_path_name")
        if path:
            if not os.path.splitext(path)[1]:
                path += ".py"
            self._save_to(path)

    # ---- visibility -------------------------------------------------------
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

    def set_geometry(self, x, y, width, height):
        if dpg.does_item_exist(self.TAG):
            dpg.set_item_pos(self.TAG, (x, y))
            dpg.set_item_width(self.TAG, width)
            dpg.set_item_height(self.TAG, height)

    # ---- rightSlotPanels arayuzu (GuiManager, camelCase adlarla cagirir) ---
    def isVisible(self):
        return self.is_visible()

    def setGeometry(self, x, y, width, height):
        self.set_geometry(x, y, width, height)
