# 0.2.4 — OCR maliyeti ve kapanış güvenilirliği

Dar altyazı görüntülerinin RapidOCR tarafından aşırı büyütülmesi giderildi. Subtitle görüntüsü tek üretici sınırında 640×96'ya oranı korunarak sığdırılır. HUD kendi geometri yolunu korur. Altı sentetik örneğin iki turunda önceki ve yeni kod exact12/12 verdi; sıcak görev 37.535 saniyeden 1.134 saniyeye, tepe işlem working set'i yaklaşık1.85GB'dan180MB'a indi. Gerçek oyun FPS/gecikmesi için bu sayıların genellenmesi doğru değildir.

Durdurulmuş oturum yeni inference başlatmaz. TV kapanışı başarısızsa servis sahibi korunur ve kapatma yeniden denenebilir. Yarım HTTP bağlantıları kapatılıp request thread'leri beklenir. Eski oturum/duraklatma durum mesajları yeni UI durumunu ezmez. Geçersiz ayarlar yedekleri korunarak kurtarılır ve başka yazıcının güncel ayarı ezilmez.

32 otomatik test, gerçek seçilmiş altyazı + duraklat/devam ve yerel Chromium video/clear akışı geçti. Handshake öncesi ham WebSocket soketleri de kabul sınırında sahiplenilip kapanışta beklenir. Yerel/çevrimdışı hedef aktif; bu sürüm tam Duplay eşdeğerliği veya %100 tamamlanma değildir. Eksik özellikler kaynak projedeki `analysis/goal-progress.md` içinde takip edilir.
