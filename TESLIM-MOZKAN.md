# MOZKAN Live Sub 0.4.1 teslim kapsamı

Bu belge yeni adla hazırlanan 0.4.1 teslimini tanımlar. `TESLIM.md` ve `analysis/teslim-0.4.0.json` önceki teslimin değişmez tarihsel kayıtlarıdır.

- Tam paket: `releases/MOZKANLiveSub-0.4.1-portable-r1.zip`.
- Küçük güncelleme: `releases/MOZKANLiveSub-0.4.1-update.zip`; yalnız mevcut 0.4.0 kurulumu içindir.
- Her iki ZIP’in iç klasörü `MOZKANLiveSub/`; başlatıcı `MOZKANLiveSub.exe`.
- Kaynak klasöründeki `MOZKANLiveSub.exe` de güncel `src/` dosyalarını kullanır.
- Tam pakette yerel Python/kütüphaneler, OCR/çeviri modelleri, oyun profilleri, Samsung yardımcıları ve kullanım belgeleri bulunur. Küçük güncelleme runtime/model/veritabanlarını yeniden içermez.
- Paket manifesti her dosyanın boyutunu ve SHA-256 değerini tutar. Nihai boyutlar, arşiv hash’leri ve denetim kapsamı kaynak projede `analysis/teslim-0.4.1.json` içinde tutulur.

Kalan bitirme kapsamından marka tutarlılığı, TV sunumu, sayfa hareketi/isteğe bağlı ses, geri/Esc/odak ayrıntıları ve yeni paketleme uygulanmıştır. Somut kullanıcı hatası bildirilirse ayrıca ele alınacaktır. Tam özgün ürün eşdeğerliği hedefinin kanıtlandığı anlamına gelmez.

Kullanıcı testleri üstlenmiştir. Bu sürümde uygulama açılışı, otomatik davranış testi, görsel/ses testi, canlı OCR/çeviri veya fiziksel cihaz testi çalıştırılmadı. Yapılan kontroller kaynak sözdizimi incelemesi, statik değişiklik gözden geçirmesi ve arşiv içerik hash denetimidir. Önceki 198 testin geçmesi ve kullanıcının 0.4.0 YouTube deneyimi bu sürümün yeni test sonucu değildir.

Kullanıcı kabulü beklenir: yeni başlatıcıyla açılış, kart/geri/klavye akışı, ayarların korunması, isteğe bağlı ses/hareket, günlük kullanımda OCR/çeviri ve kullanılacaksa TV. Fiziksel Samsung, DRM, karma DPI ve başka bilgisayar kapsamı doğrulanmış değildir.

Çalışan kullanıcı uygulaması kapatılmadı, yeniden başlatılmadı veya yerinde güncellenmedi. Eski ZIP’ler, kurulu teslim, ayarlar, yedekler ve inceleme kanıtları korunur. Otomatik güncelleme/hesap/lisans hizmeti eklenmedi.
