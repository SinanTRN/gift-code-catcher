# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An unattended bot for Whiteout Survival that runs on GitHub Actions. On a schedule it:
1. scrapes gift codes from wosgiftcodes.com,
2. skips codes already listed in `seen_codes.json`,
3. redeems each new code for every player in `players.json` on the official redeem page (wos-giftcode.centurygame.com) using headless Selenium Chrome,
4. sends a "new code" message and a per-player result report for each code to Telegram,
5. commits the updated `seen_codes.json` back to the repo.

Comments, logs and Telegram messages are in Turkish. Keep new user-facing strings in Turkish.

## The GitHub Actions loop (`.github/workflows/scraper.yml`)

- Triggers: the **primary** trigger is an external cron-job.org job that POSTs to the GitHub API `workflow_dispatch` endpoint (`/repos/SinanTRN/gift-code-catcher/actions/workflows/scraper.yml/dispatches`, body `{"ref":"main"}`) every hour, using a fine-grained PAT that has only Actions read/write on this repo. GitHub's own `schedule` gets delayed by hours or dropped under load, so the `schedule` cron (`37 */3 * * *`, UTC, off-peak minute) is only a fallback. Keep `workflow_dispatch:` in the workflow: removing it, or renaming `scraper.yml`, breaks the external trigger.
- Runner: ubuntu-latest, Python 3.10, `pip install -r requirements.txt`. Chrome comes preinstalled on the runner. `webdriver-manager` fetches a matching ChromeDriver.
- Secrets: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. If either is missing, messages are skipped silently and the run does not fail.
- State write-back: `permissions: contents: write`. After `python main.py`, the job commits **only `seen_codes.json`**, as `github-actions[bot]` with the message "Otomatik Güncelleme: Yeni hediye kodları eklendi", then runs `git pull --rebase origin main` and pushes. No commit is made when nothing changed.
- Run safety: the `concurrency: gift-code-scraper` group (no cancel) makes runs one at a time. Checkout uses `ref: main` rather than the triggering SHA, so a run that waited in the queue still reads the latest `seen_codes.json`. Keep both. Without them, overlapping or queued runs redeem the same code twice.

Implications when changing things:
- The git repo is the bot's database. `seen_codes.json` is the only persisted state across runs. Any new state the bot needs to remember must be a file added to the `git add` step.
- Remote `main` moves on its own, roughly hourly. Pull before pushing local edits.
- `main()` saves `seen_codes.json` only once, after all new codes are processed. If the job crashes partway through, every new code from that run is retried next time.
- Changes to `main.py` take effect on the next scheduled run after they are pushed to `main`. To test a change right away, trigger `workflow_dispatch`.

## Operating it (how the owner uses the data files)

- **Add a player**: append `{"nickname", "player_id", "state"}` to `players.json` by hand. The bot never writes this file.
- **Re-run a code** (for example, so a newly added player gets codes the others already claimed): delete that code from `seen_codes.json` and push. The next run redeems it for *all* players. Players who already claimed it get the "used" result. The bot then appends the code again.
- `seen_codes.json` is a flat JSON list of case-sensitive code strings, written with `indent=4`.
- `load_players()` also accepts bare ID strings and the alias keys `pid`/`id`/`name`. A missing state defaults to `DEFAULT_STATE = "2642"`. Invalid JSON silently gives an empty list, and the bot then exits early ("Oyuncu listesi boş") without failing the job. Check JSON validity after editing.

## Code flow (`main.py`, single file)

`main()` → `load_players()` → `scrape_codes()` (first `<td>` of each table row) → filter out codes already in `seen_codes.json` → for each new code: Telegram start message → `auto_redeem(code, players)` → Telegram summary → append to the seen list → `save_seen_codes()`.

- `auto_redeem()` starts one headless Chrome per code and loops through the players with fixed sleeps of about 7 s per player. Run time grows as codes × players.
- Form fields and the submit button are located through lists of fallback XPaths, joined with `|`, in `get_first_visible_element` / `click_first_clickable`. When the redeem site's markup changes, add fallbacks to those lists. Don't replace them.
- `classify_redeem_result()` matches keywords in the lowercased `page_source`. The checks run in order (`used` → `player_error` → `success` → `code_error`). The order matters because the keywords overlap ("used" appears in the first and the last bucket).

## Running locally (debugging only)

```bash
pip install -r requirements.txt
python main.py   # set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID to also get messages
```

Running locally has real effects. It submits codes for every real player and edits `seen_codes.json`. If that edit gets pushed, it changes what the scheduled bot does. To test the redeem flow without that, call `auto_redeem(code, [one_player])` directly. There are no tests or linter.

## Leftovers

`opencv-python-headless`, `pytesseract`, `Pillow` (requirements.txt) and the workflow's Tesseract apt-install step come from the captcha-OCR solver added in `d0764d5` and later removed. `main.py` no longer uses them. They only make CI slower, so ask before removing them. `__pycache__/` is tracked because there is no `.gitignore`.
