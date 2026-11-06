"""Black-and-white pixel-art burning car with live, coded fire (animated GIF).

Regenerate:  python3 .github/scripts/fire.py assets/source/car.png assets/fire.gif

Car body  -> taken from the user's image, grayscale + ordered (Bayer) dither.
Flames    -> removed from the photo and replaced by a 'Doom fire' simulation:
             each pixel's heat rises from the pixel below, cooling and drifting
             randomly, so the fire really moves frame to frame.
"""
import sys, random
import numpy as np
from PIL import Image

SRC, OUT = sys.argv[1], sys.argv[2]
PX = 3                      # size of one "pixel" on screen
W, H = 400, 190             # low-res grid  -> 1200 x 570 output
FRAMES, MS = 48, 70         # ~3.4 s loop at ~14 fps
rng = np.random.default_rng(11)

# ---------- 1. load + place the car on a wide black canvas ----------
im = Image.open(SRC).convert("RGB").crop((0, 110, 944, 905))   # trim empty sky/ground
scale = H / im.height
cw = round(im.width * scale)
im = im.resize((cw, H), Image.LANCZOS)
rgb = np.asarray(im).astype(float) / 255
r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]

# flame intensity from the photo: hot (red+green high) pixels in the upper part
yy = np.arange(H)[:, None] * np.ones((1, cw))
fint = np.clip((r - .55) / .40, 0, 1) * np.clip((g - .15) / .55, 0, 1)
fint[yy > H * .70] = 0
flame = fint > .22

# make the CAR the bright subject: red-lit metal reads bright, the yellow road reads dark
val = .65 * r + .35 * g
ratio = g / np.maximum(r, 1e-3)
road = (ratio > .62) & (yy > H * .55)
sky = ratio < .28
val = np.where(road, val * .45, val)
val = np.where(sky, val * .25, val)
yfade = np.clip((yy - H * .46) / (H * .12), 0, 1)          # 0 above the roof -> 1 below it
halo = (ratio < .45) & ~(fint > .22)
val = np.where(halo, val * (.38 + .62 * yfade), val)
# sharpen edges so the car outline, wheels and panels pop
def blur(a, k=3):
    p_ = np.pad(a, k, mode="edge"); out = np.zeros_like(a)
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            out += p_[k + dy:k + dy + a.shape[0], k + dx:k + dx + a.shape[1]]
    return out / (2 * k + 1) ** 2
val = val + 1.6 * (val - blur(val))
lum = np.clip((val - .16) / .62, 0, 1) ** 1.25
lum[flame] = 0                                        # fire is drawn by the simulation instead

car = np.zeros((H, W)); src = np.zeros((H, W))
x0 = (W - cw) // 2
car[:, x0:x0 + cw] = lum
src[:, x0:x0 + cw] = np.where(flame, fint, 0)
xs = np.arange(W)
edge = np.clip(np.minimum(xs - x0, x0 + cw - xs) / 50, 0, 1) ** 1.2
vfade = np.clip((H - 1 - np.arange(H)) / 30, 0, 1)
car *= edge[None, :] * vfade[:, None]
cols = np.nonzero(src.max(0) > 0)[0]
top = np.array([np.nonzero(src[:, x])[0].min() if src[:, x].max() > 0 else H for x in range(W)])
bot = np.array([np.nonzero(src[:, x])[0].max() if src[:, x].max() > 0 else 0 for x in range(W)])
# feed heat mostly at the base of each flame column; the sim grows the tongues
Y = np.arange(H)[:, None]
base_w = np.clip((Y - top[None, :]) / np.maximum(bot - top, 1)[None, :], 0, 1) ** 1.4
src = src * (.25 + .75 * base_w)

# ---------- 2. Doom-fire simulation ----------
# every frame, heat rises one row, cools a little and drifts sideways.
# the photo's flame pixels keep feeding heat in (with flicker), so the fire
# keeps the original shape but its tongues lick upward and move.
MAXH = 30
heat = np.zeros((H, W))

# smooth noise that scrolls upward -> flames flicker in blobs, not static
def smooth_noise(h, w, cell):
    g = rng.random((h // cell + 2, w // cell + 2))
    img = Image.fromarray((g * 255).astype(np.uint8)).resize(((w // cell + 2) * cell, (h // cell + 2) * cell), Image.BICUBIC)
    return np.asarray(img)[:h, :w] / 255
NOISE = .6 * smooth_noise(H * 3, W, 8) + .4 * smooth_noise(H * 3, W, 3)
tick = [0]

def step(heat):
    new = np.zeros_like(heat)
    for y in range(H - 1):
        decay = rng.integers(0, 4, W) * (rng.random(W) < .5)
        dst = np.clip(xs + rng.integers(-1, 2, W), 0, W - 1)
        np.maximum.at(new[y], dst, heat[y + 1] - decay)
    new = np.maximum(new, 0)
    tick[0] += 1
    off = (tick[0] * 3) % (H * 2)
    n = NOISE[H * 2 - off: H * 3 - off] if off else NOISE[H * 2:]
    feed = src * MAXH * 1.6 * np.clip(.35 + .9 * n, 0, 1.1)
    return np.maximum(new, feed)

for _ in range(60):
    heat = step(heat)

# ---------- 3. render ----------
bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 + 1 / 32
thr = np.tile(bayer, (H // 4 + 1, W // 4 + 1))[:H, :W]

sparks = []
frames = []
for f in range(FRAMES):
    heat = step(heat)
    fire = np.clip(heat / MAXH, 0, 1) ** 1.45    # only hot parts glow -> crisp tongues
    # light the car where the fire is close (simple glow by blurring the fire)
    glow = np.pad(fire, 6)
    for _ in range(4):
        glow = (glow + np.roll(glow, 3, 0) + np.roll(glow, -3, 0) + np.roll(glow, 3, 1) + np.roll(glow, -3, 1)) / 5
    glow = glow[6:-6, 6:-6]
    flick = .8 + .2 * rng.random()
    img = np.maximum(car * (1 + 1.1 * glow * flick), fire)
    # embers floating up
    if rng.random() < .7:
        x = rng.choice(cols); sparks.append([float(x), float(top[x]), rng.uniform(-.4, .4)])
    keep = []
    for s in sparks:
        s[1] -= rng.uniform(1, 2.2); s[0] += s[2] + rng.uniform(-.5, .5)
        if s[1] > 4 and 0 < s[0] < W - 1:
            img[int(s[1]), int(s[0])] = 1; keep.append(s)
    sparks = keep[-40:]
    LEVELS = 6   # a few grey steps + ordered dither = pixel-art look, still pure black & white
    q = np.floor(np.clip(img, 0, 1) * (LEVELS - 1) + thr) / (LEVELS - 1)
    bw = (np.clip(q, 0, 1) * 255).astype(np.uint8)
    frame = Image.fromarray(bw, "L").resize((W * PX, H * PX), Image.NEAREST).convert("P")
    frames.append(frame)

frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=MS, loop=0,
               optimize=True, disposal=1)
frames[FRAMES // 2].convert("L").save(OUT.replace(".gif", "_still.png"))
print("saved", OUT)
