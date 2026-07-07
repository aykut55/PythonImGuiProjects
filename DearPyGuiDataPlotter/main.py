import locale
import subprocess

import dearpygui.dearpygui as dpg
from src.config.configManager import ConfigManager
from src.plotting.guiManager import GuiManager

class App:
    def __init__(self):
        try:
            locale.setlocale(locale.LC_TIME, "tr_TR.UTF-8")
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, "Turkish_Turkey.1254")
            except locale.Error:
                pass

        self.configManager = ConfigManager()
        window = self.configManager.get("window")

        dpg.create_context()
        # ImGui'nin klavye navigasyonu (ok tuslariyla combo/listede gezinme)
        # varsayilan olarak kapali; acmazsak sadece mouse ile gezinilebiliyor.
        dpg.configure_app(keyboard_navigation=True)
        dpg.create_viewport(title="DearPyGuiDataPlotter",
                            width=window["width"], height=window["height"],
                            x_pos=window["x_pos"], y_pos=window["y_pos"])
        self._setupFont()

        self.guiManager = GuiManager(self.configManager)
        self.guiManager.build()

    def _setupFont(self):
        # Varsayilan ImGui fontu Latin Extended-A'yi icermez, yani Turkce'ye
        # ozgu bazi karakterler (U+011E-011F, U+0130-0131, U+015E-015F)
        # eksik kalir; Segoe UI + bu araliklarla yukleyip global font yapiyoruz.
        fontPath = "C:\\Windows\\Fonts\\segoeui.ttf"
        try:
            with dpg.font_registry():
                with dpg.font(fontPath, 16) as defaultFont:
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                    dpg.add_font_range(0x11E, 0x11F)
                    dpg.add_font_range(0x130, 0x131)
                    dpg.add_font_range(0x15E, 0x15F)
            dpg.bind_font(defaultFont)
        except Exception:
            pass

    def run(self):
        subprocess.call("cls", shell=True)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        try:
            dpg.start_dearpygui()
        finally:
            dpg.destroy_context()


if __name__ == "__main__":
    app = App()
    app.run()
