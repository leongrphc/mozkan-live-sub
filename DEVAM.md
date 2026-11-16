# MOZKAN Live Sub — kalıcı proje hafızası

## 16 Kasım 2026 — kullanıcı geliştirmeyi açıkça yeniden başlattı

Kullanıcı “goal başlatıp devam et bunları yapalım her şey okey olana kadar durma” dedi. BITIRME-PLANI.md kapsamındaki uygulama ve paketleme işleri tamamlandı; kullanıcı kabulü henüz bekleniyor. Önceki otomatik geliştirme durdurma kararı bu açık istekle kaldırıldı; eski bölümlerdeki durdurma talimatları tarihsel bağlamdır. Kullanıcının testleri kendisi yapacağı tercihi değişmedi; test veya uygulama çalıştırma.

Kaynak sürümü 0.4.1; arayüz commit’i `99b64c0`, son odak düzeltmesi `1d0e752`. Kalan eski ana ekran marka yazısı düzeltildi; Çeviri/TV/Samsung sekmeleri, TV durum/adres/kod ve geri bildirim sunumu, modal ayar penceresinde ortak yakalama dışlama kontrolü, geri/Esc ve odak ayrıntıları, dar form satırları, 160 ms sayfa geçişi/azaltılmış hareket ve varsayılan kapalı yerel menü sesi uygulandı. Kaynak sözdizimi incelendi; çalışma zamanı başarısı iddiası yok.

Yeni adla tam paket `releases/MOZKANLiveSub-0.4.1-portable-r1.zip` (1.367.107.975 bayt / 11.021 dosya), küçük güncelleme `releases/MOZKANLiveSub-0.4.1-update.zip` (1.097.025 bayt / 68 dosya) hazır. Tüm manifest girdileri ve kaynak/tam paket/güncelleme ortak yük hash’leri doğrulandı; uygulama/EXE/test çalıştırılmadı. Kesin yeni teslim kaydı `analysis/teslim-0.4.1.json`; 0.4.0 JSON ve ZIP’leri korunur. Kullanıcı uygulamasına yerinde güncelleme uygulanmaz; yeni paket sunulur. Kullanıcı kabulü henüz yok. İlk `MOZKANLiveSub-0.4.1-portable.zip` adayı son odak düzeltmesinden öncedir; nihai tam paket yalnız `portable-r1.zip` dosyasıdır. Eski/yeni ZIP’lerin üzerine yazılmadı. Yeni bir hata veya kullanıcı geri bildirimi olmadan tekrar paket veya gereksiz geliştirme döngüsü başlatma.

Özgün `C:\Users\MOZKAN\AppData\Local\Programs\Duplay` kurulumu artık yok; mevcut kaynak alıntıları ve raporlar referanstır. Tam eşdeğerlik iddia etme. Klasör boyutu 32.242.558.089 bayt (~30,03 GiB) ölçüldü: 7 açılmış portable kontrol kopyası ~15,42 GiB, eski ZIP’ler ~10,18 GiB. Silinebilir kopyalar kullanıcıya listelendi, bu çalışmada hiçbir klasör silinmedi.


## Güncel ürün adı: MOZKAN Live Sub

Kullanıcı bu adı seçti. Kaynak arayüz, TV alıcısı, C# başlatıcı bilgileri ve yeni paket kökü güncellendi; yeni başlatıcı `MOZKANLiveSub.exe`. Eski teslim ZIP'leri, sürüm notları ve `TESLIM.md` tarihsel kayıttır. `%LOCALAPPDATA%\AltyaziAtolyesi` ayar/günlük dizini, tek örnek kilidi ve tanılama şeması uyumluluk için korunur. Kullanıcının çalışan uygulamasına ve kurulu eski teslim klasörüne dokunulmaz. Bu ad değişikliği test çalıştırma veya listedeki diğer işleri başlatma talimatı değildir.

## 15 Kasım 2026 — teslim sonrası kullanıcı kararı

- Kullanıcı YouTube videosuyla denediğini ve uygulamanın çok güzel çalıştığını bildirdi. Bu, kullanıcı beyanına dayalı olumlu YouTube kullanım kaydıdır; eski başarısız yardımcı denemeyi silmez ve oyun/TV doğrulaması sayılmaz.
- Kullanıcı bütün testleri kendisinin yapacağını, Codex'in test çalıştırmasına gerek olmadığını belirtti. Bundan sonraki test sorumluluğu kullanıcıdadır; mevcut test dosyaları ve eski kanıtlar korunur.
- Güncel istek: test dışındaki bitirme işlerini listele, MOZKAN nickine dayalı isimler öner ve Git commitlerini oluştur. Bu istek listedeki tüm özellikleri otomatik geliştirmeye başlama talimatı değildir.
- Klasörde Git deposu yoktu. Mevcut teslim kaynakları, dokümanlar ve seçili tarihsel kanıtlarla main dalında ilk commit oluşturuldu. Eski sürümler adına geriye dönük yapay commit üretilmedi.
- Bu görüşmenin devamında kullanıcı **MOZKAN Live Sub** adını seçti. Kalan kapsam BITIRME-PLANI.md içindedir.

