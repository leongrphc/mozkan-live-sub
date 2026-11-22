# 0.4.2 — MOZKAN Live Sub (taslak, paketlenmedi)

## Düzeltmeler

- **TV eşleştirme kodu artık ağa açık değil.** Otomatik keşif adresi (`/duplay.json`) kodu yalnız yayın açıldıktan sonraki 2 dakikada veya TV sekmesindeki "Otomatik eşleştirmeyi aç" düğmesine basıldıktan sonraki 2 dakikada verir. Önceden aynı ağdaki herkes ve o ağdaki tarayıcılarda açılan web sayfaları kodu alıp altyazıları okuyabiliyordu. CORS başlığı yalnız keşif adresinde gönderilir. Samsung uygulaması bu süre içinde veya kurulumda verilen kodla bağlanır.
- **Dar pencerede yerleşim hatası düzeltildi.** 0.4.1'de satırları alt alta dizen yerleşim, PySide6'nın yeni enum yapısı yüzünden her yeniden boyutlandırmada hata veriyordu.
- Ad değişikliğinden sonra eski adı bekleyen testler ve zamanlamaya bağlı bir Samsung testi düzeltildi.
- TV açma/kapama ve profil içe aktarma hataları günlüğe yalnız hata türü olarak (`ui_error`) yazılır; mesaj metni yazılmaz.
- `main.py` içindeki TV/Samsung bölümü davranış değişmeden `tv_panel.py` dosyasına taşındı.

## Yeni özellikler

- **Genel kısayol tuşları** (oyun öndeyken de çalışır): Ctrl+Shift+F5 başlat/durdur, Ctrl+Shift+F6 duraklat/devam, Ctrl+Shift+F7 PC altyazısını gizle/göster (TV yayını sürer), Ctrl+Shift+F8 alanı yeniden seç. Çeviri sekmesinden değiştirilebilir veya kapatılabilir. Ctrl+Alt kullanılmadı; Türkçe klavyede AltGr ile çakışır. Başka uygulama aynı tuşu tutuyorsa uyarı gösterilir.
- **Çeviriyi düzelt:** İş ekranında son satırın Türkçesi düzeltilip kaydedilir. Aynı İngilizce satır tekrar okunduğunda oyun profili ve modelden önce sizin çeviriniz gösterilir. Konuşmacı adı korunur.
- **Sözlük ve düzeltmeler:** Çeviri sekmesinden terim listesi (İngilizce terim → Türkçe karşılık, boş = aynen bırak) ve kayıtlı düzeltmeler yönetilir. Terimler modele gönderilmeden önce yerleştirilir. Model ekleri yine değiştirebilir; bu bir ipucudur, garanti değildir. Gerçek modelle ölçülmedi.
- **Çeviri geçmişi:** Bu oturumdaki son 200 satır ayrı pencerede canlı görünür, kopyalanabilir ve temizlenebilir. Yalnız bellekte tutulur. Pencere ekran yakalamadan dışlanır; dışlanamazsa çeviri sırasında açılmaz.
- **TV için QR kod:** TV sekmesindeki QR kod seçili adresi ve eşleştirme kodunu birlikte açar. Kod adresin `#` sonrasında durur, sunucuya gönderilmez ve bağlandıktan sonra adres çubuğundan silinir.
- **Oyun öncelikli seçenekler:** "Çeviriyi işlemcide çalıştır" ekran kartını oyuna bırakır. "Çeviriye düşük öncelik ver" okuma ve çeviri iş parçacıklarını oyunun gerisine alır. İkisi de varsayılan kapalıdır. Gecikmeye etkisi ölçülmedi.
- **En az gösterim süresi:** Hızlı kaybolan altyazının Türkçesi seçilen süre (0–5 sn) boyunca ekranda kalır. Varsayılan kapalıdır.

Yeni veri dosyası: `%LOCALAPPDATA%\AltyaziAtolyesi\sozluk.json`. Okunamazsa üzerine yazılmaz, yanına `sozluk.okunamayan-N.json` olarak taşınır.

## Doğrulama durumu

- Birim test paketi: 221 test geçti (offscreen Qt). Alıcı sayfasının JS testleri geçti.
- Kısayol kaydı ve Windows ileti alımı, gizli bir pencere ve kullanılmayan bir tuşla gerçek Windows platformunda bir kez doğrulandı.
- Uygulama açılıp gerçek oyun, video, TV veya Samsung ile denenmedi. Paket üretilmedi; paketleme betikleri hâlâ 0.4.0→0.4.1 güncellemesine göre ayarlı.
