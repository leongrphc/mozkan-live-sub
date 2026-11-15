# Teslim sonrası bitirme kapsamı

15 Kasım 2026. Temel sürüm: teslim edilmiş 0.4.0. Bu dosya geliştirme listesi ve isim önerisidir; uygulama talimatı veya tamamlanma kanıtı değildir.

Kullanıcı YouTube videosunda güzel çalıştığını bildirdi. Bütün testleri kullanıcı üstleniyor; Codex test çalıştırmayacak. Önceki 198 test sonucu tarihsel teslim kanıtıdır.

## Test dışındaki işler

1. **Ürün adı: MOZKAN Live Sub olarak seçildi ve kaynaklara uygulandı.** Pencere/Hakkında, TV alıcısı, başlatıcı bilgileri, derleme çıktısı ve yeni paket kökü güncellendi. Mevcut ayar/günlük dizini ve tek örnek kilidi korunur. Eski teslim ZIP'leri ve tarihsel belgeler yeniden adlandırılmaz. Yeni adla tam taşınabilir paket, son teslim maddesinde hazırlanacak.
2. **Referans arayüzdeki açık sunum farklarını tamamlamak.** Ekran geçişleri/animasyonlar, isteğe bağlı tuş sesleri ve TV bağlantı sayfasının yerleşim/durum sunumu son kayıtta açık kalmıştır. Yeni isimle korunacak görsel yön belirlenerek uygulanacak; özgün üründeki her ayrıntının zorunlu olup olmadığı kapsam kararıdır.
3. **Pencere ve gezinme ayrıntılarını kapatmak.** Modal açılış/kapanış, geri/Esc, odak ve klavye gezinmesindeki referansla açık kalan davranışlar kaynak üzerinden karşılaştırılıp somut farklar düzeltilecek. Kayıtlarda kesinleşmiş hata olmayan noktalara varsayımsal düzeltme yapılmayacak.
4. **Kullanıcının bildireceği somut sorunları çözmek.** Oyun yükünde gecikme, OCR/çeviri, DPI, TV veya Samsung akışında sorun bildirilirse ilgili kod düzeltilecek. Bunlar şu anda kesinleşmiş geliştirme eksikleri değildir; test bekleyen alanlardır. Yeni model veya hız optimizasyonu peşinen zorunlu sayılmaz.
5. **Son paketi ve belgeleri tamamlamak.** Seçilen adla tek nihai paket/güncelleme, mevcut ayarları ve yedekleri koruyan geçiş, açık kullanım talimatı, bilinen sınırlar ve sürüm notları hazırlanacak. Eski arşivler korunacak. Sonraki değişiklikler anlamlı Git commitleriyle kaydedilecek; kabul testlerini kullanıcı yapacak.

## Bitmiş sayılma ölçütü

Seçilen isim ve kararlaştırılan arayüz işleri uygulanmış, kullanıcı tarafından bildirilen teslimi engelleyen hatalar giderilmiş, son paket ve belgeler hazırlanmış ve kullanıcı kabul etmiş olacak. Bu kapsamın tamamlanması bütün cihazlarda kusursuzluk veya ölçülmüş yüzde100 çeviri doğruluğu anlamına gelmez.

Yerel/çevrimdışı Windows kapsamı korunur. Hesap, lisans/güncelleme sunucusu, sesli dublaj ve yeni platformlar bu bitirme listesine dahil değildir.

## İsim adayları

- **MOZKAN Lens:** Ekrandaki yazıyı okuyup çevirme fikrine uygun, oyun ve video kullanımını kapsıyor. İlk tercih.
- **MOZKAN Sub:** Kısa, altyazı odaklı.
- **MOZKAN Translate:** İşlevi doğrudan anlatıyor.
- **MOZKAN Live:** Canlı kullanımı vurguluyor, çeviri işlevi için alt açıklama gerekir.
- **MOZKAN Ekran:** Türkçe ve geniş kapsamlı; çeviri işlevi için alt açıklama gerekir.

Bunlar geçmiş isim önerileridir. Kullanıcı **MOZKAN Live Sub** adını seçti; marka veya alan adı uygunluğu araştırılmadı.

## Git başlangıcı

Önceden Git deposu bulunmadığı için mevcut 0.4.0 kaynakları ilk commit olarak kaydedildi. Eski sürüm notları ve teslim kanıtları mevcut tarihsel kayıt olarak korundu; eski geliştirme adımları için yapay commit geçmişi oluşturulmadı. Büyük çalışma zamanı/model/paket klasörleri mevcut .gitignore kapsamında yerelde kalır. Bu kaynak deposu tek başına tam taşınabilir ürün yedeği değildir.
