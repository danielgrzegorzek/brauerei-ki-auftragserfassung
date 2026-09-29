"""Demo-Video der App automatisch aufnehmen: Dialekt-Bestellung → geprüfter Auftrag → Angriff → Übergabe an SAP.

Ein ferngesteuerter Browser (Playwright mit dem installierten Microsoft Edge) klickt sich durch die laufende App und
nimmt dabei ein Video auf. Untertitel, Titelkarten und ein sichtbarer Mauszeiger werden in die Seite eingeblendet –
die App selbst bleibt unverändert. Am Ende wandelt ffmpeg das Video in MP4 um (läuft in jedem Browser).

Vorher: App starten (z. B. Port 8501) und einmalig `python -m playwright install ffmpeg`.
Aufruf:  python -m tools.record_demo                  # Live-KI, kostet ca. 2 US-Cent (zwei Auswertungen)
         python -m tools.record_demo --demo           # Demo-Modus, kostenlos (vorbereitete KI-Ergebnisse)
Achtung: nach 14 Uhr warnt die App beim Dialekt-Beispiel („bis morgn“) vor dem Bestellschluss.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import Locator, Page, sync_playwright

VIEWPORT = {"width": 1280, "height": 720}  # = Videogröße: Playwright nimmt in Seitengröße auf und vergrößert nicht
TITLE = ("Bräu am Stein", "KI-gestützte Auftragserfassung · ein Portfolio-Projekt von Daniel Grzegorzek")
CLOSING = ("Die KI versteht.\nDer Code entscheidet.\nDer Mensch bestätigt.",
           "Selbst ausprobieren: braeu-am-stein-ki.streamlit.app")

# Untertitel, Titelkarte und Mauszeiger – wird vor jedem Laden der Seite eingefügt (Playwright: add_init_script)
OVERLAY_JS = """
([title, subtitle]) => {
  const style = `
    #demo-card { position: fixed; inset: 0; z-index: 2147483645; display: grid; place-content: center; gap: 16px;
      text-align: center; background: #f5f6f7; color: #1d2d3e; font-family: "Segoe UI", system-ui, sans-serif;
      transition: opacity .6s; pointer-events: none; }
    #demo-card.hidden { opacity: 0; }
    #demo-card .accent { width: 72px; height: 5px; margin: 0 auto 6px; border-radius: 3px; background: #0070f2; }
    #demo-card h1 { margin: 0; font-size: 52px; font-weight: 700; letter-spacing: -0.02em; white-space: pre-line; }
    #demo-card p { margin: 0; font-size: 24px; color: #556b82; }
    #demo-caption { position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%); z-index: 2147483646;
      max-width: 960px; padding: 14px 28px; border-radius: 14px; background: rgba(18, 24, 33, .88); color: #fff;
      font: 600 25px/1.35 "Segoe UI", system-ui, sans-serif; text-align: center; pointer-events: none;
      opacity: 0; transition: opacity .35s; }
    /* Entwickler-Knöpfe von Streamlit (Deploy, Stop, Menü) gehören nicht ins Video */
    [data-testid="stAppDeployButton"], [data-testid="stStatusWidget"], [data-testid="stMainMenu"] {
      visibility: hidden !important; }
    #demo-caption.visible { opacity: 1; }
    #demo-cursor { position: fixed; left: -4px; top: -2px; z-index: 2147483647; width: 26px; height: 26px;
      pointer-events: none; transform: translate(-100px, -100px); }
    .demo-ripple { position: fixed; z-index: 2147483646; width: 44px; height: 44px; margin: -22px 0 0 -22px;
      border-radius: 50%; border: 3px solid #0070f2; pointer-events: none; animation: demo-ripple .5s ease-out forwards; }
    @keyframes demo-ripple { from { transform: scale(.3); opacity: 1; } to { transform: scale(1.2); opacity: 0; } }`;
  const cursorSvg = "data:image/svg+xml," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M4 2v18l5-5 3.5 7 3-1.5-3.5-7H19z" ' +
    'fill="#111" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>');

  document.addEventListener("DOMContentLoaded", () => {
    document.head.insertAdjacentHTML("beforeend", `<style>${style}</style>`);
    document.body.insertAdjacentHTML("beforeend",
      `<div id="demo-card"><div class="accent"></div><h1></h1><p></p></div>` +
      `<div id="demo-caption"></div><img id="demo-cursor" src="${cursorSvg}" alt="">`);
    const card = document.getElementById("demo-card");
    const caption = document.getElementById("demo-caption");
    const cursor = document.getElementById("demo-cursor");
    window.demo = {
      card(heading, text) {
        card.querySelector("h1").textContent = heading;
        card.querySelector("p").textContent = text;
        card.classList.remove("hidden");
        cursor.style.visibility = "hidden";  // auf Titel- und Schlusskarte kein Mauszeiger
      },
      hideCard() {
        card.classList.add("hidden");
        cursor.style.visibility = "visible";
      },
      caption(text) {
        if (text) caption.textContent = text;
        caption.classList.toggle("visible", Boolean(text));
      },
    };
    window.demo.card(title, subtitle);  // Titelkarte von Anfang an – verdeckt das Laden der App
    document.addEventListener("mousemove", (event) => {
      cursor.style.transform = `translate(${event.clientX}px, ${event.clientY}px)`;
    }, true);
    document.addEventListener("mousedown", (event) => {
      const ripple = document.createElement("div");
      ripple.className = "demo-ripple";
      ripple.style.left = `${event.clientX}px`;
      ripple.style.top = `${event.clientY}px`;
      document.body.append(ripple);
      setTimeout(() => ripple.remove(), 600);
    }, true);
  });
}
"""


# ---------- Bausteine für die Aufnahme ----------

def pause(page: Page, seconds: float) -> None:
    page.wait_for_timeout(seconds * 1000)


def caption(page: Page, text: str | None) -> None:
    """Untertitel einblenden – None blendet ihn aus."""
    page.evaluate("text => window.demo.caption(text)", text)


def scroll_to(page: Page, target: Locator, block: str = "center") -> None:
    """Sanft zu einem Element scrollen (wie ein Mensch, nicht springend)."""
    target.evaluate("(element, block) => element.scrollIntoView({behavior: 'smooth', block})", block)
    pause(page, 1.2)


def click(page: Page, target: Locator) -> None:
    """Mauszeiger sichtbar zum Element bewegen und klicken."""
    target.scroll_into_view_if_needed()
    box = target.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y, steps=30)
    pause(page, 0.4)
    page.mouse.click(x, y)


def save_button(page: Page) -> Locator:
    return page.locator("button", has_text="Auftrag bestätigen & speichern")


def send_example(page: Page, key: str) -> None:
    """Beispielvorschlag antippen (Text landet im Eingabefeld), dann absenden."""
    click(page, page.locator(f".st-key-example_{key} button"))
    pause(page, 1.8)
    click(page, page.locator('[data-testid="stChatInputSubmitButton"]'))


def use_live_ai(page: Page, live: bool) -> None:
    """Schalter „Live-KI verwenden“ passend stellen und am Kennzeichen prüfen – kein Aufruf kostet unbemerkt."""
    switch = page.get_by_role("checkbox", name="Live-KI verwenden")
    if switch.count():
        switch.set_checked(live, force=True)  # das echte Kästchen ist unsichtbar, Streamlit zeigt einen Schalter
    badge = page.locator(".st-key-card-chat").get_by_text("Live-KI · " if live else "Demo-Modus").first
    try:
        badge.wait_for(timeout=5_000)
    except Exception:
        raise SystemExit("Live-KI nicht verfügbar (Schlüssel oder Kontingent fehlt) – mit --demo aufnehmen."
                         if live else "Demo-Modus ließ sich nicht einschalten – Abbruch, damit nichts kostet.")


# ---------- Das Drehbuch ----------

def record(page: Page, live: bool) -> float:
    """Spielt die Szenen ab und gibt den Zeitpunkt (time.monotonic) für das Vorschaubild zurück."""
    nav = page.locator('a[data-testid="stTopNavLink"]')  # Navigation oben (ab ca. 1000 px Breite)
    nav.first.wait_for()
    pause(page, 2.5)

    # Unter der Titelkarte: zur Auftragserfassung wechseln und die KI einstellen
    nav.filter(has_text="KI-Auftragserfassung").click()
    page.locator(".st-key-example_Dialekt button").wait_for()
    use_live_ai(page, live)
    page.mouse.move(640, 420)
    page.evaluate("window.demo.hideCard()")
    pause(page, 1.2)

    order_card = page.locator(".st-key-card-chat-order")
    phone = page.locator(".st-key-phone")

    # 1. Dialekt-Bestellung: links die Antwort im Chat, dann rechts der fertige Auftragsvorschlag
    caption(page, "Bestellungen kommen per WhatsApp – als Freitext, oft im Dialekt.")
    send_example(page, "Dialekt")
    caption(page, "Die KI liest mit und macht daraus einen Auftragsvorschlag …")
    save_button(page).wait_for(timeout=90_000)
    scroll_to(page, phone, block="end")
    pause(page, 2.5)
    scroll_to(page, order_card, block="start")
    caption(page, "Rechts entsteht der Auftrag: Kunde, Artikel, Mengen, Liefertermin, Pfand.")
    poster_at = time.monotonic()
    pause(page, 4.5)

    # 2. Prüfung durch Code, Freigabe durch den Menschen
    scroll_to(page, save_button(page), block="end")
    caption(page, "Preise und Regeln prüft normaler Code – nicht die KI.")
    pause(page, 3.5)
    caption(page, "Gespeichert wird erst, wenn ein Mensch bestätigt.")
    pause(page, 1.5)
    click(page, save_button(page))
    page.locator(".chat-bubble", has_text="ist bestätigt").wait_for(timeout=30_000)
    scroll_to(page, phone, block="end")
    caption(page, "Erst dann bestätigt die Brauerei den Auftrag im Chat.")
    pause(page, 4)

    # 3. Angriff per Prompt-Injection: Hinweise oben im Auftrag, dann die gesperrte Prüfung
    caption(page, "Und wenn jemand versucht, die KI auszutricksen?")
    send_example(page, "Angriff--Prompt-Injection-")
    save_button(page).wait_for(timeout=90_000)
    scroll_to(page, phone, block="end")
    pause(page, 2.5)
    scroll_to(page, order_card, block="start")
    caption(page, "Die App erkennt den Angriff – die Anweisungen werden nicht ausgeführt.")
    pause(page, 5)
    scroll_to(page, save_button(page), block="end")
    caption(page, "Und die Prüfung sperrt das Speichern.")
    pause(page, 3.5)

    # 4. Übergabe an SAP S/4HANA (der eben gespeicherte Auftrag ist vorausgewählt)
    caption(page, "Nach der Freigabe geht der Auftrag an SAP S/4HANA.")
    scroll_to(page, page.locator(".st-key-card-chat"), block="start")
    click(page, nav.filter(has_text="Prozess & SAP"))
    sap_card = page.locator(".st-key-card-sap")
    sap_card.wait_for()
    pause(page, 1)
    scroll_to(page, sap_card, block="start")
    caption(page, "Als Kundenauftrag über die Standard-API – Preise und Leergut ermittelt SAP selbst.")
    pause(page, 4)
    click(page, sap_card.get_by_role("tab", name="Nutzdaten (JSON)"))  # der JSON-Code steckt in einem Reiter
    scroll_to(page, sap_card.locator('[data-testid="stCode"]').first)
    caption(page, "Simulation: Der Aufruf wird gezeigt, aber nicht gesendet.")
    pause(page, 2.5)
    click(page, sap_card.get_by_role("button", name="Übergabe simulieren"))
    sap_card.get_by_text("Übergabe simuliert").first.wait_for()
    pause(page, 3)

    # Schlusskarte
    caption(page, None)
    page.evaluate("([heading, text]) => window.demo.card(heading, text)", list(CLOSING))
    pause(page, 4.5)
    return poster_at


def to_mp4(webm: Path, out_dir: Path, trim: float, poster_second: float) -> Path:
    """WebM (Aufnahme) → MP4 (H.264, läuft überall) plus Vorschaubild als JPEG.

    trim: so viele Sekunden am Anfang abschneiden (leere Seite vor dem Laden der App).
    poster_second: Zeitpunkt des Vorschaubilds im fertigen Video.
    """
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    mp4 = out_dir / "demo.mp4"
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-ss", f"{trim:.2f}", "-i", str(webm),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an", str(mp4)], check=True)
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-ss", f"{poster_second:.2f}", "-i", str(mp4),
                    "-frames:v", "1", "-q:v", "3", str(out_dir / "demo-poster.jpg")], check=True)
    return mp4


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo-Video der App aufnehmen")
    parser.add_argument("--url", default="http://localhost:8501", help="Adresse der laufenden App")
    parser.add_argument("--demo", action="store_true", help="Demo-Modus statt Live-KI (kostenlos)")
    parser.add_argument("--out", type=Path, default=Path("data/demo"), help="Zielordner")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge")
        context = browser.new_context(viewport=VIEWPORT, color_scheme="light", locale="de-DE",
                                      timezone_id="Europe/Berlin",
                                      record_video_dir=str(args.out), record_video_size=VIEWPORT)
        context.add_init_script(f"({OVERLAY_JS})({json.dumps(list(TITLE))})")
        page = context.new_page()  # ab hier läuft die Aufnahme
        video_start = time.monotonic()
        page.goto(args.url, wait_until="domcontentloaded")  # ab jetzt ist die Titelkarte zu sehen
        trim = time.monotonic() - video_start + 0.2
        poster_at = record(page, live=not args.demo)
        webm = Path(page.video.path())
        context.close()
        browser.close()

    mp4 = to_mp4(webm, args.out, trim, poster_at - video_start - trim)
    webm.unlink()
    print(f"Fertig: {mp4} ({mp4.stat().st_size / 1_000_000:.1f} MB) und {args.out / 'demo-poster.jpg'}")


if __name__ == "__main__":
    main()
