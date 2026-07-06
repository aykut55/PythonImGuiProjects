import sys

import dearpygui.dearpygui as dpg


class ConsolePanel:
    """Floating window that mirrors sys.stdout/sys.stderr.

    Independent of the layout system: opened/closed and moved/resized freely
    by the user via the Panels menu, not repositioned automatically like the
    layout panels or ScriptPanel.

    Uses a readonly multiline input_text (mouse-selectable/copyable, unlike
    add_text) and manually wraps lines to the current width, since DPG's
    input_text does not word-wrap on its own.
    """

    TAG = "console_panel"
    OUTPUT = "console_output"
    CLEAR_ON_DBLCLICK_CHECKBOX = "console_clear_on_dblclick"
    HANDLER_REGISTRY = "console_panel_handlers"
    OUTPUT_HANDLER_REGISTRY = "console_output_handlers"

    def __init__(self):
        self._visible = False
        self._onCloseCallback = None
        self._buffer = []
        self._wrapWidth = 760

    def attachStdout(self):
        sys.stdout = _ConsoleTee(sys.__stdout__, self)
        sys.stderr = _ConsoleTee(sys.__stderr__, self)

    def build(self, x, y, width, height, onClose=None):
        self._onCloseCallback = onClose
        self._wrapWidth = max(100, width - 40)
        with dpg.window(label="Console Panel", tag=self.TAG, pos=(x, y),
                        width=width, height=height, show=self._visible,
                        on_close=self._onClose):
            with dpg.group(horizontal=True):
                dpg.add_button(label="Clear", callback=self.clear)
                dpg.add_button(label="Copy", callback=self.copy)
                dpg.add_checkbox(label="Clear On DblClick", tag=self.CLEAR_ON_DBLCLICK_CHECKBOX,
                                 default_value=False)
            dpg.add_input_text(tag=self.OUTPUT, multiline=True, readonly=True,
                               width=-1, height=-1, default_value=self._wrappedText())

        if not dpg.does_item_exist(self.HANDLER_REGISTRY):
            with dpg.item_handler_registry(tag=self.HANDLER_REGISTRY):
                dpg.add_item_resize_handler(callback=self._onResize)
        dpg.bind_item_handler_registry(self.TAG, self.HANDLER_REGISTRY)

        if not dpg.does_item_exist(self.OUTPUT_HANDLER_REGISTRY):
            with dpg.item_handler_registry(tag=self.OUTPUT_HANDLER_REGISTRY):
                dpg.add_item_double_clicked_handler(callback=self._onOutputDoubleClick)
        dpg.bind_item_handler_registry(self.OUTPUT, self.OUTPUT_HANDLER_REGISTRY)

    def _onResize(self, sender, appData):
        width = dpg.get_item_width(self.TAG) or 0
        self._wrapWidth = max(100, width - 40)
        self._refresh()

    def _onOutputDoubleClick(self, sender, appData):
        if dpg.get_value(self.CLEAR_ON_DBLCLICK_CHECKBOX):
            self.clear()

    def _onClose(self):
        self._visible = False
        if self._onCloseCallback:
            self._onCloseCallback()

    def isVisible(self):
        return self._visible

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

    def setGeometry(self, x, y, width, height):
        if dpg.does_item_exist(self.TAG):
            dpg.set_item_pos(self.TAG, (x, y))
            dpg.set_item_width(self.TAG, width)
            dpg.set_item_height(self.TAG, height)
            self._wrapWidth = max(100, width - 40)
            self._refresh()

    def write(self, text):
        self._buffer.append(text)
        self._refresh()

    def clear(self):
        self._buffer = []
        self._refresh()

    def copy(self):
        dpg.set_clipboard_text("".join(self._buffer))

    def _refresh(self):
        if dpg.does_item_exist(self.OUTPUT):
            dpg.set_value(self.OUTPUT, self._wrappedText())

    def _wrappedText(self):
        raw = "".join(self._buffer)
        lines = []
        for rawLine in raw.split("\n"):
            lines.extend(self._wrapLine(rawLine))
        return "\n".join(lines)

    def _wrapLine(self, line):
        if not line:
            return [""]
        words = line.split(" ")
        wrapped = []
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            size = dpg.get_text_size(candidate)
            width = size[0] if size else 0
            if width > self._wrapWidth and current:
                wrapped.append(current)
                current = word
            else:
                current = candidate
        wrapped.append(current)
        return wrapped


class _ConsoleTee:
    def __init__(self, original, panel):
        self._original = original
        self._panel = panel

    def write(self, text):
        self._original.write(text)
        self._panel.write(text)

    def flush(self):
        self._original.flush()
