import locale
import subprocess

from imgui_bundle import imgui, immapp


class App:
    def __init__(self):
        try:
            locale.setlocale(locale.LC_TIME, "tr_TR.UTF-8")
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, "Turkish_Turkey.1254")
            except locale.Error:
                pass

    def gui(self):
        imgui.text("Hello World")

    def run(self):
        subprocess.call("cls", shell=True)
        immapp.run(
            gui_function=self.gui,
            window_title="DearImGuiBundleDataPlotter",
            window_size=(800, 600),
        )


if __name__ == "__main__":
    app = App()
    app.run()
