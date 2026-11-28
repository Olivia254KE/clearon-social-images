#!/usr/bin/env python3
"""Clearon Logistics: corporate vertical video from posters or carousel slides.

Usage:
  python3 tools/make_video.py --out posters/videos/NAME.mp4 [--seed N] [--headline "TEXT"] SLIDE1.jpg [SLIDE2.jpg ...]

Slides may be 1080x1350 posters/slides or 1080x1920 Story versions; 4:5 images
are placed on a blurred, darkened 9:16 background automatically.

Prints THUMBNAIL_OFFSET_MS (pass it to Buffer as the video's thumbnailOffset)
and writes <out>_cover.jpg, a cover frame taken from the middle of the first slide.

Structure (about 1.6 s intro + 6 s per slide, adjustable with --slide-seconds, + 5 s end card, adjustable with --end-seconds):
  - Intro: deep navy, logo scales in, teal rule draws across, short tagline.
  - Slides: slow push-in on each slide.
  - Transitions: eased brand wipe (teal panel, then navy panel, angled edges)
    with a whoosh in the soundtrack.
  - End card: "Chat with us on WhatsApp", number, email, website.
  - Transitions: brand wipe, vertical wipe, split panels or push-through zoom
    (--transition; the end card always enters with the brand wipe).
  - Soundtrack: original corporate track generated here, in one of three moods
    (--mood piano, pluck, ambient or maritime: sea swell, distant ship horn, container clanks), with bass, beat, whooshes and a riser. The seed varies key,
    tempo and progression so videos do not all sound the same.

Needs: Pillow, numpy, playwright (chromium or /usr/bin/google-chrome), ffmpeg,
and the npm packages @fontsource/anton and @fontsource/poppins installed in
./node_modules or in the directory given by --node-modules.
"""
import argparse, base64, os, random, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

W, H, FPS = 1080, 1920, 30
NAVY, DEEP, TEAL, BLUE = (0, 34, 68), (0, 26, 53), (0, 185, 171), (48, 121, 255)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INTRO, SLIDE, TRANS, END = 1.6, 6.0, 0.8, 5.0
MOTION = 'still'


