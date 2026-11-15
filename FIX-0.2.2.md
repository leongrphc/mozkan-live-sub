# 0.2.2 — altyazı alanı seçimi düzeltmesi

Film modu daha önce her seçimi video alanı kabul edip alt %30'unu tarıyordu. Kullanıcı yalnızca altyazı satırını seçtiğinde, yazı bu ikinci kırpmayla dışarıda kalabiliyordu.

Artık varsayılan **Yalnızca altyazı satırını seçeceğim** seçeneğidir. İşaretlenen alanın tamamı okunur. Videonun tamamını seçmek isteyenler ayrı seçeneği kullanabilir; yüzde ayarı yalnızca bu durumda etkindir. **Alanı önizle**, OCR'nin okuyacağı gerçek görüntüyü gösterir. Sekiz saniye boş OCR sonucunda panelde alanı kontrol etme mesajı gösterilir.

18 otomatik test geçti. Ayrıca gerçek Window.begin akışında 950×65 piksel altyazı seçimi, OCR ve Türkçe çeviriyle doğrulandı. Bu, kullanıcının videosunda başarının henüz gözlendiği anlamına gelmez; yeniden seçilen alanın önizlemesinde İngilizce metnin görünmesi gerekir.

Yerel çalışan kopyanın üç kaynak dosyası normal kapanıştan sonra yedeklenerek güncellendi. Küçük yama ZIP'i yalnızca `src/main.py`, `src/capture.py`, `src/video.py` ve bu notu içerir; runtime/model indirmesi gerekmez. Başka kopyalarda ZIP içeriğini uygulamanın kök klasörüne çıkarıp dosyaları güncelleyin. 0.2.1 tam arşivini kullananlar bu yamayı da uygulamalıdır.
