# MOZKAN Live Sub 0.4.2 teslim kapsamı

Bu belge 0.4.2 teslimini tanımlar. `TESLIM.md`, `analysis/teslim-0.4.0.json` ve `analysis/teslim-0.4.1.json` önceki teslimlerin değişmez tarihsel kayıtlarıdır.

- Tam paket: `releases/MOZKANLiveSub-0.4.2-portable.zip`.
- Küçük güncelleme: `releases/MOZKANLiveSub-0.4.2-update.zip`; yalnız mevcut 0.4.1 kurulumu içindir.
- Her iki ZIP’in iç klasörü `MOZKANLiveSub/`; başlatıcı `MOZKANLiveSub.exe`.
- Tam pakette yerel Python/kütüphaneler, OCR/çeviri modelleri, oyun profilleri, Samsung yardımcıları ve kullanım belgeleri bulunur. Küçük güncelleme runtime/model/veritabanlarını yeniden içermez.
- Paket manifesti her dosyanın boyutunu ve SHA-256 değerini tutar. Nihai boyutlar ve arşiv hash’leri kaynak projede `analysis/teslim-0.4.2.json` içinde tutulur.

Değişiklikler `UPDATE-0.4.2.md` içindedir: TV eşleştirme kodu sızıntısının kapatılması, dar pencere yerleşim hatasının düzeltilmesi, genel kısayollar, satır düzeltmeleri ve terim listesi, çeviri geçmişi, TV QR eşleştirmesi, oyun öncelikli seçenekler ve en az gösterim süresi.

Doğrulama: 221 otomatik birim testi görünmez Qt platformunda geçti, TV alıcı sayfası JS testleri geçti, kısayol kaydı gerçek Windows platformunda gizli pencereyle bir kez denendi ve paket içerik hash’leri doğrulandı. Uygulama gerçek oyun, video, ses, TV veya Samsung ile açılıp denenmedi; terim ipuçlarının ve performans seçeneklerinin gerçek etkisi ölçülmedi. Kullanıcı kabulü beklenir.

Çalışan kullanıcı uygulaması kapatılmadı, yeniden başlatılmadı veya yerinde güncellenmedi. Eski ZIP’ler, kurulu teslim, ayarlar, yedekler ve inceleme kanıtları korunur. Otomatik güncelleme/hesap/lisans hizmeti eklenmedi.