# ---------- helpers ----------
def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def b64(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode()


def find_node_modules(hint):
    for d in [hint, os.path.join(os.getcwd(), 'node_modules'), os.path.join(REPO, 'node_modules'),
              '/home/claude/posters/node_modules']:
        if d and os.path.isdir(os.path.join(d, '@fontsource', 'anton')):
            return d
    sys.exit('Fonts not found: run `npm install @fontsource/anton @fontsource/poppins` first.')


BACKDROP = None   # optional real photo (path) used behind 4:5 posters and on the intro/end cards


def brand_frame():
    """Clean 9:16 brand frame: deep navy vertical gradient, or a darkened real photo if --backdrop is set.
    (Replaces the old blurred copy of the poster, which looked smeared and artificial.)"""
    if BACKDROP:
        ph = Image.open(BACKDROP).convert('RGB')
        s = max(W / ph.width, H / ph.height)
        ph = ph.resize((round(ph.width * s), round(ph.height * s)), Image.LANCZOS)
        l, t = (ph.width - W) // 2, (ph.height - H) // 2
        ph = ph.crop((l, t, l + W, t + H))
        ph = ImageEnhance.Brightness(ph).enhance(0.45)
        return Image.blend(ph, Image.new('RGB', (W, H), DEEP), 0.40)
    g = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array(NAVY, float), np.array(DEEP, float)
    arr = (top * (1 - g) + bot * g) * np.ones((1, W, 1))
    return Image.fromarray(arr.astype(np.uint8))


def to_vertical(path):
    im = Image.open(path).convert('RGB')
    if im.size == (W, H):
        return im
    if abs(im.width / im.height - 9 / 16) < 0.02:
        return im.resize((W, H), Image.LANCZOS)
    bg = brand_frame()
    # the poster is placed 1:1 (no resampling when it is 1080 wide) so text stays pixel-sharp
    fg = im if im.width == W else im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
    y = (H - fg.height) // 2
    bg.paste(fg, (0, y))
    d = ImageDraw.Draw(bg)
    d.rectangle((0, y - 4, W, y - 1), fill=TEAL)                    # thin teal rules frame the poster
    d.rectangle((0, y + fg.height, W, y + fg.height + 3), fill=TEAL)
    return bg


def render_cards(nm, headline):
    """Render intro background and end card with headless Chrome (brand fonts)."""
    from playwright.sync_api import sync_playwright
    f = lambda pkg, file: f"data:font/woff2;base64,{b64(os.path.join(nm, '@fontsource', pkg, 'files', file))}"
    logo = 'data:image/png;base64,' + b64(os.path.join(REPO, 'brand', 'logo_white.png'))
    css = f"""
    @font-face{{font-family:Anton;src:url({f('anton','anton-latin-400-normal.woff2')})}}
    @font-face{{font-family:Poppins;font-weight:500;src:url({f('poppins','poppins-latin-500-normal.woff2')})}}
    @font-face{{font-family:Poppins;font-weight:700;src:url({f('poppins','poppins-latin-700-normal.woff2')})}}
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{width:{W}px;height:{H}px;overflow:hidden;font-family:Poppins;color:#fff;
      background:radial-gradient(120% 80% at 50% 35%,#003366 0%,#002244 45%,#001a35 100%)}}
    .grid{{display:none}}
    .c{{position:absolute;left:0;right:0;text-align:center}}
    """
    intro_html = f"""<html><head><style>{css}</style></head><body><div class=grid></div>
      <div class=c style="top:1180px;font-weight:500;font-size:34px;letter-spacing:10px;color:#9fe9e2">
      CLEARING &amp; FORWARDING · KENYA</div>
      <div class=c style="top:1250px;font-family:Anton;font-size:64px;letter-spacing:2px">{headline}</div>
      </body></html>"""
    end_html = f"""<html><head><style>{css}</style></head><body><div class=grid></div>
      <img src="{logo}" style="position:absolute;left:390px;top:330px;width:300px">
      <div class=c style="top:820px;font-family:Anton;font-size:92px;line-height:1.05">CHAT WITH US<br><span style="color:#00b9ab">ON WHATSAPP</span></div>
      <div class=c style="top:1110px"><div style="display:inline-block;background:#00b9ab;color:#001a35;
        border-radius:999px;padding:26px 64px;font-weight:700;font-size:64px">+254 115007849</div></div>
      <div class=c style="top:1330px;font-weight:500;font-size:40px">info@clearonlogistics.co.ke</div>
      <div class=c style="top:1400px;font-weight:500;font-size:34px;color:#9fe9e2">clearonlogistics.co.ke</div>
      <div class=c style="top:1640px;font-weight:500;font-size:28px;letter-spacing:8px;opacity:.75">
      MOMBASA PORT · JKIA · CHINA · INDIA</div></body></html>"""
    out = {}
    with sync_playwright() as p:
        exe = '/usr/bin/google-chrome' if os.path.exists('/usr/bin/google-chrome') else None
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pg = b.new_page(viewport={'width': W, 'height': H})
        for k, html in (('intro', intro_html), ('end', end_html)):
            pg.set_content(html); pg.wait_for_timeout(300)
            fn = os.path.join(tempfile.gettempdir(), f'clearon_{k}.png')
            pg.screenshot(path=fn); out[k] = Image.open(fn).convert('RGB')
        b.close()
    return out


# ---------- visuals ----------
def push_in(img, p, amount=0.0, progress=True):
    """Hold the slide pixel-exact. A thin teal progress line runs along the bottom band
    (below 4:5 posters) so the frame still feels alive without resampling the text."""
    f = img.copy()
    if MOTION == 'zoom' and amount:
        s = 1 + amount * p
        w, h = W * s, H * s
        f = img.transform((W, H), Image.AFFINE, (1 / s, 0, (w - W) / 2 / s, 0, 1 / s, (h - H) / 2 / s), Image.BICUBIC)
    if not progress:          # first slide doubles as the video cover: keep it free of player-like UI
        return f
    d = ImageDraw.Draw(f)
    y = 1700
    d.rectangle((90, y, W - 90, y + 3), fill=(0, 60, 95))
    d.rectangle((90, y, 90 + int((W - 180) * ease(p)), y + 3), fill=TEAL)
    return f


def wipe(a, b, p):
    """Brand wipe: teal panel leads, navy panel follows; angled edges; switch at midpoint."""
    base = (a if p < 0.5 else b).copy()
    d = ImageDraw.Draw(base)
    slant, band, blue = 220, 70, 26
    panel = W + slant + 40                  # navy panel just wide enough to cover at the midpoint
    total_w = panel + band + blue
    span = W + slant + total_w              # front edge travels from x=0 (off-screen) to fully past
    lead = ease(p) * span                   # front edge x at the top; screen fully covered at p=0.5
    def para(x1, x2, color):
        d.polygon([(x1, 0), (x2, 0), (x2 - slant, H), (x1 - slant, H)], fill=color)
    para(lead - blue, lead, BLUE)                       # thin blue accent at the very front
    para(lead - blue - band, lead - blue, TEAL)         # teal band
    para(lead - total_w, lead - blue - band, DEEP)      # navy panel behind
    return base


def wipe_up(a, b, p):
    """Vertical brand wipe: blue edge, teal band and navy panel rise from the bottom."""
    base = (a if p < 0.5 else b).copy()
    d = ImageDraw.Draw(base)
    slant, band, blue = 160, 70, 26
    total_h = H + slant + 40 + band + blue
    span = H + slant + total_h
    lead = H - ease(p) * span                # front edge y on the left side, moving up
    def para(y1, y2, color):                 # y1 < y2, top edge y1
        d.polygon([(0, y1), (W, y1 - slant), (W, y2 - slant), (0, y2)], fill=color)
    para(lead, lead + blue, BLUE)
    para(lead + blue, lead + blue + band, TEAL)
    para(lead + blue + band, lead + total_h, DEEP)
    return base


def split(a, b, p):
    """Two navy panels with teal inner edges close from the sides, then open on the next slide."""
    q = ease(p * 2) if p < 0.5 else ease((1 - p) * 2)
    base = (a if p < 0.5 else b).copy()
    d = ImageDraw.Draw(base)
    half = int((W / 2 + 6) * q)
    edge = 10
    if half > 0:
        d.rectangle((0, 0, half, H), fill=DEEP)
        d.rectangle((max(0, half - edge), 0, half, H), fill=TEAL)
        d.rectangle((W - half, 0, W, H), fill=DEEP)
        d.rectangle((W - half, 0, min(W, W - half + edge), H), fill=TEAL)
    return base


def zoom_fade(a, b, p):
    """Push through navy: the outgoing slide scales up into deep navy, a teal line flashes,
    then the incoming slide settles in from slightly larger. Never shows two slides at once."""
    navy = Image.new('RGB', (W, H), DEEP)
    if p < 0.5:
        q = ease(p * 2)
        s = 1 + 0.10 * q
        w, h = int(W * s), int(H * s)
        big = a.resize((w, h), Image.BICUBIC).crop(((w - W) // 2, (h - H) // 2, (w - W) // 2 + W, (h - H) // 2 + H))
        f = Image.blend(big, navy, q)
    else:
        q = ease((p - 0.5) * 2)
        s = 1.06 - 0.06 * q
        w, h = int(W * s), int(H * s)
        big = b.resize((w, h), Image.BICUBIC).crop(((w - W) // 2, (h - H) // 2, (w - W) // 2 + W, (h - H) // 2 + H))
        f = Image.blend(navy, big, q)
    if 0.35 < p < 0.65:
        d = ImageDraw.Draw(f)
        k = 1 - abs(p - 0.5) / 0.15
        L = int(W * 0.7 * k)
        d.rectangle((W // 2 - L // 2, H // 2 - 3, W // 2 + L // 2, H // 2 + 3), fill=TEAL)
    return f


TRANSITIONS = {'wipe': wipe, 'wipe_up': wipe_up, 'split': split, 'zoom': zoom_fade}


def intro_frame(bg, logo, t):
    f = bg.copy()
    p = ease(t / 0.8)
    s = 0.82 + 0.18 * p
    lw = int(360 * s); lh = int(logo.height * lw / logo.width)
    lg = logo.resize((lw, lh), Image.LANCZOS)
    # no fade from black: the very first frame already shows the logo and headline,
    # so the video never looks blank before it plays
    alpha = lg.split()[3].point(lambda v: int(v * (0.7 + 0.3 * min(1, t / 0.5))))
    f.paste(lg, ((W - lw) // 2, 760 - lh // 2), alpha)
    d = ImageDraw.Draw(f)
    q = 0.35 + 0.65 * ease(t / 0.8)
    half = int(300 * q)
    d.rectangle((W // 2 - half, 1110, W // 2 + half, 1116), fill=TEAL)
    return f


def end_frame(card, t):
    q = ease(t / 0.7)
    f = Image.new('RGB', (W, H), DEEP)
    f.paste(card, (0, int(80 * (1 - q))))
    return Image.blend(Image.new('RGB', (W, H), DEEP), f, min(1, t / 0.5))


# ---------- audio ----------
def soundtrack(total, trans_times, seed, mood='piano'):
    rnd = random.Random(seed)
    sr = 44100
    n = int(total * sr) + sr
    out = np.zeros(n)
    bpm = rnd.choice([104, 108, 112, 116])
    beat = 60 / bpm
    root = rnd.choice([60, 62, 57, 65])            # C, D, A, F
    progs = [[0, 7, 9, 5], [0, 5, 9, 7], [9, 5, 0, 7], [0, 9, 5, 7]]
    prog = rnd.choice(progs)
    minor_deg = {9, 4, 2}
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)

    def add(sig, start):
        s = int(start * sr)
        if s >= n: return
        e = min(n, s + len(sig)); out[s:e] += sig[:e - s]

    def piano(f, dur, vol):
        t = np.arange(int(dur * sr)) / sr
        env = np.exp(-t * 3.2) * np.minimum(1, t / 0.005)
        return vol * env * (np.sin(2 * np.pi * f * t) + 0.45 * np.sin(4 * np.pi * f * t) * np.exp(-t * 4)
                            + 0.18 * np.sin(6 * np.pi * f * t) * np.exp(-t * 6))

    def pad(fs, dur, vol):
        t = np.arange(int(dur * sr)) / sr
        env = np.minimum(1, t / 0.4) * np.minimum(1, (dur - t) / 0.4)
        sig = sum(np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.003 * t) for f in fs)
        return vol * env * sig / len(fs)

    def pluck(f, dur, vol):
        t = np.arange(int(dur * sr)) / sr
        env = np.exp(-t * 9) * np.minimum(1, t / 0.003)
        saw = 2 * ((f * t) % 1) - 1
        return vol * env * (0.6 * saw + 0.4 * np.sin(2 * np.pi * f * t))

    bar = 4 * beat
    nbars = int(total / bar) + 1
    for i in range(nbars):
        deg = prog[i % 4]
        r = root + deg - (12 if deg >= 7 else 0)
        third = 3 if deg in minor_deg else 4
        chord = [r, r + third, r + 7]
        t0 = i * bar
        add(pad([hz(m) for m in chord], bar + 0.2, 0.05), t0)
        add(piano(hz(r - 24), bar, 0.16), t0)                      # bass
        if mood == 'pluck':                                         # bright 16th-note plucks
            arp = [chord[0], chord[2], chord[1] + 12, chord[2], chord[0] + 12, chord[2], chord[1] + 12, chord[2]] * 2
            for k, m in enumerate(arp):
                add(pluck(hz(m + 12), 0.35, 0.05), t0 + k * beat / 4)
        elif mood == 'maritime':                                    # open, steady, ocean-going feel
            add(pad([hz(m + 12) for m in chord], bar + 0.4, 0.045), t0)
            for k, m in enumerate([chord[0], chord[2], chord[1] + 12, chord[2]]):
                add(piano(hz(m + 12), 1.4, 0.055), t0 + k * beat)
        elif mood == 'ambient':                                     # slow, wide pad with a soft pulse
            add(pad([hz(m + 12) for m in chord], bar + 0.4, 0.05), t0)
            for k in range(4):
                add(piano(hz(chord[k % 3] + 12), 1.6, 0.04), t0 + k * beat)
        else:                                                       # piano 8th-note arpeggio
            arp = [chord[0], chord[1], chord[2], chord[1] + 12, chord[2], chord[1], chord[0] + 12, chord[2]]
            for k, m in enumerate(arp):
                add(piano(hz(m + 12), 0.9, 0.07), t0 + k * beat / 2)
    nbeats = int(total / beat) + 1
    for k in range(nbeats):
        t0 = k * beat
        if t0 < 0.6: continue                                       # let the intro breathe
        if mood in ('ambient', 'maritime') and k % 2: continue      # lighter rhythm
        tt = np.arange(int(0.3 * sr)) / sr
        if k % 2 == 0:                                              # kick on 1 and 3
            add(0.45 * np.sin(2 * np.pi * (48 + 90 * np.exp(-tt * 28)) * tt) * np.exp(-tt * 9), t0)
        else:                                                       # clap on 2 and 4
            nz = np.random.RandomState(k).randn(int(0.12 * sr))
            env = np.exp(-np.arange(len(nz)) / sr * 30)
            add(0.10 * np.convolve(nz, [1, -1], 'same') * env, t0)
        hh = np.random.RandomState(k + 999).randn(int(0.04 * sr))  # off-beat hat
        add(0.025 * np.diff(hh, prepend=0) * np.exp(-np.arange(len(hh)) / sr * 90), t0 + beat / 2)
    if mood == 'maritime':                                          # shipping sound design
        L = int(total * sr)                                         # sea bed: slow swelling waves
        nz = np.random.RandomState(seed % 9973).randn(L)
        sea = np.convolve(nz, np.ones(60) / 60, 'same')
        tt = np.arange(L) / sr
        swell = 0.55 + 0.45 * np.sin(2 * np.pi * tt / 5.5) ** 2
        add(0.20 * sea * swell, 0.0)
        H_ = int(2.2 * sr); th = np.arange(H_) / sr                 # distant ship horn on the intro
        henv = np.minimum(1, th / 0.25) * np.minimum(1, (2.2 - th) / 0.6)
        horn = sum(np.sin(2 * np.pi * f * th * (1 + 0.003 * np.sin(2 * np.pi * 5 * th))) * w
                   for f, w in ((73.4, 1.0), (110.0, 0.7), (146.8, 0.35), (220.0, 0.15)))
        add(0.16 * henv * horn, 0.15)
        for tt0 in trans_times[1:-1]:                                # container clank on cuts
            C = int(0.5 * sr); tc = np.arange(C) / sr
            clank = sum(np.sin(2 * np.pi * f * tc) * np.exp(-tc * d) for f, d in
                        ((523, 9), (811, 12), (1247, 16), (1873, 22), (2610, 30)))
            add(0.05 * clank, tt0 - 0.02)
    for tt0 in trans_times:                                         # whoosh on each wipe
        L = int(0.7 * sr); x = np.arange(L) / L
        nz = np.random.RandomState(int(tt0 * 100)).randn(L)
        sm = np.convolve(nz, np.ones(25) / 25, 'same')
        add(0.22 * sm * np.sin(np.pi * x) ** 2, tt0 - 0.2)
    L = int(1.1 * sr); x = np.arange(L) / L                         # intro riser
    add(0.12 * np.convolve(np.random.RandomState(7).randn(L), np.ones(15) / 15, 'same') * x ** 2, 0.0)
    fade = np.ones(n); fo = int(1.6 * sr); end = int(total * sr)
    fade[end - fo:end] = np.linspace(1, 0, fo); fade[end:] = 0
    fade[:int(0.05 * sr)] = np.linspace(0, 1, int(0.05 * sr))
    out *= fade
    out = np.tanh(out * 1.4) / np.tanh(1.4)
    out /= max(1e-9, np.max(np.abs(out))) / 0.74   # about -2.6 dBFS sample peak: headroom so AAC never overshoots 0 dBTP
    return out[:end], sr


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('slides', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--headline', default='IMPORT SMARTER')
    ap.add_argument('--node-modules', default=None)
    ap.add_argument('--transition', default='auto', choices=['auto', 'mix'] + ['wipe', 'wipe_up', 'split', 'zoom'],
                    help='auto: one style picked from the seed; mix: vary style at each cut')
    ap.add_argument('--mood', default='auto', choices=['auto', 'piano', 'pluck', 'ambient', 'maritime'],
                    help='soundtrack style; auto picks from the seed')
    ap.add_argument('--slide-seconds', type=float, default=None,
                    help='seconds each slide stays on screen (default 6.0; use 7-8 for text-heavy posters)')
    ap.add_argument('--end-seconds', type=float, default=None,
                    help='seconds the WhatsApp end card holds (default 5.0, long enough to note the number)')
    ap.add_argument('--backdrop', default=None,
                    help='optional real photo (e.g. brand/backgrounds/x.jpg) shown darkened behind 4:5 posters')
    ap.add_argument('--motion', default='still', choices=['still', 'zoom'],
                    help='still (default): slides held pixel-sharp; zoom: slow bicubic push-in')
    a = ap.parse_args()
    global SLIDE, END, BACKDROP, MOTION
    BACKDROP, MOTION = a.backdrop, a.motion
    if a.slide_seconds: SLIDE = a.slide_seconds
    if a.end_seconds: END = a.end_seconds

    nm = find_node_modules(a.node_modules)
    cards = render_cards(nm, a.headline.upper())
    logo = Image.open(os.path.join(REPO, 'brand', 'logo_white.png')).convert('RGBA')
    slides = [to_vertical(s) for s in a.slides]

    # timeline: intro, [slide, wipe] ..., end; wipes overlap segment boundaries
    segs = [('intro', INTRO)] + [('slide', SLIDE)] * len(slides) + [('end', END)]
    total = sum(d for _, d in segs)
    bounds, t = [], 0.0
    for _, d in segs:
        bounds.append(t); t += d
    trans_times = bounds[1:]
    nframes = int(total * FPS)

    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, 'a.wav')
    rnd = random.Random(a.seed)
    mood = a.mood if a.mood != 'auto' else rnd.choice(['piano', 'pluck', 'ambient', 'maritime', 'maritime'])
    names = list(TRANSITIONS)
    if a.transition == 'mix':
        order = names[:]; rnd.shuffle(order)            # rotate evenly, never the same style twice in a row
        styles = [order[i % len(order)] for i in range(len(trans_times))]
    else:
        one = a.transition if a.transition != 'auto' else rnd.choice(names)
        styles = [one] * len(trans_times)
    # keep the brand wipe into the end card for a consistent sign-off
    styles[-1] = 'wipe'
    print(f'STYLE transitions={",".join(styles)} mood={mood}')
    audio, sr = soundtrack(total, trans_times, a.seed, mood)
    st = (np.stack([audio, audio], 1) * 32767).astype(np.int16)
    with wave.open(wav, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(st.tobytes())

    def seg_frame(i, local):
        kind = segs[i][0]
        if kind == 'intro': return intro_frame(cards['intro'], logo, local)
        if kind == 'end': return end_frame(cards['end'], local)
        return push_in(slides[i - 1], local / SLIDE, 0.03 if MOTION == 'zoom' else 0.0, progress=i > 1)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                           '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', wav,
                           '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-profile:v', 'high', '-tune', 'stillimage',
                           '-g', '60', '-pix_fmt', 'yuv420p',
                           '-c:a', 'aac', '-b:a', '256k', '-af', 'lowpass=f=15000', '-shortest', '-movflags', '+faststart', a.out],
                          stdin=subprocess.PIPE)
    half = TRANS / 2
    for fi in range(nframes):
        t = fi / FPS
        i = max(k for k, b in enumerate(bounds) if b <= t)
        local = t - bounds[i]
        frame = seg_frame(i, local)
        # wipe around each boundary
        for k, bt in enumerate(trans_times, start=1):
            if bt - half <= t < bt + half:
                p = (t - (bt - half)) / TRANS
                prev_f = seg_frame(k - 1, min(t - bounds[k - 1], segs[k - 1][1] - 1e-3))
                next_f = seg_frame(k, max(0.0, t - bt))
                frame = TRANSITIONS[styles[k - 1]](prev_f, next_f, p)
        ff.stdin.write(frame.tobytes())
    ff.stdin.close(); ff.wait()
    # size guard: still slides compress to a few MB at CRF 14; motion-heavy videos (--motion zoom,
    # photo backdrops) can exceed the 15 MB limit, so step the quality down only as far as needed
    for crf in (17, 20, 23):
        if os.path.getsize(a.out) < 14.5e6:
            break
        tmp_out = a.out + '.tmp.mp4'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', a.out, '-c:v', 'libx264', '-preset', 'slow',
                        '-crf', str(crf), '-profile:v', 'high', '-g', '60', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
                        '-movflags', '+faststart', tmp_out], check=True)
        os.replace(tmp_out, a.out)
        print(f'SIZE_GUARD re-encoded at crf {crf}')
    # cover / thumbnail: the middle of the first slide (the poster itself, fully visible)
    thumb_ms = int((INTRO + SLIDE / 2) * 1000)
    cover = os.path.splitext(a.out)[0] + '_cover.jpg'
    seg_frame(1, SLIDE / 2).save(cover, 'JPEG', quality=95)
    print(a.out, f'{total:.1f}s')
    print(f'THUMBNAIL_OFFSET_MS={thumb_ms}')
    print(f'COVER_JPG={cover}')


if __name__ == '__main__':
    main()
