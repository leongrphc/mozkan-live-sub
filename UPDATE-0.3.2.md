# 0.3.2 — CUDA seçimi, CPU yedeği ve tamamlanmış çeviri

Altyazı/film çevirisi kullanılabilir NVIDIA CUDA üzerinde FP16 seçer. Paket içindeki NVIDIA kitaplıkları yalnız uygulama sürecinin arama yoluna eklenir; kurulum/indirme veya kullanıcı ortamına kalıcı yazma yapılmaz. İlk kısa hazırlık gerçek CUDA kitaplıklarını sınar. GPU yükleme veya inference sırasında kullanılamazsa aynı giriş ve seçenekler CPU INT8 üzerinde denenir. CPU hatası gizlenmez. HUD her zaman CPU INT8 ve tek thread kullanır; CUDA'yı sorgulamaz. Panel kullanılan cihazı veya CPU'ya dönüşü bildirir.

Durdurma/duraklatma ve eskimiş çeviri revision'ı; tokenizer yüklemesi, GPU hazırlığı ve CPU'ya dönüş sınırlarında yeni inference'ı engeller. Film ilk model yüklemesinde duraklatılırsa aynı motorla devam eder.

Uzun kaynak satırları 160 tokenlık parçalara ayrılır; giriş truncation kapalıdır. Çıktının model bitiş işareti kontrol edilir. 256 sınırında tamamlanmayan parçalar bir kez 512 sınırıyla tekrar denenir; yine tamamlanmazsa kesilmiş metin gösterilmez veya önbelleğe alınmaz. Bu, çevirinin anlamsal kalitesini garanti etmez.

117 test geçti. Gerçek yerel modelle otomatik GPU, CPU-only HUD ve eksik CUBLAS kaynaklı gerçek GPU→CPU dönüşü sınandı. CPU INT8 ve GPU FP16 bazı cümlelerde farklı sözcükler seçer. Gerçek ekran seçimi/çeviri/duraklat/devam ve +2 adım kaydırma geçti. 2480 karakter/464 tokenlık kontrollü uzun kaynak üç parçada giriş kaybı olmadan ve bitiş işaretiyle tamamlandı. Ham kayıtlar kaynak projede `analysis/translation-device-cost.json`, `analysis/translation-long-production.json` ve `analysis/mt-cuda-native-subtitle.txt`.

Gerçek oyun yükü altındaki GPU gecikmesi/VRAM, başka GPU/sürücü, fiziksel TV ve başka bilgisayar henüz doğrulanmadı. OCR accurate/pale seçenekleri, kayıtlı alanlar, referans arayüzü ve Samsung yardımcı akışı kalan işlerdir. Tam hedef aktif.
