#!/usr/bin/env python3
"""Clearon quality gate: automatic technical checks before anything is pushed or scheduled.

  python3 tools/qa_check.py images  <jpg...>           # posters, cards, carousel slides, stories
  python3 tools/qa_check.py videos  <mp4...>           # also writes <name>_qa_sheet.jpg frame strip to --sheet-dir
  python3 tools/qa_check.py captions <captions.json>   # [{"platform": "x", "text": "...", "card": true}, ...]
  python3 tools/qa_check.py sheet --out sheet.jpg <jpg...>   # review sheet: full size + phone-size previews

Every check prints PASS or FAIL lines; the exit code is 1 if anything failed.
Anything that fails here must be fixed and re-checked before it is pushed or scheduled.
The visual design review (tools/QA_RUBRIC.md) comes after these checks pass.
"""
import json, os, re, subprocess, sys, argparse
from PIL import Image, ImageStat

FAILS = []

def fail(name, msg):
    FAILS.append(f'{name}: {msg}')
    print(f'FAIL {name}: {msg}')

def ok(name, msg=''):
    print(f'PASS {name} {msg}')

# ---------------------------------------------------------------- images
def check_image(p):
    n = os.path.basename(p)
    if not p.lower().endswith('.jpg'):
        return fail(n, 'not a .jpg')
    im = Image.open(p)
    if im.format != 'JPEG': fail(n, f'format {im.format}, must be JPEG')
    if im.mode != 'RGB': fail(n, f'mode {im.mode}, must be RGB')
    story = '/stories/' in p or p.endswith('_story.jpg') or p.endswith('_cover.jpg')
    want = (1080, 1920) if story else (1080, 1350)
    if im.size != want: fail(n, f'size {im.size}, expected {want}')
    if im.info.get('progressive') or im.info.get('progression'):
        fail(n, 'progressive JPEG (save baseline: progressive=False)')
    if im.info.get('icc_profile'):
        fail(n, 'embedded ICC profile (Threads rejected one of these; re-save without icc_profile)')
    size = os.path.getsize(p)
    if size > 8 * 1024 * 1024: fail(n, f'{size/1e6:.1f} MB, must be under 8 MB')
    if size < 60 * 1024: fail(n, f'only {size//1024} KB; probably blank or over-compressed')
    q = estimate_quality(im)
    if q and q < 90: fail(n, f'JPEG quality about {q}, must be 92+')
    g = im.convert('L')
    sd = ImageStat.Stat(g).stddev[0]
    if sd < 18: fail(n, f'very low contrast/detail (stddev {sd:.0f}); blank or washed out?')
    # footer band present: bottom 92px should differ from the area just above it or be a solid band
    if not story:
        band = g.crop((0, 1350 - 80, 1080, 1350 - 12))
        if ImageStat.Stat(band).stddev[0] < 4:
            fail(n, 'footer band looks empty (contact footer missing?)')
    if not any(f.startswith(n) for f in FAILS):
        ok(n, f'{im.size[0]}x{im.size[1]} q~{q} {size//1024}KB')

def estimate_quality(im):
    """Rough libjpeg quality from the luminance quantisation table."""
    try:
        t = im.quantization[0]
        base = [16,11,10,16,24,40,51,61,12,12,14,19,26,58,60,55,14,13,16,24,40,57,69,56,14,17,22,29,51,87,80,62,
                18,22,37,56,68,109,103,77,24,35,55,64,81,104,113,92,49,64,78,87,103,121,120,101,72,92,95,98,112,100,103,99]
        vals = list(t)  # zigzag order in Pillow; compare sorted sums which is order independent
        s = sum(vals) / sum(base)
        q = (200 - s * 100) / 2 if s <= 1 else 5000 / (s * 100)
        return int(round(q))
    except Exception:
        return None

# ---------------------------------------------------------------- videos
def ffprobe(p):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                          'stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate:format=duration',
                          '-of', 'json', p], capture_output=True, text=True).stdout
    return json.loads(out)

def frame_at(p, t, w=270):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', p, '-frames:v', '1',
                        '-vf', f'scale={w}:-1', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True)
    import io
    return Image.open(io.BytesIO(r.stdout)).convert('RGB')

