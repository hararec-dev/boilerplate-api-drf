from pathlib import Path

from decouple import config

STATIC_URL = config("STATIC_URL", default="static/")
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "media"
