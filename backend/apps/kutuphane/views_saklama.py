"""Saklama ve anonimleştirme uçları (tasarım §6.4; F11) — İNCE görünümler, YALNIZ yönetici kipi.

| Uç | Ad | İş |
|---|---|---|
| `GET library/retention/` | `library-retention` | Ayarlar → Saklama: kural başına kişisiz aday sayıları, süreler, onay bekleme ve 6 ay sınırı, son tetik, yedeklerdeki kalıntı, önizlemenin parmak izi |
| `GET library/retention/persons/` | `library-retention-persons` | Kaydı silinecek kişiler (AD İÇERİR — yalnız yönetici kipinde, Türkçe sıralı) |
| `GET library/retention/price-reminders/` | `library-retention-price-reminders` | Bedel adımında bir yıldan uzun bekleyen dosyalar (yıllık hatırlatma listesi; kişisiz) |
| `POST library/retention/apply/` | `library-retention-apply` | `{password, digest}` — GERİ DÖNÜŞSÜZ tetik: önce `pre-anonim` yedeği, sonra tek işlem |
| `GET library/dashboard/retention/` | `library-dashboard-retention` | Genel Bakış kartları: aday sayısı, 6 ay uyarısı, bedel listesi sayısı |

Hiçbiri görevli kipi izin listesinde DEĞİLDİR (varsayılan kapalı — CLAUDE.md §2-4):
ara katman keser, görünüm bir kez daha keser (`YoneticiKipiGorunumu`). Tetik kişi
kaydı SİLER: `RequiresAdminPassword` taşır ve gövdede yönetici parolasını ister
(yanlışsa 400 + kademeli gecikme). Yanıtlar `Cache-Control: no-store`.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.kutuphane.serializers_saklama import (
    BedelHatirlatmasiSerializer,
    SaklamaTetikSerializer,
    SilinecekKisiSerializer,
)
from apps.kutuphane.services import saklama
from apps.kutuphane.views_ilisik import YoneticiKipiGorunumu
from apps.okul.permissions import RequiresAdminPassword
from apps.okul.services import app_password


def _yanit(veri: Any, durum_kodu: int = status.HTTP_200_OK) -> Response:
    yanit = Response(veri, status=durum_kodu)
    yanit["Cache-Control"] = "no-store"
    return yanit


class RetentionStatusView(YoneticiKipiGorunumu):
    """`GET library/retention/` — kişisiz durum ve önizleme (kayıt YAZMAZ)."""

    def get(self, request: Request) -> Response:
        return _yanit(saklama.durum())


class RetentionPersonsView(YoneticiKipiGorunumu):
    """`GET library/retention/persons/` — silinecek kişilerin adları (yönetici kipi)."""

    def get(self, request: Request) -> Response:
        return _yanit(SilinecekKisiSerializer(saklama.silinecek_kisiler(), many=True).data)


class RetentionPriceRemindersView(YoneticiKipiGorunumu):
    """`GET library/retention/price-reminders/` — yıllık hatırlatma listesi (kişisiz)."""

    def get(self, request: Request) -> Response:
        return _yanit(BedelHatirlatmasiSerializer(saklama.bedel_hatirlatmalari(), many=True).data)


class RetentionApplyView(YoneticiKipiGorunumu):
    """`POST library/retention/apply/` `{password, digest}` — onaylı, geri dönüşsüz tetik."""

    permission_classes = [RequiresAdminPassword]

    def post(self, request: Request) -> Response:
        istek = SaklamaTetikSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        try:
            app_password.verify_password(istek.validated_data["password"])
        except app_password.AppPasswordError as exc:
            raise serializers.ValidationError({"password": [str(exc)]}) from exc
        sonuc = saklama.tetikle(anahtar=istek.validated_data["digest"])
        return _yanit(
            {
                "ran_at": sonuc.run.ran_at,
                "backup_name": sonuc.run.backup_name,
                "summary": sonuc.ozet,
                "pre_migrate_removed": sonuc.run.pre_migrate_removed,
                "old_db_removed": sonuc.run.old_db_removed,
                "wal_truncated": sonuc.wal_bosaldi,
            }
        )


class DashboardRetentionView(YoneticiKipiGorunumu):
    """`GET library/dashboard/retention/` — Genel Bakış kartlarının kişisiz özeti."""

    def get(self, request: Request) -> Response:
        return _yanit(saklama.pano_ozeti())
