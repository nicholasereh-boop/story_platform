import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def local_cache(settings):
    """Tests must not need Redis: use an in-memory cache, emptied before every test (throttle counters live there)."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()
    yield
    cache.clear()


PASSWORD = "Correct-horse-battery-9"


@pytest.fixture
def password():
    return PASSWORD


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(email="reader@example.com", password=PASSWORD)


@pytest.fixture
def staff(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(email="staff@example.com", password=PASSWORD, is_staff=True)


def register_payload(email="new@example.com", **extra):
    return {"email": email, "password": PASSWORD, "display_name": "Nia", **extra}


@pytest.fixture
def staff_client(staff):
    c = APIClient()
    c.force_authenticate(staff)
    return c


@pytest.fixture
def superuser(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_superuser(email="boss@example.com", password=PASSWORD)


@pytest.fixture
def superuser_client(superuser):
    c = APIClient()
    c.force_authenticate(superuser)
    return c
