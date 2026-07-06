import locale
import subprocess

import dearpygui.dearpygui as dpg


class App:
    def __init__(self):
        try:
            locale.setlocale(locale.LC_TIME, "tr_TR.UTF-8")
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, "Turkish_Turkey.1254")
            except locale.Error:
                pass

        dpg.create_context()
        dpg.create_viewport(title="DearPyGuiDataPlotter", width=800, height=600)

        with dpg.window(label="Ana Pencere", tag="main_window"):
            dpg.add_text("Hello World")

        dpg.set_primary_window("main_window", True)

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
