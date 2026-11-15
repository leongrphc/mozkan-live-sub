# 0.3.3 — kayıtlı alanlar ve ekran değişiklikleri

Altyazı/video ve görev alanları; seçimin türü, monitör geometrisi, ölçeği ve mevcut ekran bilgisiyle birlikte kaydedilir. Açılışta geçerli alan geri gelir; otomatik yakalama başlamaz. Tam video alanı tekrar kırpılıp küçülmez. Video seçimi, mod değişince altyazı satırı gibi kullanılmaz; uygun moda dönülebilir veya yeni alan seçilebilir. Eksik ekran bilgisi donanım kimliği kanıtı sayılmaz.

Çalışan yakalamanın fiziksel koordinatı ve canlı ekran sahibi ayrı, değişmez bir planda tutulur. Geç gelen, iptal edilmiş, eski oturumdaki veya eski ekran yapılandırmasındaki seçim sonucu kullanılmaz. Seçim açıkken Başlat bekler; Esc önceki geçerli alanı korur. Çalışırken alan değiştirilemez. Ekran olayları ve saniyelik fiziksel eşleme kontrolü değişikliği yakaladığında oturum geçersiz kılınır, PC/TV sonuçları temizlenir ve etkilenen alan yeniden seçime alınır. Kaydetme başarısızsa geçerli alan o oturumda kullanılabilir, kaydedilmediği panelde bildirilir.

Seçim penceresi kapanışta temizlenir. Ekran gözlem bağlantılarının kapanışı tamamlanamazsa sahibi korunur; yeniden kapatma kalan bağlantıları temizler. Çalışan motor bittikten sonraki son kapanış da bu temizliği bekler.

133 test geçti. Referansın saf alan doğrulayıcısıyla 26 sınır/biçim örneği aynı. Gerçek Qt seçim penceresine yalnız kendi widget'ına gönderilen olaylarla seçim ve Esc sınandı; yeniden açılan uygulama aynı alanı kullanarak gerçek MSS/OCR/yerel çeviri ve duraklat/devam yaptı. Sonra fiziksel eşleme değişikliği simüle edilerek durdurma/temizleme/alan geçersizliği doğrulandı. Gerçek monitör çıkarma, karma DPI veya başka bilgisayar denenmedi. Ham kanıtlar `analysis/region-validation-parity.json`, `analysis/region-poll-cost.json` ve native/kurulu test kayıtlarıdır.

Referans fiziksel koordinatları da doğrudan saklar; bu sürüm fiziksel eşlemeyi başlatmadan önce güncel monitörden türetir ve doğrular. Bu bilinçli farktır, tüm arayüz/cihaz eşdeğerliği iddiası değildir. Accurate/pale OCR, arayüz, tanılama ve Samsung akışı kalan işlerdir; tam hedef aktif.