def check_video(p, sheet_dir, thumb_ms=None):
    n = os.path.basename(p)
    info = ffprobe(p)
    dur = float(info['format']['duration'])
    v = [s for s in info['streams'] if s['codec_type'] == 'video']
    a = [s for s in info['streams'] if s['codec_type'] == 'audio']
    if not v: return fail(n, 'no video stream')
    v = v[0]
    if v['codec_name'] != 'h264': fail(n, f"codec {v['codec_name']}, must be h264")
    if v.get('pix_fmt') != 'yuv420p': fail(n, f"pix_fmt {v.get('pix_fmt')}, must be yuv420p")
    if (v['width'], v['height']) != (1080, 1920): fail(n, f"{v['width']}x{v['height']}, expected 1080x1920")
    if not a: fail(n, 'no audio track')
    elif a[0]['codec_name'] != 'aac': fail(n, f"audio {a[0]['codec_name']}, must be aac")
    size = os.path.getsize(p)
    if size > 15 * 1024 * 1024: fail(n, f'{size/1e6:.1f} MB, must be under 15 MB')
    if dur < 9 or dur > 90: fail(n, f'duration {dur:.1f}s outside 9-90s')
    # first frame branded, not blank/black
    f0 = frame_at(p, 0.0)
    st = ImageStat.Stat(f0.convert('L'))
    if st.mean[0] < 12 or st.stddev[0] < 8: fail(n, 'first frame is blank/black')
    # cover frame
    tm = (thumb_ms or 4600) / 1000
    fc = frame_at(p, tm)
    if ImageStat.Stat(fc.convert('L')).stddev[0] < 25: fail(n, f'cover frame at {tm:.1f}s looks empty')
    # silence check on audio
    if a:
        r = subprocess.run(['ffmpeg', '-v', 'info', '-i', p, '-af', 'volumedetect', '-f', 'null', '-'],
                           capture_output=True, text=True).stderr
        m = re.search(r'mean_volume: (-?[\d.]+) dB', r)
        mx = re.search(r'max_volume: (-?[\d.]+) dB', r)
        if m and float(m.group(1)) < -50: fail(n, f'soundtrack nearly silent ({m.group(1)} dB mean)')
        if mx and float(mx.group(1)) > -0.1: fail(n, f'audio clipping (max {mx.group(1)} dB)')
    # frame strip every 0.5 s for the visual review (transitions, overlaps, end card)
    if sheet_dir:
        os.makedirs(sheet_dir, exist_ok=True)
        ts = [i * 0.5 for i in range(int(dur / 0.5))]
        fr = [frame_at(p, t, 180) for t in ts]
        cols = 12
        rows = (len(fr) + cols - 1) // cols
        sh = Image.new('RGB', (cols * 180, rows * 320), (40, 40, 40))
        for i, f in enumerate(fr):
            sh.paste(f.resize((180, 320)), ((i % cols) * 180, (i // cols) * 320))
        out = os.path.join(sheet_dir, n.replace('.mp4', '_qa_sheet.jpg'))
        sh.save(out, quality=85)
        print(f'     frame sheet (every 0.5s, read left to right): {out}')
    if not any(f.startswith(n) for f in FAILS):
        ok(n, f'{dur:.1f}s {size/1e6:.1f}MB h264/aac 1080x1920')

# ---------------------------------------------------------------- captions
LIMITS = {'x': 280, 'threads': 500, 'instagram': 2200, 'tiktok': 2200, 'facebook': 5000, 'linkedin': 3000}
HASHTAGS = {'instagram': 6, 'threads': 3, 'x': 2, 'tiktok': 6, 'facebook': 3, 'linkedin': 5}

def x_len(t):
    return len(re.sub(r'https?://\S+', 'x' * 23, t))

def check_caption(i, c):
    pf, t = c['platform'].lower(), c.get('text', '')
    n = f"caption[{i}] {pf} {c.get('label', '')}".strip()
    if c.get('story'):
        return ok(n, '(story, no caption)')
    L = x_len(t) if pf == 'x' else len(t)
    if L > LIMITS[pf]: fail(n, f'{L} chars, limit {LIMITS[pf]}')
    tags = re.findall(r'#\w+', t)
    if len(tags) > HASHTAGS[pf]: fail(n, f'{len(tags)} hashtags, max {HASHTAGS[pf]}')
    if '115007849' not in t: fail(n, 'missing phone/WhatsApp number')
    if pf not in ('x',) and 'info@clearonlogistics.co.ke' not in t and pf != 'tiktok':
        fail(n, 'missing email')
    for u in re.findall(r'https?://(?:www\.)?clearonlogistics\.co\.ke/\S*', t) + ([c['link']] if c.get('link') else []):
        if 'utm_source=' not in u: fail(n, f'link without UTM: {u}')
        else:
            if '/?utm_' not in u: fail(n, f'missing trailing slash before ?: {u}')
            src = re.search(r'utm_source=(\w+)', u).group(1)
            if src != pf: fail(n, f'utm_source={src} on a {pf} post')
            if 'utm_medium=social' not in u or 'utm_campaign=autopilot' not in u or not re.search(r'utm_content=\d{4}-\d{2}-\d{2}_(\w+)', u):
                fail(n, f'incomplete UTM: {u}')
    if re.search(r'wa\.me/\S*utm_', t): fail(n, 'UTM on a wa.me link')
    if pf in ('instagram', 'tiktok') and re.search(r'https?://', t): fail(n, 'URL in IG/TikTok caption (say "link in bio")')
    if c.get('card') and '?' not in t.split('\n\n')[-1] + t[-400:]:
        fail(n, 'card caption should end with a question or comment prompt')
    banned = ['guarantee', 'cheapest', 'best price', 'fastest', '#1', 'number one', 'clients say', 'testimonial']
    for b in banned:
        if b in t.lower(): fail(n, f'risky claim word: "{b}"')
    if re.search(r'\b(\d+)\s*(days?|weeks?)\b', t) and not c.get('fact_source'):
        fail(n, 'mentions a time period; add fact_source (Clearon article) or remove it')
    if re.search(r'(KES|KSh|USD|\$)\s?\d', t) and not c.get('fact_source'):
        fail(n, 'mentions a price/figure; add fact_source (Clearon article) or remove it')
    if not any(f.startswith(n) for f in FAILS):
        ok(n, f'{L} chars, {len(tags)} tags')

# ---------------------------------------------------------------- review sheet
def make_sheet(files, out):
    """Each image at feed size (540 wide) next to a phone-size preview (360 wide, how it looks in a feed)."""
    tiles = []
    for p in files:
        im = Image.open(p).convert('RGB')
        big = im.resize((540, round(im.height * 540 / im.width)))
        small = im.resize((360, round(im.height * 360 / im.width)))
        t = Image.new('RGB', (540 + 360 + 30, max(big.height, small.height) + 10), (235, 235, 235))
        t.paste(big, (0, 0)); t.paste(small, (560, 0))
        tiles.append(t)
    per_row = 2
    rows = [tiles[i:i + per_row] for i in range(0, len(tiles), per_row)]
    W = per_row * (930 + 20)
    H = sum(max(t.height for t in r) + 20 for r in rows)
    sh = Image.new('RGB', (W, H), (255, 255, 255))
    y = 0
    for r in rows:
        x = 0
        for t in r:
            sh.paste(t, (x, y)); x += t.width + 20
        y += max(t.height for t in r) + 20
    sh.save(out, quality=88)
    print('review sheet:', out)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['images', 'videos', 'captions', 'sheet'])
    ap.add_argument('files', nargs='+')
    ap.add_argument('--sheet-dir')
    ap.add_argument('--thumb-ms', type=int)
    ap.add_argument('--out')
    a = ap.parse_args()
    if a.mode == 'images':
        for f in a.files: check_image(f)
    elif a.mode == 'videos':
        for f in a.files: check_video(f, a.sheet_dir, a.thumb_ms)
    elif a.mode == 'captions':
        for f in a.files:
            for i, c in enumerate(json.load(open(f))): check_caption(i, c)
    else:
        make_sheet(a.files, a.out or 'review_sheet.jpg')
    print(f'\n{len(FAILS)} problem(s)' if FAILS else '\nALL CHECKS PASSED')
    sys.exit(1 if FAILS else 0)
