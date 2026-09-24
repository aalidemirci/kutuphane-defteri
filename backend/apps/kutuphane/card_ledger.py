"""Verilmiş kart numaralarının geri yüklemeden etkilenmeyen defteri (tasarım §7.1, D21).

**Neden var?** "Kart no asla yeniden kullanılmaz" değişmezini veritabanında
`IssuedCard` sağlar. Ama yedekten geri yükleme bütün veritabanı dosyasını takas
eder: yedekten SONRA verilmiş kartların satırları da geri sarılır. O kartlar basılıp
dağıtılmışsa öğrencilerin elinde kalır; sonraki bir üyeliğe aynı numara çekilirse
eldeki eski kart masada yeni üyeye çözülür ve ödünç onun adına yazılırdı (F6
düzeltme turu).

**Nasıl?** Her verilen numaranın kör indeksi, veritabanının yanındaki (veri
dizini — `guvenlik.json` ile aynı yer) yalnız-eklenen bir metin dosyasına da
yazılır. Geri yükleme bu dosyaya dokunmaz. `services.memberships.issue_card_number`
yeni numarayı HEM `IssuedCard`'a HEM bu deftere karşı denetler.

**Kişisel veri değildir.** Dosyada yalnız kör indeksler (HMAC-SHA256, anahtar
DEK'ten türer; 64 onaltılık hane) vardır: ad, kart no ya da tarih yoktur, anahtar
olmadan numaraya geri çevrilemez. DEK parola değişiminde değişmediği için indeksler
kalıcıdır.

**Hata yolu.** Defter okunamaz ya da yazılamazsa kart yine verilir (asıl güvence
veritabanındaki `IssuedCard`'dır; defter geri yüklemeye karşı ek güvencedir) ve
günlüğe yalnız olay yazılır. Bozuk satırlar atlanır. İşlem geri sarılırsa defterde
fazladan bir indeks kalır: o numara hiç verilmemiş olsa da bir daha verilmez —
zararsızdır.

**Kalan risk** (teknik borç TB33): veri dizini de kaybolup program yeni bir
bilgisayara yedekten kurulursa defter yoktur; o zaman yedekten sonra verilmiş kartlar
için güvence yalnız olasılıktır (10⁶'lık uzayda rastgele numara).
"""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path

from apps.okul.services import app_password

logger = logging.getLogger("kutuphane_defteri.kutuphane")

#: Defter dosyasının adı (veri dizininde, `db.sqlite3` ve `guvenlik.json`'un yanında).
LEDGER_FILE_NAME = "verilmis-kartlar.txt"

_INDEKS = re.compile(r"^[0-9a-f]{64}$")
_kilit = threading.Lock()


def ledger_path() -> Path:
    """Defterin yolu — güvenlik dosyasının dizini (paketli kipte veri dizini)."""
    return app_password.state_path().parent / LEDGER_FILE_NAME


def issued_indexes() -> set[str]:
    """Defterdeki bütün kör indeksler; dosya yoksa ya da okunamazsa boş küme."""
    yol = ledger_path()
    with _kilit:
        try:
            metin = yol.read_text(encoding="ascii", errors="replace")
        except FileNotFoundError:
            return set()
        except OSError:
            logger.warning("Verilmiş kart defteri okunamadı; yalnız veritabanına bakılıyor.")
            return set()
    return {satir.strip() for satir in metin.splitlines() if _INDEKS.match(satir.strip())}


def contains(card_no_index: str) -> bool:
    """Bu kör indeks daha önce verilmiş bir kartın mı?"""
    return card_no_index in issued_indexes()


def record(card_no_index: str) -> None:
    """Kör indeksi deftere ekler (dosya sonuna, diske zorlanarak)."""
    if not _INDEKS.match(card_no_index):
        raise ValueError("Kör indeks 64 onaltılık hane olmalıdır.")
    yol = ledger_path()
    with _kilit:
        try:
            yol.parent.mkdir(parents=True, exist_ok=True)
            with yol.open("a", encoding="ascii", newline="\n") as dosya:
                dosya.write(f"{card_no_index}\n")
                dosya.flush()
                os.fsync(dosya.fileno())
        except OSError:
            logger.warning("Verilmiş kart defterine yazılamadı; kart veritabanına kaydedildi.")
