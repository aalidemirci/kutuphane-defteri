"""Kütüphane uygulama tanımı.

Katalog çekirdeği (F2): bölüm, eser, nüsha, edinim, komisyon kararı, bağış ön
kaydı, politika ve numara sayacı — OYS `apps/kutuphane`'den uyarlanarak
(tasarım §6.2, §12). Katalog Excel şablonu ve sütun sözlüğü F1'den gelir
(tasarım §8.1); içe aktarımın kendisi F3'tedir.

Üyelik, ödünç, teslim, ayıklama ve sayım modelleri BURADA DEĞİLDİR: kendi
fazlarında (F6-F9) eklenir.
"""

from __future__ import annotations

from django.apps import AppConfig


class KutuphaneConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.kutuphane"
    verbose_name = "Kütüphane"
