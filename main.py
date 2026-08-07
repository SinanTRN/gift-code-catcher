import os
import json
import time
import requests
from bs4 import BeautifulSoup

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
DEFAULT_STATE = "2642"

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
def load_players():
    if os.path.exists(PLAYERS_FILE):
        try:
            with open(PLAYERS_FILE, "r") as f:
                raw_players = json.load(f)
                players = []

                if isinstance(raw_players, list):
                    for entry in raw_players:
                        if isinstance(entry, str):
                            player_id = entry.strip()
                            if player_id:
                                players.append({
                                    "player_id": player_id,
                                    "state": DEFAULT_STATE,
                                    "nickname": player_id
                                })
                        elif isinstance(entry, dict):
                            player_id = str(entry.get("player_id") or entry.get("pid") or entry.get("id") or "").strip()
                            state = str(entry.get("state") or DEFAULT_STATE).strip()
                            nickname = str(entry.get("nickname") or entry.get("name") or player_id).strip()
                            if player_id:
                                players.append({
                                    "player_id": player_id,
                                    "state": state,
                                    "nickname": nickname or player_id
                                })

                return players
        except Exception:
            return []
    return []

def load_seen_codes():
    if os.path.exists(STATE_FILE):
        try:
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

# ----- SELENIUM FONKSİYONLARI -----
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

def get_first_visible_element(driver, xpaths, timeout=10):
    locator = (By.XPATH, " | ".join(xpaths))
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(locator))

def click_first_clickable(driver, xpaths, timeout=10):
    locator = (By.XPATH, " | ".join(xpaths))
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator)).click()

def classify_redeem_result(page_text):
    if any(keyword in page_text for keyword in ["already claimed, unable to claim again", "already claimed"]):
        return "used"
    if any(keyword in page_text for keyword in ["character info is incorrect", "please confirm and try again"]):
        return "player_error"
    if any(keyword in page_text for keyword in ["success", "congratulations", "başarılı", "redeemed", "claim the rewards"]):
        return "success"
    if any(keyword in page_text for keyword in ["verification code error", "incorrect code", "invalid", "used", "expired"]):
        return "code_error"
    return "unknown"

def auto_redeem(code, players):
    results = []
    driver = setup_driver()
    
    try:
        for player in players:
            pid = player["player_id"]
            state = player.get("state", "").strip()
            nickname = player.get("nickname", pid).strip() or pid

            if not state:
                results.append(f"⚠️ {nickname}: State bilgisi eksik, atlandı.")
                continue

            driver.get(REDEEM_URL)
            time.sleep(3) # Sayfa yüklenmesi

            try:
                id_input = get_first_visible_element(driver, [
                    "//input[@placeholder='Player ID']",
                    "//input[contains(@placeholder, 'Player ID')]",
                    "//input[contains(@placeholder, 'Oyuncu')]"
                ])
                id_input.clear()
                id_input.send_keys(pid)

                state_input = get_first_visible_element(driver, [
                    "//input[@placeholder='State']",
                    "//input[contains(@placeholder, 'State')]",
                    "//input[contains(@placeholder, 'State/Region')]"
                ])
                state_input.clear()
                state_input.send_keys(state)

                code_input = get_first_visible_element(driver, [
                    "//input[@placeholder='Enter Gift Code']",
                    "//input[contains(@placeholder, 'Gift Code')]",
                    "//input[contains(@placeholder, 'Hediye')]"
                ])
                code_input.clear()
                code_input.send_keys(code)

                click_first_clickable(driver, [
                    "//div[contains(@class, 'exchange_btn') and not(contains(@class, 'disabled'))]",
                    "//button[contains(@class, 'exchange_btn') and not(contains(@class, 'disabled'))]",
                    "//div[contains(@class, 'exchange_btn') and contains(., 'Confirm') and not(contains(@class, 'disabled'))]",
                    "//button[contains(., 'Confirm') and not(contains(@class, 'disabled'))]"
                ])

                time.sleep(4)
                page_text = driver.page_source.lower()
                result_type = classify_redeem_result(page_text)

                if result_type == "used":
                    results.append(f"ℹ️ {nickname}: Kod kullanılmış.")
                elif result_type == "player_error":
                    results.append(f"❌ {nickname}: ID veya eyalet bilgisi hatalı.")
                elif result_type == "success":
                    results.append(f"✅ {nickname}: Başarılı!")
                elif result_type == "code_error":
                    results.append(f"⚠️ {nickname}: Kod geçersiz/süresi dolmuş olabilir.")
                else:
                    results.append(f"⚠️ {nickname}: Gönderildi, ancak sonuç net okunamadı.")

            except Exception as e:
                results.append(f"❌ {nickname}: Form doldurma/gönderme başarısız. {e}")

    finally:
        driver.quit()
            
    return results

# ----- ANA İSKELET -----
def main():
    print("Whiteout Survival Otomatik Bot Başladı...")
    players = load_players()
    if not players:
        print("Oyuncu listesi boş! Lütfen players.json dosyasını kontrol edin.")
        return
    if any(not player.get("state", "").strip() for player in players):
        print("Bazı kayıtlar için State bilgisi eksik. players.json içine state ekleyin.")
        
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
            redeem_results = auto_redeem(code, players)
            
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
