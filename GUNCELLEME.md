# MOZKAN Live Sub 0.4.1 → 0.4.2 geçişi

## Tam paketle geçiş

En doğrudan yöntem `MOZKANLiveSub-0.4.2-portable.zip` dosyasını yeni bir klasöre çıkarıp içindeki `MOZKANLiveSub.exe` dosyasını açmaktır. Aynı anda tek normal örnek açılabildiği için eski uygulamayı önce kendiniz kapatın. Mevcut `%LOCALAPPDATA%\AltyaziAtolyesi` ayarları, içe aktarılan profiller ve günlükler kullanılır; bunları taşımayın veya silmeyin. Eski kurulum ve ZIP’ler olduğu gibi kalır. Geri dönmek için yeni uygulamayı kapatıp eski kurulumun EXE’sini açabilirsiniz. 0.4.1 yeni `sozluk.json` dosyasını ve yeni ayar anahtarlarını okumaz, yok sayar.

## Küçük güncellemeyle mevcut 0.4.1 kurulumunu koruma

1. `MOZKANLiveSub-0.4.2-update.zip` dosyasını kurulumun dışında yeni bir klasöre çıkarın. Güncelleme klasörü tam uygulama değildir; tek başına EXE’sini açmayın.
2. Güncellenecek 0.4.1 uygulamasını kendiniz kapatın. Araç çalışan uygulamayı kapatmaz ve hedef kurulumdan çalışan işlem bulursa devam etmez.
3. Çıkardığınız `MOZKANLiveSub` klasöründe PowerShell açın ve hedefinizi belirterek çalıştırın:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-update.ps1 -TargetDirectory 'C:\Yol\MOZKANLiveSub'
```

4. Başarı bildirimi sonrasında hedef klasördeki **MOZKANLiveSub.exe** dosyasını açın. Uygulama kendiliğinden açılmaz.

Araç yalnız 0.4.1 kaynak sürümünü kabul eder; 0.4.0 için tam paketi kullanın. Kaynak dosyalarının hash’lerini değişiklikten önce kontrol eder; değişecek mevcut dosyaların tümünü `backups/before-0.4.2-...` dizinine kopyalar. Dosyaları geçici dosyadan değiştirir, `src/main.py` en son yazılır ve kurulu hash’ler kontrol edilir. Model/runtime/oyun verileri ve LocalAppData ayarları bu güncellemenin dışında kalır. Eski sürüm notları korunur.

Kesinti veya izin hatasında uygulamayı açmayın; araç gösterdiği yedek klasörünü ve `applied-files.txt` listesini korur. Otomatik geri alma uygulanmaz. En kolay dönüş, değişmez 0.4.1 tam ZIP’ini yeni klasöre çıkarmaktır; ayarlar aynı veri alanında kalır.

Bu güncelleme aracı kaynak ve PowerShell sözdizimi üzerinden incelendi; gerçek bir kuruluma uygulanmadı. Şüphede tam paketi ayrı klasöre çıkarma yöntemini kullanın.
