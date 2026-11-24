# MOZKAN Live Sub

**🇹🇷 Türkçe** · [🇬🇧 English](#english)

Oyunda ya da videoda İngilizce altyazı mı var? MOZKAN Live Sub ekrandaki yazıyı okur, anında Türkçeye çevirir ve çeviriyi ekranın üstünde gösterir. Her şey kendi bilgisayarında çalışır; internet bağlantısı, hesap ya da API anahtarı gerekmez.

## Ne işe yarar?

- **Oyunlar:** Diyalogları, görev ve HUD yazılarını canlı çevirir. Konuşmacıyı ve bir önceki repliği de gösterebilir.
- **Dizi ve film:** Tarayıcıda veya oynatıcıda çıkan İngilizce altyazıyı Türkçe olarak takip edersin.
- **TV'de altyazı:** İstersen çeviriyi aynı ağdaki TV'nin tarayıcısına gönderirsin. Görüntü değil, yalnız altyazı metni gider.
- **Kendi düzeltmelerin:** Yanlış çevrilen satırı düzeltirsin; aynı cümle bir daha geldiğinde senin çevirin kullanılır. Karakter adları için terim listesi de tutabilirsin.

Uygulama ses dinlemez, yalnız ekranda seçtiğin alandaki yazıyı okur (OCR).

## Kurulum

1. [Releases](../../releases/latest) sayfasından `MOZKANLiveSub-*-windows-x64.zip` dosyasını indir.
2. ZIP'i boş bir klasöre çıkar.
3. **`MOZKANLiveSub.exe`**'yi çalıştır. Python kurmana gerek yok, her şey paketin içinde.

> Windows 10/11, 64 bit. NVIDIA ekran kartı varsa çeviri GPU'da hızlanır; yoksa işlemcide çalışır.

## Kullanım

1. İngilizce altyazıyı ekranda görünür yap.
2. Ana ekranda **Canlı Çeviri**, **Oyunlar** ya da **Dizi ve film**'i seç.
3. **Alan seç ve başlat** ile altyazının çıktığı bölgeyi çerçevele.
4. Türkçe çeviri ekranın üstünde belirir. Yazı boyutu, renk ve konum **Altyazı** düğmesinden ayarlanır.

Kısayollar oyun açıkken de çalışır:

| Tuş | İşlev |
| --- | --- |
| `Ctrl+Shift+F5` | Çeviriyi başlat / durdur |
| `Ctrl+Shift+F6` | Duraklat / devam et |
| `Ctrl+Shift+F7` | Altyazıyı gizle / göster |
| `Ctrl+Shift+F8` | Alanı yeniden seç |

Tüm ayrıntılar için [KULLANIM.md](KULLANIM.md) dosyasına bak.

## Bilmen gerekenler

- Çeviri makine çevirisidir. Argo, deyim ve çok hızlı geçen altyazılarda hata yapabilir.
- DRM korumalı yayınlarda (bazı Netflix/Disney+ görüntüleri gibi) ekran siyah görünüyorsa yazı okunamaz.
- Hazır oyun çeviri profilleri pakette yoktur; uygulamadan kendi profil dosyanı ekleyebilirsin.

## Kaynaktan çalıştırma

Python 3.11 gerekir. Modeller depoda yok; release ZIP'indeki `models` klasörünü proje köküne kopyala.

```powershell
pip install -r requirements.txt
python src\main.py --models models
```

Kaynak kod `src/`, testler `tests/` klasöründe. `build.ps1` başlatıcıyı derler, `package.py` taşınabilir paketi üretir.

## Teşekkürler

Çeviri: [OPUS-MT](https://github.com/Helsinki-NLP/OPUS-MT) (Helsinki-NLP, CC BY 4.0) + [CTranslate2](https://github.com/OpenNMT/CTranslate2). Yazı tanıma: [RapidOCR](https://github.com/RapidAI/RapidOCR) / PaddleOCR modelleri (Apache 2.0). Arayüz: PySide6 (Qt).

---

<a id="english"></a>

# MOZKAN Live Sub (English)

English subtitles in your game or video? MOZKAN Live Sub reads the text on screen, translates it into **Turkish** in real time, and shows the translation as an overlay. Everything runs locally on your PC: no internet connection, account, or API key required.

## What it does

- **Games:** Translates dialogue, quest and HUD text live. Can also show the speaker and the previous line.
- **Series and movies:** Follow English subtitles from your browser or media player in Turkish.
- **Subtitles on your TV:** Optionally send the translation to a TV browser on the same network. Only the subtitle text is sent, never the picture.
- **Your own fixes:** Correct a bad line once and your version is used every time it shows up again. A glossary keeps character names and terms consistent.

The app does not listen to audio; it only reads text (OCR) inside the screen area you select.

## Install

1. Download `MOZKANLiveSub-*-windows-x64.zip` from [Releases](../../releases/latest).
2. Extract it into an empty folder.
3. Run **`MOZKANLiveSub.exe`**. No Python install needed, everything is bundled.

> Windows 10/11, 64-bit. With an NVIDIA GPU translation runs on CUDA; otherwise it falls back to the CPU.

## Usage

1. Make the English subtitle visible on screen.
2. Pick **Canlı Çeviri** (live), **Oyunlar** (games) or **Dizi ve film** (series & movies) on the home screen.
3. Use **Alan seç ve başlat** (select area and start) to draw a box around the subtitle.
4. The Turkish translation appears on top of the screen. Change size, color and position with the **Altyazı** button.

Global hotkeys (work while a game is focused): `Ctrl+Shift+F5` start/stop, `F6` pause/resume, `F7` hide/show subtitle, `F8` reselect area.

The interface is in Turkish. The full guide is in [KULLANIM.md](KULLANIM.md) (Turkish).

## Good to know

- This is machine translation; slang, idioms and very fast subtitles can come out wrong.
- DRM-protected video that captures as a black screen cannot be read.
- Pre-made game translation profiles are not included; you can import your own profile file from the app.

## Run from source

Requires Python 3.11. Models are not in the repo; copy the `models` folder from the release ZIP into the project root.

```powershell
pip install -r requirements.txt
python src\main.py --models models
```

Source lives in `src/`, tests in `tests/`. `build.ps1` compiles the launcher, `package.py` builds the portable package.

## Credits

Translation: [OPUS-MT](https://github.com/Helsinki-NLP/OPUS-MT) (Helsinki-NLP, CC BY 4.0) + [CTranslate2](https://github.com/OpenNMT/CTranslate2). Text recognition: [RapidOCR](https://github.com/RapidAI/RapidOCR) / PaddleOCR models (Apache 2.0). UI: PySide6 (Qt).
