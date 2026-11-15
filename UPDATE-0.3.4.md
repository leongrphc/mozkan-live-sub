# 0.3.4 — alan kaydının tek sahibi ve kalıcı bozuk kayıt yedeği

Kayıtlı alanları ayar deposu ayrıştırır; pencere bu değişmez alan bilgilerini kullanır. Bozuk/tanınmayan alan verisi diğer geçerli tercihleri silmez. Alanı onardıktan sonra başka bir ayarı kaydetmek, orijinal bozuk kaydın tek yedeğini ezmez; kaynak baytları içerik kimliğiyle ayrı korunur. Yeni bozuk alan verisi dosyaya yazılmadan reddedilir.

Kaydedilen durum, gerçekten üretilen JSON baytlarından sahiplenilir. Çağıranın sonradan değiştirdiği iç içe listeler kayıt durumunu kendiliğinden değiştirmez. Başka bir yazıcı bizim kaydımızın hemen ardından dosyayı değiştirirse onun baytları kendi yüklenmiş durumumuz gibi benimsenmez; sonraki kayıt güncellik hatasıyla durur. Bu, süreçler arasında işlem kilidi eklendiği anlamına gelmez.

Mod, alan türü ve video bandı Başlat'a basılmadan da kaydedilir. Mod değişikliği açık bir seçimi iptal eder; geç gelen sonuç yeni modun alanı gibi yorumlanmaz. Kapanan pencerenin gecikmiş mod/HUD tercih olayları kayıt yapmaz.

137 test geçti. Önceki değişmez 0.3.3 kaynak kopyasıyla gerçek geçici dosya işlemleri karşılaştırıldı: bozuk kaydı onarma ve sonraki yazı boyutu kaydı, çağıranın veri değişikliği ve kayıttan hemen sonraki başka yazıcı müdahalesi. Önceki sorunlar yeniden üretildi; yeni sahiplik kuralıyla kaynak korundu. Müdahale, gerçek dosya yazan kontrollü replace sınırı kancasıdır; rastgele çok süreçli yarış iddiası değildir. Ham kanıt `analysis/settings-owner-comparison.json`.

0.3.3 alan seçimi/geri yükleme/ekran değişikliği davranışı korunur. Gerçek monitör değişimi/karma DPI/başka bilgisayar doğrulaması ve tüm proje kapsamı hâlâ açıktır. Son tam taşınabilir arşiv 0.3.2'dir; 0.3.4 kurulu güncelleme olarak teslim edilir.
