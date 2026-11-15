# 0.2.9 — Unicode eşleştirme düzeltmesi

0.2.8'in TV/HUD, yerel keşif ve bağlantı kontrollerini içerir. Son sınır kontrolünde Türkçe/emoji içeren yanlış eşleştirme kodunun HTTP500 sunucu hatasına dönüştüğü gerçek loopback WebSocket ile doğrulandı. Kimlik karşılaştırması UTF-8 bayt sınırında yapılır; bu kodlar artık403 ile reddedilir, doğru kodla sonraki bağlantı çalışır. Geçersiz tek UTF-16 surrogate girişi tarayıcıda URI oluşturmadan önce açık hata verir.

88 Python testi ve gerçek receiver JavaScript sınır testleri geçti. Normal eşleştirme ve otomatik keşif değişmez. Fiziksel TV, Samsung widget ve native ekran doğrulaması bekliyor. Bu sürüm %100 tamamlanma değildir.