Önceki devam kaydı: 15 Kasım 2026. Kullanıcı, buraya kadarki gelişmelerin kaydedilmesini ve ileride “devam et” dediğinde bu bilgiyle çalışılmasını istedi. Bu kayıt bir geliştirme başlatma talimatı değildir.

## Önce bilinmesi gereken durum

- Çalışılan proje **D:\Duplay-Rebuild**. **D:\REA ayrı araç deposudur; ürün değişikliklerini oraya yapma.**
- Referans: `C:\Users\MOZKAN\AppData\Local\Programs\Duplay\Duplay.exe` ve aynı kurulumdaki `app` kaynakları/varlıkları. REA ve reverse-engineer-anything becerisi önceki incelemelerde kullanıldı. Tam ürün kaynakları eldeyken normal kaynak incelemesi için yeniden REA kurulumu/doctor çalıştırmak gerekmez.
- **Önceki teslim sürümü 0.4.0**; güncel kaynak ve paket 0.4.1’dir. Son kayıt bu dosyanın üst bölümünde ve `analysis/teslim-0.4.1.json` içindedir.
- Kullanıcı yaklaşık dokuz saatlik otomatik çalışma sonunda **“artık bitir şu goali teslim et bana”** dedi. Paket teslim edildi ve otomatik goal **paused** durumuna alındı. Yeni bir açık devam isteği olmadan otomatik geliştirme başlatma.
- Tam özellik/davranış/görsel eşdeğerlik kanıtlanmadı. Teslim edilmiş olması yüzde100 tamamlanmış olduğu anlamına gelmez.
- Sohbette verilen **%80–85 yalnız kaba hazırlık tahminidir**, ölçülmüş tamamlanma/çeviri kalitesi puanı değildir.

## Kullanıcı tercihleri ve çalışma biçimi

- Türkçe, samimi ve doğrudan iletişim. Kullanıcı tekrar tekrar “devam et” demek ve onay vermek istemiyor.
- Devam istendiğinde önce mevcut dosya/teslim kayıtlarını kontrol et; somut işi bitir. Yeni özellik listeleri veya sürekli küçük sürümler üretip teslimi uzatma.
- Kapsam **yerel/çevrimdışı Windows uygulaması**. Uygulama hesabı, lisans sunucusu veya güncelleme sunucusu olmayacak.
- Kullanıcının açık uygulamasını/oyununu kapatma, yeniden başlatma veya önceliğini değiştirme. Yalnız sahipliği doğrulanmış test yardımcılarını yönet.
- Kaynakları, kullanıcı ayarlarını, eski teslimleri ve kanıtları koru. Var olan ZIP üzerine yazma; yedekli güncelleme yap. Ölçülmemiş başarı/kalite/performans iddiası kurma.

## Teslim dosyaları ve kesin kanıt

- Kurulu EXE: `D:\Duplay-Rebuild\releases\AltyaziAtolyesi\AltyaziAtolyesi.exe`
- Tam paket: `D:\Duplay-Rebuild\releases\AltyaziAtolyesi-0.4.0-portable.zip`
- Güncelleme: `D:\Duplay-Rebuild\releases\AltyaziAtolyesi-0.4.0-update.zip`
- Tam paket: **11.014 dosya**, ZIP **1.367.142.945 bayt**, kaynak toplamı **2.356.050.888 bayt**.
- ZIP SHA-256: `d81c7c1a71ff520b1e46a3ef80f46d9ce2131c959fcc4b7d155104a08c22eb2b`.
- Güncelleme: **41 dosya**, **1.042.062 bayt**, SHA-256 `36c3e5b2da770949ebe4f5f1207a2aaf749f71c6aa2021b2badd6d00f66a35b1`.
- Teslimin asıl durum kaydı: **`analysis/teslim-0.4.0.json`**. Önce bunu oku.
- Ayrıntılar: `UPDATE-0.4.0.md`, `TESLIM.md`, `README.md`, `analysis/delivery-0.4.0.json`.
- Kaynak/kurulu/çıkarılmış kopyanın 41 teslim girdisi hash eşitliği doğrulandı. Kullanıcının çalışan süreci yeniden başlatılmadı.
- Arşiv bütünlüğü kontrol edildi ve `analysis/Portable 0.4.0 check/AltyaziAtolyesi` konumuna çıkarıldı. Kendi EXE açılış testi **0** ile bitti. Kendi runtime'ı beş JPEG kapağı gerçek oyun kartı yükleyicisiyle açtı.
- `analysis/tests-0.4.0-release.txt`: **198 test geçti, 32,799 saniye**. Bu dilsel çeviri kalitesi puanı değildir.
- Önceki 0.3.9 ve daha eski ZIP'ler tarihsel kanıttır. 0.3.9 için resmi tam arşiv `portable-r1.zip`; ilk 0.3.9 portable, sürüm notları eksik olduğu için superseded olarak kaydedildi.

