# 0.4.0 → MOZKAN Live Sub 0.4.1 geçişi

## Tam paketle geçiş

En doğrudan yöntem tam ZIP’i yeni bir klasöre çıkarmak ve içindeki `MOZKANLiveSub.exe` dosyasını açmaktır. Aynı anda tek normal örnek açılabildiği için eski uygulamayı önce kendiniz kapatın. Mevcut `%LOCALAPPDATA%\AltyaziAtolyesi` ayarları, içe aktarılan profiller ve günlükler kullanılır; bunları taşımayın veya silmeyin. Eski kurulum ve ZIP’ler olduğu gibi kalır. Geri dönmek isterseniz yeni uygulamayı kapatıp eski kurulumun EXE’sini açabilirsiniz.

## Küçük güncellemeyle mevcut kurulumu koruma

1. `MOZKANLiveSub-0.4.1-update.zip` dosyasını kurulumun dışında yeni bir klasöre çıkarın. Güncelleme klasörü tam uygulama değildir; tek başına EXE’sini açmayın.
2. Güncellenecek eski uygulamayı kendiniz kapatın. Araç çalışan uygulamayı kapatmaz ve hedef kurulumdan çalışan işlem bulursa devam etmez.
3. Çıkardığınız `MOZKANLiveSub` klasöründe PowerShell açın ve hedefinizi belirterek çalıştırın:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-update.ps1 -TargetDirectory 'D:\Duplay-Rebuild\releases\AltyaziAtolyesi'
```

4. Başarı bildirimi sonrasında hedef klasördeki **MOZKANLiveSub.exe** dosyasını açın. Uygulama kendiliğinden açılmaz. Eski `AltyaziAtolyesi.exe` dosyası korunur; yeni kısayolunuzu yeni başlatıcıya yönlendirin.

Araç yalnız 0.4.0 kaynak sürümünü kabul eder. Kaynak dosyalarının hash’lerini değişiklikten önce kontrol eder; değişecek mevcut dosyaların tümünü `backups/before-0.4.1-...` dizinine kopyalar. Dosyaları geçici dosyadan değiştirir, `src/main.py` en son yazılır ve kurulu hash’ler kontrol edilir. Model/runtime/oyun verileri ve LocalAppData ayarları bu güncellemenin dışında kalır. Eski `TESLIM.md` ve sürüm notları korunur.

Kesinti veya izin hatasında uygulamayı açmayın; araç gösterdiği yedek klasörünü ve `applied-files.txt` listesini korur. Otomatik geri alma uygulanmaz. En kolay dönüş, değişmez 0.4.0 tam ZIP’ini yeni klasöre çıkarmaktır; ayarlar aynı veri alanında kalır. Eski kurulumun `package-manifest.json` dosyası eski tam paketin tarihsel manifestidir; 0.4.1 kaydı `TESLIM-MOZKAN.md` ve kurulu güncelleme kaydıdır.

Bu güncelleme aracı kaynak ve sözdizimi üzerinden incelendi; kullanıcı tercihi gereği gerçek kuruluma uygulanmadı veya davranış testi çalıştırılmadı. Aynı anda kurulumdan uygulama açmayın. Şüphede tam paketi ayrı klasöre çıkarma yöntemini kullanın.
