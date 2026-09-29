"""Demo-Video der App automatisch aufnehmen: ca. 45 Sekunden, stumm, 1920 × 1080, 30 fps – Drehbuch in record().

Ein ferngesteuerter Browser (Playwright mit dem installierten Microsoft Edge) klickt sich durch die App wie ein
Mensch: sichtbarer Mauszeiger mit Klick-Hervorhebung, ruhige Bewegungen, weiches Scrollen, Pausen zum Mitlesen.
Einblendungen und Mauszeiger werden in die Seite eingefügt – die App selbst bleibt unverändert.

Aufgenommen wird Bild für Bild über das Chrome-DevTools-Protokoll (Screencast in voller Auflösung). Chrome liefert
nur dann ein Bild, wenn sich etwas ändert – ffmpeg macht daraus ein MP4 mit gleichmäßigen 30 fps, dazu ein
Vorschaubild, ein kurzes GIF (Chat → Auftrag) fürs README und ein Prüfbild je Szene.

Aufruf:  python -m tools.record_demo                                  # Live-App mit Live-KI, ca. 1 US-Cent
         python -m tools.record_demo --demo                           # Live-App im Demo-Modus, kostenlos
         python -m tools.record_demo --url http://localhost:8502 --demo  # lokaler Probelauf, kostenlos
Nach 14 Uhr zeigt das Dialekt-Beispiel („bis morgn“) den Bestellschluss: Lieferung übermorgen, mit Hinweis.
"""

import argparse
import base64
import shutil
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import Frame, Locator, Page, sync_playwright

LIVE_URL = "https://braeu-am-stein-ki.streamlit.app"
VIEWPORT = {"width": 1536, "height": 864}  # CSS-Pixel – mit Browser-Zoom 125 % ergibt das 1920 × 1080 Bildpunkte
ZOOM = 1.25
SIZE = (1920, 1080)
FPS = 30
MAX_MB = 8            # Zielgröße des MP4
HEADER = 80           # so viele CSS-Pixel oben verdeckt die feste Kopfleiste der App

# Streamlit Cloud: Die App steckt in einem iframe (Pfad /~/+/), die äußere Seite zeigt nur Plaketten –
# die gehören nicht ins Video
SHELL_JS = """
() => document.head.insertAdjacentHTML("beforeend", `<style>
  [class*="_viewerBadge"], [class*="_profileContainer"], iframe[src*="statuspage"] { display: none !important; }
</style>`)
"""

# Einblendungen, Mauszeiger und Klick-Ring – wird nach dem Laden in den Rahmen der App eingesetzt.
# Streamlit wechselt die Seiten ohne Neuladen, deshalb bleibt es die ganze Aufnahme über erhalten.
OVERLAY_JS = """
() => {
  const appStyle = `
    #demo-caption { position: fixed; left: 50%; bottom: 30px; z-index: 2147483646; max-width: 1000px;
      transform: translateX(-50%); padding: 12px 28px; border-radius: 14px; background: rgba(18, 24, 33, .78);
      color: #fff; font: 600 24px/1.35 "Segoe UI", system-ui, sans-serif; text-align: center;
      pointer-events: none; opacity: 0; transition: opacity .3s ease; }
    #demo-caption.visible { opacity: 1; }
    #demo-cursor { position: fixed; left: -3px; top: -2px; z-index: 2147483647; width: 24px; height: 24px;
      pointer-events: none; transform: translate(-100px, -100px); }
    .demo-ripple { position: fixed; z-index: 2147483646; width: 40px; height: 40px; margin: -20px 0 0 -20px;
      border-radius: 50%; background: rgba(0, 112, 242, .18); border: 3px solid #0070f2; pointer-events: none;
      animation: demo-ripple .55s ease-out forwards; }
    @keyframes demo-ripple { from { transform: scale(.3); opacity: 1; } to { transform: scale(1.25); opacity: 0; } }
    /* Entwickler- und Cloud-Knöpfe (Deploy, Fork, GitHub, Menü) gehören nicht ins Video */
    [data-testid="stAppDeployButton"], [data-testid="stStatusWidget"], [data-testid="stMainMenu"],
    [data-testid="stToolbarActions"] { visibility: hidden !important; }`;
  const cursorSvg = "data:image/svg+xml," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M4 2v18l5-5 3.5 7 3-1.5-3.5-7H19z" ' +
    'fill="#111" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>');

  document.head.insertAdjacentHTML("beforeend", `<style>${appStyle}</style>`);
  document.body.insertAdjacentHTML("beforeend",
    `<div id="demo-caption"></div><img id="demo-cursor" src="${cursorSvg}" alt="">`);
  const caption = document.getElementById("demo-caption");
  const cursor = document.getElementById("demo-cursor");
  window.demo = {
    caption(text) {  // neuer Text: kurz ausblenden, tauschen, wieder einblenden
      const show = () => { caption.textContent = text; caption.classList.add("visible"); };
      if (!text) { caption.classList.remove("visible"); return; }
      if (caption.classList.contains("visible")) { caption.classList.remove("visible"); setTimeout(show, 300); }
      else { show(); }
    },
  };
  document.addEventListener("mousemove", (event) => {
    cursor.style.transform = `translate(${event.clientX}px, ${event.clientY}px)`;
  }, true);
  document.addEventListener("mousedown", (event) => {
    const ripple = document.createElement("div");
    ripple.className = "demo-ripple";
    ripple.style.left = `${event.clientX}px`;
    ripple.style.top = `${event.clientY}px`;
    document.body.append(ripple);
    setTimeout(() => ripple.remove(), 650);
  }, true);
}
"""

