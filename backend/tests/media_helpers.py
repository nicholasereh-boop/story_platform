"""Helpers that build real images in memory for the media tests."""
import os
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}


def image_bytes(fmt="JPEG", size=(40, 30), color=(200, 30, 30), **save_kwargs):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, fmt, **save_kwargs)
    return buf.getvalue()


def make_image(fmt="JPEG", size=(40, 30), name=None, content_type=None, color=(200, 30, 30), **save_kwargs):
    return SimpleUploadedFile(
        name or f"photo{EXT[fmt]}", image_bytes(fmt, size, color, **save_kwargs), content_type=content_type or MIME[fmt]
    )


def noisy_png(side=60, name="noise.png"):
    """Incompressible image: a few KB, used to exceed a tiny size limit."""
    img = Image.frombytes("RGB", (side, side), os.urandom(side * side * 3))
    buf = BytesIO()
    img.save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def animated_gif(frames=3):
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    imgs = [Image.new("RGB", (20, 20), colors[i % 4]) for i in range(frames)]
    buf = BytesIO()
    imgs[0].save(buf, "GIF", save_all=True, append_images=imgs[1:], duration=100, loop=0)
    return SimpleUploadedFile("anim.gif", buf.getvalue(), content_type="image/gif")


def jpeg_with_exif(size=(40, 30), orientation=6):
    """A JPEG carrying EXIF (orientation, camera make and, best effort, GPS)."""
    exif = Image.Exif()
    exif[0x0112] = orientation
    exif[0x010F] = "SpyCam"
    try:
        gps = exif.get_ifd(0x8825)
        gps[1], gps[2], gps[3], gps[4] = "N", (51.0, 30.0, 0.0), "W", (0.0, 7.0, 0.0)
    except Exception:  # GPS writing differs between Pillow versions; the other tags still prove the point
        pass
    buf = BytesIO()
    Image.new("RGB", size, (10, 120, 200)).save(buf, "JPEG", exif=exif)
    return SimpleUploadedFile("camera.jpg", buf.getvalue(), content_type="image/jpeg")


def flat_png(size, name="flat.png"):
    """A huge but tiny-on-disk image (1-bit), for the pixel-limit tests without using much memory."""
    buf = BytesIO()
    Image.new("1", size).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")
