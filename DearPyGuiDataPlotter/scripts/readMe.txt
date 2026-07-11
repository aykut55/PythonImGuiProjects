DearPyGuiDataPlotter/scripts kisa notlari

default_full_pipeline.py
Eski/full gelistirme scriptidir; data okuma, indikator hesaplama, trade sinyali uretme ve cizimi tek dosyada yapar. Hala referans veya hizli deneme scripti olarak tutulabilir.
(eski adı : default.py dir)

default.py
Hazir .npz bundle ve .view.json dosyalarini okuyup panelleri olusturan viewer scriptidir. Strateji veya indikator hesaplamaz; C# ya da baska bir producer tarafindan hazirlanan datayi cizer.


default_template.py
Genel script taslagi olarak tutulur. Yeni deneysel scriptler icin baslangic noktasi gibi kullanilabilir.
(default_template.py = default.py)

default_full_pipeline_template.py
Yeni template akisini temsil eder; data okur, indikator ve sinyalleri hesaplar, isterse inputs altina .npz/.view/input dosyalarini yazar. Normal modda cizimi default.py'ye devreder, 
direct memory modunda diske yazmadan kendisi cizer.
(default_full_pipeline.py nin template olarak uyarlanmış halidir)


create_test_bundle.py
Test amacli sentetik .npz bundle, .view.json ve input.json ureten yardimci scriptir. C# tarafi henuz hazir degilken default.py viewer akisini denemek icin kullanilir.

external_window.py
New Script Window tarafindan default yuklenen external window template scriptidir. Son yuklenen bundle datasindaki indikator/sinyal serilerini bagimsiz lightweight window'da acar; INDICATOR_NAMES / INDICATOR_PREFIXES / computeCustomSeries / assignSeriesToWindow noktalarindan ozellestirilir.