# Weiches Scrollen im Inhaltsbereich der App (dort scrollt Streamlit, nicht das Fenster)
SCROLL_JS = """
([y, ms]) => new Promise(resolve => {
  const main = document.querySelector('[data-testid="stMain"]');
  const start = main.scrollTop, target = Math.max(0, Math.min(y, main.scrollHeight - main.clientHeight));
  const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const t0 = performance.now();
  const step = now => {
    const t = Math.min(1, (now - t0) / ms);
    main.scrollTop = start + (target - start) * ease(t);
    t < 1 ? requestAnimationFrame(step) : resolve();
  };
  requestAnimationFrame(step);
})
"""


# ---------- Aufnahme: Einzelbilder über das Chrome-DevTools-Protokoll ----------

class Screencast:
    """Sammelt die Bilder, die Chrome bei jeder Änderung der Seite schickt – mit Zeitstempel."""

    def __init__(self, page: Page, folder: Path):
        self.folder, self.frames = folder, []
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self.on_frame)

    def start(self) -> None:
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": SIZE[0],
                                               "maxHeight": SIZE[1], "everyNthFrame": 1})

    def on_frame(self, event: dict) -> None:
        path = self.folder / f"{len(self.frames):05d}.jpg"
        path.write_bytes(base64.b64decode(event["data"]))
        self.frames.append((event["metadata"]["timestamp"], path))
        self.cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})  # sonst kommt kein weiteres Bild

    def stop(self) -> float:
        """Beendet die Aufnahme und gibt die Endzeit zurück (Zeitstempel wie bei den Bildern)."""
        end = time.time()
        self.cdp.send("Page.stopScreencast")
        return end


# ---------- Regie: Uhr, Maus, Scrollen, Einblendungen ----------

class Director:
    def __init__(self, page: Page, app: Frame):
        self.page, self.app = page, app
        self.x, self.y = VIEWPORT["width"] / 2, VIEWPORT["height"] * 0.6
        self.start = time.monotonic()
        self.wall_start = time.time()  # dieselbe Uhr wie die Zeitstempel der Bilder – für die Umrechnung der Marken

    def now(self) -> float:
        return time.monotonic() - self.start

    def until(self, second: float) -> None:
        """Warten, bis die Szenen-Uhr diese Sekunde erreicht – ist sie schon vorbei, geht es gleich weiter."""
        remaining = second - self.now()
        if remaining > 0:
            self.page.wait_for_timeout(remaining * 1000)

    def pause(self, seconds: float) -> None:
        self.page.wait_for_timeout(seconds * 1000)

    def caption(self, text: str | None) -> None:
        print(f"{self.now():5.1f} s  {text}")  # Protokoll: wann welche Einblendung kommt
        self.app.evaluate("text => window.demo.caption(text)", text)

    def glide(self, x: float, y: float, seconds: float = 0.8) -> None:
        """Mauszeiger ruhig zum Ziel bewegen – langsam anfahren, langsam abbremsen.
        Die Position richtet sich nach der echten Uhr: So dauert die Bewegung wirklich `seconds`."""
        x0, y0, start = self.x, self.y, time.monotonic()
        while True:
            t = min(1.0, (time.monotonic() - start) / seconds)
            eased = 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
            self.page.mouse.move(x0 + (x - x0) * eased, y0 + (y - y0) * eased)
            if t >= 1.0:
                break
            self.page.wait_for_timeout(12)
        self.x, self.y = x, y

    def click(self, target: Locator, seconds: float = 0.8) -> None:
        """Zum Element gleiten, kurz verweilen, klicken (der Klick-Ring zeigt, wo)."""
        box = target.bounding_box()
        self.glide(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, seconds)
        self.pause(0.25)
        self.page.mouse.down()
        self.pause(0.08)
        self.page.mouse.up()

    def hover(self, target: Locator, seconds: float = 0.8) -> None:
        box = target.bounding_box()
        self.glide(box["x"] + box["width"] * 0.35, box["y"] + box["height"] / 2, seconds)

    def scroll_to(self, target: Locator, offset: int = HEADER + 16, seconds: float = 1.0) -> None:
        """Weich so weit scrollen, dass das Element knapp unter der Kopfleiste steht."""
        y = target.evaluate("(e, off) => document.querySelector('[data-testid=\"stMain\"]').scrollTop"
                            " + e.getBoundingClientRect().top - off", offset)
        self.app.evaluate(SCROLL_JS, [y, int(seconds * 1000)])

    def scroll_bottom_to(self, target: Locator, margin: int = 24, seconds: float = 1.0) -> None:
        """Weich so weit scrollen, dass das Element unten im Bild steht."""
        y = target.evaluate("(e, m) => { const main = document.querySelector('[data-testid=\"stMain\"]');"
                            " return main.scrollTop + e.getBoundingClientRect().bottom - main.clientHeight + m; }",
                            margin)
        self.app.evaluate(SCROLL_JS, [y, int(seconds * 1000)])


