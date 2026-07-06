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
        dpg.create_viewport(title="DearPyGuiDataPlotter",
                            width=window["width"], height=window["height"],
                            x_pos=window["x_pos"], y_pos=window["y_pos"])

        self.guiManager = GuiManager(self.configManager)
        self.guiManager.build()

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
