#!/usr/bin/env python3
"""auto-snap: send a black snap to all your Snapchat friends via Snapchat Web.

Commands:
  login   Open a visible browser, log in manually (2FA etc.), save the session.
  run     Headless: open Snapchat Web with the saved session, snap everyone.

Snapchat has no public API, so this drives web.snapchat.com with Playwright.
The camera is replaced by a fake all-black video feed, so every snap is black.
"""
import argparse
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "state" / "session.json"
DEBUG_DIR = HERE / "state" / "debug"
URL = "https://web.snapchat.com/"

# --- Selectors / labels: Snapchat changes its UI often. Tweak here if needed. ---
CAPTURE_BUTTON = '[aria-label*="Take" i], [title*="Take" i], button[class*="capture" i]'
SEND_TO_BUTTON = 'button:has-text("Send To"), button:has-text("Send to")'
SELECT_ALL = 'text=/select all/i'
FRIEND_CHECKBOX = '[role="checkbox"], input[type="checkbox"]'
FINAL_SEND = 'button:has-text("Send"):not(:has-text("Send To")):not(:has-text("Send to"))'


def make_black_video(path: Path, w=640, h=480, frames=30) -> None:
    """Write a tiny all-black YUV4MPEG2 file Chromium can use as a fake webcam."""
    header = f"YUV4MPEG2 W{w} H{h} F30:1 Ip A1:1 C420jpeg\n".encode()
    frame = b"FRAME\n" + bytes([16]) * (w * h) + bytes([128]) * (w * h // 2)
    with open(path, "wb") as f:
        f.write(header)
        for _ in range(frames):
            f.write(frame)


def launch(p, headless: bool, video: Path | None):
    args = ["--no-sandbox"]
    if video:
        args += [
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-video-capture={video}",
        ]
    return p.chromium.launch(headless=headless, args=args)


def cmd_login(_args) -> int:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p, headless=False, video=None)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(URL)
        input("Log in to Snapchat in the opened window (finish any 2FA), "
              "wait until you see the main screen, then press Enter here... ")
        ctx.storage_state(path=str(STATE_FILE))
        browser.close()
    STATE_FILE.chmod(0o600)
    print(f"Session saved to {STATE_FILE}")
    print("On a VPS: run this on your own computer, then scp the file to the same path on the VPS.")
    return 0


def shot(page, name: str) -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(DEBUG_DIR / f"{name}.png"))


def cmd_run(args) -> int:
    if not STATE_FILE.exists():
        print("No saved session. Run `python autosnap.py login` first.", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "black.y4m"
        make_black_video(video)
        with sync_playwright() as p:
            browser = launch(p, headless=not args.headed, video=video)
            ctx = browser.new_context(
                storage_state=str(STATE_FILE),
                permissions=["camera", "microphone"],
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            try:
                page.goto(URL, wait_until="domcontentloaded")
                page.wait_for_timeout(8000)
                if "accounts.snapchat.com" in page.url or "/login" in page.url:
                    print("Session expired. Re-run `login` and copy the new session file.", file=sys.stderr)
                    shot(page, "session_expired")
                    return 3

                page.locator(CAPTURE_BUTTON).first.click(timeout=30000)
                page.wait_for_timeout(1500)
                page.locator(SEND_TO_BUTTON).first.click(timeout=15000)
                page.wait_for_timeout(1500)

                select_all = page.locator(SELECT_ALL)
                if select_all.count():
                    select_all.first.click()
                else:
                    boxes = page.locator(FRIEND_CHECKBOX)
                    for i in range(boxes.count()):
                        boxes.nth(i).click()
                shot(page, "before_send")

                if args.dry_run:
                    print("Dry run: friends selected but nothing sent. See state/debug/before_send.png")
                    return 0

                page.locator(FINAL_SEND).last.click(timeout=15000)
                page.wait_for_timeout(5000)
                shot(page, "after_send")
                print("Snap sent.")
                return 0
            except PWTimeout as e:
                shot(page, "error")
                print(f"UI element not found (Snapchat UI may have changed): {e}\n"
                      f"See {DEBUG_DIR}/error.png and update the selectors at the top of autosnap.py",
                      file=sys.stderr)
                return 1
            finally:
                browser.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="log in manually and save session").set_defaults(fn=cmd_login)
    r = sub.add_parser("run", help="send a black snap to all friends")
    r.add_argument("--dry-run", action="store_true", help="select friends but don't press send")
    r.add_argument("--headed", action="store_true", help="show the browser (needs a display / xvfb)")
    r.set_defaults(fn=cmd_run)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
