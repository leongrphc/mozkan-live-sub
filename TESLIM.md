# Altyazı Atölyesi 0.4.0 — yerel taşınabilir teslimat

`AltyaziAtolyesi.exe` dosyasını açın. Ana ekranda Canlı çeviri → Tek replik/Diyalog, Oyunlar → profil veya Dizi ve film seçin. İngilizce altyazı ekrandayken alanı seçin ve çeviriyi başlatın. Ana ekrana/Esc ile geri dönüş çalışan çeviriyi durdurur; kapanış bitene kadar yeni kaynak seçilmez. Ayarlar ve TV ayrı pencerededir.

Python runtime, OCR/çeviri modelleri, hazır profiller ve isteğe bağlı Samsung helper paket içindedir. Duplay'ın kurulu olması veya sistemde Python bulunması gerekmez. ZIP'i tamamen çıkarın; EXE'yi diğer klasörlerden ayrı taşımayın. Ayarlar ve günlükler `%LOCALAPPDATA%\AltyaziAtolyesi` altında kalır. Runtime ve modeller kullanıcı tarafından sağlanan kurulumdan yerel kopyalandı; yeni model/çalışma zamanı indirilmedi. Hesap/lisans/güncelleme sunucusu eklenmedi.

Teslim öncesi198otomatik test32,799s içinde geçti. Kapsam UPDATE-0.4.0.md dosyasındadır. Bazı boundary testleri kontrollü üreticiler kullanır; gerçek Qt/MSS/OCR/çeviri/GPU/HUD/PC/yerel WebSocket ve tarayıcı video zincirleri ayrıca kontrollü içerikle sınandı. Bunlar tüm oyunlar/yayın siteleri/DRM/karma DPI/fiziksel TV/başka Windows bilgisayarı için kanıt değildir. Paket manifesti dosya boyutlarını ve SHA-256 kimliklerini tutar. Her arşiv ayrıca doğrulanmalıdır; kaynak projede sürümlü kayıtlar `analysis/package-*` altındadır.

Altyazı/film çevirisi NVIDIA CUDA FP16 kullanabilir; GPU hatasında CPU INT8'e döner. HUD bağımsız tek thread CPU kullanır, 1,2s başlangıç beklemesi ve normal altı sahipli iş parçacığı önceliği vardır. Uzun giriş parçalara ayrılır; bitiş işareti kontrol edilir. Tamamlanmayan çıktı gösterilmez veya önbelleğe alınmaz. Bu, anlamsal doğruluk veya her soluk yazının okunacağı garantisi değildir.

Alanlar seçimin türü ve monitör yapılandırmasıyla kaydedilir; tekrar açılışta doğrulanır, otomatik başlatılmaz. Geçersiz ekran eşlemesinde çeviri durur. Gerçek seçim/Esc/restore/pause-resume sınandı; fiziksel hotplug/karma DPI henüz doğrulanmadı. Hızlı/ayrıntılı OCR, tarama aralığı ve güven/süre/yöntem/kaynak bilgisi ayarlarda bulunur. Varsayılan olarak görüntü veya tanınan metin dosyaya kaydedilmez.

Samsung bölümü mevcut helper binary'sinin adaptörüdür. Gerçek ağ taraması tamamlandı ve TV bulunmadı. Geliştirici modu, Samsung hesabı ve TV'ye kurulum/oturum yenileme fiziksel cihazda denenmedi. Kurulum seçilirse gerçek cihaz işlemi başlar; yalnız isteğe bağlı Samsung cihaz hizmeti kendi hesabını isteyebilir. Uygulamanın kendisi hesap gerektirmez. İptal/normal çıkışta işlem grubu boşalana kadar beklenir. Yardımcı çıktısı80.000bayt/satır ve8MiB/çalışma, günlük1MiB ile sınırlıdır; kapasite aşımı açıkça gösterilir. Günlükler veri klasöründeki `samsung/logs` altındadır.

Duplay ile tam özellik/davranış ve görsel eşdeğerliği henüz kanıtlanmadı. Başlangıç hazırlığı, arayüzün yakalamaya izin vermesi, Hakkında ve metadata günlüğü eklendi. Tam özgün görsel/etkileşim eşdeğerliği ve yukarıdaki gerçek cihaz doğrulamaları açık tutulur. Bu sürüm yüzde100 tamamlanma iddiası değildir. İnceleme çıktıları, kullanıcı ayarları ve hesap bilgileri taşınabilir arşive dahil edilmez.

0.3.8: Önizleme yalnız bellekte960×260thumbnail ile gösterilir. PNG ve JSON kaydı kullanıcı düğmesiyle yapılır; JSON’a metin ekleme ayrıca seçilir. Alan yokken Başlat seçimi açar ve geçerli seçimden sonra devam eder. Konuşmacı adını eşleştirmede yok sayma seçeneği ve önceki repliği gösterme tercihi kaydedilir. Yeni tercihlerde referansın28boyut/alanüstü/#f6f8ff/0.35s varsayılanları kullanılır; kayıtlı değerler korunur.


0.3.9: Modeller hazırlanırken aşama gösterilir ve iptal edilebilir. Ana çeviri ve HUD hazırlığında tokenizer ilk yüklemesi çakışmaz; bekleyen kanal iptal edilebilir. HUD hatası ana altyazıyı durdurmaz. Oyun profilinde canlı diyalog görünümü kullanılmaz; eşleşme puanı0–100ölçeğinde gösterilir. Metadata günlükleri `logs` altında çalışma başına1MiB ile sınırlıdır; altyazı veya ekran görüntüsü içermez. Eski günlükler otomatik silinmez. Hakkında, günlük klasörü ve kullanıcı seçimiyle PNG/JSON dışa aktarımı arayüzdedir.


040teslimi: kapaklı oyun kartları, anında uygulanan altyazı görünümü, aynı yerde Başlat/Durdur ve hazırlık sırasında pencere açma koruması. Yerel oyun kapakları sağlanan özgün kurulumdan değiştirilmeden alındı; uygulama motoru özgün Python modüllerini import etmez. Özgün arayüzün tüm hareket/ses/görsel ayrıntıları aynı değildir. Fiziksel cihaz ve son yüksek-yük OCR kontrolünün sınırları sürüm notlarında açık bırakılmıştır.
