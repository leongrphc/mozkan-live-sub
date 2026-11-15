# 0.3.5 — uyarlamalı OCR, küçük değişimler ve canlı gözlemler

**Hızlı** mod normal görüntüyle başlar; soluk/parlak sahnelerde gerekirse ikinci görüntüyü karşılaştırır. Başarılı açık-zemin denemeleri sonraki okumaya öncülük edebilir. **Ayrıntılı** mod normal ve yerel kontrast görüntüsünü iki geçişle karşılaştırır. Her geçiş algılama ve gerektiğinde satır tanıma içerebilir; geçiş sayısı model çağrısı sayısı değildir. Aynı karenin iki geçişi iki bağımsız doğrulama sayılmaz. Belirsiz güven puanı bilinmeyen kalır. Tamamen tek renkli yakalamada hızlı mod sinir ağını çalıştırmaz; soluk ama değişken pikseller bu kısayolla atılmaz.

Değişim filtresi kısa kelime, soluk cümle ve değişen rakamı yalnız bütün alanın ortalamasıyla değerlendirmez. Gerçek modellerle önceki sürümün kaçırdığı `No!`, soluk cümle ve120→121 değişimi yeniden üretildi; yeni filtre okumayı tetikledi. Düzenli yenileme korunur. 640×96 sınırlı algılama geometrisi değişmez.

Geçerli tekil/ayrık kutulardaki tanıma sonucu yeniden kullanılır. Örtüşen kutuların birleşik satırı ayrıca tanınır. Böylece gereksiz yeniden kırpma/tanıma sonucu bozmaz. Bozuk kutu geometrisinde satır bilgisi açık bir geri dönüşle korunur; kapasite aşımı sessiz metin kesmek yerine hata bildirir.

Tarama aralığı0,08–3s arasında kaydedilir; gerçek OCR süresi çevrimi uzatabilir. Panel ayrı altyazı/görev kanallarında OCR güvenini, süreyi, yöntemi, geçiş sayısını ve önbellek durumunu gösterir. Çevirinin oyun profili/model/önbellek kaynağı, kullanılan cihaz ve süresi de görünür. Eşleşme puanı çeviri doğruluğu olasılığı değildir. Gözlemler kanal/tür başına tek güncel kayıtla sınırlıdır; duraklatma/durdurma/eski oturum sonuçları reddedilir. Varsayılan olarak görüntü veya tanınan metin dosyaya kaydedilmez.

Eskiyen altyazı model yüklenirken değişse de tamamlanmış model kazanımı korunur; yalnız eski istek için inference iptal edilir. Önbellek, çevirinin özgün cihaz/kaynak bilgisini taşır. Küçük ekranlarda bütün kontrollere kaydırarak erişilebilir.

Gerçek Qt seçim/geri yükleme, MSS/OCR/yerel çeviri, ayrıntılı iki geçiş, canlı gözlem ve duraklat/devam akışı denendi. Geniş gerçek oyun/yayın/TV/karma DPI kapsamı hâlâ doğrulanmadı. Her soluk görüntünün okunacağı garanti edilmez; üretilmiş zor örneklerin tam sonuçları kaynak projede `analysis/ocr-quality-comparison.json` içindedir. Son tam taşınabilir arşiv0.3.2; bu sürüm kurulu güncellemedir. Tam hedef aktif.
