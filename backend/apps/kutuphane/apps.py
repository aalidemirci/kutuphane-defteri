"""Kütüphane uygulama tanımı.

F1'de modeli YOKTUR: yalnız katalog Excel şablonu ve sütun sözlüğü buradadır
(tasarım §8.1 "Şablon ve sütun sözlüğü F1'de sabitlenir"). Eser, nüsha, edinim,
bölüm ve sayaç modelleri F2'de OYS `apps/kutuphane`'den uyarlanarak gelir
(tasarım §6.2, §12).
"""

from __future__ import annotations

from django.apps import AppConfig


class KutuphaneConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.kutuphane"
    verbose_name = "Kütüphane"
