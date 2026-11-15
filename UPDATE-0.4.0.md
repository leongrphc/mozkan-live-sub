# 0.4.0 — teslim sürümü

Canlı çeviri, oyun ve dizi/film seçimleri kart görünümündedir. Beş paket oyun profili için özgün kurulumdaki JPEG kapaklar değiştirilmeden eklendi; tanınmayan veya içe aktarılan profile adına bakılarak kapak atanmaz. Arama, tek tıklama ve Enter gerçek profil kimliğini kullanır. Dar pencerede kartlar tek sütuna iner; klavye odağı görünür alana kayar.

Çalışma alanında Başlat ve Durdur aynı yerde gösterilir. İşçi kapanmadan Başlat geri gelmez. Altyazı düğmesi boyut/konum/renk/arka plan/kontur ve PC görünümünü canlı örnekle düzenler; değişiklikler anında uygulanır ve Kapat ile korunur. Genel ayarlar ve TV üstteki düğmededir. Kaynaklar hazırlanırken ayar düğmeleri devre dışıdır; doğrudan pencere isteği de reddedilir. Pencere açmak eski seçimden başlatma isteğini geçersiz kılar. Profil başlığı ve hata metinleri düz metin olarak gösterilir.

Görünüm, Hakkında, HUD ve Qt renk seçici pencereleri ortak yakalama dışlama kontrolünü kullanır. Kapanınca geçici pencere bırakılmaz. Gerçek Win32/MSS denemesinde görünüm ve renk pencereleri sabit kaynağı0piksel değiştirdi; dışlamanın yalnız testin kendi penceresinde geçici kaldırılması46924/40751piksel değiştirdi; geri açılması yine0oldu. Kaynak ve pencere örtüşmesi ayrıca doğrulandı. Bu, OCR/çeviri veya fiziksel TV testi değildir.

Doğrulama: önceki kaynakta197otomatik test temiz geçti. Son Başlat/Durdur, anında görünüm ve hazırlık koruması için9arayüz+7başlangıç testi geçti. Teslim öncesi tam kontrol198test ile32,799s içinde geçti. Arşiv/EXE sonuçları kaynak projenin analysis/teslim-0.4.0.json kaydında tutulur.

Son tam canlı OCR/çeviri denemesi yüksek kaynak yükünde90s test sınırını aştı: yakalama-açık bildirimi79,203s içinde geldi, doğrulanmış OCR/çeviri çıktısı gelmedi. Sonraki yerel ölçüm111MiB boş RAM,%87commit ve%91CPU gösterdi. Kaynak baskısı etkili olabilir; nedensellik kanıtlanmadı ve bu deneme başarılı sayılmadı. Uygulamanın kendisinde90s kesme sınırı yoktur. Aynı çeviri çekirdeğiyle039ve önceki040geliştirme kopyasında gerçek Qt/MSS/OCR/NVIDIA ve duraklat/devam et kontrolleri geçti; bu, son kaynak koşulundaki denemenin yerini tutmaz.

Uygulama yerel/çevrimdışıdır; hesap/lisans/güncelleme sunucusu yoktur. Samsung isteğe bağlı mevcut helper adaptörüdür. Gerçek oyun/harici yayın/DRM/karma DPI/fiziksel Samsung kurulumu ve başka bilgisayar doğrulamaları tamamlanmadı. Özgün UI hareket/ses, TV sayfa sunumu ve tam görsel eşdeğerlik de kanıtlanmadı. Bu paket yüzde100 eşdeğerlik iddiası değildir. İnceleme çıktıları, kullanıcı ayarları ve günlükler arşive eklenmez.