def app_frame(page: Page, timeout: float = 120) -> Frame:
    """Der Rahmen mit der Streamlit-App: in der Cloud das iframe unter /~/+/ (erscheint erst nach dem Laden bzw.
    Aufwecken der App), lokal die Seite selbst."""
    if not page.url.split("/")[2].endswith(".streamlit.app"):
        return page.main_frame
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = next((frame for frame in page.frames if "/~/+/" in frame.url), None)
        if frame:
            return frame
        page.wait_for_timeout(500)
    raise SystemExit("Die App ist in Streamlit Cloud nicht geladen – später noch einmal versuchen.")


def use_live_ai(app: Frame, live: bool) -> None:
    """Schalter „Live-KI verwenden“ passend stellen und am Kennzeichen prüfen – kein Aufruf kostet unbemerkt."""
    switch = app.locator('input[aria-label="Live-KI verwenden"]')  # Rolle „switch“, technisch ein Kästchen
    try:  # erscheint nach dem Seitenwechsel etwas später als die Beispiel-Knöpfe; ohne Schlüssel gibt es ihn nicht
        switch.wait_for(state="attached", timeout=15_000)
        switch.set_checked(live, force=True)  # das echte Kästchen ist unsichtbar, Streamlit zeigt einen Schalter
    except Exception:
        pass
    badge = app.locator(".st-key-card-chat .stMarkdownBadge", has_text="Live-KI · " if live else "Demo-Modus")
    try:
        badge.wait_for(timeout=10_000)
    except Exception:
        raise SystemExit("Live-KI nicht verfügbar (Schlüssel oder Kontingent fehlt) – mit --demo aufnehmen."
                         if live else "Demo-Modus ließ sich nicht einschalten – Abbruch, damit nichts kostet.")


# ---------- Das Drehbuch (Sekunde | Bild | Einblendung) ----------

