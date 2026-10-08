"""Wily's Windows icon (08/10, the installer): the site's icon (site_wily.ICON: a dark rounded square, a blue ring, an
orange crosshair) drawn at 1024 px and scaled down, saved as installer/wily.ico with the sizes Windows asks for."""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))


def draw(n=1024):
    k = n / 64   # the SVG's 64-unit box
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=12 * k, fill="#0d1117")
    r, w = 17 * k, 5 * k   # the ring: radius 17, stroke 5
    d.ellipse([32 * k - r - w / 2, 32 * k - r - w / 2, 32 * k + r + w / 2, 32 * k + r + w / 2], outline="#5aa9ff", width=round(w))
    for x0, y0, x1, y1 in ((32, 6, 32, 20), (32, 44, 32, 58), (6, 32, 20, 32), (44, 32, 58, 32)):   # the crosshair, round caps
        d.line([x0 * k, y0 * k, x1 * k, y1 * k], fill="#f0b23a", width=round(w))
        for x, y in ((x0, y0), (x1, y1)):
            d.ellipse([x * k - w / 2, y * k - w / 2, x * k + w / 2, y * k + w / 2], fill="#f0b23a")
    return im


if __name__ == "__main__":
    im = draw()
    out = os.path.join(HERE, "wily.ico")
    im.resize((256, 256), Image.LANCZOS).save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    im.resize((256, 256), Image.LANCZOS).save(os.path.join(HERE, "wily-256.png"))
    print(out, os.path.getsize(out), "bytes")
