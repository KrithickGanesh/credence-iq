"""Record the CredenceIQ demo walkthrough with Playwright.

The recording is intentionally scripted: the seeded book is deterministic, so
the same applicant, levers, and outcome reproduce on every run. Captions are
injected into the page rather than added in post so the video and the live UI
stay in sync.

Usage:
    python scripts/record_demo.py
    python scripts/record_demo.py --base-url http://127.0.0.1:3000
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "docs" / "demo" / "raw"

OVERLAY_JS = r"""
() => {
  if (document.getElementById('ciq-cursor')) return;
  const style = document.createElement('style');
  style.textContent = `
    #ciq-cursor {
      position: fixed; left: 0; top: 0; width: 15px; height: 15px; border-radius: 50%;
      background: rgba(255,255,255,0.96); border: 2px solid #0f172a;
      box-shadow: 0 2px 10px rgba(0,0,0,0.32), 0 0 0 4px rgba(255,255,255,0.22);
      transform: translate(-50%, -50%); z-index: 2147483647; pointer-events: none;
      transition: transform 80ms linear;
    }
    #ciq-cursor::after {
      content: ''; position: absolute; inset: -6px; border-radius: 50%;
      border: 2px solid rgba(20,134,106,0.75); opacity: 0; transform: scale(0.5);
      transition: 120ms ease-out;
    }
    #ciq-cursor.clicking::after { opacity: 1; transform: scale(1.45); }
    #ciq-caption {
      position: fixed; left: 24px; bottom: 22px; display: flex; align-items: center; gap: 10px;
      padding: 9px 17px 9px 11px; border-radius: 999px;
      background: rgba(15,23,42,0.93); color: #f8fafc;
      font: 500 13.5px/1.35 Inter, "Segoe UI", system-ui, sans-serif;
      box-shadow: 0 12px 30px rgba(0,0,0,0.30);
      z-index: 2147483646; pointer-events: none; max-width: 780px;
    }
    #ciq-caption .step {
      display: inline-flex; align-items: center; justify-content: center; min-width: 25px; height: 25px;
      padding: 0 6px; border-radius: 999px; background: #14866a; color: #fff;
      font: 600 10px "JetBrains Mono", Consolas, monospace; letter-spacing: 0.02em;
    }
    #ciq-caption .dot {
      width: 7px; height: 7px; border-radius: 50%; background: #34d399;
      box-shadow: 0 0 0 4px rgba(52,211,153,0.16); flex: none;
    }
    #ciq-progress {
      position: fixed; left: 0; top: 0; height: 3px; width: 0; background: #14866a;
      z-index: 2147483647; box-shadow: 0 0 12px rgba(20,134,106,0.6);
      transition: width 280ms ease;
    }
  `;
  document.head.appendChild(style);

  const cursor = document.createElement('div');
  cursor.id = 'ciq-cursor';
  document.body.appendChild(cursor);

  const caption = document.createElement('div');
  caption.id = 'ciq-caption';
  caption.innerHTML = '<span class="dot"></span><span class="step">01</span><span class="text"></span>';
  document.body.appendChild(caption);

  const progress = document.createElement('div');
  progress.id = 'ciq-progress';
  document.body.appendChild(progress);

  const place = (x, y) => {
    cursor.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
  };
  document.addEventListener('mousemove', (event) => place(event.clientX, event.clientY));
  document.addEventListener('mousedown', () => cursor.classList.add('clicking'));
  document.addEventListener('mouseup', () => cursor.classList.remove('clicking'));

  window.__ciqMove = place;
  window.__ciqCaption = (text, step, pct) => {
    caption.querySelector('.text').textContent = text;
    caption.querySelector('.step').textContent = String(step).padStart(2, '0');
    progress.style.width = `${pct}%`;
  };
}
"""


def warm_up(base_url: str) -> None:
    payload = json.dumps(
        {
            "revolving_paydown": 23000,
            "income_increase_annual": 250000,
            "resolve_exposure_mismatch": True,
            "additional_hard_inquiries": 0,
        }
    ).encode()
    requests = [
        ("GET", "/api/overview", None),
        ("GET", "/api/scoring/udf", None),
        ("GET", "/api/applicant/129798/reconciliation", None),
        ("POST", "/api/applicant/129798/simulate", payload),
        ("POST", "/api/applicant/129798/adverse-action", json.dumps({"tone": "formal"}).encode()),
        ("POST", "/api/applicant/129798/simulate", payload),
    ]
    for method, path, body in requests:
        request = urllib.request.Request(
            base_url + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=90) as response:
            response.read()
        print(f"warm {method:4} {path:48} {1000 * (time.perf_counter() - started):7.0f} ms")


def install_overlay(page: Page) -> None:
    page.evaluate(OVERLAY_JS)
    page.evaluate("window.__ciqMove(760, 380)")


def caption(page: Page, text: str, step: int, progress: int) -> None:
    page.evaluate(
        "([text, step, progress]) => window.__ciqCaption(text, step, progress)",
        [text, step, progress],
    )


def smooth_move(page: Page, x: float, y: float, steps: int = 16) -> None:
    page.mouse.move(x, y, steps=steps)
    page.wait_for_timeout(180)


def click_box(page: Page, locator, ratio: float = 0.5) -> None:
    box = locator.bounding_box()
    if box is None:
        raise RuntimeError("element has no bounding box")
    x = box["x"] + box["width"] * ratio
    y = box["y"] + box["height"] / 2
    smooth_move(page, x, y)
    page.mouse.click(x, y)
    page.wait_for_timeout(450)


def scroll_page(page: Page, top: int, wait: int = 800) -> None:
    page.evaluate(f"window.scrollTo({{ top: {top}, behavior: 'smooth' }})")
    page.wait_for_timeout(wait)


def scroll_drawer(page: Page, top: int, wait: int = 800) -> None:
    page.evaluate(
        f"""() => {{
            const pane = document.querySelector('.fixed .overflow-y-auto');
            if (pane) pane.scrollTo({{ top: {top}, behavior: 'smooth' }});
        }}"""
    )
    page.wait_for_timeout(wait)


def scroll_control_into_view(page: Page, locator, wait: int = 850) -> None:
    locator.evaluate("(el) => el.scrollIntoView({ behavior: 'smooth', block: 'center' })")
    page.wait_for_timeout(wait)


def record(base_url: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for old in RAW_DIR.glob("*.webm"):
        old.unlink()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1440, "height": 810},
            device_scale_factor=1,
            record_video_dir=str(RAW_DIR),
            record_video_size={"width": 1440, "height": 810},
        )
        page = context.new_page()
        page.set_default_timeout(90_000)
        video = page.video
        started = time.perf_counter()

        # Overview
        page.goto(base_url + "/", wait_until="networkidle", timeout=90_000)
        page.get_by_text("Reported exposure overstates the book", exact=False).wait_for()
        page.wait_for_timeout(2_200)
        install_overlay(page)
        first_caption = time.perf_counter()
        caption(page, "Portfolio overview · 30,000 seeded customers", 1, 6)
        page.wait_for_timeout(3_000)

        scroll_page(page, 330, 900)
        caption(page, "30,000 applicants scored inside Exasol by a Python SET UDF", 2, 14)
        page.wait_for_timeout(3_000)

        scroll_page(page, 690, 900)
        caption(page, "Exposure, decision mix, and denial drivers", 3, 22)
        page.wait_for_timeout(3_000)
        scroll_page(page, 0, 700)

        # Audit
        page.goto(base_url + "/audit?customer=129798", wait_until="networkidle", timeout=90_000)
        page.locator(".fixed").get_by_text("Applicant 360", exact=True).wait_for()
        page.locator(".fixed").get_by_text("Manthan Aurora", exact=False).first.wait_for()
        page.wait_for_timeout(1_200)
        install_overlay(page)
        caption(page, "Applicant 360 · every figure traces to a facility", 4, 31)
        page.wait_for_timeout(3_000)

        scroll_drawer(page, 470, 900)
        caption(page, "Facility audit · ₹11,558 double-counted across ledgers", 5, 39)
        page.wait_for_timeout(3_000)

        scroll_drawer(page, 780, 900)
        caption(page, "Factor evidence, bureau context, and appeal route", 6, 46)
        page.wait_for_timeout(3_000)
        scroll_drawer(page, 0, 600)

        # Studio
        page.goto(base_url + "/studio?customer=129798", wait_until="networkidle", timeout=90_000)
        page.get_by_text("Credit Decision Notice", exact=False).wait_for()
        page.wait_for_timeout(1_200)
        install_overlay(page)
        caption(page, "Current decision: declined · the notice drafts itself", 7, 55)
        page.wait_for_timeout(3_200)

        scroll_page(page, 380, 900)
        caption(page, "Principal reasons, observed values, and the grievance route", 8, 63)
        page.wait_for_timeout(3_000)

        scroll_page(page, 250, 900)
        caption(page, "Now test the path back to approval", 9, 70)
        page.wait_for_timeout(1_200)

        paydown = page.locator('input[aria-label="Revolving paydown"]')
        click_box(page, paydown, 0.985)
        paydown.focus()
        paydown.press("End")
        page.wait_for_timeout(1_700)
        caption(page, "Full ₹22,732 card payoff clears the revolving balance", 10, 76)
        page.wait_for_timeout(1_900)

        income = page.locator('input[aria-label="Additional verified income"]')
        scroll_control_into_view(page, income)
        click_box(page, income, 0.10)
        if income.input_value() != "250000":
            income.focus()
            income.press("Home")
            for _ in range(5):
                income.press("ArrowRight")
                page.wait_for_timeout(80)
        page.wait_for_timeout(1_600)
        caption(page, "Plus ₹2,50,000 of verified annual income", 11, 83)
        page.wait_for_timeout(1_800)

        toggle = page.locator("button[aria-pressed]")
        scroll_control_into_view(page, toggle)
        click_box(page, toggle, 0.5)
        page.wait_for_timeout(1_800)
        caption(page, "Resolve the ₹11,558 cross-ledger mismatch", 12, 89)
        page.wait_for_timeout(1_700)

        scroll_page(page, 240, 1_000)
        caption(page, "Projected 778.9 · approved", 13, 96)
        page.wait_for_timeout(3_600)

        elapsed = time.perf_counter() - started
        trim = max(0.0, first_caption - started - 1.0)
        context.close()
        browser.close()

    webm = max(RAW_DIR.glob("*.webm"), key=lambda path: path.stat().st_mtime)
    target = RAW_DIR / "credenceiq-demo.webm"
    if webm != target:
        if target.exists():
            target.unlink()
        webm.rename(target)

    meta = {
        "trim_seconds": round(trim, 3),
        "recording_seconds": round(elapsed, 3),
        "first_caption_seconds": round(first_caption - started, 3),
        "base_url": base_url,
    }
    (RAW_DIR / "recording.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    print(f"wrote {target}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:3000")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    warm_up(args.api_url)
    record(args.base_url)


if __name__ == "__main__":
    main()