def record(d: Director, live: bool) -> dict[str, float]:
    """Spielt die Szenen ab und gibt Zeitmarken für Vorschaubild, GIF und Prüfbilder zurück."""
    app = d.app
    nav = app.locator('a[data-testid="stTopNavLink"]')
    marks = {}

    # 0–5 s: Startseite mit Kacheln
    d.caption("Bräu am Stein – KI-gestützte Auftragserfassung")
    marks["start"] = d.now() + 1.5
    d.until(1.6)
    tile = app.locator(".st-key-tile-message")
    d.hover(tile, seconds=1.2)
    d.until(3.6)
    d.click(tile, seconds=0.3)

    # 5–10 s: KI-Auftragserfassung, Handy-Chat sichtbar
    example = app.locator(".st-key-example_Dialekt button")
    example.wait_for(timeout=30_000)
    use_live_ai(app, live)
    d.until(5.0)
    d.caption("Bestellungen per WhatsApp – oft im Dialekt")
    marks["chat"] = d.now() + 2.0
    d.pause(0.8)
    d.hover(example, seconds=1.0)
    d.until(8.8)
    d.click(example, seconds=0.35)
    d.pause(0.7)  # der Text landet im Eingabefeld, darüber erscheint eine Erklärzeile – das Layout setzt sich

    # 10–22 s: absenden, die KI liest, rechts entsteht der Auftrag
    d.until(9.8)
    d.caption("KI erkennt Kunde, Artikel, Termin")
    send = app.locator('[data-testid="stChatInputSubmitButton"]')
    d.scroll_bottom_to(send, margin=150, seconds=0.9)  # Senden-Knopf über der Einblendung
    marks["gif_start"] = d.now()
    d.click(send, seconds=0.7)
    order_card = app.locator(".st-key-card-chat-order")
    d.pause(0.4)
    d.scroll_to(order_card, seconds=1.0)  # rechts oben mitverfolgen, wie der Auftrag entsteht
    save = app.locator("button", has_text="Auftrag bestätigen & speichern")
    save.wait_for(timeout=90_000)          # Live-KI: meist 3–5 Sekunden, danach Schritt für Schritt
    try:  # die Positionen-Tabelle zeichnet der Browser etwas später (in der Cloud spürbar)
        order_card.locator('[data-testid="stDataFrame"] canvas').first.wait_for(timeout=10_000)
    except Exception:
        pass
    d.pause(0.3)
    marks["order"] = d.now() + 0.4
    d.until(max(d.now() + 0.5, 18.8))
    d.caption("Regeln prüfen, Mensch bestätigt")
    d.hover(app.locator('[data-testid="stDateInput"]').first, seconds=0.8)
    marks["gif_end"] = d.now() + 0.5
    d.until(max(d.now() + 0.7, 21.2))

    # 22–32 s: bestätigen & speichern, Link zur SAP-Übergabe, Object Page, „Übergabe simulieren“
    d.scroll_bottom_to(save, margin=140, seconds=0.7)
    d.click(save, seconds=0.5)
    d.caption("Kundenauftrag für SAP S/4HANA")
    link = app.locator("a", has_text="So sähe die Übergabe an SAP aus")
    link.wait_for(timeout=30_000)
    d.scroll_to(order_card, seconds=0.7)
    d.click(link, seconds=0.5)
    sap_card = app.locator(".st-key-card-sap")
    sap_card.wait_for(timeout=30_000)
    d.pause(0.2)
    d.scroll_to(sap_card, offset=HEADER + 150, seconds=0.9)  # mit Überschrift und Auftragsauswahl
    marks["sap"] = d.now() + 0.3
    d.pause(0.4)
    d.click(sap_card.get_by_role("button", name="Übergabe simulieren"), seconds=0.6)
    sap_card.get_by_text("Übergabe simuliert").first.wait_for(timeout=20_000)
    d.until(max(d.now() + 1.0, 31.4))

    # 32–38 s: Business Case mit den drei Kennzahlen
    d.click(nav.filter(has_text="Business Case"), seconds=0.5)
    d.caption("Business Case: Zeitersparnis pro Jahr")  # Einblendung wechselt mit dem Klick
    shown = d.now()
    kpis = app.locator(".st-key-bc-kpis")
    kpis.wait_for(timeout=30_000)
    app.locator('[data-testid="stPlotlyChart"] .main-svg').first.wait_for(timeout=30_000)  # Diagramm gezeichnet
    marks["business_case"] = d.now() + 1.2
    d.pause(0.6)
    d.hover(kpis.locator('[data-testid="stMetricValue"]').first, seconds=0.9)
    d.until(max(shown + 4.5, 37.4))  # mindestens 4,5 s zum Lesen, auch wenn die Cloud langsamer lädt

    # 38–45 s: Making-of
    d.click(nav.filter(has_text="Making-of"), seconds=0.5)
    d.caption("Konzipiert von Daniel Grzegorzek")
    shown = d.now()
    app.locator(".st-key-card-making-of-role").wait_for(timeout=30_000)
    marks["making_of"] = d.now() + 2.0
    d.pause(0.8)
    d.hover(app.locator(".st-key-card-making-of-role [data-testid='stMarkdown']").first, seconds=1.0)
    d.until(max(shown + 5.5, 45.0))
    print(f"{d.now():5.1f} s  Ende")
    return marks


# ---------- Schnitt: Einzelbilder → MP4, Vorschaubild, GIF, Prüfbilder ----------

def ffmpeg(*arguments: str) -> None:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", *arguments], check=True)


