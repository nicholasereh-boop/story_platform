"""Fake reviewed adapters for the video tools tests."""
import os

from apps.video_tools.services.providers import AdapterError, DownloadAdapter, FetchResult


class OkAdapter(DownloadAdapter):
    provider = "youtube"
    method = "Test adapter: official export of the uploader's own video."
    formats = [{"key": "mp4", "label": "MP4 video"}, {"key": "mp3", "label": "Audio only"}]
    configured = True

    def is_configured(self):
        return self.configured

    def fetch(self, job, format_key, workdir):
        path = os.path.join(workdir, "out.bin")
        with open(path, "wb") as f:
            f.write(b"FAKEVIDEO" * 100)
        return FetchResult(path, "../../My Video?.mp4", "video/mp4")


class RefusingAdapter(OkAdapter):
    def fetch(self, job, format_key, workdir):
        raise AdapterError("The uploader has not allowed downloads.", "not_permitted")


class CrashingAdapter(OkAdapter):
    def fetch(self, job, format_key, workdir):
        raise RuntimeError("secret internal detail https://internal.example/token=abc")


class EscapingAdapter(OkAdapter):
    def fetch(self, job, format_key, workdir):
        return FetchResult("/etc/hostname", "x.mp4")


class OversizeAdapter(OkAdapter):
    def fetch(self, job, format_key, workdir):
        path = os.path.join(workdir, "big.bin")
        with open(path, "wb") as f:
            f.write(b"x" * 5000)
        return FetchResult(path, "big.mp4")


class WrongProviderAdapter(OkAdapter):
    provider = "tiktok"
