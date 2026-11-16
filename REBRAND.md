# MOZKAN Live Sub — isim geçişi

Bu bölüm 15 Kasım 2026’daki isim değişikliğinin kaydıdır. Sonraki 0.4.1 paketlemesi ve güncel geçiş talimatları `TESLIM-MOZKAN.md` ve `GUNCELLEME.md` içindedir.

Kullanıcının seçimiyle ürün adı Altyazı Atölyesi yerine **MOZKAN Live Sub** oldu. Çekirdek sürüm 0.4.0 olarak kaldı; bu ad değişikliği yeni bir işlev sürümü veya yeni test sonucu değildir.

- Güncel kaynak klasöründen açılış: `MOZKANLiveSub.exe` veya `start.ps1`.
- Derleme: `build.ps1`, `MOZKANLiveSub.exe` üretir.
- Yeni taşınabilir paketlerin iç klasörü: `MOZKANLiveSub/`. Örnek üretim: `.\python\python.exe -B -E -s -X utf8 package.py --output releases\MOZKANLiveSub-0.4.0-brand-portable.zip`.
- Paket denetim aracı hem yeni kökü hem eski `AltyaziAtolyesi/` kökünü kabul eder; tek arşivde karışık kökleri reddeder.
- Mevcut `%LOCALAPPDATA%\AltyaziAtolyesi` ayar/günlük dizini, tek örnek kilidi, Samsung iş nesnesi öneki ve `altyazi-atolyesi/diagnostics-v2` şeması uyumluluk amacıyla kalır. Ayar taşınmaz veya sıfırlanmaz.
- Eski ZIP'ler, eski EXE ve kurulu teslim klasörü korunur. Çalışan uygulama kapatılmaz veya yeniden başlatılmaz; açık uygulama eski başlığı göstermeye devam edebilir.
- `TESLIM.md`, eski sürüm notları ve `analysis/teslim-0.4.0.json` eski teslimin tarihsel kayıtlarıdır. O test sonuçları isim değişikliğinin doğrulandığı anlamına gelmez.

Bu adımda tam taşınabilir ZIP yeniden üretilmedi. Kullanıcının isteği gereği test çalıştırılmadı; kabul testleri kullanıcıya aittir.
