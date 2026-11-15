# 0.2.8 — TV HUD yerleşimi ve bağlantı kontrolleri

TV adresleri etkin ağ arayüzlerinden bulunur. Adresi/kodu kopyala, bağlı alıcı sayısı ve test altyazısı kontrolleri eklendi. Alıcı, yerel keşif endpoint'inden kodu alıp otomatik bağlanır; geç gelen keşif kullanıcının manuel seçimini ezmez. Etkinliği kaybolan bir adres seçimi sessizce başka adresle değiştirilmez. Test yayını fiziksel cihazın aldığını doğrulayan ACK değildir.

HUD konumu seçili alanın kendi monitörüne göre normalleştirilir. TV alıcısı metni alanın altına, yer yoksa üstüne yerleştirir; sınırları ve yeniden boyutlandırmayı gözetir. Dışarıda/kesişen/belirsiz monitör için koordinat uydurulmaz. Altı geçerli geometri referansın izole metoduyla aynı sonucu verdi; üç geçersiz sahiplik durumu açıkça reddedilir. Gerçek çoklu monitör/karma DPI testi değildir.

Altyazı/HUD artık 400/800 karakterde sessizce kesilmez. Alan başına8192 karakter, konuşmacı46 karakter ve JSON genişlemesinden türetilen mesaj sınırı uygulanır. Geçersiz yayın eski geçerli durumu kısmen ezmez. Uzun görünüm kaydırılabilir. Bu kapasite davranışı referansın kesme davranışından bilinçli ayrılır; eski widget kapasitesi ayrıca doğrulanmalıdır.

Alıcı eski soket/TTL olaylarını reddeder, en fazla beş kez yeniden dener, kod değiştirildiğinde eski denemeyi başlatmaz. Gelen metin HTML olarak çalıştırılmaz. Gerçek HTTP/WebSocket + Chromium offscreen HUD/resize/clear/reconnect kontrolü ve Node sınır testleri geçti.

Okumayan gerçek TCP/WebSocket alıcısında kapanışın3 saniyelik gözlem boyunca takıldığı doğrulandı. Sahipli ham soketler protokol close'dan önce kesilerek writer mutex bekleyişi giderildi; aynı test .380 saniyede kapandı ve sahipli soket/thread bırakmadı. Bu fiziksel TV ölçümü değildir.

87 Python testi geçti. Ortak kısa mesaj işinde8alıcı ×100güncelleme (1600WSmesajı): önce toplam .52696s/.203125CPU s/34,332,672bayt peak, yeni .52094s/.1875CPU s/34,394,112bayt peak. Soğuk/sıcak/cleanup ayrı raw raporda; fresh süreç, OS cache kontrolsüz, token ölçülmedi. Büyük yeni mesajlar/GUI/browser bu eşdeğer maliyet işine dahil değildir. Tek koşudan genel hız artışı çıkarılmaz.

Gerçek TV, Samsung widget, çoklu monitör ve yeni native ekran testi henüz doğrulanmadı. HUD düğme/kelime yerleşimi, OCR accurate/pale, GPU fallback ve ana arayüz işleri açık. Hedef %100 tamamlanmış değildir.
