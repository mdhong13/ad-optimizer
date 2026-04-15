from platforms.meta import MetaAds
from platforms.google_ads import GoogleAds
from config.settings import settings


def get_active_platforms():
    """설정된 플랫폼만 반환"""
    platforms = []
    meta = MetaAds()
    if meta.is_configured():
        platforms.append(meta)
    google = GoogleAds()
    if google.is_configured():
        platforms.append(google)
    return platforms
