# MOZKAN Live Sub 0.4.2

Windows üzerinde görünen İngilizce altyazıyı okuyup Türkçesini gösteren yerel uygulama. Oyunlarda, tarayıcıda ve video oynatıcıda kullanılabilir. Ekrandaki yazıyı okur; ses dinlemez. TV kullanımı isteğe bağlıdır.

## Açılış ve ilk çeviri

Tam taşınabilir ZIP’i yeni bir klasöre çıkarın. İçindeki **MOZKANLiveSub.exe** dosyasını açın. Python kurulumu gerekmez; `python`, `src`, `models`, `game_profiles` ve `samsung` klasörlerini paketle birlikte tutun. Kaynak klasöründe `start.ps1` de kullanılabilir.

1. İngilizce altyazıyı oyunda veya videoda görünür hale getirin.
2. Ana ekranda **Canlı Çeviri**, **Oyunlar** veya **Dizi ve film** seçin. Canlı çeviride Tek Replik güncel altyazıyı, Diyalog konuşmacı ve önceki repliği takip eder. Oyun kartları kayıtlı çeviri profillerini açar.
3. **Alan seç ve başlat** ile İngilizce yazıyı çevreleyen dikdörtgeni seçin. Esc seçimi iptal eder. Önceden alan varsa **Alanı önizle** ile kontrol edip **Çeviriyi başlat** düğmesini kullanın.
4. Hazırlık adımları tamamlanınca okuma başlar. Panel seçili alanla örtüşüyorsa küçülür; görev çubuğundan yeniden açabilirsiniz. Hazırlığı Durdur veya Esc ile iptal edebilirsiniz.
5. **Duraklat / Devam et** modelleri bellekte tutar. **Durdur** işlemlerin kapanmasını bekler; kapanmadan yeni oturum başlamaz.

Alanlar monitör yapılandırmasıyla saklanır; açılışta çeviri kendiliğinden başlamaz. Oyunu/tarayıcıyı taşırsanız alanı yeniden seçin. Ekran düzeni veya ölçek değişirse eski alan geçersizleşebilir. Bu özellik pencere takibi değildir. Dizi/film ayarlarında tam video seçimi ayrıca açılabilir; o zaman videonun alt bandı okunur. DRM nedeniyle önizleme siyahsa o görüntüden OCR yapılamaz.

## Görünüm, gezinme ve ayarlar

**Altyazı** düğmesi yazı boyutu (14–64), konum, renk, arka plan opaklığı, kontur ve PC görünümünü canlı örnekle düzenler. Değişiklikler anında uygulanır; Kapat veya Esc geri almaz. PC altyazısını kapatmak TV yayınını durdurmaz. Görev görünümü penceresindeki Kaydet/Vazgeç ise ayrı bir işlemdir.

**Ayarlar** penceresinde Çeviri, TV bağlantısı ve Samsung sekmeleri bulunur. Hızlı/ayrıntılı OCR, tarama aralığı, eşleşmeyeni modelle çevirme, konuşmacı eşleştirme ve isteğe bağlı ikinci Görev/HUD alanı buradan düzenlenir. Çalışma sırasında değiştirilemeyen seçenekler devre dışıdır. Dar pencerelerde satırlar alt alta geçer ve sekme içeriği kaydırılır.

- Tab / Shift+Tab: denetimler arasında geçiş; Enter / Boşluk: odaktaki düğmeyi çalıştırma.
- Ana ekran ve çeviri biçimi kartlarında ok tuşları: seçimler arasında geçiş.
- Oyun aramasında Aşağı: sonuç listesine geçiş; Enter: seçili oyunla devam.
- Arama kutusunda Esc önce dolu aramayı temizler. Sayfada Esc veya **Geri** önceki seçim ekranına döner; çalışan çevirinin kapanmasını bekler. Ana ekrandaki Esc uygulamayı kapatmaz.
- Ayar penceresinde Esc veya Kapat: pencereyi kapatma. Çeviri hazırlığı sırasında ayar pencereleri açılmaz.

**Menü sesleri** başlangıçta kapalıdır. Açıldığında kartlar arasında klavye geçişinde ve ekran değişiminde düşük sesli yerel bir ton çalar. Ses aygıtı yoksa çeviri çalışması buna bağlı değildir. **Ekran geçişlerinde hareketi azalt** kısa sayfa geçişlerini kapatır; kayıtlı tercih yoksa Windows animasyon tercihi kullanılır.

