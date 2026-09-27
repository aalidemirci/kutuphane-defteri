// İstatistiğin ve okuma ödülü iç çıktısının dönem seçicisi (F10).
//
// Seçenekler: etkin ders yılı (sunucunun varsayılanı — boş sorgu), öbür ders yılları ve
// tarih aralığı. Ders yılının dönemi yıl sonu raporununkiyle AYNI kuraldır (sunucuda —
// `selectors_istatistik.istatistik_donemi`): ders yılının başından sonraki ders yılının
// başına dek. Ekran dönemin kendisini hesaplamaz; sunucunun döndürdüğü dönemi yazar.
//
// Tarih aralığı seçilince seçim hemen "aralık" olur (tarihler boş olabilir; çağıran eksik
// aralıkla istek atmaz). İstatistikte tarihler "Göster" denince uygulanır (yarım girilmiş
// tarih her tuşta istek atmasın); `aninda` verilirse (iç çıktının formu) yazıldıkça iletilir.

import { useEffect, useState } from "react";

import Button from "../../ui/Button";
import Select from "../../ui/Select";
import TextField from "../../ui/TextField";
import { okulApi } from "../okul/api";
import type { SchoolYear } from "../okul/api";
import type { DonemSecimi } from "./api";

/** Seçicinin değeri: "" etkin yıl, "yil-<kimlik>" ders yılı, "aralik" tarih aralığı. */
function secimDegeri(d: DonemSecimi): string {
  if (d.tur === "yil") return `yil-${d.yilId}`;
  if (d.tur === "aralik") return "aralik";
  return "";
}

/** Tarih aralığı eksik mi? (çağıran bu durumda istek atmaz) */
export function eksikAralik(d: DonemSecimi): boolean {
  return d.tur === "aralik" && (!d.bas || !d.son);
}

export default function DonemSecici({
  deger,
  onDegisti,
  aninda = false,
}: {
  deger: DonemSecimi;
  onDegisti: (d: DonemSecimi) => void;
  /** Tarihler yazıldıkça iletilir ("Göster" düğmesi yok). */
  aninda?: boolean;
}) {
  const [yillar, setYillar] = useState<SchoolYear[]>([]);
  const secim = secimDegeri(deger);
  const [bas, setBas] = useState(deger.tur === "aralik" ? deger.bas : "");
  const [son, setSon] = useState(deger.tur === "aralik" ? deger.son : "");

  useEffect(() => {
    let iptal = false;
    okulApi
      .listSchoolYears()
      .then((y) => {
        if (!iptal) setYillar(y);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  const etkin = yillar.find((y) => y.is_active) ?? null;
  const secenekler = [
    {
      value: "",
      label: etkin ? `${etkin.name} ders yılı (etkin)` : "Etkin ders yılı",
    },
    ...[...yillar]
      .filter((y) => !y.is_active)
      .sort((a, b) => b.start_date.localeCompare(a.start_date))
      .map((y) => ({ value: `yil-${y.id}`, label: `${y.name} ders yılı` })),
    { value: "aralik", label: "Tarih aralığı" },
  ];

  const sec = (v: string) => {
    if (v === "") onDegisti({ tur: "etkin" });
    else if (v === "aralik")
      onDegisti({ tur: "aralik", bas: aninda ? bas : "", son: aninda ? son : "" });
    else onDegisti({ tur: "yil", yilId: Number(v.slice(4)) });
  };

  const tarihYaz = (yeniBas: string, yeniSon: string) => {
    setBas(yeniBas);
    setSon(yeniSon);
    if (aninda) onDegisti({ tur: "aralik", bas: yeniBas, son: yeniSon });
  };

  return (
    <div className="flex flex-wrap items-end gap-3">
      <Select
        className="w-72"
        label="Dönem"
        value={secim}
        onChange={(e) => sec(e.target.value)}
        options={secenekler}
      />
      {secim === "aralik" && (
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (bas && son) onDegisti({ tur: "aralik", bas, son });
          }}
        >
          <TextField
            className="w-44"
            label="Başlangıç tarihi"
            type="date"
            value={bas}
            onChange={(e) => tarihYaz(e.target.value, son)}
          />
          <TextField
            className="w-44"
            label="Bitiş tarihi"
            type="date"
            value={son}
            onChange={(e) => tarihYaz(bas, e.target.value)}
          />
          {!aninda && (
            <Button type="submit" variant="tonal" icon="filter_alt" disabled={!bas || !son}>
              Göster
            </Button>
          )}
        </form>
      )}
    </div>
  );
}
