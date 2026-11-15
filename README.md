# Altyazı Atölyesi — taşınabilir 0.4.0

Bağımsız yazılmış Python/Qt uygulaması. Bölge seçimi, ekran OCR, yerel İngilizce–Türkçe çeviri, tarayıcıda dizi/film izleme modu, oyun profilleri, diyalog görünümü ve TV tarayıcı alıcısı içerir. Henüz Duplay ile tam özellik eşdeğerliği doğrulanmadı.

## Çalıştırma

PowerShell içinde:

```powershell
& D:\Duplay-Rebuild\start.ps1
```

Alternatif: `AltyaziAtolyesi.exe` dosyasına çift tıklayın. Başlatıcı yalnızca aynı klasördeki `python/pythonw.exe`, `models/` ve `src/` yollarını kullanır; eski Duplay kurulumuna geri dönüş yoktur. Açılış günlüğü `%LOCALAPPDATA%\AltyaziAtolyesi\startup.log` dosyasındadır. Uygulama tek örnek kilidiyle çalışır.

Python runtime, modeller ve oyun profilleri proje klasörüne yerel olarak kopyalandı. Kendi kodu orijinal uygulama modüllerini import etmez. Yeni bilgisayarda Python kurulması gerekmez; EXE, `python`, `src`, `models` ve isteğe bağlı `game_profiles`/`samsung` klasörleri birlikte taşınmalıdır. Başka Windows bilgisayarında henüz doğrulanmadı. Hazır runtime'ı yeniden oluşturmak için `prepare-runtime.ps1 -SourceInstallation KURULUM_KLASORU`; yerel taşınabilir arşiv üretmek için `python/python.exe package.py --output releases/YENI_PAKET.zip` çalıştırılır. Paket her dosyanın SHA-256 kimliğini `package-manifest.json` içinde tutar. `package.py` var olan arşivin üzerine yazmaz.

1. Bölge seç düğmesiyle yalnızca İngilizce altyazının bulunduğu dikdörtgeni işaretleyin. Escape seçimi iptal eder.
2. Çeviriyi başlat düğmesine basın. Hazırlık adımları gösterilir. Modeller hazır olunca yakalama başlar; panel okunan alanla örtüşüyorsa küçülür. Hazırlık sırasında Durdur veya Esc ile iptal edebilirsiniz.
3. Durdurmak için görev çubuğundan paneli açıp Durdur'a basın. Devam eden inference tamamlanmadan yeni oturum başlamaz. Pencereyi kapatmak da aynı temizliği bekler.

Altyazı/video ve görev alanları, alan türü ve monitör yapılandırmasıyla kaydedilir. Aynı yapılandırmada yeniden açıldığında alan hazır gelir; çeviri kendiliğinden başlamaz. Ekran konumu/ölçeği veya fiziksel eşleme değiştiğinde okuma durur, eski sonuç temizlenir ve etkilenen alan yeniden seçilmelidir. Tam video seçimi altyazı satırı seçimi gibi yeniden yorumlanmaz. Tarayıcı/oyun penceresini taşımak hâlâ alanı yeniden seçmeyi gerektirir; bu özellik pencere takibi değildir.

Kısa ara vermek için **Duraklat**, aynı alanla sürdürmek için **Devam et** düğmesini kullanın. Bu işlem modelleri bellekte tutar ve eski çeviriyi temizler. Tarayıcı/oyun taşındığında **Alanı yeniden seç** düğmesi aktif işin kapanmasını bekleyip yeni seçimi açar. Alanı seçtikten sonra Başlat'a basın.

Altyazı varsayılan olarak seçilen bölgenin üstüne, yer yoksa altına konur. Güvenli yerleşim yapılamazsa çeviri panelde kalır. Altyazı/film çevirisinde kullanılabilir NVIDIA CUDA FP16 seçilir; GPU yükleme/inference hatasında aynı istek CPU INT8 üzerinde denenir. HUD çevirisi daima tek thread CPU kullanır. Cihaz durumu panelde gösterilir. Uzun giriş parçalarının tamamlandığı model bitiş işaretiyle kontrol edilir; tamamlanamayan çıktı kesilmiş halde gösterilmez. Son altı gerçek OCR okuması birlikte değerlendirilir; normalde iki, düşük/bilinmeyen güven puanında üç okuma gerekir. Önbellekten yinelenen aynı sonuç yeni doğrulama sayılmaz. Benzer yazım hatasının kabul edilmiş cümleyi değiştirmesi için baskın tekrar gerekir; kelime oylaması noktalama ve sözcükleri korur. İki saniyelik boş OCR altyazıyı temizler. Bekleyen işler en yeni kabul edilen metinle değiştirilir, eski oturum sonuçları reddedilir.

