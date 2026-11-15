# 0.2.6 — OCR güven puanı ve gerçek okuma doğrulaması

Önbellekten dönen bir OCR sonucu artık ayrı bir okuma gibi sayılmaz. Doğrulama beklerken yeni OCR yapılır; kabul edilen değişmeyen altyazı için önbellek kullanılmaya devam eder. Düşük veya bilinmeyen güven puanında üç, normalde iki gerçek okuma istenir. Son altı okumadan kelime oylaması yapılır; tek bir yazım hatası kabul edilen cümleyi değiştirmez. Değişen sayılar anlamlı değişiklik kabul edilir.

OCR üreticisi metin, güven puanı, yöntem ve süreyi tek sonuçta taşır. Eksik/geçersiz puan bilinmeyen kalır. Düşük puanlı bir kelime cümleden tek başına silinmez. Okunabilirlik filtresi bütün altyazıya uygulanır; kısa konuşmalar ve sayılar korunur. HUD bu altyazı filtresinden bağımsızdır.

69 Python testi geçti. Altı üretilmiş görüntü × iki OCR turu 12/12 doğru çıktı. Gerçek yerel OCR/çeviri/kararlılık/boş satır temizliği üretilmiş karelerle ekran ve film modlarında geçti. Sıcak 12 OCR görevi .975 saniye, 2.359 CPU saniyesi ve 180,764,672 bayt tepe working set kullandı; aynı görev referansta .705 saniye, 1.797 CPU saniyesi ve 185,573,376 bayt kullandı. Tek koşu, OS cache kontrolsüz, token maliyeti ölçülmedi.

Windows oturumu kilitli olduğundan yeni kodun gerçek masaüstü/video doğrulaması bekliyor. Referans ilk iyi okumayı gösterebilir; bu sürüm en az iki gerçek okumayı bekler. Pale/accurate OCR kurtarma, gelişmiş diyalog/HUD/TV ve arayüz eşdeğerliği hâlâ açık. %100 tamamlanma iddiası yoktur.
