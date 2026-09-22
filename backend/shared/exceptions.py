"""Standart API hata yanıtı — `{code, message, fields}` sözleşmesi (tasarım §4.3).

OYS `shared/exceptions.py`'den uyarlandı: AccessLog/yetki-reddi bölümleri
KALDIRILDI (hesapsız program — masadaki kişi ayrımı kiple yapılır, §4.4); gövde
dönüşümü AYNEN. FE `lib/api.ts` bu biçimi bekler:

    { "code": "validation_error", "message": "Türkçe açıklama", "fields": {...} }

Fail-closed şifreleme (§6.3-2/3): anahtar bellekte değilken şifreli alana yazma
girişimi (`shared.crypto.KeyMissingError`, alt sınıfı
`app_password.PasswordRequired` dahil) **409 `parola_gerekli`** olur. Parola
kuruluysa kilitli durum zaten ara katmanda (423) kesildiği için bu yanıt
pratikte "önce yönetici parolasını kurun" demektir.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from shared.crypto import KeyMissingError

# Sözleşme §2 — FE bu kodu tanır (kurulum sihirbazına yönlendirir). S105: hata kodu
# ve kullanıcı iletisidir, parola değil.
PASSWORD_REQUIRED_CODE = "parola_gerekli"  # noqa: S105
PASSWORD_REQUIRED_MESSAGE = (
    "Kişi kaydı için önce yönetici parolasını kurun (Kurulum Sihirbazı'nın ilk adımı)."  # noqa: S105
)


class PasswordRequiredResponse(APIException):
    """`KeyMissingError`'ın DRF karşılığı: 409 `parola_gerekli` (işlem geri alınır)."""

    status_code = status.HTTP_409_CONFLICT
    default_code = PASSWORD_REQUIRED_CODE
    default_detail = PASSWORD_REQUIRED_MESSAGE


# Django/DRF'in kayıt-bulunamadı metinleri İngilizcedir ve model adını sızdırır
# ("No ExamSession matches the given query."). Sözleşme Türkçe mesaj
# ister; view'ın kendi verdiği Türkçe detay ("Kayıt bulunamadı.") korunur.
_GENERIC_NOT_FOUND = "Kayıt bulunamadı."

# Alan adı OLMADAN anlamsız kalan DRF varsayılanları ("Bu alan zorunlu."). Bunlar
# `message`'a taşınmaz; form alanının altında (`fields`) gösterilmeleri gerekir.
_CONTEXT_FREE_CODES = frozenset({"required", "null", "blank", "empty"})


def _is_default_not_found_detail(message: str) -> bool:
    """Mesaj, kullanıcıya gösterilmeyecek DRF/Django varsayılanı mı?"""
    return message.startswith("No ") or message in {"Not found.", str(NotFound.default_detail)}


def _explanatory_messages(value: Any) -> list[str]:
    """Alan hata ağacından, alan adı olmadan da ANLAŞILIR mesajları sırayla toplar.

    Ağaç iç içe sözlük/liste olabilir (çoklu kayıt serializer'ları). Yapraklar
    DRF `ErrorDetail`'dir; `code`'u bağlamsız varsayılanlardan olanlar atlanır.
    """
    if isinstance(value, dict):
        return [m for item in value.values() for m in _explanatory_messages(item)]
    if isinstance(value, list | tuple):
        return [m for item in value for m in _explanatory_messages(item)]
    if getattr(value, "code", None) in _CONTEXT_FREE_CODES:
        return []
    text = str(value).strip()
    return [text] if text else []


def _service_error(exc: Exception) -> DjangoValidationError | None:
    """Hatanın kaynağı servis katmanının Django `ValidationError`'ı mı?

    Ya doğrudan o fırlatılmıştır ya da view onu `raise DRF… from exc` ile
    çevirmiştir (`__cause__`). Serializer'ın kendi alan hataları bu yoldan GEÇMEZ.
    """
    if isinstance(exc, DjangoValidationError):
        return exc
    cause = exc.__cause__
    return cause if isinstance(cause, DjangoValidationError) else None


def kd_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF varsayılan hata gövdesini sözleşme biçimine dönüştürür."""
    if isinstance(exc, KeyMissingError):
        # DRF APIException'a çevrilir: böylece DRF işlemi geri alınacak diye
        # işaretler (`set_rollback`) ve gövde aşağıdaki ortak yoldan kurulur.
        # Hatanın kendi metni (iç ayrıntı) yankılanmaz; sözleşme metni gider.
        converted_key = PasswordRequiredResponse()
        converted_key.__cause__ = exc
        exc = converted_key
    service_error = _service_error(exc)
    if isinstance(exc, DjangoValidationError):
        # Servis katmanı Django `ValidationError` fırlatır; DRF onu TANIMAZ (handler
        # None döner → 500). View'ların çoğu elle çevirir ama unutulan her yol
        # kullanıcıya "sunucu hatası" olarak yansıyordu (A5: okul ayarında geçersiz
        # ders saati → 500). Çeviri merkezîdir; rollback'i DRF handler'ı işaretler.
        detail: Any = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        converted = DRFValidationError(detail)
        converted.__cause__ = exc
        exc = converted
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    # Http404 bir APIException değildir → `default_code` taşımaz; DRF onu içeride
    # NotFound'a çevirdiği için sözleşme kodunu burada elle veriyoruz.
    code = "not_found" if isinstance(exc, Http404) else getattr(exc, "default_code", "error")
    # DRF doğrulama hatalarının generic kodu "invalid"; sözleşme `validation_error`
    # ister. Özel exception'ların kendi kodu (not_found, parse_error vb.) korunur.
    if code == "invalid":
        code = "validation_error"
    fields: dict[str, Any] = {}
    message = "İşlem gerçekleştirilemedi."

    if isinstance(data, dict):
        if "detail" in data:
            message = str(data["detail"])
            if code == "not_found" and _is_default_not_found_detail(message):
                message = _GENERIC_NOT_FOUND
        else:
            # Alan-bazlı doğrulama hataları. Servis katmanının alan sözlüğüyle
            # verdiği ret ("on_date": "Yerleştirilemez: … 4 sınava girmiş olurdu")
            # snackbar'da GÖRÜNMELİDİR: arayüz `message`'ı basar, genel cümle asıl
            # gerekçeyi yutuyordu. Serializer'ın KENDİ retleri de ("Bu küme zaten
            # kayıtlı.", "Bitiş tarihi başlangıçtan sonra olmalıdır.") aynı yoldan
            # görünür; yalnız alan adı olmadan anlamsız kalan varsayılanlar
            # ("Bu alan zorunlu.") genel cümlede kalır.
            fields = data
            message = "Gönderilen veride hatalar var."
            if service_error is not None:
                message = "; ".join(str(m) for m in service_error.messages) or message
            else:
                explained = list(dict.fromkeys(_explanatory_messages(data)))
                if explained:
                    message = " ".join(explained)
    elif isinstance(data, list):
        message = "; ".join(str(item) for item in data)

    response.data = {"code": code, "message": message, "fields": fields}
    return response
