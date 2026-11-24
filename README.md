# Gift Code Catcher

Bu proje, Whiteout Survival için yeni gift kodlarını otomatik olarak takip eden ve Telegram üzerinden bildirim gönderen bir Python botudur.

## Özellikler

- Web sitesinden yeni gift kodlarını tarar
- Daha önce işlenen kodları kayıt eder
- Telegram botu üzerinden bildirim gönderir
- Selenium kullanarak otomatik redeem denemesi yapar
- Oyuncu bilgilerini JSON dosyası üzerinden yönetir

## Kurulum

1. Proje dizinine girin:
   ```bash
   cd gift-code-catcher
   ```

2. Sanal ortam oluşturun:
   ```bash
   python -m venv .venv
   ```

3. Sanal ortamı aktif edin:
   ```bash
   .venv\Scripts\activate
   ```

4. Bağımlılıkları kurun:
   ```bash
   pip install -r requirements.txt
   ```

## Yapılandırma

Aşağıdaki ortam değişkenlerini tanımlamanız gerekir:

```bash
set TELEGRAM_BOT_TOKEN=your_bot_token
set TELEGRAM_CHAT_ID=your_chat_id
```

Windows dışında kullanıyorsanız yerine uygun komutları kullanın.

## Kullanım

1. Oyuncu bilgilerini [players.json](players.json) dosyasına ekleyin.
2. İsterseniz [seen_codes.json](seen_codes.json) dosyasını başlangıçta boş bırakın.
3. Botu çalıştırın:
   ```bash
   python main.py
   ```

## Oyuncu Ekleme / Silme

`players.json` dosyasını elle düzenlemek gerekmez. İki yol var, ikisini de yalnızca repo sahibi kullanabilir:

**Telegram komutları** (bir sonraki saatlik çalışmada işlenir):

```
/ekle <player_id> <state> [nick]   -> oyuncu ekle / güncelle
/sil <player_id>                   -> oyuncu sil
/liste                             -> oyuncuları listele
```

Komutları yalnızca `TELEGRAM_ADMIN_ID` secret'ındaki Telegram kullanıcısı verebilir. Bu secret tanımlı değilse `TELEGRAM_CHAT_ID` kullanılır.

**GitHub issue formu** (birkaç saniye içinde işlenir): Issues → New issue → "Oyuncu ekle / sil". Sonuç issue'ya yorum olarak yazılır ve issue kapatılır.

Yeni eklenen oyuncu için sitede hâlâ listelenen aktif kodlar otomatik denenir. Diğer oyuncular için bu kodlar tekrar denenmez.

## Dosya Açıklamaları

- [main.py](main.py): Ana bot mantığı ve otomatik redeem akışı
- [players.json](players.json): Oyuncu ID, state ve nickname bilgileri
- [seen_codes.json](seen_codes.json): Daha önce görülen kodların kaydı
- [requirements.txt](requirements.txt): Gerekli Python paketleri

## Notlar

- Bu proje eğitim ve kişisel kullanım amaçlıdır.
- Web sitesi yapısı değişirse botun çalışması etkilenebilir.
- Chrome ve ChromeDriver kurulu olmalıdır.
