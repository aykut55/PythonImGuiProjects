from dataclasses import dataclass
from itertools import count

from .panelData import PanelData


@dataclass
class PoolItem:
    id: str
    label: str
    group: str          # "Data" | "Indicators"
    data: PanelData
    key: str = ""
    symbol: str = ""    # ust grup (or. "THYAO") -> pool'da Sembol > Grup > item


class PoolDataManager:
    """Panele BAGLI OLMADAN (candle + hesaplanan tum indikatorler) veri tutan
    havuz. Ref3'teki DataPool karsiligi (camelCase'e cevrilerek, PoolDataManager
    adiyla). Sembol > Grup ("Data"/"Indicators") > item hiyerarsisi."""

    def __init__(self):
        self._items: dict[str, PoolItem] = {}
        self._keys: dict[str, str] = {}
        self._counter = count(1)

    def clear(self):
        self._items.clear()
        self._keys.clear()

    def getAllItems(self):
        return list(self._items.values())

    def iterateAllItems(self):
        for item in self._items.values():
            yield item

    def getItem(self, itemId):
        return self._items.get(str(itemId))

    def _match(self, item, label, symbol, group):
        return ((label is None or item.label == label)
                and (symbol is None or item.symbol == symbol)
                and (group is None or item.group == group))

    def findItem(self, label: str = None, symbol: str = None, group: str = None):
        """Olcutlere (label/symbol/group) uyan ILK PoolItem'i dondurur (yoksa None).
        Kod ile pool_N id'sini bilmeden erisim icin:
          pool.findItem('Open', symbol='THYAO')      -> PoolItem
          pool.findItem('EMA8', symbol='THYAO', group='Indicators')
        Sonra .id / .data ile devam edilir."""
        return next((it for it in self._items.values()
                     if self._match(it, label, symbol, group)), None)

    def findAllItems(self, label: str = None, symbol: str = None, group: str = None):
        """Olcutlere uyan TUM PoolItem'leri liste olarak dondurur (or. bir sembolun
        'Data' grubunun tamami: pool.findAllItems(symbol='THYAO', group='Data'))."""
        return [it for it in self._items.values()
                if self._match(it, label, symbol, group)]

    def searchItems(self, text: str, symbol: str = None, group: str = None):
        """label'da (buyuk/kucuk harf duyarsiz) ALT-DIZE aramasi; eslesen TUM
        PoolItem'leri dondurur. Opsiyonel symbol/group ile daraltilir."""
        t = (text or "").lower()
        return [it for it in self._items.values()
                if t in it.label.lower()
                and (symbol is None or it.symbol == symbol)
                and (group is None or it.group == group)]

    def removeItem(self, itemId) -> bool:
        """Tek bir pool item'ini id ile siler (or. 'Open' -> pool_2). Silindiyse True."""
        item = self._items.pop(str(itemId), None)
        if item and item.key and self._keys.get(item.key) == str(itemId):
            self._keys.pop(item.key, None)
        return item is not None

    def removeGroup(self, symbol: str, group: str) -> int:
        """Bir sembolun bir grubundaki (or. 'Data') TUM item'leri siler. Silinen sayi."""
        ids = [iid for iid, it in self._items.items()
               if it.symbol == symbol and it.group == group]
        for iid in ids:
            self.removeItem(iid)
        return len(ids)

    def removeSymbol(self, symbol: str) -> int:
        """Bir sembolun altindaki TUM item'leri (tum gruplar) siler. Silinen sayi."""
        ids = [iid for iid, it in self._items.items() if it.symbol == symbol]
        for iid in ids:
            self.removeItem(iid)
        return len(ids)

    def addItem(self, label: str, group: str, data: PanelData, key: str = None,
               symbol: str = ""):
        if key:
            self._dedupeKey(key)
        self._dedupeIdentity(label, group, symbol, keepKey=key)
        if key and key in self._keys:
            item = self._items[self._keys[key]]
            item.label = label
            item.group = group
            item.symbol = symbol
            item.data = clonePanelData(data, data.id)
            item.key = key
            return item
        itemId = f"pool_{next(self._counter)}"
        item = PoolItem(itemId, label, group, clonePanelData(data, data.id),
                        key or "", symbol)
        self._items[itemId] = item
        if key:
            self._keys[key] = itemId
        return item

    def _dedupeKey(self, key: str):
        ids = [itemId for itemId, item in self._items.items()
               if item.key == key]
        if not ids:
            return
        keep = ids[0]
        self._keys[key] = keep
        for itemId in ids[1:]:
            self._items.pop(itemId, None)

    def _dedupeIdentity(self, label: str, group: str, symbol: str = "",
                        keepKey: str = None):
        ids = [itemId for itemId, item in self._items.items()
               if item.label == label and item.group == group
               and item.symbol == symbol
               and (keepKey is None or item.key != keepKey)]
        for itemId in ids:
            old = self._items.pop(itemId, None)
            if old and old.key and self._keys.get(old.key) == itemId:
                self._keys.pop(old.key, None)


def _copySeq(seq):
    if seq is None:
        return []
    try:
        return list(seq)
    except TypeError:
        return []


def _fullOrCurrent(fullSeq, currentSeq):
    return _copySeq(fullSeq) if fullSeq is not None else _copySeq(currentSeq)


def clonePanelData(source: PanelData, dataId: int = None, name: str = None):
    """source'un BAGIMSIZ bir kopyasini olusturur (pool, panelden ayri
    yasamali - panel silinse/degisse bile pool'daki veri etkilenmemeli)."""
    clone = PanelData(
        source.id if dataId is None else dataId,
        source.name if name is None else name,
        source.dataType,
        _fullOrCurrent(source._fullXs, source.xs),
        _fullOrCurrent(source._fullYs, source.ys),
        source.color,
    )
    clone.isVisible = source.isVisible
    clone.xFormat = source.xFormat
    clone.isIntraday = source.isIntraday
    clone.timestamps = _copySeq(source.timestamps)
    clone.open = _fullOrCurrent(source._fullOpen, source.open)
    clone.high = _fullOrCurrent(source._fullHigh, source.high)
    clone.low = _fullOrCurrent(source._fullLow, source.low)
    clone.close = _fullOrCurrent(source._fullClose, source.close)
    clone.volume = _fullOrCurrent(source._fullVolume, source.volume)
    clone.size = _copySeq(source.size)
    clone.openInterest = _copySeq(source.openInterest)
    clone.tradeCount = _copySeq(source.tradeCount)
    clone.setFullData()
    clone.updateStats()
    return clone