## Tarayıcıda dizi ve film

1. Tarayıcıda videoyu açın ve İngilizce altyazıları etkinleştirin. Tam ekran kullanacaksanız bölge seçmeden önce tam ekrana geçin.
2. Uygulamada **Dizi / film · Tarayıcı videosu** modunu seçin.
3. Varsayılan **Yalnızca altyazı satırını seçeceğim** seçeneğinde **Altyazı alanını seç** ile İngilizce yazının tamamını çevreleyen alanı işaretleyin. **Alanı önizle** ile yazının görüntüde kaldığını kontrol edin. Videonun tamamını seçmek için ayrı **Videonun tamamını seçeceğim** seçeneğini kullanın; yalnızca o durumda alt %30'luk bant okunur ve oran %50'ye kadar genişletilebilir.
4. **Çeviriyi başlat** düğmesine basın. Model hazırlığı tamamlanınca çeviri video üzerinde görüntülenir. Panel okunan alanla örtüşüyorsa küçülür. Pencereyi taşırsanız veya video boyutunu değiştirirseniz durdurup alanı yeniden seçin.

Bu modda oyun profili ve HUD kullanılmaz. Noktalama/büyük harf farkları aynı altyazıyı yeniden çevirmeyi tetiklemez; sözcük ve sayı değişiklikleri korunur. Yeni altyazı doğrulandığında eski çeviri gizlenir. Boş OCR .8 saniye sürdüğünde çeviri temizlenir. Görüntü kapısından kaçabilecek küçük değişimler için en geç .75 saniyede yeniden OCR yapılır; bunlar hedef aralıklarıdır, inference daha uzun sürerse gerçek süre uzar. Çeviri modeli ilk altyazıdan önce hazırlanır.

Ses tanıma yapılmaz; ekranda görünen İngilizce yazı çevrilir. Siteye veya tarayıcı hesabına bağlanmaz, sekmeleri otomatik keşfetmez. Korumalı video yakalamada siyah görüntü gelirse bu yöntem içerikten OCR çıkaramaz. Harici yayın servisleri ve DRM senaryoları denenmedi.

## Oyun profilleri ve görünüm

Canlı çeviri yerine kurulumda bulunan beş oyun profilinden birini seçin veya Profil aç ile başka bir `.sqlite` dosyası alın. Dosya doğrulanarak uygulamanın kendi veri klasörüne kopyalanır; seçtiğiniz asıl dosya değiştirilmez. Kaynak dosya taşınsa veya silinse de içeri aktarılan profil çalışır. Profil içeriği SHA-256 kimliğiyle, kurulumla gelen profiller dosya adıyla saklanır. Eksik/değişmiş bir seçim açık hata verir.

Tam/yakın eşleşme, birleşen sözcükler, cümle başlangıcı, bağlama bağlı devam ve orta parça eşleştirmesi kullanılır. Birleşik satırlar referansın en az %68 kapsama kuralını izler. Bağlam 12 saniyede eskir. Kontrollü 23 senaryoda ve beş gerçek profilden seçilmiş 356 sorguda sonuçlar referansla aynı çıktı; bu gerçek oyun akışının tamamında eşdeğerlik iddiası değildir. Modelle çeviri yedeği kapatılabilir; açık olduğunda model yakalamadan önce hazırlanır. Yedek kapalı oyun profilinde çeviri modeli yüklenmez. Açık `İsim: metin` konuşmacı etiketleri çeviride korunur ve sabit renklerle gösterilir.

**Diyalog · son konuşmacı** seçeneği, oyunun ekranda bıraktığı eski İngilizce satırları ayırarak son konuşmacıyı çevirir. **Önceki altyazıyı göster** bunun ayrı görünüm tercihidir. Büyüyen bir cümle aynı mantıksal satırı günceller; önceki satıra taşınmaz. Noktalama/yazım tekrarları geçmişi doldurmaz. Önceki satırı gizlemek geçmişi silmez. Bilgisayar ve TV aynı önceki/güncel satır sahibini kullanır. Film modu kendi tam altyazı akışını korur; diyalog seçiminiz oyun moduna dönünce geri gelir. Eski sürümde önceki altyazı açık olan seçimler diyalog moduna taşınır.

