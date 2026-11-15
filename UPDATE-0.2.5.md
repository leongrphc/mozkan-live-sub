# 0.2.5 — Oyun profilleri ve altyazı görünümü

Profil eşleştirmesi cümle başlangıcı, devam, orta parça, konuşmacı, birleşik satır ve bitişik sözcükleri kapsar. Referansın saklanan normalizasyonu ve %68 birleşik kapsama kuralı korunur. 23 kontrollü senaryo ve beş gerçek profilden seçilen 356 sorgu referansla aynı beş sonuç alanını verdi. Bu ölçüm gerçek oyun/OCR akışı değildir.

Profil aç, doğrulanan dosyayı uygulamanın kendi veri klasörüne alır. Kaynak dosyanın sonradan kaldırılması seçimi bozmaz. İçeri aktarılan dosyanın bütünlüğü kontrol edilir; kayıp/değişmiş profiller sessizce canlı çeviriye dönmez.

Görünüm penceresi konum, renk, arka plan opaklığı, kenar kalınlığı, dikey uzaklık ve bilgisayar üst yazısını açma/kapatmayı sunar. Yazı 14–64 aralığındadır. Bilgisayar görünümü kapatılınca TV yayını çalışır. Metinler çizim alanına sarılır; kapasite aşılırsa açık hata gösterilir. Tercihler korunur.

58 otomatik test geçti. Yeni görünümün gerçek ekran testi Windows oturumu kilitli olduğundan yapılmadı; önceki 0.2.4 canlı testleri yeni çizimin doğrulaması değildir. Oyun indeksinin yüklenmesi RDR2 örneğinde referanstan daha yavaş ve daha fazla bellek kullanıyor; seçilmiş sıcak sorgular daha hızlı. Ham zaman/CPU/tepe bellek raporları kaynak projede `analysis/real-profile-parity.json` içinde, token maliyeti ölçülmedi.

Bu güncelleme bağımsız yerel uygulamaya uygulanır; hesap/lisans sunucusu eklemez. Tam Duplay eşdeğerliği ve %100 hedefi henüz tamamlanmadı.
