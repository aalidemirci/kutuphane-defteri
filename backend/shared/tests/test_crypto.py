"""`shared.crypto` birim testleri — fail-closed alan, kör indeks (T14), anahtar sayacı.

DB istemez: alan davranışı `get_prep_value` üzerinden, kör indeks doğrudan
sınanır. Varsayılan ortam `backend/conftest.py`'dedir (anahtar `TEST_DEK` yüklü).
"""

from __future__ import annotations

import hmac
import re
from hashlib import sha256
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from conftest import TEST_DEK
from shared import crypto

_ALAN = crypto.EncryptedCharField("ad", max_length=100)


# ---------------------------------------------------------------------------
# Fail-closed şifreli alan (§6.3-3)
# ---------------------------------------------------------------------------
def test_anahtar_yokken_bos_olmayan_deger_yazilmaz(kilitli: Path) -> None:
    with pytest.raises(crypto.KeyMissingError):
        _ALAN.get_prep_value("EMRE")


def test_anahtar_yokken_bos_dize_ve_none_serbest(kilitli: Path) -> None:
    assert _ALAN.get_prep_value("") == ""
    assert _ALAN.get_prep_value(None) is None


def test_anahtar_varken_token_yazilir_ve_cozulur() -> None:
    token = _ALAN.get_prep_value("EMRE")
    assert token is not None and token.startswith("gAAAA")
    assert "EMRE" not in token
    assert _ALAN.from_db_value(token, None, None) == "EMRE"


def test_kilitliyken_okuma_tokeni_oldugu_gibi_dondurur() -> None:
    token = _ALAN.get_prep_value("EMRE")
    crypto.unload_key()
    assert _ALAN.from_db_value(token, None, None) == token


def test_key_missing_error_runtime_error_alt_sinifidir() -> None:
    """Servis `ValueError` çevirisi (400) onu yutmamalı: 409'a giden yol ayrıdır."""
    assert issubclass(crypto.KeyMissingError, RuntimeError)
    assert not issubclass(crypto.KeyMissingError, ValueError)


# ---------------------------------------------------------------------------
# Kör indeks (T14)
# ---------------------------------------------------------------------------
def test_kor_indeks_belirlenimci_ve_64_haneli() -> None:
    ilk = crypto.blind_index("1234")
    assert ilk == crypto.blind_index("1234")
    assert re.fullmatch(r"[0-9a-f]{64}", ilk)
    assert crypto.blind_index("1235") != ilk


def test_kor_indeks_tasarimdaki_formulle_hesaplanir() -> None:
    """HMAC-SHA256(HKDF-SHA256(DEK, salt=None, info="kd-kor-indeks", 32), değer)."""
    anahtar = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"kd-kor-indeks").derive(
        TEST_DEK
    )
    beklenen = hmac.new(anahtar, "Öğrenci-42".encode(), sha256).hexdigest()
    assert crypto.blind_index("Öğrenci-42") == beklenen


def test_kor_indeks_farkli_dekte_farklidir() -> None:
    ilk = crypto.blind_index("1234")
    crypto.load_key(b"\x07" * 32)
    assert crypto.blind_index("1234") != ilk


def test_kor_indeks_yeniden_yuklemede_ayni_kalir() -> None:
    """Anahtar yalnız DEK'e bağlıdır (parola değişimi DEK'i değiştirmez; uçtan uca
    kanıtı `test_app_password.py::test_kor_indeks_parola_degisiminden_sonra_ayni_kalir`)."""
    ilk = crypto.blind_index("1234")
    crypto.unload_key()
    crypto.load_key(TEST_DEK)
    assert crypto.blind_index("1234") == ilk


def test_kor_indeks_bos_dizede_bos_doner(kilitli: Path) -> None:
    assert crypto.blind_index("") == ""


def test_kor_indeks_kilitliyken_key_missing_error(kilitli: Path) -> None:
    with pytest.raises(crypto.KeyMissingError):
        crypto.blind_index("1234")


def test_kor_indeks_normallestirme_yapmaz() -> None:
    """Normalleştirme çağıranın işidir: "0123" ile "123" farklı indeks verir."""
    assert crypto.blind_index("0123") != crypto.blind_index("123")


# ---------------------------------------------------------------------------
# Anahtar sayacı (kip katmanı yeni kilit açılışını buradan anlar)
# ---------------------------------------------------------------------------
def test_key_epoch_yukleme_ve_bosaltmada_artar() -> None:
    ilk = crypto.key_epoch()
    crypto.unload_key()
    assert crypto.key_epoch() == ilk + 1
    crypto.load_key(TEST_DEK)
    assert crypto.key_epoch() == ilk + 2
    crypto.load_key(TEST_DEK)  # aynı anahtarın yeniden yüklenmesi de yeni açılıştır
    assert crypto.key_epoch() == ilk + 3


def test_kaldirilan_duz_yazma_araclari_yoktur() -> None:
    for ad in ("plaintext_writes", "writes_encrypted"):
        assert not hasattr(crypto, ad), ad
    assert not hasattr(crypto._holder, "_encrypt_writes")
