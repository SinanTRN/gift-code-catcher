import os
import json
import requests
from bs4 import BeautifulSoup

# Çevresel değişkenler (GitHub Secrets'tan otomatik gelecek)
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL = "https://wosgiftcodes.com/"
STATE_FILE = "seen_codes.json"

def send_telegram_message(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram BOT_TOKEN veya CHAT_ID eksik, mesaj gönderilemedi.")
        return False
    
    send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.get(send_url, params=params)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Telegram mesajı gönderilirken hata oluştu: {e}")
        return False

def load_seen_codes():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"State dosyası okunamadı: {e}")
    return []

def save_seen_codes(codes):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(codes, f, indent=4)
    except Exception as e:
        print(f"State dosyası kaydedilemedi: {e}")

def scrape_codes():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(URL, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        scraped_codes = []
        
        # -------------------------------------------------------------------------
        # HTML'den kodları çekme kısmı (Tablodaki ilk sütundan)
        # -------------------------------------------------------------------------
        tbody = soup.find('tbody')
        rows = tbody.find_all('tr') if tbody else soup.find_all('tr')
        
        for row in rows:
            first_td = row.find('td')
            if first_td:
                code_text = first_td.text.strip()
                # Eğer içinde boş kod yoksa listeye ekle
                if code_text:
                    scraped_codes.append(code_text)
                
        return scraped_codes
        
    except Exception as e:
        print(f"Web sitesi kazınırken hata oluştu: {e}")
        return []

def main():
    print("Whiteout Survival Gift Code Scraper çalışıyor...")
    current_codes = scrape_codes()
    
    if not current_codes:
        print("Sayfada hiç kod bulunamadı veya HTML class bilgisi hatalı. Lütfen main.py içindeki find_all kısmını kontrol edin.")
        return

    seen_codes = load_seen_codes()
    new_codes = [code for code in current_codes if code not in seen_codes]

    if new_codes:
        print(f"{len(new_codes)} yeni kod bulundu: {new_codes}")
        for code in new_codes:
            # Telegram'a gönderilecek mesajın şablonu
            message = f"🎁 <b>Yeni Whiteout Survival Kodu!</b>\n\n👉 <code>{code}</code>\n\nHemen kullanın!"
            send_telegram_message(message)
            seen_codes.append(code)
        
        # GitHub action bittikten sonra bu JSON dosyasını kaydedip, repoya commit'leyecek
        save_seen_codes(seen_codes)
        print("Yeni kodlar kaydedildi.")
    else:
        print("Sitede yeni kod bulunamadı.")

if __name__ == "__main__":
    main()