**Altyazı görünümü** ile üst/alt/alan üstü/otomatik konum, renk, arka plan saydamlığı, kenar kalınlığı ve dikey uzaklık ayarlanır. Yazı boyutu 14–64 aralığındadır. Bilgisayar üst yazısını kapatmak TV yayınını durdurmaz. Uzun metin sessizce kesilmez; güvenli alana sığmıyorsa panelde neden gösterilir. Yeni çizim yolu Qt offscreen testleriyle doğrulandı; bu sürümün gerçek Windows ekran testi oturum kilidi nedeniyle bekliyor.

0.2.7 kontur çiziminde harflerin içini karartan hatayı düzeltir; kontur ve renkli dolgu tek yerleşimden ayrı geçişlerle çizilir. Güçlendirilen görsel testler gerçek üretim fontuyla kontur 1/2/5 altında da metin renklerinin kaldığını doğrular.

HUD bölgesi seç ile görev metinleri için ikinci bölge tanımlanabilir. HUD kendi OCR/çeviri kanalını ve .55 saniyelik tarama aralığını kullanır. Sözcük kutuları korunur; görsel düğmeler tanınarak çeviri boyunca tutulur, PC ve TV'de rozet olarak çizilir. Model işareti düşürür/çoğaltırsa çevresindeki metin ayrı çevrilir. **Görev görünümü** ile yatay/dikey konum (10Qt piksel/adım) ve %70–150 ölçek ayarlanır. + yatay sağa, + dikey yukarı taşır. Kartın bir OCR alanına geri okunması önlenir. İki kanal ortak durdurma sinyaline bağlıdır; ana worker ikisinin de temizliği bitmeden tamamlanmaz. Gerçek oyun ve fiziksel kontrolcüyle eşdeğerlik henüz doğrulanmadı.

Ayarlar `%LOCALAPPDATA%\AltyaziAtolyesi\settings.json` dosyasına kaydedilir; güncellemeden önce `.json.bak` yedeği alınır. Yazı boyutu, profil ve çeviri tercihleri korunur. Bölge her açılışta yeniden seçilir.

## TV

TV yayınını aç düğmesi WebSocket 8765 ve HTTP 8766 portlarında yerel ağ yayını başlatır. Listeden TV ile aynı ağdaki adresi seçip **Adresi kopyala** ile alın; TV tarayıcısında açın ve **Kodu kopyala** ile alınan eşleştirme kodunu girin. “Bu bilgisayar” adresi yalnız yerel kontrol içindir. Birden fazla ağ varsa uygun adresi seçin; etkinliği kaybolan seçim sessizce başka adresle değiştirilmez. Bağlı alıcı sayısı protokol bağlantılarını sayar, fiziksel TV sayısı değildir. **Test altyazısı** yalnız bağlı alıcı varken yayın yapar.

Altyazı/temizleme, HUD ve diyalog mesajları desteklenir. HUD kutusu seçili alanın kendi monitörüne göre taşınır; TV alıcısı metni kutunun altına, yer yoksa üstüne koyar ve pencere boyutu değişince yerleşimi yeniler. Monitör dışındaki/iki monitörü kesen/aidiyeti belirsiz alan için sahte koordinat üretilmez. 0.3.0 düğme rozetlerini ortak katalogdan PC ve TV'de çizer; gerçek oyun/fiziksel kontrolcü kapsamı hâlâ doğrulanmadı.

Her istemcinin kendi gönderim döngüsü vardır; yavaş istemci diğerlerini sıraya sokmaz. En fazla sekiz alıcı bağlanır. Tek sahipli güncel durum hem canlı gönderimi hem yeniden bağlanmayı besler. Yeniden bağlanan alıcı HUD ve diyalogla birlikte altyazının kalan süresini alır; eski altyazı yeniden canlandırılmaz. Alıcı kopuşta en fazla beş kez artan beklemeyle dener; eski soket olayları ve eski TTL zamanlayıcıları yeni metni değiştiremez. Kodu değiştir ile bağlantı bilinçli kapatılır. Uzun metinler 400/800 karakterde kesilmez; alan başına 8192 karakter sınırı aşılırsa açık hata döner. Uzun görünüm kaydırılabilir. JSON kontrol karakteri/Unicode genişlemesi hesaba katılmıştır. Okumayan bir alıcı gönderimi tıkasa bile kapanış önce sahipli TCP bağlantısını keser ve protokol temizliğini tamamlar.

