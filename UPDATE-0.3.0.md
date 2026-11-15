# 0.3.0 — HUD düğme rozetleri ve bağımsız yerleşim

Görev alanı sözcük kutularıyla okunur; görsel düğmeler ayrı tanınır. RB/LB/LT/RT, Xbox yüz düğmeleri, PS şekilleri ve Menü/Görünüm rozetleri çeviri sırasında korunur. Model bir işareti düşürür veya çoğaltırsa metin işaretin çevresinden çevrilir. A→B gibi bir düğme değişimi yazım hatası sayılmaz. Kaynak sözcük koordinatları ve tanıma yöntemi bellekte korunur; satır kutusuna geri dönüş sözcük kutusu gibi sunulmaz.

**Görev görünümü** yatay/dikey kaydırma ve %70–150 ölçek sunar. + yatay sağa, + dikey yukarı; her adım10Qt pikselidir. Kart alanın altında, yer yoksa üstünde; metin sola hizalanır. PC ve TV rozetleri aynı katalogdan çizilir. Görüntü yakalamadan dışlanma doğrulanamazsa kart her iki OCR alanından da uzak tutulur. Panelde iç işaret biçimi gösterilmez ve gelen HTML metni çalıştırılmaz.

HUD OCR ve çeviri kendi CPU kanalında birer iş parçacığı kullanır. Durdurma/duraklatma sonrası yeni rozet inference'ı ve iptal edilmiş çeviri yedeği başlatılmaz; yarım sonuç önbelleğe alınmaz. Profil yüklerken durdurma motor kurulumunu önler.

101 Python testi geçti. Gerçek yerel modeller, üretilmiş kareler üzerinden Window.begin → OCR/çeviri → PC rozeti → gerçek loopback TV → boş karede temizleme akışında denendi. Ayrıca açık Windows oturumunda kendi test pencerelerimiz gerçek MSS ile yakalandı; RB/A çevirisi ve temizleme geçti. Çeviri katmanı kaynak alanın üstüne taşındığında yakalanan kaynakta değişen piksel sayısı 0 oldu. Normal altyazı duraklat/devam ve yerel Chromium video testi de geçti. Bunlar gerçek oyun testi değildir. Ham kanıtlar kaynak projede `analysis/hud-parity.json`, `analysis/hud-native-pipeline.json` ve `analysis/hud-production-pipeline.json` içindedir.

Gerçek TV/oyun ve farklı DPI/monitör doğrulaması bekliyor. Native ekran testi bu makinedeki tek monitörde kontrollü içerikle sınırlıdır. Kaynakta görülen CPU thread önceliği/bekleme zamanlaması birebir eşdeğerlik iddiasına dahil değildir; bu audit açıktır. Tam proje hedefi hâlâ aktiftir.
