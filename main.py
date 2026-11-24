import os
import re
import sys
import json
import html
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
# Oyuncu ekleme/silme komutlarını yalnızca bu Telegram kullanıcısı verebilir.
# Tanımlı değilse CHAT_ID kullanılır (bota özelden yazılıyorsa chat id = kullanıcı id).
ADMIN_ID = (os.environ.get('TELEGRAM_ADMIN_ID') or CHAT_ID or "").strip()
ISSUE_RESULT_FILE = "issue_result.md"

URL = "https://wosgiftcodes.com/"
REDEEM_URL = "https://wos-giftcode.centurygame.com/"
STATE_FILE = "seen_codes.json"
PLAYERS_FILE = "players.json"
DEFAULT_STATE = "2642"

# ----- TELEGRAM FONKSİYONLARI -----
def send_telegram_message(message, chat_id=None):
    chat_id = chat_id or CHAT_ID
    if not BOT_TOKEN or not chat_id:
        print("Telegram API bilgileri eksik, mesaj gönderilmedi.")
        return False

    send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": chat_id,
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

def save_players(players):
    data = [
        {"nickname": p["nickname"], "player_id": p["player_id"], "state": p["state"]}
        for p in players
    ]
    with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")

def upsert_player(players, pid, state, nickname=""):
    """Oyuncu ekler; ID zaten varsa state/nickname günceller.
    Dönüş: (mesaj, yeni_oyuncu_dict | None, değişti_mi)"""
    pid = str(pid).strip()
    state = str(state).strip()
    nickname = str(nickname or "").strip() or pid

    if not pid.isdigit():
        return f"❌ Geçersiz Player ID: {html.escape(pid)} (sadece rakam olmalı)", None, False
    if not state.isdigit():
        return f"❌ Geçersiz State: {html.escape(state)} (sadece rakam olmalı)", None, False

    for p in players:
        if p["player_id"] == pid:
            if p["state"] == state and p["nickname"] == nickname:
                return f"ℹ️ {html.escape(nickname)} ({pid}) zaten listede, değişiklik yok.", None, False
            p["state"] = state
            p["nickname"] = nickname
            return f"✏️ {html.escape(nickname)} ({pid}) güncellendi. State: {state}", None, True

    new_player = {"nickname": nickname, "player_id": pid, "state": state}
    players.append(new_player)
    return f"✅ {html.escape(nickname)} ({pid}, state {state}) eklendi.", new_player, True

def remove_player(players, pid):
    """Dönüş: (mesaj, değişti_mi)"""
    pid = str(pid).strip()
    for i, p in enumerate(players):
        if p["player_id"] == pid:
            players.pop(i)
            return f"🗑️ {html.escape(p['nickname'])} ({pid}) silindi.", True
    return f"❌ {html.escape(pid)} ID'li oyuncu listede yok.", False

def format_player_list(players):
    lines = [f"👥 <b>Oyuncular ({len(players)}):</b>"]
    for p in players:
        lines.append(f"• {html.escape(p['nickname'])} — <code>{p['player_id']}</code> (state {p['state']})")
    return "\n".join(lines)

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
            nickname = html.escape(player.get("nickname", pid).strip() or pid)  # mesajlar parse_mode=HTML

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

def redeem_active_codes_for(player, skip_codes=()):
    """Sitede listelenen (aktif) kodları yalnızca verilen oyuncu için dener.
    seen_codes.json'a dokunmaz. Telegram'a rapor gönderir, rapor metnini döndürür."""
    nickname = html.escape(player["nickname"])
    codes = [c for c in scrape_codes() if c not in skip_codes]
    if not codes:
        report = f"🆕 <b>{nickname}</b> için denenecek aktif kod yok."
        send_telegram_message(report)
        return report

    lines = []
    for code in codes:
        result = auto_redeem(code, [player])
        lines.append(f"<code>{html.escape(code)}</code>: " + " ".join(result))
    report = f"🆕 <b>{nickname} için aktif kodlar ({len(codes)}):</b>\n\n" + "\n".join(lines)
    send_telegram_message(report)
    return report

# ----- TELEGRAM KOMUTLARI -----
HELP_TEXT = (
    "🤖 <b>Komutlar</b>\n"
    "/ekle &lt;player_id&gt; &lt;state&gt; [nick] — oyuncu ekle/güncelle\n"
    "/sil &lt;player_id&gt; — oyuncu sil\n"
    "/liste — oyuncuları listele\n\n"
    "Komutlar bir sonraki saatlik çalışmada işlenir."
)

def telegram_api(method, **params):
    try:
        res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", params=params, timeout=30)
        data = res.json()
        if not data.get("ok"):
            print(f"Telegram {method} hatası: {data.get('description')}")
            return None
        return data.get("result")
    except Exception as e:
        print(f"Telegram {method} hatası: {e}")
        return None