`/duplay.json` yalnızca yerel/özel ağ istemcilerine gözlenen Duplay discovery sözleşmesini döndürür (wire adı `Duplay`). Alıcı sayfası kodu buradan alıp otomatik bağlanır; keşif kullanılamazsa manuel giriş kalır. Geç gelen keşif, sizin girdiğiniz kodu/bağlantı seçimini değiştirmez. Fiziksel TV ve orijinal widget uyumluluğu henüz denenmedi. 0.2.8 gerçek yerel HTTP/WebSocket + Chromium offscreen testinde otomatik keşif, HUD/resize/clear/reconnect ve metnin HTML olarak çalıştırılmaması geçti; bu fiziksel TV veya masaüstü yakalama testi değildir.

Samsung TV ara / TV’ye kur, proje içindeki `samsung/DuplaySamsung.exe` ve `Duplay.wgt` için yerel adaptördür; Samsung installer yeniden yazılmadı. Gerçek salt okunur ağ taraması tamamlandı, TV bulunmadı. Fiziksel kurulum/oturum yenileme doğrulanmadı. Bulunan TV listesi, ilerleme, Tizen/hata/yardım bilgisi ve isteğe bağlı oturum yenileme desteklenir. Sahipli Windows işlem grubu, iptal ve normal çıkışta alt işlemleri kapatır; grup boşalmadan işlem bitmiş sayılmaz. Gerçek yerel süreçlerle çocuk/torun temizliği ve temizleme hatası sonrası yeniden deneme sınandı. Her çalışmanın 1MiB sınırlı günlüğü veri klasöründe tutulur; TV yayın kodu çıkarılır. Samsung'un kendi hesap bağlantısı yalnız kullanıcı tıklamasıyla açılır.

## Yapılan doğrulama

- Mevcut Python runtime ile `-m unittest discover -s tests -v`: 182 test geçti. Gerçek okuma/önbellek ayrımı, güven puanı, HUD geometri/rozet/çeviri/iptal/ayarlar, sürümlü kaydırma geçişi, diyalog/GUI/yerel WebSocket zinciri, Unicode eşleştirme, profil importu ve cleanup retry dahil. Bazı boundary testleri kontrollü fake üreticiler kullanır; gerçek modeller ayrıca üretilmiş görüntülerle sınandı.
- Diyalog kaynağıyla 32 kontrollü çıktı karşılaştırmasının 27'si aynı. Beş bilinçli fark: noktalaması değişen eski cümlenin tekrar çevrilmemesi (iki durum), kısa `Go!` komutunun korunması (iki durum) ve değişen sayının benzer yazım hatası olarak bastırılmaması. Bu farklar `analysis/dialogue-parity.json` içinde açıkça saklanır; birebir eşdeğerlik iddiası değildir.
- 0.2.6 OCR üreticisi altı üretilmiş görüntünün iki turunda 12/12 doğru metin verdi. Sıcak görev yeni .975s / 2.359 CPU s / 180,764,672 bayt tepe working set; referans .705s / 1.797 CPU s / 185,573,376 bayt. Gerçek üretim OCR + yerel çeviri + kararlılık + boş satır temizleme zinciri üretilmiş karelerle hem ekran hem film modunda geçti. Bunlar gerçek masaüstü veya yayın sitesi testleri değildir; ham raporlar `analysis/ocr-confidence-*.json` içindedir.
- Gerçek tarayıcı alıcı JavaScript'i minimal tarayıcı sınırıyla Node üzerinde çalıştırıldı: yeniden bağlanma, eski bağlantı olayının reddi, HUD temizliği ve diyalog satırları geçti (`tests/test_receiver.js`). Bu fiziksel tarayıcı veya TV testi değildir.
- RDR2 profilinde 100 tam eşleşme örneği ve bir birleşik cümle denemesi geçti. 199.324 kayıt yükleme 1.821 s, görev CPU süresi 1.750 s, tek birleşik sorgu yaklaşık 0.071 ms. Önce/sonra karşılaştırması yok; token ve tepe bellek ölçülmedi. Ham sonuç `analysis/profile-validation.txt`; tüm kayıtlar veya oyun akışı için kapsama iddiası değildir.
- Gerçek RDR2 profili 199.324 kayıtla yüklendi ve bir kaynak satırın eşleşmesi doğrulandı. Bu tüm kayıtların doğruluğu veya kapsam ölçümü değildir.
- Gerçek loopback WebSocket ile Türkçe altyazı iletimi ve sunucu kapanışı doğrulandı.
- Gerçek yerel ONNX OCR ve CTranslate2 INT8 denemesi: üretilen test görüntüsünden “We need to leave before the guards return.” aynen okundu; “Gardiyanlar dönmeden önce gitmemiz gerek.” çevirisi üretildi.
- Qt offscreen smoke: panel oluşturma, bölge seçiminin başlat düğmesine bağlanması ve çeviri gösterimi geçti; `analysis/prototype-panel.png` kaydedildi.
- Gerçek Windows masaüstü testi (`tests/live_capture_smoke.py`): yalnızca oluşturulan bilinen test penceresi MSS ile yakalandı; İngilizce cümle birebir okundu, Türkçe sonucu üretildi ve worker kapandı. Sonuç `analysis/live-capture-result.txt`. Bu testte monitör ismi eşleştirme ve örtüşen OCR kutusu hataları bulundu ve üretici sınırlarında düzeltildi.
- Chromium video testi (`tests/browser_video_smoke.py`): yerel HTML `<video>` içinde canvas akışı oynatıldı, yalnızca alt bandı gerçek MSS ile yakalandı; altyazı aynen okundu, Türkçesi üretildi, yazı kaldırılınca sonuç temizlendi. Son çalıştırma toplam 8.953 s; bu açılış + OCR + çeviri + temizleme görev süresidir, tek altyazı gecikmesi değildir. Ham sonuç `analysis/browser-video-result.txt`. Film modu panel/alan/bant kontrolleri Qt offscreen ile doğrulandı. CPU, süreç ailesi tepe belleği, token maliyeti ve ayrı sıcak görev ölçülmedi; gerçek yayın sitesi, reklam, iki satırlı video altyazısı ve DRM henüz doğrulanmadı.

