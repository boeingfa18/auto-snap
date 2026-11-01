# auto-snap 👻

Sends a black snap to all your Snapchat friends once a day to keep streaks alive. Runs headless on an Ubuntu VPS.

Snapchat has no public API, so this drives **Snapchat Web** (web.snapchat.com) with Playwright/Chromium. A fake all-black webcam feed is used, so every snap is a black photo.

> ⚠️ **Read first**
> - Automating Snapchat likely violates its Terms of Service. Your account could be locked or banned. Use at your own risk.
> - Snapchat Web's UI changes and varies by region/account. The selectors at the top of `autosnap.py` are best-effort and **may need adjusting**. Use `--dry-run` and the screenshots in `state/debug/` to tune them.
> - Snapchat Web must have camera/snap support enabled for your account.

## Setup (Ubuntu)

```bash
sudo apt update && sudo apt install -y python3 python3-venv git
git clone https://github.com/boeingfa18/auto-snap /opt/auto-snap
cd /opt/auto-snap
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/playwright install --with-deps chromium
```

## Log in (once)

Snapchat needs an interactive login (captcha/2FA), so do it on a computer with a screen:

```bash
python autosnap.py login          # log in in the window, press Enter
scp state/session.json you@your-vps:/opt/auto-snap/state/session.json
```

(On the VPS, `mkdir -p /opt/auto-snap/state` first.) Keep `session.json` private — it grants access to your account. Re-do this if the session expires (the script tells you).

## Test

```bash
venv/bin/python autosnap.py run --dry-run   # selects friends, doesn't send
venv/bin/python autosnap.py run             # really sends
```

On failure, check `state/debug/*.png`.

## Schedule daily (systemd)

```bash
sudo cp systemd/auto-snap.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now auto-snap.timer
systemctl list-timers auto-snap.timer
```

Runs daily around 12:00 (±30 min random delay). Edit `systemd/auto-snap.timer` to change it. Logs: `journalctl -u auto-snap`.
