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
        "# Hazir: gm, pm, tsr, dpg, Panel, PanelData\n"
    )

    def __init__(self):
        self._namespace = {"dpg": dpg}
        self._visible = True
        self._on_close_cb = None
        self._on_run_complete = None
        self._on_open_console = None
        self._next_external_window_id = 1
        self._external_windows = {}
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
                dpg.add_text("File:")
                dpg.add_text(os.path.basename(self._current_path), tag=self.FILE_LABEL)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Run", callback=self._run)
                dpg.add_button(label="Open", callback=lambda: dpg.show_item(self.OPEN_DIALOG))
                dpg.add_button(label="Reopen", callback=self._reopen)
                dpg.add_button(label="Save", callback=self._save)
                dpg.add_button(label="Save As", callback=lambda: dpg.show_item(self.SAVEAS_DIALOG))
                dpg.add_button(label="Console",
                               callback=lambda: self._on_open_console and self._on_open_console())
                dpg.add_button(label="Clear", callback=self._new)
                dpg.add_button(label="Copy", callback=self._copy)
                dpg.add_button(label="New Script Window",
                               callback=self._open_external_script_window)
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

    def _run_script_file(self, fileName):
        path = os.path.join(self._scripts_dir, fileName)
        try:
            code = self._read_file(path)
            exec(compile(code, path, "exec"), self._namespace)
        except Exception:
            print(traceback.format_exc())
        if self._on_run_complete:
            try:
                self._on_run_complete()
            except Exception:
                print(traceback.format_exc())

    def _open_external_script_window(self):
        windowId = self._next_external_window_id
        self._next_external_window_id += 1

        path = os.path.join(self._scripts_dir, "external_window.py")
        windowTag = f"external_script_window_{windowId}"
        codeTag = f"external_script_code_{windowId}"
        fileLabelTag = f"external_script_file_label_{windowId}"
        statusTag = f"external_script_status_{windowId}"
        openDialogTag = f"external_script_open_dialog_{windowId}"
        saveAsDialogTag = f"external_script_saveas_dialog_{windowId}"

        self._external_windows[windowId] = {
            "path": path,
            "windowTag": windowTag,
            "codeTag": codeTag,
            "fileLabelTag": fileLabelTag,
            "statusTag": statusTag,
            "openDialogTag": openDialogTag,
            "saveAsDialogTag": saveAsDialogTag,
        }

        with dpg.window(label=f"External Script Window {windowId}",
                        tag=windowTag, width=720, height=520):
            with dpg.group(horizontal=True):
                dpg.add_text("File:")
                dpg.add_text(os.path.basename(path), tag=fileLabelTag)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Run",
                               callback=self._on_external_run_clicked,
                               user_data=windowId)
                dpg.add_button(label="Open",
                               callback=self._on_external_open_clicked,
                               user_data=openDialogTag)
                dpg.add_button(label="Reopen",
                               callback=self._on_external_reopen_clicked,
                               user_data=windowId)
                dpg.add_button(label="Save",
                               callback=self._on_external_save_clicked,
                               user_data=windowId)
                dpg.add_button(label="Save As",
                               callback=self._on_external_saveas_clicked,
                               user_data=saveAsDialogTag)
                dpg.add_button(label="Clear",
                               callback=self._on_external_clear_clicked,
                               user_data=windowId)
                dpg.add_button(label="Copy",
                               callback=self._on_external_copy_clicked,
                               user_data=windowId)
            dpg.add_text("Waiting...", tag=statusTag)
            dpg.add_input_text(tag=codeTag, multiline=True, width=-1, height=-1,
                               default_value=self._read_file(path), tab_input=True)

        with dpg.file_dialog(tag=openDialogTag, show=False, directory_selector=False,
                             width=600, height=400, default_path=self._scripts_dir,
                             callback=lambda sender, app_data, user_data=windowId:
                             self._on_external_open_selected(user_data, app_data)):
            dpg.add_file_extension(".py")
            dpg.add_file_extension(".*")

        with dpg.file_dialog(tag=saveAsDialogTag, show=False, directory_selector=False,
                             width=600, height=400, default_path=self._scripts_dir,
                             callback=lambda sender, app_data, user_data=windowId:
                             self._on_external_saveas_selected(user_data, app_data)):
            dpg.add_file_extension(".py")
            dpg.add_file_extension(".*")

    def _on_external_run_clicked(self, sender=None, app_data=None, user_data=None):
        self._run_external_window(user_data)

    def _on_external_open_clicked(self, sender=None, app_data=None, user_data=None):
        if user_data:
            dpg.show_item(user_data)

    def _on_external_reopen_clicked(self, sender=None, app_data=None, user_data=None):
        self._reopen_external_window(user_data)

    def _on_external_save_clicked(self, sender=None, app_data=None, user_data=None):
        self._save_external_window(user_data)

    def _on_external_saveas_clicked(self, sender=None, app_data=None, user_data=None):
        if user_data:
            dpg.show_item(user_data)

    def _on_external_clear_clicked(self, sender=None, app_data=None, user_data=None):
        state = self._external_windows.get(user_data)
        if state and dpg.does_item_exist(state["codeTag"]):
            dpg.set_value(state["codeTag"], "")

    def _on_external_copy_clicked(self, sender=None, app_data=None, user_data=None):
        state = self._external_windows.get(user_data)
        if not state or not dpg.does_item_exist(state["codeTag"]):
            return
        try:
            dpg.set_clipboard_text(dpg.get_value(state["codeTag"]))
            if dpg.does_item_exist(state["statusTag"]):
                dpg.set_value(state["statusTag"], "Copied")
        except Exception:
            print(traceback.format_exc())

    def _run_external_window(self, windowId):
        state = self._external_windows.get(windowId)
        if not state or not dpg.does_item_exist(state["codeTag"]):
            print(f"External Script Window Run: gecersiz windowId={windowId}")
            return
        code = dpg.get_value(state["codeTag"])
        path = state["path"]
        if dpg.does_item_exist(state["statusTag"]):
            dpg.set_value(state["statusTag"], "Running...")
        print(f"External Script Window Run: {path}")
        try:
            exec(compile(code, path, "exec"), self._namespace)
            result = self._namespace.get("EXTERNAL_WINDOW_RESULT")
            if dpg.does_item_exist(state["statusTag"]):
                dpg.set_value(state["statusTag"], str(result or "Run completed"))
        except Exception:
            text = traceback.format_exc()
            print(text)
            if dpg.does_item_exist(state["statusTag"]):
                dpg.set_value(state["statusTag"], "Run error, see console")
        if self._on_run_complete:
            try:
                self._on_run_complete()
            except Exception:
                print(traceback.format_exc())

    def _on_external_saveas_selected(self, windowId, app_data):
        state = self._external_windows.get(windowId)
        if not state:
            return
        path = app_data.get("file_path_name")
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".py"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(dpg.get_value(state["codeTag"]))
            state["path"] = path
            if dpg.does_item_exist(state["fileLabelTag"]):
                dpg.set_value(state["fileLabelTag"], os.path.basename(path))
            print(f"Kaydedildi: {path}")
        except Exception:
            print(traceback.format_exc())

    def _on_external_open_selected(self, windowId, app_data):
        state = self._external_windows.get(windowId)
        if not state:
            return
        path = app_data.get("file_path_name")
        if not path:
            return
        self._load_external_window_path(windowId, path)

    def _load_external_window_path(self, windowId, path):
        state = self._external_windows.get(windowId)
        if not state:
            return
        state["path"] = path
        if dpg.does_item_exist(state["codeTag"]):
            dpg.set_value(state["codeTag"], self._read_file(path))
        if dpg.does_item_exist(state["fileLabelTag"]):
            dpg.set_value(state["fileLabelTag"], os.path.basename(path))
        if dpg.does_item_exist(state["statusTag"]):
            dpg.set_value(state["statusTag"], f"Loaded: {os.path.basename(path)}")

    def _reopen_external_window(self, windowId):
        state = self._external_windows.get(windowId)
        if not state:
            return
        self._load_external_window_path(windowId, state["path"])

    def _save_external_window(self, windowId):
        state = self._external_windows.get(windowId)
        if not state or not dpg.does_item_exist(state["codeTag"]):
            return
        try:
            os.makedirs(os.path.dirname(state["path"]), exist_ok=True)
            with open(state["path"], "w", encoding="utf-8") as f:
                f.write(dpg.get_value(state["codeTag"]))
            if dpg.does_item_exist(state["statusTag"]):
                dpg.set_value(state["statusTag"], f"Saved: {os.path.basename(state['path'])}")
            print(f"Kaydedildi: {state['path']}")
        except Exception:
            print(traceback.format_exc())

    def _reopen(self):
        # Reload the active file from disk (e.g. after editing it externally).
        self._load_path(self._current_path)
        print(f"Yeniden yuklendi: {self._current_path}")

    def _new(self):
        """Editordeki metni temizler (Clear gibi) - DISKTEKI dosyaya (_current_path)
        dokunmaz, Save/Save As hala ayni dosyayi hedef alir. Amac: acik/calisan
        app'e karsi hizlica ad-hoc debug kodu yazip Run'a basabilmek - _run()
        her zaman AYNI kalici namespace'i (gm/pm/dpg) kullandigi icin buraya
        yapistirilan kod da halihazirda calisan uygulamaya karsi calisir."""
        if dpg.does_item_exist(self.CODE):
            dpg.set_value(self.CODE, "")

    def _copy(self):
        if not dpg.does_item_exist(self.CODE):
            return
        try:
            dpg.set_clipboard_text(dpg.get_value(self.CODE))
            print("Script editor icerigi clipboard'a kopyalandi.")
        except Exception:
            print(traceback.format_exc())

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