Windows koordinatları, seçilen Qt ekranına bağlı özel native pencerenin Windows monitör kimliği üzerinden fiziksel piksele çevrilir; monitörler arası bölge reddedilir. Tek gerçek monitörde doğrulandı; karma DPI, oyun ve tam ekran senaryoları denenmedi. Değişmeyen 320×48 görüntü özetinde OCR sonucu, periyodik yeniden okumalar arasında tekrar kullanılır; boş metnin süre aşımı çalışır. Gelişmiş gürültü filtreleri, bazı oyun devam/parça eşleşmeleri, kaynak önceliklendirmesi, orijinal UI eşleşmesi ve başka bilgisayarda doğrulama devam işidir. Tam özellik eşdeğerliği iddia edilmez.

İnceleme ve kanıtlar: [analysis/INCELEME.md](analysis/INCELEME.md).

Kaynak projedeki performans ölçümünün kapsamı ve ham sonuçları `analysis/PERFORMANCE.md` dosyasındadır. Önceki değişim kapısı sürümünde sabit 12 karelik görevde her karede OCR toplam 23.599 s, değişim kapısıyla 5.102 s sürdü; film modunun periyodik yeniden okumasını içermez ve gerçek oyuna genellenmez. TV tarayıcı JavaScript'i `node --check` ile sözdizimi kontrolünden geçti. Taşınabilir runtime ve modellerle ekran/Chromium video testleri, başka yerel klasöre çıkartılan kopyayla EXE açılışı ve gerçek OCR/çeviri geçti. Başka bilgisayar veya Samsung cihaz kurulumu denenmedi. Teslim kapsamı [TESLIM.md](TESLIM.md) dosyasındadır.

0.2.4 üretici karşılaştırmasında, aynı altı fixture iki kez okunurken önceki kod37.535s/CPU70.656s/peak1,850,343,424bayt; yeni kod1.134s/CPU2.688s/peak179,822,592bayt ölçüldü. İkisi de exact12/12. Yeni soğuk tamamlanan ilk OCR.991s/CPU1.250s. Bunlar sadece sentetik OCR görevleri; gerçek oyun FPS/gecikmesi değildir. Ayrıntılar kaynak projede `analysis/ocr-parity-report.md` ve `analysis/ocr-parity-production.json` içinde. Hedef yerel/çevrimdışı ürün olarak aktiftir; hesap/lisans sunucusu ve online update kapsam dışıdır.

