"""Private storage for generated downloads: outside MEDIA_ROOT, no public URL, deleted when they expire."""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateDownloadStorage(FileSystemStorage):
    @property
    def base_location(self):
        return str(settings.VIDEO_TOOLS_PRIVATE_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None

    def url(self, name):
        raise ValueError("Downloads have no public URL. Use the authorised file endpoint.")


def private_storage():
    return PrivateDownloadStorage()
