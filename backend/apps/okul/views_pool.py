"""Ayrılış havuzu uçları (F1 eki 7; tasarım §6.1, §8.3) — İNCE görünümler.

Kullanıcı kararı (22.09.2026): e-Okul aktarımı kimseyi ayırmaz ve silmez;
listede bulunmayan aktif kişi ayrılış havuzuna girer, karar burada verilir.

- `GET leave-pool/` — havuzdaki öğrenciler ve personel AYRI listeler, TR
  sıralı, adlarla (yönetim yüzeyi). `?summary=true` yalnız sayıları döner
  (Genel Bakış kartı; kişisel veri yok). Kişi YAZMAZ.
- `POST leave-pool/resolve/` — toplu karar: `{students: {leave, keep},
  personnel: {leave, keep}}`. Kişi yazar → `RequiresAdminPassword` (parola
  kurulmadan 409 `parola_gerekli`).

İkisi de görevli kipinin izin listesinde YOKTUR (varsayılan kapalı, 403
`kip_yetkisiz`): karar yönetici işidir.
"""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.okul import selectors
from apps.okul.permissions import RequiresAdminPassword
from apps.okul.serializers import (
    LeavePoolPersonnelSerializer,
    LeavePoolResolveSerializer,
    LeavePoolStudentSerializer,
)
from apps.okul.services import persons as persons_service

_TRUE_VALUES = frozenset({"true", "1"})


class LeavePoolView(APIView):
    """`GET leave-pool/` — ayrılış kararı bekleyen kişiler (ya da `?summary=true` sayılar)."""

    def get(self, request: Request) -> Response:
        if request.query_params.get("summary", "").strip().lower() in _TRUE_VALUES:
            return Response(selectors.leave_pool_counts())
        ogrenciler = selectors.leave_pool_students()
        personel = selectors.leave_pool_personnel()
        benzerler = selectors.leave_pool_similar_personnel(personel)
        return Response(
            {
                "student_count": len(ogrenciler),
                "personnel_count": len(personel),
                "students": LeavePoolStudentSerializer(ogrenciler, many=True).data,
                "personnel": LeavePoolPersonnelSerializer(
                    personel, many=True, context={"similar": benzerler}
                ).data,
            }
        )


class LeavePoolResolveView(APIView):
    """`POST leave-pool/resolve/` — "Ayrıldı olarak işaretle" / "Aktif kalsın" (tek işlem).

    Yanıt: uygulanan sayılar + havuzda kalan sayılar. Seçilen kişi artık havuzda
    değilse hiçbir karar uygulanmaz (400, liste yenilenmeli).
    """

    permission_classes = [RequiresAdminPassword]

    def post(self, request: Request) -> Response:
        req = LeavePoolResolveSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        ogrenci = req.validated_data.get("students") or {}
        personel = req.validated_data.get("personnel") or {}
        sonuc = persons_service.resolve_leave_pool(
            students=persons_service.PoolDecision(
                leave=tuple(ogrenci.get("leave", ())), keep=tuple(ogrenci.get("keep", ()))
            ),
            personnel=persons_service.PoolDecision(
                leave=tuple(personel.get("leave", ())), keep=tuple(personel.get("keep", ()))
            ),
        )
        return Response({**sonuc, **selectors.leave_pool_counts()})