0.3.8: Hızlı/ayrıntılı OCR ve0,08–3s tarama aralığı kaydedilir. Canlı gözlemler OCR güveni/süresi/yöntemi/geçişi ile çeviri profil/model/önbellek kaynağını gösterir; varsayılan görüntü veya metin kaydı yoktur. Kısa/soluk yerel değişimler ayrıca kontrol edilir. Küçük ekranlarda panel kaydırılır. Model kaynak/güven bilgisi anlamsal doğruluk garantisi değildir; test kapsamı UPDATE-0.3.8.md dosyasındadır.

0.3.8: Ana ekran, Tek replik/Diyalog seçimi, aranabilir oyun listesi ve çeviri çalışma alanı eklendi. Ayarlar ve TV aynı kontrollere sahip ayrı pencerede açılır. Ana ekrana/Esc ile geri dönüş çalışan çeviriyi durdurur, worker bitmeden kaynak değişmez. Tam özgün görsel/etkileşim eşdeğerliği henüz doğrulanmadı.

0.3.8: Alan seçmeden Başlat’a basıldığında seçim açılır ve geçerli seçimden sonra çeviri başlar. Önizleme çalışma alanında yalnız bellekte tutulur. Ayarlardan OCR görüntüsü PNG ve tanılama JSON kaydedilebilir; metin ekleme ayrı seçimdir. Oyun eşleştirmesinde konuşmacı adını yok sayma seçeneği kaydedilir ve motorun aynı seçeneğine iletilir. Replik türünü değiştirmek önceki repliği gösterme tercihini sıfırlamaz.


0.3.9: OCR, profil ve çeviri modeli hazırlığı ayrı adımlarla gösterilir; kaynaklar hazır olunca arayüz yakalamayı başlatır. İptal edilen/eski oturumun hazır bildirimi yeni oturumu açmaz. HUD hatası yalnız görev kanalını durdurur; ana çeviri sürer. Ana kanal durdurulunca iki kanalın kapanışı beklenir. Canlı diyalogdan oyun profiline geçişte diyalog yığını taşınmaz. Profil eşleşme yüzdesi doğru ölçekte gösterilir.

Uygulama olay günlüğü `%LOCALAPPDATA%\AltyaziAtolyesi\logs\app-*.jsonl` altındadır. Her çalıştırma ayrı, en fazla1MiB dosya kullanır; eski çalıştırmalar otomatik silinmez. Günlük sürüm, oturum, hazırlık adımı ve hata sınıfını içerir; altyazı akışı, ekran görüntüsü, ham hata metni ve ortam değişkenleri yazılmaz. Bu, tüm bağımlılıkların standart konsol çıktısını kaydetmez. Samsung helper günlüğü ayrıdır. Günlük klasörü ve Hakkında düğmeleri arayüzdedir. Tanılama JSON biçimi `altyazi-atolyesi/diagnostics-v2`; profil puanı `match_percent` alanında0–100, OCR güveni0–1 değeridir. Ayrıntılar UPDATE-0.3.9.md dosyasındadır.


0.4.0 teslimi: Ana ekran/çeviri biçimi kartları ve beş oyun için kapaklı seçim ekranı eklendi. Arama, tek tıklama ve Enter profil kimliğini korur. Profil ekleme oyun ekranındadır. Çalışma alanında Başlat/Durdur aynı yerde gösterilir; iş kapanmadan Başlat geri gelmez. Altyazı düğmesi canlı görünüm örneğini açar; boyut, konum, renk, opaklık ve PC görünümü değişiklikleri anında uygulanır. Kapat önceki değişiklikleri geri almaz. Genel ayarlar ve TV, üstteki Ayarlar ve TV düğmesindedir. Modeller hazırlanırken ayar pencereleri açılmaz.

Son canlı çeviri kontrolü, yüksek sistem yükünde90s test sınırına takıldı; hemen sonraki ölçümde111MiB boş RAM ve%91 toplam CPU vardı. Bu sonuç başarılı doğrulama sayılmadı. Uygulamanın kendisinde90s çeviri kesme sınırı yoktur. Önceki039taşınabilir kopyada gerçek OCR/NVIDIA çevirisi doğrulandı;040için son kontrolün kapsamı UPDATE-0.4.0.md dosyasındadır. Tam Duplay görsel/cihaz eşdeğerliği iddia edilmez.
