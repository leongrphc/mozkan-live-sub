# 0.2.3 — duraklatma ve alanı yeniden seçme

- **Duraklat / Devam et:** seçimi ve yüklenmiş modelleri korur. Duraklatırken ekrandaki ve TV'deki eski çeviri temizlenir. Devam edince alan yeniden okunur.
- **Alanı yeniden seç:** aktif işlem varsa kapanışı bekler ve ardından seçim çerçevesini açar. Yeni alanı seçtikten sonra Başlat'a basın.
- Duraklatma veya kaynak değişimi öncesinde üretilmiş, GUI kuyruğunda bekleyen sonuçların yeni durumun üzerine yazması engellendi. Altyazı ve HUD kendi sonuç kimliklerini taşır.
- 0.2.2'deki altyazı satırını ikinci kez kırpmama düzeltmesi korunur.

21 otomatik test geçti. Gerçek Window.begin + yalnızca altyazı satırı seçimiyle OCR/çeviri geçti. Gerçek ekran üzerinde duraklatıp aynı worker ile devam etme ve ikinci çeviriyi alma doğrulandı (soğuk başlangıç dahil tamamlanan görev 16.86 s; tek altyazı gecikmesi ölçümü değildir). Modelin tekrar oluşturulmaması ve eski inference sonucunun atılması ayrı kontrollü testle doğrulandı. CPU, tepe bellek ve gerçek filmde gecikme/FPS ölçülmedi.

Küçük yama ZIP'i mevcut 0.2.1 veya 0.2.2 kurulumunun köküne uygulanabilir; model/runtime içermez. Güncelleme için uygulamayı kapatın, kaynakları yedekleyin ve dosyaları kök klasöre çıkarın. Bu bilgisayardaki kullanılan kopyaya yedekli olarak uygulanmıştır. Diğer Windows/TV doğrulaması ve tam Duplay eşdeğerliği hâlâ tamamlanmadı.