## Ürün kimlere ve neye yarıyor?

- Ana hedef: Windows PC'de görünen İngilizce altyazı ve oyun yazılarını Türkçe takip etmek isteyen oyuncular ve dizi/film izleyicileri.
- **Sadece PC yeterli; TV veya ekran yansıtma zorunlu değildir.** Türkçe PC üzerinde gösterilebilir.
- Tarayıcı/oynatıcıda İngilizce altyazı görünür olmalı; kullanıcı okunacak alanı seçer. Gizli sekmeleri/pencereleri otomatik keşfetmez, ses dinlemez.
- Dizi/film modu altyazı satırı veya ayrı tam-video seçimini destekler. Tam-video seçiminde alt bant kullanılır. Alanı önizleme ve seçimden başlatma vardır.
- Oyunlarda canlı OCR/çeviri, hazır oyun profili eşleştirmesi, son konuşmacı/diyalog görünümü ve ayrı görev/HUD alanı bulunur.
- İngilizce öğrenirken kaynak ve Türkçeyi karşılaştırmak için yardımcı olabilir; dil öğretmeni/garantili sözlük değildir.
- TV alıcısına yerel ağda **altyazı metni** gönderilir; bu hizmet oyun/film görüntüsünü yayınlayan bir ekran yansıtma sistemi değildir.
- Konsol görüntüsü PC'ye ayrıca ulaşmadan uygulama PS/Xbox→TV hattını okuyamaz. Konsola kurulan uygulama değildir.
- Ses üzerinden altyazı üretme, anlık Türkçe dublaj, bütün diller, macOS/Linux veya telefon uygulaması kapsamda yoktur.

## Çeviriyi kim yapıyor; kalite konusunda ne biliyoruz?

- Yerel model: **OPUS-MT İngilizce→Türkçe**, klasör `models/opus-mt-tc-big-en-tr-ct2`.
- Çalıştırıcı: **CTranslate2**. Ana çeviride uygun NVIDIA CUDA FP16; GPU hatasında CPU INT8 geri dönüşü. HUD bağımsız tek thread CPU kullanır.
- Tokenizer yerel dosyalardan yüklenir; çevrimiçi indirme kapalıdır. ChatGPT/OpenAI/Google Translate API'sine metin gönderilmez.
- Hazır oyun profilinde önce SQLite içindeki kayıtlı Türkçe replik aranır; eşleşmeyende model yedeği açıksa yerel model kullanılır. Kayıtlı çevirilerin ilk çevirmeni doğrulanmadı; bunları profesyonel/insan çevirisi diye tanıtma.
- OCR okuma hatası ile model çeviri hatası ayrı aşamalardır. Akıcı Türkçe, anlamın doğru olduğunu garanti etmez. Argo, espri, deyim, bağlam, küçük/soluk/hareketli yazı ve hızlı altyazılar riskli.
- Kapsamlı insan değerlendirmesi yapılmadı. Yüzdelik dilsel doğruluk veya profesyonel yerelleştirme seviyesi iddia etme.

## Gerçekleştirilen başlıca geliştirmeler

