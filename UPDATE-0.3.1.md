# 0.3.1 — altyazı kaydırma yönü ve sınırı

Altyazı görünümünde + dikey kaydırma, referanstaki gibi her adımda 10 Qt piksel yukarı taşır. Sıfır dışı kaydırma ekranın üst/alt 8 piksel sınırında durur. Yakalamadan dışlama doğrulanmazsa kendi OCR alanını veya diğer kanalın alanını kapatmaz. Sığmayan kartın gösterilmemesi korunur.

Önceki sürümlerin aşağı yönlü piksel ayarı sürümlü olarak tam dönüştürülür: örneğin eski +23 piksel, yeni -2,3 adım olur. Okuma sırasında dosya değişmez; sonraki kayıtta önceki dosya yedeklenir. Böylece kayıtlı tercihin yönü veya büyüklüğü kendiliğinden değişmez. Yeni ayar 1 adımla değişir; eski konumun hassasiyetini korumak için onda bir adımı gösterebilir. Tanınmayan birim sürümü sessizce yorumlanmaz.

104 test geçti. Shipped saf `_nudge_rect` fonksiyonu ile 45 kontrollü geometri aynı; bu tüm arayüz/yerleşim eşdeğerliği iddiası değildir. Gerçek ekran yakalamada seçili altyazı, gerçek OCR/çeviri ve duraklat/devam testi +2 adımın 20 piksel yukarı uygulandığını doğruladı. Ham kayıtlar `analysis/subtitle-offset-parity.json` ve `analysis/subtitle-offset-native.txt`. Karışık DPI/çok monitör/gerçek oyun/TV doğrulaması bekliyor; tam hedef aktif.
