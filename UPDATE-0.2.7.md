# 0.2.7 — Mantıksal diyalog ve son konuşmacı

Yeni **Diyalog · son konuşmacı** seçimi, ekranda kalan eski İngilizce konuşmadan son satırı ayırır. **Önceki altyazıyı göster** ayrı tercihtir. Uzayan aynı cümle geçmişe taşınmaz, tekrarlar geçmişi doldurmaz. Önceki satırı gizleyip açmak geçmişi korur. Periyodik OCR aynı birleşik metni okuyunca eski cümle tekrar çevrilmez.

Konuşmacı etiketi oyun profili çevirisinde de korunur; bilinen isimler sabit renkte görünür. PC ve TV aynı önceki/güncel satır verisini kullanır. Çeviri sürerken TV yayını açılırsa güncel satır hemen gönderilir. Durdurma/duraklatma ve gerçek boş altyazı geçmişi temizler. Film modu diyalog ayırmasını uygulamaz, kayıtlı seçimi korur.

Görsel kontrolde bulunan konturun harf içini karartma hatası giderildi. Tek metin yerleşimi önce kontur, sonra renkli dolgu olarak çizilir; ayrı raster maske veya ikinci metin dokümanı yoktur. Kontur 1/2/5 değerlerinde dolgu ve renklerin de kaldığı doğrulanır. Gerçek üretim fontuyla 500 offscreen çizim eski1.893s/1.891 CPU s/59,715,584 bayt tepe, yeni1.991s/1.969 CPU s/59,617,280 bayt tepe kullandı. Görüntü doğruluğu değiştiğinden bu eşit kalitede hız karşılaştırması değildir. Ham sonuç `analysis/overlay-fill-cost.json` içindedir.

79 test geçti. Window.begin → gerçek yakalama kuyruğu/kontrol → Qt görünüm → loopback WebSocket zinciri kontrol edildi; bu testin OCR/MT üreticileri kontrollü sahtedir. Gerçek OCR ve çeviri modelleriyle üretilmiş iki konuşmacılı görüntü zinciri de geçti; masaüstü yakalaması değildir.

Referansın 32 kontrollü çıktısından 27'si aynı. Beş fark bilinçlidir: noktalama değişiminden sonra eski cümleyi tekrar çevirmeme (iki), kısa Go! komutunu koruma (iki) ve anlamlı sayı değişimini bastırmama (bir). Ham sonuçlar `analysis/dialogue-parity.json` içinde. 32.000 sıcak işlem yeni .382s/ .375 CPU s/21,405,696 bayt tepe working set; referans .420s/.422 CPU s/20,824,064 bayt. Birer fresh süreç, OS cache kontrolsüz, token ölçülmedi; gerçek oyun gecikmesine genellenmez.

Windows oturumu kilitli olduğu için yeni görünümün canlı masaüstü testi bekliyor. Gelişmiş HUD/TV, accurate/pale OCR, ana arayüz ve gerçek cihaz doğrulaması açık. Hedef aktif, %100 tamamlanmış değildir.
