import json
import os


class ConfigManager:
    """<root>/config/config.json dosyasini okur/yazar. Uygulamanin tum ayarlari
    (tema, pencere boyutu, layout sabitleri vb.) buradan gelir. Dosya yoksa
    varsayilan degerlerle olusturulur."""

    DEFAULT_CONFIG = {
        "theme": "dark",
        "window": {
            "width": 1920,
            "height": 1080,
            "x_pos": 0,
            "y_pos": 0,
        },
        "panels": {
            "scriptPanel": {
                "initialCoordinates": {"x": 1546, "y": 147, "width": 520, "height": 551},
                "visible": True,
            },
            "dataManager": {
                "initialCoordinates": {"x": 1546, "y": 147, "width": 520, "height": 819},
                "visible": False,
            },
            "leftMenu": {
                "visible": True,
            },
            "poolPanel": {
                "initialCoordinates": {"x": 1000, "y": 147, "width": 420, "height": 600},
                "visible": False,
            },
            "panelManagerWindow": {
                "initialCoordinates": {"x": 550, "y": 100, "width": 700, "height": 900},
                "visible": False,
            },
            "consolePanel": {
                "initialCoordinates": {"x": 1546, "y": 705, "width": 520, "height": 261},
                "visible": False,
            },
        },
        "topPanel": {
            "activeUpdateMode": "Click",
            "viewRange": {
                "mode": "FitToScreen (Ultra)",
                "n": 0,
                "n2": 0,
                "fitToScreenBarWidth": {
                    "normal": 4.0,
                    "wide": 2.5,
                    "ultra": 1.5,
                },
            },
            "panMode": "VisibleScreenWidth",
            "panStep": 100,
            "zoomRatio": "30%",
            "showSliderRange": True,
            "crossHairMode": "All",
            "showScrollBar": True,
            "showInfoPanels": True,
            "autoSyncX": True,
            "showBarNumbers": False,
            "autoSyncY": False,
            "showOhlc": True,
        },
        "debug": {
            "interactionEvents": False,
            "interactionEventsFormatted": False,
        },
    }

    def __init__(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.configDir = os.path.join(root, "config")
        self.configPath = os.path.join(self.configDir, "config.json")
        self.settings = self.load()

    def load(self):
        if not os.path.exists(self.configPath):
            self.settings = self._deepCopy(self.DEFAULT_CONFIG)
            self.save()
            return self.settings
        with open(self.configPath, "r", encoding="utf-8") as f:
            self.settings = json.load(f)
        if self._mergeMissingDefaults(self.settings, self.DEFAULT_CONFIG):
            self.save()
        return self.settings

    def save(self):
        os.makedirs(self.configDir, exist_ok=True)
        with open(self.configPath, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value

    def _deepCopy(self, value):
        return json.loads(json.dumps(value))

    def _mergeMissingDefaults(self, target, defaults):
        changed = False
        for key, value in defaults.items():
            if key not in target:
                target[key] = self._deepCopy(value)
                changed = True
                continue
            if isinstance(target[key], dict) and isinstance(value, dict):
                changed = self._mergeMissingDefaults(target[key], value) or changed
        return changed