1. RapidOCR altyazı geometrisi düzeltildi; ince satır artık aşırı büyütülmüyor. Uyarlamalı hızlı/iki geçişli ayrıntılı OCR, yerel küçük değişim algılama, güven/süre/yöntem ve gerçek yeni örneklerle kararlılık kontrolü var.
2. Yerel MT için CUDA/CPU seçimi, hata geri dönüşü, uzun metin parçalama/EOS kontrolü, tamamlanmamış çıktıyı göstermeme ve cihaz bilgili önbellek eklendi.
3. SQLite oyun eşleştirmesi, bağlam/devam/parça yolları, konuşmacı adını yok sayma, model yedeği ve sahipli/hash doğrulamalı profil içe aktarma geliştirildi.
4. PC altyazısı: boyut/renk/arka plan/kontur/konum, konuşmacı ve önceki replik, güvenli bölge yerleşimi ve yakalama dışlama.
5. HUD: ayrı alan/işçi/CPU modeli, tuş simgeleri, PC ve TV gönderimi, gecikmeli düşük öncelikli başlangıç. HUD hatası ana kanalı durdurmaz; ana duruş her iki kanalı bekler.
6. Alanlar türü ve monitör yapılandırmasıyla saklanır; fiziksel eşleme değişince durur/temizlenir. Aynı düzenle açılışta otomatik çeviri başlamaz. Pencere takibi değildir.
7. Duraklat/devam, yeniden alan seçimi, oturum/revizyon bazlı geç sonuç reddi ve işçi kapanmadan yeniden başlamama.
8. Yerel TV HTTP/WebSocket alıcısı; token, adres/kod kopyalama, bağlantı durumu, test altyazısı, HUD ve temizleme; sınırlandırılmış kuyruk/bağlantı temizliği.
9. Samsung mevcut helper adaptörü; ilerleme/cihaz seçimi/oturum yenileme/kontrollü giriş bağlantısı ve sahipli Windows Job temizliği. Gerçek tarama sıfır TV buldu; fiziksel kurulum/hesap oturumu denenmedi.
10. Ana ekran ve Tek replik/Diyalog kartları, arama yapılabilen kapaklı oyun kartları, film seçeneği ve çalışma alanı. Beş kapak özgün yerel HTML'den değiştirilmeden alındı (`src/art`). Bilinmeyen/içe aktarılan isme bakarak kapak tahmin edilmez.
11. Başlat/Durdur aynı yerde gösterilir; işçi emekliye ayrılmadan Başlat dönmez. Altyazı düğmesi canlı örnekli görünümü açar. **Son 0.4.0'da ayarlar anında uygulanır; Kapat geri almaz.** Önceki geliştirme aşamasının Kaydet/Vazgeç anlatımı artık geçerli değildir.
12. Kaynak hazırlığı ve GUI'nin yakalamaya izin vermesi ayrıldı. Eski hazır bildirimi yeni oturumu başlatmaz. Hazırlıkta ayar düğmeleri ve doğrudan modal açma engellenir; pencere açmak bekleyen eski seçimden başlatmayı iptal eder.
13. PNG/JSON elle dışa aktarma; görüntü ve metin varsayılan otomatik kaydedilmez. JSON'a metin eklemek ayrı seçimdir. Tanılama biçimi v2: profil `match_percent` 0–100, OCR güveni 0–1.
14. Çalışma başına en fazla1MiB metadata günlüğü; altyazı akışı/ham hata/ortam yazılmaz. Son hata kuyruğu kapanıştan önce boşaltılır; başarısız temizleme sahipliği korunur. Günlük klasörü ve Hakkında vardır.
15. Modal yakalama dışlaması ortak sınırdan uygulanır; bilinmeyen canlı dışlamada pencere reddedilir; geçici pencereler bırakılmaz. Profil tooltip'i kaçışlanmış, durum metni açıkça düz metindir.

## Kanıt ve sınırlamaları karıştırma

- **Son 0.4.0 canlı OCR/çeviri kontrolü başarılı değil:** `analysis/native-0.4.0-dev-game-preview.txt`, 90s yardımcı test sınırı; yakalama-açık durumu79,203s, doğrulanmış OCR/çeviri çıktısı yok. Ürünün kendisinde90s kesme sınırı yok.
- Ardından111MiB boş RAM, %91 toplam CPU ve %87commit gözlendi. Kaynak baskısı olası etken; nedensellik kanıtlanmadı. Kullanıcının diğer uygulamaları değiştirilmedi.
- Önceki0.3.9 taşınabilir kopyada ve daha erken0.4.0 kart aşamasında gerçek MSS/OCR/NVIDIA çevirisi + duraklat/devam geçti. Bunlar son denemenin yerine geçmez.
- Native modal bileşen testi: `analysis/appearance-0.4.0-dev-native-final-v2.txt`; görünüm0/46924/0, renk seçici0/40751/0piksel (dışlanmış/yalnız kendi penceresinde dışlama kaldırılmış/yeniden dışlanmış). Sahipli sabit kaynak, RGB ve önde pencere kontrolleriyle doğrulandı. Bu bileşen kanıtı son küçük UI/akış değişikliklerinden öncedir; tüm son çeviri zinciri kanıtı değildir.
- İlk başarısız yakalama yardımcıları sabit kaynağı gerçekten öne getirmemiş ve hareketli arka planı ölçmüştü. Bunlar ürün hatası kanıtı değildir. İleride sahnenin görünürlüğünü ve gerçek örtüşmesini doğrulamadan piksel eşitliği kullanma.
- Bazı eski197test çalışmaları eksik FailingService fixture'ı yüzünden Qt callback AttributeError yazdırırken OK dönmüştü. Fixture üretici sınırında düzeltildi; doğrudan poll/readiness/temizleme denetimi eklendi. Son198test temiz çalışmadır.
- Kontrollü özgün HTML ön yüzü sahte QWebChannel ile, dış bağlantılar engellenerek görüntülendi. Özgün Python/lisans motoru çalıştırılmadı. Oyun DOM'unda kartlar görünse de offscreen Qt görüntüsü boş kaldı; bu nedenle tam piksel eşitliği iddia edilmedi.
- Performans kayıtları belirli görevler içindir; tüm oyun FPS/gecikmesine genellenmez. Soğuk süreç/sıcak görev, CPU ve tepe bellek kapsamları raporlarda; token/GPU belleği gibi ölçülmeyenler açık bırakılmıştır.

