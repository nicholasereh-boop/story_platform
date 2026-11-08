from dataclasses import dataclass


class ProviderUnavailable(Exception):
    """No reviewed, authorized download method is configured for this provider."""


@dataclass(frozen=True)
class FormatOption:
    key: str
    label: str
    content_type: str


class ProviderAdapter:
    provider = ""
    label = ""
    # Formats are only advertised by a concrete adapter after its permitted method is configured.
    formats = ()

    def is_configured(self) -> bool:
        return False

    def inspect(self, parsed_url):
        return {
            "provider": self.provider,
            "label": self.label,
            "download_available": False,
            "formats": [],
            "message": "No reviewed, permitted download integration is configured for this provider.",
        }

    def fetch(self, job, format_key: str, workdir: str, progress_callback=None):
        raise ProviderUnavailable(
            "Downloads are unavailable until a permitted provider integration is configured."
        )
