# Hazir: gm, pm, pool, dpg, Panel, PanelData

# External window script template.
#
# Bu script son yuklenen bundle datasina gm.currentPreparedData uzerinden erisir.
# Istersen mevcut indikator listelerinden seri secebilir, istersen
# computeCustomSeries() icinde yeni custom seri hesaplayabilirsin.

TITLE = "External Window"
SOURCE_PANEL_ID = None       # None: aktif panel -> OHLC panel -> ilk uygun panel
FOLLOW_SOURCE = True

# Bundle indikatorlerinden secilecek seriler. Bos ise prefix kurali kullanilir.
INDICATOR_NAMES = []
INDICATOR_PREFIXES = ["EMA"]  # Ornek: ["EMA"], ["MACD"], ["RSI"], ["Stoch"]

# Bundle primitive verilerinden secilecek seriler.
# Ornek: ["close"], ["open", "high", "low", "close"], ["volume", "size"]
# Bos birakilirsa primitive veriler cizime eklenmez ama ctx["primitive"]
# icinden ham liste olarak kullanilabilir.
PRIMITIVE_NAMES = []

# Signal Step gibi bundle ozel serileri.
INCLUDE_SIGNAL_STEPS = False


ctx = {}
EXTERNAL_WINDOW_RESULT = None


def finite(value):
    try:
        import math
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def init():
    """Script context'ini hazirlar."""
    ctx.clear()
    ctx["data"] = getPreparedData()
    ctx["sourcePanelId"] = resolveSourcePanelId()
    ctx["primitive"] = getPrimitiveData(ctx["data"])
    ctx["series"] = []
    ctx["state"] = None
    return ctx["data"] is not None and ctx["sourcePanelId"] is not None


def compute():
    """Bundle datasindan/custom hesaplardan cizilecek serileri hazirlar."""
    data = ctx.get("data")
    if data is None:
        return False
    ctx["series"] = assignSeriesToWindow(data)
    return bool(ctx["series"])


def draw():
    """Hazirlanan serileri external window'da cizer."""
    sourcePanelId = ctx.get("sourcePanelId")
    series = ctx.get("series") or []
    if sourcePanelId is None or not series:
        return False

    ctx["state"] = gm.externalIndicatorWindowManager.openIndicatorWindow(
        sourcePanelId=sourcePanelId,
        series=series,
        title=TITLE,
        followSource=FOLLOW_SOURCE,
    )
    return ctx["state"] is not None


def getPreparedData():
    """default.py son bundle'i yuklediginde gm.currentPreparedData olarak expose eder."""
    data = getattr(gm, "currentPreparedData", None)
    if data is None:
        print("currentPreparedData yok. Once default.py veya pipeline scripti ile data yukle.")
    return data


def indicatorNameAccepted(name):
    if INDICATOR_NAMES:
        return name in INDICATOR_NAMES
    upper = name.upper()
    return any(upper.startswith(prefix.upper()) for prefix in INDICATOR_PREFIXES)


def getPrimitiveData(data):
    """OHLCV/size gibi temel bundle verilerini ham liste olarak verir.

    Kullanim:
        primitive = ctx["primitive"]
        closes = primitive["close"]
        volumes = primitive["volume"]
    """
    if data is None:
        return {}

    return {
        "xs": list(getattr(data, "xs", [])),
        "timestamps": list(getattr(data, "timestamps", [])),
        "open": [float(v) for v in getattr(data, "open", [])],
        "high": [float(v) for v in getattr(data, "high", [])],
        "low": [float(v) for v in getattr(data, "low", [])],
        "close": [float(v) for v in getattr(data, "close", [])],
        "volume": [float(v) for v in getattr(data, "volume", [])],
        "size": [int(v) for v in getattr(data, "size", [])],
    }


def getPrimitiveSeriesFromBundle(data):
    """PRIMITIVE_NAMES icinde secilen temel verileri cizilebilir seri yapar."""
    out = []
    primitive = getPrimitiveData(data)
    xs = primitive.get("xs") or []
    if not xs:
        return out

    accepted = {name.lower() for name in PRIMITIVE_NAMES}
    for name in ("open", "high", "low", "close", "volume", "size"):
        if name not in accepted:
            continue
        values = primitive.get(name) or []
        out.append({
            "name": name.capitalize(),
            "xs": list(xs),
            "ys": [float(v) if finite(v) else float("nan") for v in values],
        })
    return out


def getIndicatorSeriesFromBundle(data):
    """Bundle icindeki indicatorNames/indicatorValues listesinden seri uretir."""
    out = []
    if data is None:
        return out

    for name, ys in zip(data.indicatorNames, data.indicatorValues):
        if not indicatorNameAccepted(name):
            continue
        out.append({
            "name": name,
            "xs": list(data.xs),
            "ys": [float(v) if finite(v) else float("nan") for v in ys],
        })
    return out


def getSignalSeriesFromBundle(data):
    """Signal Step gibi bundle ozel serilerini burada cizilebilir hale getir."""
    out = []
    if data is None:
        return out
    if INCLUDE_SIGNAL_STEPS and data.signalSteps:
        out.append({
            "name": "Signal Step",
            "xs": list(data.xs),
            "ys": [float(v) for v in data.signalSteps],
        })
    return out


def computeCustomSeries(data):
    """Yeni custom indikator/seri hesaplama yeri.

    Ornek:
        diff = [a - b for a, b in zip(ema50, ema100)]
        return [{"name": "EMA50-EMA100", "xs": data.xs, "ys": diff}]

    Simdilik bos; ihtiyaca gore buraya hesap ekle.
    """
    return []


def assignSeriesToWindow(data):
    """Bu pencerede cizilecek tum serileri burada net olarak assign ediyoruz."""
    series = []
    series += getPrimitiveSeriesFromBundle(data)
    series += getIndicatorSeriesFromBundle(data)
    series += getSignalSeriesFromBundle(data)
    series += computeCustomSeries(data)
    return series


def panelHasAnyData(panel):
    return panel is not None and any(True for _ in panel.iterateAllData())


def resolveSourcePanelId():
    if SOURCE_PANEL_ID is not None:
        return SOURCE_PANEL_ID

    for panel in pm.iterateAllPanels():
        if panel.name == "OHLC" and panelHasAnyData(panel):
            return panel.id

    activeId = pm.getActivePanelId()
    activePanel = pm.getPanel(activeId)
    if panelHasAnyData(activePanel):
        return activeId

    for panel in pm.iterateAllPanels():
        if panelHasAnyData(panel):
            return panel.id
    return None


def run():
    """SDK benzeri ana akis: init -> compute -> draw."""
    global EXTERNAL_WINDOW_RESULT
    EXTERNAL_WINDOW_RESULT = None

    if not init():
        if ctx.get("data") is None:
            EXTERNAL_WINDOW_RESULT = "No prepared data"
            return
        EXTERNAL_WINDOW_RESULT = "No source panel"
        print("External Window: uygun source panel bulunamadi.")
        return

    if not compute():
        EXTERNAL_WINDOW_RESULT = "No series"
        print("External Window: cizilecek seri bulunamadi.")
        return

    if not draw():
        EXTERNAL_WINDOW_RESULT = "Window open failed"
        print("External Window: window acilamadi.")
        return

    names = ", ".join(item["name"] for item in ctx["state"]["series"])
    EXTERNAL_WINDOW_RESULT = f"Opened: {names}"
    print(f"External Window acildi: {names}")


run()
