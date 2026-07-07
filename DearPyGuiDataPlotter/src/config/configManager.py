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
            },
            "dataManager": {
                "initialCoordinates": {"x": 1546, "y": 147, "width": 520, "height": 819},
            },
            "consolePanel": {
                "initialCoordinates": {"x": 1546, "y": 705, "width": 520, "height": 261},
            },
        },
    }

    def __init__(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.configDir = os.path.join(root, "config")
        self.configPath = os.path.join(self.configDir, "config.json")
        self.settings = self.load()

    def load(self):
        if not os.path.exists(self.configPath):
            self.settings = dict(self.DEFAULT_CONFIG)
            self.save()
            return self.settings
        with open(self.configPath, "r", encoding="utf-8") as f:
            self.settings = json.load(f)
        return self.settings

    def save(self):
        os.makedirs(self.configDir, exist_ok=True)
        with open(self.configPath, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
