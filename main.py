import os
import json
import time
import requests
from bs4 import BeautifulSoup

import cv2
import pytesseract
import numpy as np

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ----- AYARLAR -----
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL = "https://wosgiftcodes.com/"
REDEEM_URL = "https://wos-giftcode.centurygame.com/"
STATE_FILE = "seen_codes.json"
PLAYERS_FILE = "players.json"

# ----- TELEGRAM FONKSİYONLARI -----
def send_telegram_message(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram API bilgileri eksik, mesaj gönderilmedi.")
        return False
    
    send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.get(send_url, params=params)
        return True
    except Exception as e:
        print(f"Telegram mesaj hatası: {e}")
        return False

# ----- VERİ YÖNETİMİ -----
def load_seen_codes():
    if os.path.exists(STATE_FILE):
        tplayer_ids():
    if os.path.exists(PLAYERS_FILE):
        try:
            with open(PLAYERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def load_ry:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_seen_codes(codes):
    with open(STATE_FILE, "w") as f:
        json.dump(codes, f, indent=4)

def scrape_codes():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        res = requests.get(URL, headers=headers)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, 'html.parser')
        scraped_codes = []
        
        tbody = soup.find('tbody')
        rows = tbody.find_all('tr') if tbody else soup.find_all('tr')
        for row in rows:
            first_td = row.find('td')
            if first_td and first_td.text.strip():
                scraped_codes.append(first_td.text.strip())
                
        return scraped_codes
    except Exception as e:
        print(f"Scrape Hatası: {e}")
        return []

# ----- SELENIUM & OCR FONKSİYONLARI -----
def setup_driver():
    options = Options()
    options.add_argument("--headless") # Arka planda çalışma
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("window-size=1920,1080")
    
    # Github sunucularında engellenmemek için dummy agent
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def solve_captcha(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return ""
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    text = pytesseract.image_to_string(thresh, config=custom_config)
    
    return text.strip()

def auto_redeem(code, player_ids):
    results = []
    driver = setup_driver()
    
    try:
        for pid in player_ids:
            driver.get(REDEEM_URL)
            time.sleep(3) # Sayfa yüklenmesi
            
            success = False
            
            # --- 1. AŞAMA: Player ID Log In ---
            try:
                id_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Oyuncu Kimliği']"))
                )
                id_input.clear()
                id_input.send_keys(pid)
                
                login_btn = driver.find_element(By.XPATH, "//div[contains(@class, 'login_btn')]")
                login_btn.click()
                time.sleep(3) # Giriş sonrası modalı bekle
                
            except Exception as e:
                results.append(f"❌ {pid}: Giriş yapılamadı. Element bulunamadı.")
                continue
                
            # --- 2. AŞAMA: Kod + Captcha Doldurma (Max 3 Retry) ---
            for attempt in range(3):
                try:
                    code_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Hediye Kodunu Gir']"))
                    )
                    code_input.clear()
                    code_input.send_keys(code)
                    
                    captcha_input = driver.find_element(By.XPATH, "//input[@placeholder='Lütfen kodu girin']")
                    captcha_img = driver.find_element(By.XPATH, "//img[@class='verify_pic']")
                    
                    captcha_img.screenshot("captcha.png")
                    captcha_text = solve_captcha("captcha.png")
                    if not captcha_text:
                        captcha_text = "0000" # Bilerek patlatıp döngüye soksun
                        
                    captcha_input.clear()
                    captcha_input.send_keys(captcha_text)
                    
                    # Kullanma / Redeem Butonu
                    redeem_btn = driver.find_element(By.XPATH, "//div[contains(@class, 'btn')] | //button[contains(text(), 'Redeem') or contains(text(), 'Kullan')]")
                    redeem_btn.click()
                    time.sleep(3)
                    
                    # Sonuç okuma (sayfanın kaynağı üzerinden anahtar kelirme arıyoruz)
                    page_text = driver.page_source.lower()
                    
                    if "verification code error" in page_text or "captcha" in page_text or "doğrulama" in page_text:
                        print(f"[{pid}] Deneme {attempt+1}: Captcha Hatalı ({captcha_text})")
                        driver.refresh()
                        time.sleep(3)
                        continue
                        
                    elif "success" in page_text or "congratulations" in page_text or "başarılı" in page_text:
                        results.append(f"✅ {pid}: Başarılı! (Captcha: {captcha_text})")
                        success = True
                        break
                        
                    else:
                        # Kod zaten kullanılmış veya geçersizse
                        results.append(f"⚠️ {pid}: Sonuç belirsiz (Geçersiz veya kullanılmış olabilir).")
                        success = True # Captcha hatası değil, bu yüzden retry kırılır
                        break
                        
                except Exception as e:
                    print(f"[{pid}] Deneme {attempt+1} Hatası: {e}")
                    driver.refresh()
                    time.sleep(3)
            
            if not success:
                results.append(f"❌ {pid}: Max 3 captcha denemesi başarısız.")
                
    finally:
        driver.quit()
        if os.path.exists("captcha.png"):
            os.remove("captcha.png")
            
    return results

# ----- ANA İSKELET -----
def main():
    print("Whiteout Survival Otomatik Bot Başladı...")
    player_ids = load_player_ids()
    if not player_ids:
        print("Oyuncu ID listesi boş! Lütfen players.json dosyasını kontrol edin.")
        return
        
    current_codes = scrape_codes()
    
    if not current_codes:
        print("Sayfada hiç kod bulunamadı.")
        return

    seen_codes = load_seen_codes()
    new_codes = [c for c in current_codes if c not in seen_codes]

    if new_codes:
        print(f"{len(new_codes)} yeni kod bulundu: {new_codes}")
        for code in new_codes:
            # 1. Başlangıç Mesajı
            msg_start = f"🎁 <b>Yeni Kod Bulundu!</b>\n👉 <code>{code}</code>\n\n⏳ <b>Otomatik kullanım süreci başlatıldı...</b>"
            send_telegram_message(msg_start)
            
            # 2. Redeem İşlemi
            redeem_results = auto_redeem(code, player_ids)
            
            # 3. Sonuç / Özet Mesajı
            summary = "\n".join(redeem_results)
            msg_end = f"🔔 <b>Rapor ({code}):</b>\n\n{summary}"
            send_telegram_message(msg_end)
            
            seen_codes.append(code)
        
        save_seen_codes(seen_codes)
    else:
        print("Sitede yeni kod yok.")

if __name__ == "__main__":
    main()