def encode(frames: list[tuple[float, Path]], end: float, out_dir: Path) -> Path:
    """Einzelbilder → MP4 (H.264) mit gleichmäßigen 30 fps, ohne Tonspur, unter MAX_MB.
    Für jedes der 30 Bilder pro Sekunde wird das Einzelbild genommen, das zu diesem Zeitpunkt zu sehen war –
    so ist das Video genau so lang wie die Aufnahme."""
    first = frames[0][0]
    count = round((end - first) * FPS)
    mp4 = out_dir / "demo.mp4"
    for crf in (23, 26, 29, 32):  # so gut wie möglich, aber unter MAX_MB
        encoder = subprocess.Popen(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS),
             "-c:v", "mjpeg", "-i", "-",
             # Einzelbilder kommen im Vollbereich (JPEG) – das MP4 bekommt den üblichen Videobereich
             "-vf", f"scale={SIZE[0]}:{SIZE[1]}:flags=lanczos:in_range=pc:out_range=tv,format=yuv420p",
             "-color_range", "tv", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
             "-movflags", "+faststart", "-an", str(mp4)],
            stdin=subprocess.PIPE)
        index, data = 0, frames[0][1].read_bytes()
        for number in range(count):
            moment = first + number / FPS
            if index + 1 < len(frames) and frames[index + 1][0] <= moment:
                while index + 1 < len(frames) and frames[index + 1][0] <= moment:
                    index += 1
                data = frames[index][1].read_bytes()
            encoder.stdin.write(data)
        encoder.stdin.close()
        if encoder.wait() != 0:
            raise SystemExit("ffmpeg konnte das Video nicht erzeugen.")
        if mp4.stat().st_size <= MAX_MB * 1_000_000:
            break
    return mp4


def extras(mp4: Path, marks: dict[str, float], out_dir: Path) -> None:
    """Vorschaubild (1280 px breit), GIF fürs README (800 px, 12 fps) und ein Prüfbild je Szene."""
    ffmpeg("-ss", f"{marks['order']:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=1280:-2",
           "-q:v", "3", str(out_dir / "demo-poster.jpg"))
    start, length = marks["gif_start"], min(10.0, marks["gif_end"] - marks["gif_start"])
    ffmpeg("-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(mp4), "-vf",
           "fps=12,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];"
           "[b][p]paletteuse=dither=bayer:bayer_scale=4", "-loop", "0", str(out_dir / "demo-chat.gif"))
    check = out_dir / "check"
    check.mkdir(exist_ok=True)
    for name in ("start", "chat", "order", "sap", "business_case", "making_of"):
        ffmpeg("-ss", f"{marks[name]:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=960:-2",
               "-q:v", "4", str(check / f"{name}.jpg"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo-Video der App aufnehmen")
    parser.add_argument("--url", default=LIVE_URL, help="Adresse der App (Standard: Live-App)")
    parser.add_argument("--demo", action="store_true", help="Demo-Modus statt Live-KI (kostenlos)")
    parser.add_argument("--out", type=Path, default=Path("data/demo"), help="Zielordner")
    args = parser.parse_args()
    frames_dir = args.out / "frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge")
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=ZOOM, color_scheme="light",
                                      locale="de-DE", timezone_id="Europe/Berlin")
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        app = app_frame(page)
        app.locator(".st-key-launchpad").wait_for(timeout=120_000)  # App ist fertig geladen (auch nach Aufwecken)
        if app != page.main_frame:
            page.evaluate(SHELL_JS)
        app.evaluate(OVERLAY_JS)
        page.wait_for_timeout(2000)
        page.mouse.move(VIEWPORT["width"] / 2, VIEWPORT["height"] * 0.6)

        screencast = Screencast(page, frames_dir)
        screencast.start()
        director = Director(page, app)
        try:
            marks = record(director, live=not args.demo)
        except Exception:
            page.screenshot(path=str(args.out / "fehler.png"))  # zeigt, wo das Drehbuch hängen geblieben ist
            raise
        end = screencast.stop()
        page.wait_for_timeout(500)
        context.close()
        browser.close()

    first = screencast.frames[0][0]  # Zeitstempel des ersten Bildes = Sekunde 0 im Video
    marks = {name: second + director.wall_start - first for name, second in marks.items()}
    mp4 = encode(screencast.frames, end, args.out)
    extras(mp4, marks, args.out)  # Einzelbilder bleiben in frames/ – zum Nachschneiden ohne neue Aufnahme
    print(f"Fertig: {mp4} ({mp4.stat().st_size / 1_000_000:.1f} MB), {len(screencast.frames)} Einzelbilder, "
          f"Dauer ca. {end - first:.1f} s – dazu demo-poster.jpg, demo-chat.gif und Prüfbilder in {args.out / 'check'}")


if __name__ == "__main__":
    main()
