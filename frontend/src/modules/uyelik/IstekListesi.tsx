// Kişiler → Üyelik İstek Listesi (F6; tasarım §9-2, Md. 17/1 "üye olmak isteyen").
// Şube seçilir, şubedeki aktif öğrenciler sınıf listesi sırasıyla gelir; kütüphane
// yöneticisi yalnız üye olmak isteyenleri işaretler ve "Seçilenleri üye yap" ile tek
// işlemde üyelik açar (ya hepsi ya hiçbiri: listede biri bu arada üye olduysa ya da
// ayrıldıysa hiçbir üyelik açılmaz, liste yenilenir). Liste kimseyi üye YAPMAZ;
// e-Okul aktarımı da üyelik açmaz. Yeni kartlar "Kart Basımı" sekmesine düşer.

import { useCallback, useEffect, useState } from "react";

import { formatNumber, todayIso } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { uyelikApi } from "./api";
import type { MembershipRequestRow } from "./api";
import { SatirSecimi, subeOku, TD, TH, TumunuSec, useSubeSecenekleri } from "./ortak";

export default function IstekListesi() {
  const subeler = useSubeSecenekleri();
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const [sube, setSube] = useState("");
  const [satirlar, setSatirlar] = useState<MembershipRequestRow[]>([]);
  const [secim, setSecim] = useState<Set<number>>(new Set());
  const [istekTarihi, setIstekTarihi] = useState(todayIso());
  const [yukleniyor, setYukleniyor] = useState(false);
  const [mesgul, setMesgul] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);

  const yenile = useCallback(() => setTazeleme((k) => k + 1), []);

  useEffect(() => {
    const { classLevel, classSection } = subeOku(sube);
    if (classLevel === null) {
      setSatirlar([]);
      return;
    }
    let iptal = false;
    setYukleniyor(true);
    uyelikApi
      .istekListesi(classLevel, classSection)
      .then((s) => {
        if (iptal) return;
        setSatirlar(s);
        setSecim(new Set());
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Şubenin öğrenci listesi yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [sube, tazeleme]);

  const uyeOlmayanlar = satirlar.filter((s) => !s.is_member).map((s) => s.student_id);
  const uyeSayisi = satirlar.length - uyeOlmayanlar.length;

  const uygula = async () => {
    const kimlikler = [...secim];
    if (kimlikler.length === 0) return;
    const tamam = await confirm({
      title: `${formatNumber(kimlikler.length)} öğrenciye üyelik açılsın mı?`,
      message:
        "Her öğrenciye yeni bir kart numarası verilir ve kartları “Kart Basımı” sekmesinde basılmayı bekler. Üyelik isteğe bağlıdır: yalnız üye olmak isteyenleri seçtiğinizden emin olun.",
      confirmLabel: "Üyelik aç",
    });
    if (!tamam) return;
    setMesgul(true);
    setHata(null);
    try {
      const acilan = await uyelikApi.istekleriUygula(kimlikler, istekTarihi || undefined);
      snackbar.success(`${formatNumber(acilan.length)} öğrenciye üyelik açıldı.`);
      yenile();
    } catch (e) {
      setHata(hataOku(e, "Üyelikler açılamadı."));
      yenile();
    } finally {
      setMesgul(false);
    }
  };

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <p className="max-w-4xl text-body-medium text-on-surface-variant">
        Üyelik isteğe bağlıdır (Okul Kütüphaneleri Yönetmeliği Md. 17/1). Şubeyi seçin, üye olmak
        isteyen öğrencileri işaretleyin ve seçilenleri üye yapın. Liste kimseyi kendiliğinden üye
        yapmaz.
      </p>
      <Card
        elevation={0}
        className="flex flex-wrap items-end gap-3 p-[var(--kd-panel-padding)] shadow-elevation-1"
      >
        <Select
          className="w-44"
          label="Şube"
          placeholder="Seçin"
          value={sube}
          onChange={(e) => setSube(e.target.value)}
          options={subeler}
        />
        <TextField
          className="w-48"
          type="date"
          label="Üyelik isteği tarihi"
          value={istekTarihi}
          max={todayIso()}
          onChange={(e) => setIstekTarihi(e.target.value)}
          helperText="Öğrencilerin üyelik istediği gün."
        />
        <Button
          icon="how_to_reg"
          onClick={() => void uygula()}
          disabled={secim.size === 0 || mesgul}
        >
          Seçilenleri üye yap
          {secim.size > 0 ? ` (${formatNumber(secim.size)})` : ""}
        </Button>
      </Card>

      {hata && <ErrorBand hata={hata} />}

      {sube === "" ? (
        <EmptyState
          icon="groups"
          title="Şube seçin"
          description="Şubedeki öğrenciler ve üyelik durumları burada listelenir."
        />
      ) : yukleniyor ? (
        <SkeletonList rows={5} />
      ) : satirlar.length === 0 ? (
        <EmptyState icon="groups" title="Bu şubede aktif öğrenci yok." />
      ) : (
        <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <p className="text-body-small text-on-surface-variant">
            {formatNumber(satirlar.length)} öğrenci · {formatNumber(uyeSayisi)} üye
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-body-small">
              <caption className="sr-only">Şubenin üyelik istek listesi</caption>
              <thead>
                <tr className="border-b border-outline-variant">
                  <th className={TH}>
                    <TumunuSec
                      kimlikler={uyeOlmayanlar}
                      secim={secim}
                      onSecim={setSecim}
                      etiket="Üye olmayanların tümünü seç"
                    />
                  </th>
                  <th className={TH}>Okul no</th>
                  <th className={TH}>Ad soyad</th>
                  <th className={TH}>Sınıf</th>
                  <th className={TH}>Üyelik</th>
                </tr>
              </thead>
              <tbody>
                {satirlar.map((s) => (
                  <tr key={s.student_id} className="border-t border-outline-variant/50">
                    <td className={TD}>
                      <SatirSecimi
                        id={s.student_id}
                        etiket={`${s.full_name} seç`}
                        secim={secim}
                        onSecim={setSecim}
                        disabled={s.is_member}
                      />
                    </td>
                    <td className={TD}>{s.student_number || "—"}</td>
                    <td className={TD}>{s.full_name}</td>
                    <td className={TD}>{s.class_label}</td>
                    <td className={TD}>
                      {s.is_member ? (
                        <span className="rounded-full bg-secondary-container px-2 py-0.5 text-label-medium text-on-secondary-container">
                          Üye
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
