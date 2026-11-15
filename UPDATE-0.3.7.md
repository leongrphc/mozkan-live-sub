# 0.3.7 — Samsung işlem yönetimi ve HUD zamanlaması

Samsung yardımcı programının JSON satırları tek yerde ayrıştırılır. Bulunan TV’ler IP kimliğiyle listelenir; kullanıcı listeden birini seçmedikçe yazdığı adres değişmez. İlerleme, Tizen sürümü, hata kodu ve yardım mesajı ayrı olgular olarak korunur. Giriş bağlantısı yalnız doğrulanan Samsung HTTPS adresine kullanıcı tıklamasıyla açılır. İsteğe bağlı oturum yenileme, kaydedilen TV adresi ve işlem günlüğü eklendi. Uygulama hesabı/lisans/güncelleme servisi yoktur; Samsung’un kendi cihaz kurulum servisi ayrı ve isteğe bağlıdır.

Yardımcı, başka bir program başlatmadan önce uygulamanın oluşturduğu Windows işlem grubuna katılır. İptal ve normal ana işlem çıkışında grup boşalana kadar meşgul durumu sürer. Başlatma ve son temizleme hataları sahipliği kaybettirmez; iptal/yeniden deneme mümkündür. Sonunda satır sonu olmayan sonuçlar da işlenir. Satır80.000bayt, toplam çıktı8MiB, günlük1MiB ile sınırlıdır. Günlük kapasitesi açıkça gösterilir; tanınan TV yayın kodu günlükten çıkarılır. Her çalışmanın kendi günlük dosyası vardır.

HUD, OCR/model yüklemeden önce iptal edilebilir1,2s bekler; ana altyazı kanalına başlangıç önceliği tanır. HUD yakalama ve çeviri iş parçacıkları Windows’ta normalin altına alınır; sahibi bitişte eski önceliği geri yükler. Ana altyazının önceliği değiştirilmez.

173 test geçti. Gerçek yardımcıyla salt okunur ağ taraması tamamlandı; TV bulunmadı. Fiziksel TV’ye kurulum, Samsung oturum yenileme ve geliştirici modu henüz cihaz üzerinde doğrulanmadı. Kontrollü gerçek süreçlerle alt işlem üyeliği, iptal, ana işlem sonrası kalan çocuk, başlatma hatası, bozuk/yoğun çıktı, parçalı UTF8, satır sonu olmayan sonuç ve son temizleme hatası/yeniden deneme doğrulandı. Bunlar gerçek TV kurulum kanıtı değildir.

Güncel tam taşınabilir paket ayrıca hazırlanır ve dosya manifestiyle doğrulanır. Özgün arayüzün kalan önizleme/başlatma/diyalog ayrıntıları, elle tanılama dışa aktarımı ve erişilemeyen gerçek cihaz/oyun/karma DPI/başka bilgisayar doğrulamaları açık tutulur. Tam hedef aktif; yüzde100 eşdeğerlik iddiası yoktur.
