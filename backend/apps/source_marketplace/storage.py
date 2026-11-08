"""Private storage for source packages.

Packages live OUTSIDE MEDIA_ROOT and have no URL at all: the only way to get one is the authorised download endpoint
(views.PackageDownloadView), which checks the buyer on every request. The location is read from settings each time it
is used, so a test (or a deployment) can point it somewhere else without re-importing anything.
"""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivatePackageStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def base_location(self):
        return str(settings.MARKETPLACE_PRIVATE_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None  # never reachable by URL

    def url(self, name):
        raise ValueError("Source packages have no public URL. Use the authorised download endpoint.")

    def deconstruct(self):  # keeps migrations stable: no path baked into them
        return ("apps.source_marketplace.storage.PrivatePackageStorage", [], {})


def private_storage():
    return PrivatePackageStorage()