## Kısayollar, düzeltmeler ve geçmiş

**Genel kısayol tuşları** oyun veya tarayıcı öndeyken de çalışır: **Ctrl+Shift+F5** çeviriyi başlatır/durdurur (çalışma ekranındayken), **Ctrl+Shift+F6** duraklatır/devam ettirir, **Ctrl+Shift+F7** PC altyazısını gizler/gösterir (TV yayını sürer), **Ctrl+Shift+F8** alanı yeniden seçtirir. Tuşlar Ayarlar → Çeviri sekmesinden değiştirilebilir veya kapatılabilir; başka uygulama aynı tuşu kullanıyorsa orada uyarı görünür. Ayar penceresi açıkken kısayollar işlem yapmaz.

**Çeviriyi düzelt** (çalışma ekranı) son satırın Türkçesini düzenleyip kaydeder. Aynı İngilizce satır tekrar okunduğunda oyun profili ve modelden önce sizin çeviriniz kullanılır; büyük/küçük harf, boşluk ve sondaki noktalama fark etmez, konuşmacı adı korunur.

**Sözlük ve düzeltmeler** (Ayarlar → Çeviri) terim listesini ve kayıtlı düzeltmeleri yönetir. Terim listesinde İngilizce terime Türkçe karşılık verilir; karşılık boşsa terim olduğu gibi bırakılır (ör. karakter adları). Terimler yalnız modele giden metne uygulanır, oyun profili eşleştirmesini değiştirmez. Model ekleri yine değiştirebilir; terim listesi bir ipucudur, garanti değildir. Veriler `%LOCALAPPDATA%\AltyaziAtolyesi\sozluk.json` dosyasındadır; dosya okunamazsa üzerine yazılmaz, yanına `sozluk.okunamayan-N.json` olarak taşınır.

**Geçmiş** (çalışma ekranı) bu oturumda çevrilen son 200 satırı ayrı pencerede canlı gösterir; kopyalanabilir ve temizlenebilir. Yalnız bellekte tutulur. Pencere ekran yakalamadan dışlanamıyorsa çeviri sırasında açılmaz veya kapatılır.

**En az gösterim** (Ayarlar → Çeviri) hızlı kaybolan altyazının Türkçesini seçilen süre boyunca ekranda tutar; yeni satır gelince hemen değişir. Varsayılan kapalıdır.

**Oyun öncelikli seçenekler** varsayılan kapalıdır. *Çeviriyi işlemcide çalıştır* NVIDIA ekran kartını kullanmaz; çeviri yavaşlayabilir ama GPU oyuna kalır. *Çeviriye düşük öncelik ver* okuma ve çeviri iş parçacıklarını oyunun gerisine alır; yoğun anlarda gecikme artabilir. Etkileri ölçülmedi; kendi oyununuzda deneyin.

Oyun profillerinde önce kayıtlı Türkçe replik aranır. Eşleşmeyen metin için model yedeği kullanılabilir. Profil ekleme, dosyayı doğrulayarak uygulama veri dizinine alır; özgün SQLite dosyasını değiştirmez. Tanınmayan profil adına bakılarak oyun kapağı seçilmez. Kayıtlı çevirilerin ilk çevirmeni doğrulanmadı.

## TV bağlantısı

Üstteki **TV’ye bağlan** doğrudan TV sekmesini açar.

1. TV ve bilgisayarı aynı yerel ağa bağlayın, **TV yayınını aç** düğmesine basın.
2. TV ile aynı ağdaki adresi listeden seçin. **Adresi kopyala** ile alın ve TV tarayıcısında açın. “Bu bilgisayar” adresi TV’den erişim için kullanılmaz.
3. Alıcı isterse ekrandaki eşleştirme kodunu girin. Bağlı alıcı sayısı görünür; **Test altyazısı** bağlı alıcı varsa kullanılabilir. Kopyalama ve gönderim sonucu aynı sekmede gösterilir.

Kamerası olan cihazda TV sekmesindeki **QR kodu** okutmak adresi ve kodu birlikte açar; kod adresin `#` sonrasında taşınır, sunucuya gönderilmez ve bağlantıdan sonra adres çubuğundan silinir. Aynı ağdaki alıcıların kodu kendiliğinden alması (otomatik eşleştirme, Samsung uygulaması dahil) yalnız yayın açıldıktan sonraki 2 dakikada veya **Otomatik eşleştirmeyi aç** düğmesinden sonraki 2 dakikada mümkündür. Önceden bağlanmış alıcılar kodu hatırlar.

