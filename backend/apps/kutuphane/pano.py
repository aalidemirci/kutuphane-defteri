"""Genel Bakış'ın dolaşım kartları: gecikmiş ödünç sayısı ve beklenmedik kapanış (A11, T15).

- **Gecikmiş ödünç sayısı** kişisizdir (yalnız sayı); liste yönetici kipindeki
  "Gecikmiş Ödünçler" sayfasındadır (A11). Pano uçları görevli kipi izin
  listesinde DEĞİLDİR: görevli kipinde Genel Bakış zaten açılmaz.
- **Beklenmedik kapanış** (T15): masaüstü kabuğu önceki oturumun temiz kapanış
  işaretini okur ve sonucu `KD_ONCEKI_OTURUM` ile taşır
  (`desktop/clean_shutdown.py`). Önceki oturum düzensiz bittiyse (elektrik
  kesintisi, zorla sonlandırma) WAL'deki son işlemler kaybolmuş olabilir; kart
  "son oturumdaki ödünç ve iadeleri kontrol edin" der ve diske yazılmış son
  işlemleri listeler (`selectors_dolasim.recent_transactions`).
- **"Kontrol ettim"** kartı bu oturum için kapatır. Onay SÜREÇ İÇİNDEDİR (dosyaya
  ya da veritabanına yazılmaz): bu oturum temiz kapanırsa sonraki açılışta kart
  zaten çıkmaz; yine düzensiz biterse yeniden çıkması doğrudur.
"""

from __future__ import annotations

import threading

from apps.kutuphane import selectors_dolasim

_kilit = threading.Lock()
_kapanis_onaylandi = False


def unexpected_shutdown_pending() -> bool:
    """Beklenmedik kapanış kartı gösterilsin mi? (önceki oturum düzensiz + bu oturumda onaylanmadı)"""
    with _kilit:
        onaylandi = _kapanis_onaylandi
    return not onaylandi and selectors_dolasim.previous_session_unexpected()


def acknowledge_unexpected_shutdown() -> None:
    """'Kontrol ettim': kart bu oturum boyunca gösterilmez."""
    global _kapanis_onaylandi
    with _kilit:
        _kapanis_onaylandi = True


def reset_for_tests() -> None:
    """Yalnız testler: onayı sıfırlar."""
    global _kapanis_onaylandi
    with _kilit:
        _kapanis_onaylandi = False


def circulation_summary() -> dict[str, object]:
    """Pano kartlarının kişisiz özeti."""
    return {
        "overdue_count": selectors_dolasim.overdue_count(),
        "unexpected_shutdown": unexpected_shutdown_pending(),
    }