## Devam istendiğinde öncelik sırası

1. Bu dosyayı, `analysis/teslim-0.4.0.json`, `UPDATE-0.4.0.md` ve son `analysis/goal-progress.md` bölümünü oku. Dosya/sürüm/goal durumunu yeniden kontrol et; eski aktif süreç varsayma.
2. **Öncelik gerçek kullanımda zamanında çeviri.** Son başarısız denemeyi kaynak yükü/okuma/başlatma aşamalarıyla ayır. Değişmeyen koşullarda sürekli model yükleyip sistemi zorlamak yerine, kontrollü ve kaynakları kaydedilmiş karşılaştırma yap. Eager hazırlığı sırf testi geçirmek için kaldırma: referans da OCR+çevirici/hafıza hazırlığını takip ediyor.
3. Normal ve oyunla birlikte yük altında gerçek çeviri doğrula. Gerçek oyun/tarayıcı oynatımı, pencere/çerçevesiz/tam ekran ve farklı yazı örnekleriyle kapsama ekle. OCR doğruluğu, dilsel doğruluk ve gecikmeyi ayrı değerlendir.
4. İnsan tarafından değerlendirilen temsilî İngilizce→Türkçe cümle seti hazırla; jargon/argo/bağlam hatalarını ölçmeden modele kalite yüzdesi verme.
5. Gerçek yayın servisleri/DRM, fiziksel TV ve Samsung kurulum/yenileme, karma DPI ve başka Windows bilgisayarında taşınabilir çalışma açık doğrulamalardır.
6. Referans UI hareket/ses/TV sayfa sunumu ve bütün modal/geri/klavye ayrıntıları eşleşmedi. Bunlar tamamlanmış diye işaretlenmeyecek; yeni alakasız özellik listesi yaratılmayacak.
7. Değişiklik gerekiyorsa tek somut teslim döngüsü yap: ilgili testler, kayıtlı sınırlamalar, yedekli güncelleme, tam paket/doğrulama ve kullanıcıya dosya. Her küçük görsel değişim için yeni sürüm yayınlama.

## Dosyalar ve geliştirme işlemleri

- Tam ayrıntılı kronoloji: `analysis/goal-progress.md`. Önceki bulgular için bu dosyayı arayarak ilerle; tüm büyük raporları baştan yükleme.
- Sonraki önemli kayıtlar: `analysis/ui-parity-0.4.0-dev-game-preview.json` (ara durum; son anında uygulama/dock düzeltmelerinden öncedir), `analysis/game-art-source.json`, `analysis/package-0.4.0-verified.json`, `analysis/package-0.4.0-self-test.json`, `analysis/package-0.4.0-art.json`.
- Test: `.\python\python.exe -B -E -s -X utf8 -m unittest discover -s tests`.
- Paket: `.\python\python.exe -B -E -s -X utf8 package.py --output releases\YENI_AD.zip`.
- Kontrol: `.\python\python.exe -B -E -s -X utf8 verify-package.py releases\YENI_AD.zip --extract-to 'analysis\YENI KLASOR'`.
- Son teslim üreticisi `analysis/deliver_040.py` örnektir; **src/art JPEG'lerini de içerir**. Eski039üreticisindeki yalnız `src/*.py` globuna dönme.
- `analysis` kayıtları, kullanıcı ayarları/günlükleri ve yedekler tam taşınabilir arşive girmez. `package.py` sürüm notlarını ve kaynak altındaki kaynak/varlıkları toplar. Teslim ZIP'leri değişmez tutulur.