def handle_command(text, players):
    """Tek bir komutu işler. Dönüş: (cevap, yeni_oyuncu | None, değişti_mi)"""
    parts = text.split()
    cmd = parts[0][1:].split("@")[0].lower()
    args = parts[1:]

    if cmd == "ekle":
        if len(args) < 2:
            return "❌ Kullanım: /ekle &lt;player_id&gt; &lt;state&gt; [nick]", None, False
        return upsert_player(players, args[0], args[1], " ".join(args[2:]))
    if cmd == "sil":
        if len(args) != 1:
            return "❌ Kullanım: /sil &lt;player_id&gt;", None, False
        msg, changed = remove_player(players, args[0])
        return msg, None, changed
    if cmd == "liste":
        return format_player_list(players), None, False
    if cmd in ("yardim", "yardım", "help", "start"):
        return HELP_TEXT, None, False
    return None, None, False  # Bilinmeyen komut: sessizce yok say

def process_telegram_commands():
    """Bota gelen komutları okur, players.json'u günceller, cevap verir.
    Dönüş: bu çalışmada yeni eklenen oyuncular."""
    if not BOT_TOKEN or not ADMIN_ID:
        return []

    updates = telegram_api("getUpdates", timeout=0, allowed_updates='["message"]')
    if not updates:
        return []

    players = load_players()
    new_players = []
    changed_any = False

    for update in updates:
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        sender_id = str((message.get("from") or {}).get("id", ""))
        chat_id = (message.get("chat") or {}).get("id")

        if not text.startswith("/") or sender_id != ADMIN_ID:
            continue

        reply, new_player, changed = handle_command(text, players)
        if changed:
            changed_any = True
        if new_player:
            new_players.append(new_player)
        if reply:
            send_telegram_message(reply, chat_id=chat_id)

    if changed_any:
        save_players(players)

    # İşlenen mesajları Telegram'a onayla; bir daha gelmezler.
    telegram_api("getUpdates", offset=updates[-1]["update_id"] + 1, timeout=0)

    # Eklenip aynı çalışmada silinenleri çıkar
    current_ids = {p["player_id"] for p in players}
    return [p for p in new_players if p["player_id"] in current_ids]

# ----- GITHUB ISSUE FORMU -----
def parse_issue_form(body):
    """GitHub issue formunun markdown gövdesini {başlık: değer} sözlüğüne çevirir."""
    fields = {}
    for section in re.split(r"^###\s+", body or "", flags=re.MULTILINE)[1:]:
        label, _, value = section.partition("\n")
        value = value.strip()
        if value == "_No response_":
            value = ""
        # "İ".lower() -> "i" + U+0307 (birleşik nokta); onu at ki "İşlem" -> "işlem" olsun
        fields[label.strip().lower().replace("̇", "")] = value
    return fields

def handle_issue():
    """'Oyuncu ekle/sil' issue'sunu işler; sonucu issue_result.md'ye yazar."""
    fields = parse_issue_form(os.environ.get("ISSUE_BODY", ""))
    action = fields.get("işlem", "").lower()
    pid = fields.get("player id", "")
    state = fields.get("state", "")
    nickname = fields.get("nickname", "")

    players = load_players()
    new_player = None
    changed = False

    if action.startswith("ekle"):
        if not state:
            msg = "❌ Ekleme için State zorunlu."
        else:
            msg, new_player, changed = upsert_player(players, pid, state, nickname)
    elif action.startswith("sil"):
        msg, changed = remove_player(players, pid)
    else:
        msg = f"❌ Bilinmeyen işlem: {html.escape(action) or '(boş)'}"

    ok = not msg.startswith("❌")
    if changed:
        save_players(players)

    send_telegram_message(f"📝 <b>GitHub issue:</b> {msg}")
    report = ""
    if new_player:
        report = redeem_active_codes_for(new_player)

    # Telegram HTML'ini GitHub yorumu için düz metne çevir
    def to_markdown(text):
        text = re.sub(r"</?b>", "**", text)
        text = re.sub(r"</?code>", "`", text)
        return html.unescape(text)

    body = to_markdown(msg)
    if report:
        body += "\n\n" + to_markdown(report)
    with open(ISSUE_RESULT_FILE, "w", encoding="utf-8") as f:
        f.write(body + "\n")

    print(body)
    if not ok:
        sys.exit(1)

# ----- ANA İSKELET -----
def main():
    print("Whiteout Survival Otomatik Bot Başladı...")
    added_players = process_telegram_commands()
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

    # Telegram'dan yeni eklenen oyunculara aktif kodları dene
    # (bu çalışmada yeni bulunan kodlar onlar için zaten kullanıldı)
    for player in added_players:
        redeem_active_codes_for(player, skip_codes=new_codes)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "issue":
        handle_issue()
    else:
        main()
