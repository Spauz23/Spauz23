"""Render the seamless 25s cinematic loop from the five source stills.

Usage: python3 video/render.py [WIDTH HEIGHT]   (default 854 480)
Requires: numpy, opencv-python-headless, imageio-ffmpeg
"""
import subprocess
import sys
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

HERE = Path(__file__).parent
W, H = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (854, 480)
FPS = 24
T = 25.0          # loop length (s)
XF = 1.6          # dissolve length (s)
N = int(T * FPS)
rng = np.random.default_rng(7)


def load(name):
    img = cv2.imread(str(HERE / "src" / f"{name}.png")).astype(np.float32) / 255.0
    return img


def noise(h, w, cell, seed):
    r = np.random.default_rng(seed)
    g = r.random((max(2, h // cell + 3), max(2, w // cell + 3))).astype(np.float32)
    return cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def ease(x):
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(x, 0, 1))


# ---------------------------------------------------------------- sources
src = {k: load(k) for k in ["wheat", "olive", "lemon", "matera", "tomato"]}

# San Marzano: remove glyph-like specular artefacts, keep a soft gloss instead
tom = src["tomato"]
t8 = (tom * 255).astype(np.uint8)
hsv = cv2.cvtColor(t8, cv2.COLOR_BGR2HSV)
spec = ((hsv[..., 2] > 200) & (hsv[..., 1] < 150) & (t8[..., 2] > 200)).astype(np.uint8) * 255
spec = cv2.dilate(spec, np.ones((3, 3), np.uint8))
clean = cv2.inpaint(t8, spec, 4, cv2.INPAINT_TELEA).astype(np.float32) / 255.0
gloss = cv2.GaussianBlur(spec.astype(np.float32) / 255.0, (0, 0), 3.0)[..., None]
src["tomato"] = np.clip(clean + gloss * 0.22 * np.array([0.75, 0.85, 1.0], np.float32), 0, 1)

# Matera: warm window-light mask (lights fade in during blue hour)
m8 = (src["matera"] * 255).astype(np.uint8)
mhsv = cv2.cvtColor(m8, cv2.COLOR_BGR2HSV)
lights = ((mhsv[..., 2] > 170) & (mhsv[..., 0] < 30) & (mhsv[..., 1] > 110)).astype(np.float32)
lights[: int(lights.shape[0] * 0.28)] = 0  # ignore the sunset sky
matera_lights = cv2.GaussianBlur(lights, (0, 0), 1.2)
matera_glow = cv2.GaussianBlur(lights, (0, 0), 6.0)

# Lemon: sparkles on the sea (right side, bright pixels)
l8 = (src["lemon"] * 255).astype(np.uint8)
lhsv = cv2.cvtColor(l8, cv2.COLOR_BGR2HSV)
sea = ((lhsv[..., 2] > 190) & (lhsv[..., 0] > 85) & (lhsv[..., 0] < 130)).astype(np.float32)
sea[:, : int(sea.shape[1] * 0.55)] = 0
lemon_sea = cv2.GaussianBlur(sea, (0, 0), 2.0)

# ---------------------------------------------------------------- scenes
# Camera: (cx, cy, crop width) in source pixels, start -> end, eased.
SCENES = [
    dict(name="wheat", start=-XF, dur=5.0 + XF,
         cam0=(250, 215, 540), cam1=(300, 250, 470), wind=(1.6, "bottom")),
    dict(name="olive", start=5.0 - XF, dur=5.0 + XF,
         cam0=(300, 250, 470), cam1=(265, 225, 520), wind=(0.9, "top")),
    dict(name="tomato", start=10.0 - XF, dur=5.0 + XF,
         cam0=(380, 260, 700), cam1=(430, 235, 620), wind=(0.7, "bottom")),
    dict(name="lemon", start=15.0 - XF, dur=5.0 + XF,
         cam0=(270, 250, 470), cam1=(300, 230, 420), wind=(1.2, "all")),
    dict(name="matera", start=20.0 - XF, dur=5.0 + XF,
         cam0=(430, 245, 800), cam1=(400, 235, 700), wind=(0.0, "all")),
]

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
u = xx / W - 0.5
v = yy / H - 0.5

# large drifting textures (output resolution), sampled with sub-pixel offsets
TEX = {
    "dapple": noise(H * 2, W * 2, max(8, W // 30), 11),
    "mist": noise(H * 2, W * 3, max(16, W // 8), 12),
    "shadow": noise(H * 2, W * 2, max(12, W // 18), 13),
    "twinkle": noise(H * 2, W * 2, max(3, W // 240), 14),
    "flare": noise(H * 2, W * 2, max(20, W // 6), 15),
}


def tex(name, ox, oy):
    t = TEX[name]
    th, tw = t.shape
    cx = (ox % (tw - W - 2)) + W / 2
    cy = (oy % (th - H - 2)) + H / 2
    return cv2.getRectSubPix(t, (W, H), (float(cx), float(cy)))


def render_scene(sc, lt):
    """lt: local time in seconds since scene start."""
    img = src[sc["name"]]
    sh, sw = img.shape[:2]
    p = ease(lt / sc["dur"])
    cx, cy, cw = [a + (b - a) * p for a, b in zip(sc["cam0"], sc["cam1"])]
    ch = cw * H / W
    cx = np.clip(cx, cw / 2, sw - cw / 2)
    cy = np.clip(cy, ch / 2, sh - ch / 2)
    mx = cx + u * cw
    my = cy + v * ch

    amp, zone = sc["wind"]
    if amp:
        if zone == "bottom":
            a = smooth((v + 0.2) / 0.7)
        elif zone == "top":
            a = smooth((0.1 - v) / 0.6)
        else:
            a = np.ones_like(v)
        gust = 0.65 + 0.35 * np.sin(lt * 0.9) * np.sin(lt * 0.37 + 1.0)
        dx = (np.sin(2 * np.pi * (0.35 * lt + mx / 70.0 + my / 140.0))
              + 0.5 * np.sin(2 * np.pi * (0.61 * lt + mx / 23.0))) * amp * a * gust
        dy = 0.35 * np.sin(2 * np.pi * (0.28 * lt + mx / 55.0)) * amp * a * gust
        mx = mx + dx
        my = my + dy

    mx = mx.astype(np.float32)
    my = my.astype(np.float32)
    out = cv2.remap(img, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    name = sc["name"]

    if name == "wheat":
        # breathing sun flare near the sun (source ~ (415,100))
        sx = (415 - cx) / cw + 0.5
        sy = (100 - cy) / ch + 0.5
        d = np.sqrt(((xx / W - sx) * W / H) ** 2 + (yy / H - sy) ** 2)
        pulse = 0.85 + 0.15 * np.sin(lt * 1.3)
        glow = np.exp(-(d / 0.22) ** 2) * 0.28 * pulse
        streak = np.exp(-((yy / H - sy) / 0.012) ** 2) * np.exp(-((xx / W - sx) / 0.35) ** 2) * 0.10
        out += (glow + streak)[..., None] * np.array([0.35, 0.72, 1.0], np.float32)
        out *= (0.94 + 0.08 * tex("flare", lt * 12, lt * 4))[..., None]

    elif name == "olive":
        dap = tex("dapple", lt * W * 0.012, lt * W * 0.004)
        lum = cv2.cvtColor(np.clip(out, 0, 1), cv2.COLOR_BGR2GRAY)
        k = 0.22 * smooth((lum - 0.25) / 0.5)
        out *= (1 + k * (dap - 0.5) * 2)[..., None]

    elif name == "lemon":
        sea_m = cv2.remap(lemon_sea, mx, my, cv2.INTER_LINEAR)
        tw_ = tex("twinkle", lt * W * 0.01, lt * W * 0.02)
        sp = sea_m * smooth((tw_ - 0.55) / 0.35) * 0.55
        out += cv2.GaussianBlur(sp, (0, 0), W / 480)[..., None] * np.array([0.8, 0.95, 1.0], np.float32)

    elif name == "matera":
        lm = cv2.remap(matera_lights, mx, my, cv2.INTER_LINEAR)
        gm = cv2.remap(matera_glow, mx, my, cv2.INTER_LINEAR)
        on = 0.35 + 0.65 * smooth((lt - 1.2) / 4.0)
        flick = 0.97 + 0.03 * np.sin(lt * 7.0 + xx / 37.0)
        out = out * (1 - lm * (1 - on))[..., None]
        out += (gm * 0.35 * on * flick)[..., None] * np.array([0.25, 0.6, 1.0], np.float32)
        # fading daylight -> deeper blue hour
        dusk = smooth(lt / sc["dur"])
        out *= (1 - 0.18 * dusk * (1 - lm))[..., None]
        out[..., 0] += 0.035 * dusk
        # drifting valley mist
        mist = tex("mist", lt * W * 0.018, lt * 3)
        mm = smooth((mist - 0.35) / 0.5) * smooth((v + 0.1) / 0.5) * 0.30
        out = out * (1 - mm[..., None]) + mm[..., None] * np.array([0.62, 0.55, 0.52], np.float32)

    elif name == "tomato":
        shd = tex("shadow", lt * W * 0.010, -lt * W * 0.003)
        s = smooth((shd - 0.45) / 0.4) * 0.18
        out *= (1 - s)[..., None]
        out += ((1 - s) * 0.03)[..., None] * np.array([0.2, 0.5, 1.0], np.float32)

    return out


# ---------------------------------------------------------------- grading
vign = 1 - 0.55 * smooth((np.sqrt((u * 1.1) ** 2 + v ** 2) - 0.25) / 0.55)
vign = vign[..., None].astype(np.float32)
haze_col = np.array([0.30, 0.45, 0.62], np.float32)  # warm amber (BGR)


def grade(img, fi):
    img = np.clip(img, 0, 1.3)
    img = img / (1 + 0.25 * img)          # soft highlight roll-off
    img = img * 1.25
    lum = cv2.cvtColor(np.clip(img, 0, 1), cv2.COLOR_BGR2GRAY)[..., None]
    img = lum + (img - lum) * 0.88          # no oversaturation
    img = img * np.array([0.93, 0.99, 1.04], np.float32)  # amber/terracotta
    img = img * 0.93 + 0.035 * np.array([0.35, 0.55, 0.8], np.float32)  # lifted brown blacks
    img = img + haze_col * 0.05 * (1 - lum)                 # atmospheric haze
    img = img * vign
    # soft organic 35mm grain
    g = rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32)
    g = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)
    g += rng.normal(0, 0.6, (H, W)).astype(np.float32)
    img = img + (g * 0.022 * (0.6 + 0.8 * lum[..., 0] * (1 - lum[..., 0]) * 2))[..., None]
    return np.clip(img, 0, 1)


def weight(sc, t):
    lt = (t - sc["start"]) % T
    if lt > sc["dur"]:
        return 0.0, lt
    w = min(smooth(lt / XF), smooth((sc["dur"] - lt) / XF))
    return float(w), lt


def main():
    out_path = HERE / f"italia_loop_{H}p.mp4"
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "20" if H >= 1080 else "22",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-tune", "grain", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for fi in range(N):
        t = fi / FPS
        acc = np.zeros((H, W, 3), np.float32)
        tot = 0.0
        for sc in SCENES:
            w, lt = weight(sc, t)
            if w > 0:
                acc += render_scene(sc, lt) * w
                tot += w
        frame = grade(acc / max(tot, 1e-6), fi)
        proc.stdin.write((frame * 255 + 0.5).astype(np.uint8).tobytes())
        if fi % 48 == 0:
            print(f"{fi}/{N}", flush=True)
    proc.stdin.close()
    proc.wait()
    print(out_path)


if __name__ == "__main__":
    main()
