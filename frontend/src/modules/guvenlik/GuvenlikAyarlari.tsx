// Güvenlik ayarları bölümü — Ayarlar sayfasına bir sekme/kart olarak takılır.
//
// Eylemler: yönetici parolasını değiştir / "Kilitle" / kurtarma anahtarı çıktısını
// yeniden al. Yönetici parolası zorunludur ve YALNIZ kurulum sihirbazının ilk
// adımında kurulur (kurtarma anahtarı orada gösterilir ve saklandığı doğrulanır);
// bu ekranda "parolayı kur" ya da "parolayı kaldır" eylemi YOKTUR (tasarım §6.3).
// Parola kurulmamışsa (kurulum kapısı bunu zaten sihirbaza yönlendirir) yalnız
// sihirbaza giden bağlantı gösterilir. Metinler `metinler.ts`'ten gelir ve
// DÜRÜSTTÜR: bu koruma alan şifrelemesidir, tam disk şifrelemesi değildir.

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import KurtarmaCiktisiKarti from "./KurtarmaCiktisiKarti";
import SifreliYedekleme from "./SifreliYedekleme";
import YedektenGeriYukleme from "./YedektenGeriYukleme";
import { guvenlikApi } from "./api";
import type { GuvenlikDurumu } from "./api";
import { kilitOlayiYayinla } from "./GuvenlikKapisi";
import { KAPSAM_DISI_METNI, KAPSAM_METNI, YARIM_GECIS_METNI } from "./metinler";

function hataMesaji(err: unknown, varsayilan: string): string {
  return err instanceof Error && err.message ? err.message : varsayilan;
}

export default function GuvenlikAyarlari() {
  const snackbar = useSnackbar();
  const [durum, setDurum] = useState<GuvenlikDurumu | null>(null);
  const [degistirAcik, setDegistirAcik] = useState(false);
  const [parola, setParola] = useState("");
  const [parolaTekrar, setParolaTekrar] = useState("");
  const [yeniParola, setYeniParola] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

  const oku = useCallback(() => {
    guvenlikApi
      .durum()
      .then(setDurum)
      .catch(() => snackbar.error("Güvenlik durumu okunamadı."));
  }, [snackbar]);

  useEffect(() => oku(), [oku]);

  function kapat() {
    setDegistirAcik(false);
    setParola("");
    setParolaTekrar("");
    setYeniParola("");
    setHata(null);
  }

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    if (parolaTekrar !== yeniParola) {
      setHata("Parolalar eşleşmedi.");
      return;
    }
    setCalisiyor(true);
    try {
      await guvenlikApi.parolaDegistir(parola, yeniParola);
      snackbar.success("Yönetici parolası değiştirildi.");
      kapat();
      oku();
    } catch (err) {
      setHata(hataMesaji(err, "İşlem tamamlanamadı."));
    } finally {
      setCalisiyor(false);
    }
  }

  async function kilitle() {
    try {
      await guvenlikApi.kilitle();
      kilitOlayiYayinla();
    } catch (err) {
      snackbar.error(hataMesaji(err, "Kilitlenemedi."));
    }
  }

  if (durum === null) return <SkeletonList rows={2} />;

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-6">
        <div className="mb-2 flex items-center gap-3">
          <Icon name={durum.password_set ? "lock" : "lock_open"} className="text-primary" />
          <h2 className="text-title-large text-on-surface">
            {durum.password_set ? "Kişisel veri alanları şifreli" : "Yönetici parolası kurulmadı"}
          </h2>
        </div>

        <p className="text-body-medium text-on-surface-variant">{KAPSAM_METNI}</p>
        <p className="mt-2 text-body-small text-on-surface-variant">{KAPSAM_DISI_METNI}</p>

        {durum.protected_fields.length > 0 && (
          <p className="mt-3 text-body-small text-on-surface-variant">
            <span className="text-label-large">Şifrelenen alanlar: </span>
            {durum.protected_fields.join(", ")}
          </p>
        )}

        {durum.transition_pending && (
          <p className="mt-3 rounded-shape-md bg-tertiary-container p-3 text-body-small text-on-tertiary-container">
            {YARIM_GECIS_METNI}
          </p>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-2">
          {durum.password_set ? (
            <>
              <Button variant="tonal" icon="key" onClick={() => setDegistirAcik(true)}>
                Parolayı değiştir
              </Button>
              <Button variant="outlined" icon="lock" onClick={kilitle}>
                Kilitle
              </Button>
            </>
          ) : (
            <>
              <p className="text-body-medium text-on-surface-variant">
                Yönetici parolası kurulum sihirbazının ilk adımında kurulur; kurtarma anahtarı da
                orada verilir.
              </p>
              <Link
                to="/kurulum"
                className="inline-flex items-center gap-1.5 text-label-large font-medium text-primary underline-offset-4 hover:underline"
              >
                Kurulum sihirbazına git
                <Icon name="arrow_forward" size="sm" />
              </Link>
            </>
          )}
        </div>
      </Card>

      {durum.password_set && <KurtarmaCiktisiKarti />}

      <SifreliYedekleme parolaKurulu={durum.password_set} />

      <YedektenGeriYukleme />

      <Dialog open={degistirAcik} onClose={kapat} title="Parolayı değiştir">
        <form onSubmit={gonder} className="flex flex-col gap-4">
          <TextField
            label="Mevcut parola"
            type="password"
            value={parola}
            onChange={(e) => setParola(e.target.value)}
            autoComplete="current-password"
            required
          />

          <TextField
            label="Yeni parola"
            type="password"
            value={yeniParola}
            onChange={(e) => setYeniParola(e.target.value)}
            autoComplete="new-password"
            helperText="En az 8 karakter."
            required
          />

          <TextField
            // Etiket "Yeni parola (tekrar)" DEĞİL: iki alanın adı aynı ön ekle
            // başladığında hem ekran okuyucuda hem testte ayrışmıyor.
            label="Parola (tekrar)"
            type="password"
            value={parolaTekrar}
            onChange={(e) => setParolaTekrar(e.target.value)}
            autoComplete="new-password"
            error={hata ?? undefined}
            required
          />

          <div className="flex justify-end gap-2">
            <Button variant="text" type="button" onClick={kapat}>
              Vazgeç
            </Button>
            <Button type="submit" disabled={calisiyor}>
              {calisiyor ? "Uygulanıyor…" : "Uygula"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
