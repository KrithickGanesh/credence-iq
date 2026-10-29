"""Render the title and end cards used by the demo video."""

from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "demo" / "cards.html"
OUT = ROOT / "docs" / "demo"


def main() -> None:
    url = "file:///" + quote(HTML.as_posix())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 810}, device_scale_factor=1)
        page.goto(url, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(500)
        for element_id, filename in (("title", "title.png"), ("end", "end.png")):
            page.locator(f"#{element_id}").screenshot(path=str(OUT / filename))
            print(f"wrote {OUT / filename}")
        browser.close()


if __name__ == "__main__":
    main()
