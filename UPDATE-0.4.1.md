# 0.4.1 — MOZKAN Live Sub

- Ana ekrandaki eski marka yazısı düzeltildi. Başlatıcı, pencere, Hakkında ve TV alıcısı MOZKAN Live Sub adını kullanır.
- Ayarlar Çeviri, TV bağlantısı ve Samsung sekmelerine ayrıldı. TV sekmesinde yayın durumu, adres, eşleştirme kodu, alıcı sayısı ve işlem geri bildirimi bir araya getirildi. Üst çubuktan doğrudan TV bağlantısına erişilir.
- Dar pencerelerde ayar, üst çubuk ve alt çubuk satırları alt alta yerleşir. Genel ayarlar tek modeless form yerine ana pencereye bağlı modal pencere olarak açılır; diğer modal pencerelerle aynı yakalama dışlama kontrolünü kullanır. Canlı yakalamada dışlama doğrulanamıyorsa açılmaz.
- Geri/Esc düğmesi eklendi. Oyun aramasından Aşağı ile listeye geçilir; dolu aramada Esc filtreyi temizler. Başlat/Durdur değişiminde klavye odağı korunur. Geçici pencereler kapanınca önceki denetime odak geri verilir.
- Kısa (160 ms) ekran geçişi ve hareketi azaltma tercihi eklendi. Animasyon bitince grafik efekti devre dışı kalır. Başlangıçta kapalı isteğe bağlı menü sesi yerel olarak üretilmiş 45 ms WAV kullanır; yeni ağ bağımlılığı yoktur.
- Yeni adla tam taşınabilir paket ve 0.4.0 için kaynak güncellemesi hazırlanır. Güncelleme aracı hedef kurulumdan çalışan işlem varsa durur; uygulama kapatmaz. Dosyaları değiştirmeden önce yedekler, ana sürüm dosyasını en son değiştirir. Mevcut ayar/model/runtime ve tarihsel teslimler korunur.

OCR/çeviri motoruna, modeline, oyun veritabanlarına ve TV protokolüne değişiklik yapılmadı. Yeni özellikler için test veya uygulama açılışı çalıştırılmadı; kabul kontrolleri kullanıcıya aittir. Kaynak sözdizimi ve paket bütünlüğü kontrolü çalışma zamanı başarısı veya tam referans eşdeğerliği kanıtı değildir. Eski özgün kurulum artık kayıtlı konumunda yoktur; kalan sunum çalışması önceki kaynak alıntıları ve mevcut uygulama kaynakları üzerinden yapıldı.