Yalnız altyazı ve görev metinleri gönderilir; oyun/video görüntüsü TV’ye aktarılmaz. Alıcı sayısı protokol bağlantılarını sayar, fiziksel TV sayısını garanti etmez. HTTP 8766 ve WebSocket 8765 portları kullanılır. Birden fazla ağ varsa doğru adresi seçin. Yayın kapanırken yeniden açılması engellenir; kapanış hatasında yeniden deneme sunulur.

**Samsung** sekmesi mevcut `DuplaySamsung.exe` ve `Duplay.wgt` araçları için isteğe bağlı kurulum adaptörüdür. TV tarayıcısı ile kullanımda gerekmez. Fiziksel kurulum ve oturum yenileme henüz doğrulanmadı; hesap bağlantısı yalnız kullanıcı tıklamasıyla açılır.

## Veriler ve güncelleme

Ayar, içe aktarılan profiller ve günlükler uyumluluk için `%LOCALAPPDATA%\AltyaziAtolyesi` altında kalır. Yeni adla açılan uygulama mevcut ayarları kullanır; veri dizini taşınmaz. Ayarlar yazılırken önceki dosya yedeklenir. Başka bir işlem ayar dosyasını değiştirirse üzerine sessizce yazılmaz. Aynı anda yalnız bir normal uygulama örneği açılır.

Çalışma günlüğü çalışma başına en fazla 1 MiB metadata tutar. OCR metni ve görüntü otomatik kaydedilmez. **OCR görüntüsünü kaydet** ve **Tanılamayı kaydet** elle dışa aktarır; JSON’a okunan metni eklemek ayrıca seçilir. Başlatıcı günlüğü `startup.log`, uygulama günlükleri `logs` altındadır.

0.4.1’den geçiş, yedek ve geri dönüş için **GUNCELLEME.md** dosyasını okuyun. Yeni teslimin kapsamı **TESLIM-MOZKAN.md**, değişiklikleri **UPDATE-0.4.2.md** içindedir. `TESLIM.md` ve eski sürüm notları tarihsel kayıtlardır.

## Kapsam ve doğrulama sınırı

Çeviriyi yerel OPUS-MT İngilizce→Türkçe modeli ve CTranslate2 yapar; uygun NVIDIA CUDA, hata halinde CPU geri dönüşü vardır. OCR RapidOCR/ONNX Runtime kullanır. Metin OpenAI/Google çeviri API’sine gönderilmez; uygulama hesabı, lisans veya güncelleme sunucusu yoktur.

Yanlış OCR, argo, deyim, bağlam ve hızlı altyazılar sonucu etkileyebilir. Ölçülmüş çeviri doğruluk yüzdesi veya tam referans eşdeğerliği iddia edilmez. Kullanıcı 0.4.0’ı YouTube’da olumlu değerlendirdi. Tarihsel son teslimde 198 otomatik test geçti; son otomatik canlı çeviri denemesi ağır sistem yükünde süre sınırına takıldı. Bu kayıtlar 0.4.1 testi değildir.

0.4.2’de otomatik birim testleri (görünmez Qt ile, 221 test) ve TV alıcı sayfası testleri çalıştırıldı; uygulama gerçek oyun, video, ses, TV veya Samsung ile açılıp denenmedi. Bu testler davranışın gerçek kullanımda doğru olduğunun kanıtı sayılmaz. Gerçek oyun/yayın/DRM, karma DPI, fiziksel TV/Samsung ve başka Windows bilgisayarındaki kabul kontrolleri kullanıcıya aittir.

## Kaynak ve paketleme

Kaynaklar `src/` içindedir. `build.ps1` C# başlatıcıyı derler. `package.py --output releases/YENI_AD.zip` yerel runtime ile tam paket üretir; `--update` yalnız kaynak/başlatıcı/belge güncellemesi üretir. Var olan ZIP’in üzerine yazılmaz. `verify-package.py ARSIV.zip` manifest SHA-256 değerlerini kontrol eder; `--extract-to` yalnız yeni klasöre çıkarır. İnceleme raporları ve kullanıcı verileri pakete eklenmez.
