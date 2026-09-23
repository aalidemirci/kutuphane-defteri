// Künye önerisinin alan listesi — ISBN ile künye getirme (U13, tasarım §8.5) ve
// çevrimdışı künye dosyası aynı bileşeni kullanır.
//
// ÜÇ KURAL BURADA GÖRÜNÜR OLUR (§8.5-5, §8.5-10):
//   1. Onaysız yazma yok: her alanın kendi onay kutusu vardır, kutu işaretli
//      değilse o alan gönderilmez. Sunucu zaten hiçbir şey yazmaz; öneri döner.
//   2. Dolu alan sessizce ezilmez: eserde değer varsa kutu İŞARETSİZ gelir ve
//      satır mevcut değeri de gösterir — kullanıcı farkı görerek karar verir.
//   3. Konum dili: her alanın yanında kaynak ve tarih etiketi ("Bakanlık
//      kataloğu, 23.09.2026") ve "dış kaynaktan alındı, doğrulayın" rozeti durur.
//      Program künyeyi "resmî" ya da doğrulanmış diye sunmaz.
//
// Çevirmen alanı listede HİÇ YOKTUR ve olmayacaktır (kaynaklar çevirmeni
// yazardan ayırmıyor); önerinin kendi uyarı satırı bunu söyler, ön yüz ikinci
// bir kopya yazmaz.

import Icon from "../../ui/Icon";
import type { KunyeAlani, WorkBody } from "./api";

/** Alan seçimi: alan adı → yazılsın mı. */
export type KunyeSecimi = Record<string, boolean>;

/**
 * Varsayılan seçim: DOLU OLMAYAN alanlarda işaretli gelir.
 *
 * "Dolu alan sessizce üzerine yazılmaz" kuralının somut hâli budur: eserde
 * değer varsa kutu işaretsizdir, kullanıcı bilerek işaretlemedikçe yazılmaz.
 */
export function varsayilanSecim(alanlar: KunyeAlani[]): KunyeSecimi {
  const secim: KunyeSecimi = {};
  for (const alan of alanlar) {
    secim[alan.alan] = alan.deger !== null && alan.deger !== "" && !alan.dolu;
  }
  return secim;
}

/** Seçili alanları eser gövdesine çevirir (bilinmeyen alan adı SESSİZCE düşer). */
const YAZICILAR: Record<string, (govde: Partial<WorkBody>, deger: string | number) => void> = {
  title: (g, v) => {
    g.title = String(v);
  },
  authors: (g, v) => {
    g.authors = String(v);
  },
  publisher: (g, v) => {
    g.publisher = String(v);
  },
  edition: (g, v) => {
    g.edition = String(v);
  },
  publish_year: (g, v) => {
    g.publish_year = Number(v);
  },
  isbn: (g, v) => {
    g.isbn = String(v);
  },
  subjects: (g, v) => {
    g.subjects = String(v);
  },
  classification_code: (g, v) => {
    g.classification_code = String(v);
  },
  call_number: (g, v) => {
    g.call_number = String(v);
  },
  language: (g, v) => {
    g.language = String(v);
  },
};

/**
 * Seçili ve DOLU önerileri eser gövdesine çevirir.
 *
 * Yazıcı sözlüğü bilinçlidir: sunucu yeni bir alan eklerse ön yüz onu sessizce
 * `Work`'e yazmaz — önce burada karşılığı tanımlanır. Boş öneri hiçbir zaman
 * gönderilmez ("bulunamadı" bir değer değildir, mevcut değeri silmemelidir).
 */
export function kunyeGovdesi(alanlar: KunyeAlani[], secim: KunyeSecimi): Partial<WorkBody> {
  const govde: Partial<WorkBody> = {};
  for (const alan of alanlar) {
    if (!secim[alan.alan]) continue;
    if (alan.deger === null || alan.deger === "") continue;
    YAZICILAR[alan.alan]?.(govde, alan.deger);
  }
  return govde;
}

/** Yazılacak alan var mı? (düğmeyi açan tek soru) */
export function secilenAlanVar(alanlar: KunyeAlani[], secim: KunyeSecimi): boolean {
  return Object.keys(kunyeGovdesi(alanlar, secim)).length > 0;
}

function deger(v: string | number | null): string {
  return v === null || v === "" ? "—" : String(v);
}

export default function KunyeAlanlari({
  alanlar,
  secim,
  onSecim,
  kaynakEtiketi,
  rozet,
  uyarilar = [],
  baslik = "Künye önerisi",
}: {
  alanlar: KunyeAlani[];
  secim: KunyeSecimi;
  onSecim: (alan: string, secili: boolean) => void;
  /** "Bakanlık kataloğu, 23.09.2026" — sunucuda biçimlenir. */
  kaynakEtiketi: string;
  /** "Dış kaynaktan alındı, doğrulayın" (docs/sozluk.md). */
  rozet: string;
  uyarilar?: string[];
  baslik?: string;
}) {
  const yazilabilir = alanlar.filter((a) => a.deger !== null && a.deger !== "");
  if (yazilabilir.length === 0) {
    return (
      <p className="text-body-medium text-on-surface-variant">
        Bu kaynakta doldurulabilecek alan bulunamadı; künyeyi elle yazabilirsiniz.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-label-large text-on-surface">{baslik}</p>
        {rozet && (
          <span className="inline-flex items-center gap-1 rounded-full bg-tertiary-container px-2 py-0.5 text-label-medium text-on-tertiary-container">
            <Icon name="travel_explore" size="sm" />
            {rozet}
          </span>
        )}
      </div>

      {uyarilar.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-body-small text-on-surface-variant">
          {uyarilar.map((uyari) => (
            <li key={uyari}>{uyari}</li>
          ))}
        </ul>
      )}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-body-small">
          <thead>
            <tr className="border-b border-outline-variant text-left text-label-medium text-on-surface-variant">
              <th className="p-2">Yazılsın</th>
              <th className="p-2">Alan</th>
              <th className="p-2">Gelen değer</th>
              <th className="p-2">Kayıttaki değer</th>
              <th className="p-2">Kaynak</th>
            </tr>
          </thead>
          <tbody>
            {yazilabilir.map((alan) => (
              <tr key={alan.alan} className="border-t border-outline-variant/50">
                <td className="p-2">
                  <label className="flex min-h-11 items-center gap-2">
                    <input
                      type="checkbox"
                      checked={secim[alan.alan] ?? false}
                      onChange={(e) => onSecim(alan.alan, e.target.checked)}
                      className="size-5 shrink-0 accent-primary"
                      aria-label={`${alan.etiket} alanını yaz`}
                    />
                  </label>
                </td>
                <td className="p-2 text-on-surface">{alan.etiket}</td>
                <td className="p-2 text-on-surface">{deger(alan.deger)}</td>
                <td className="p-2 text-on-surface-variant">
                  {deger(alan.mevcut_deger)}
                  {alan.dolu && alan.farkli && (
                    <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-tertiary-container px-2 py-0.5 text-label-small text-on-tertiary-container">
                      <Icon name="warning" size="sm" />
                      Bu alan dolu
                    </span>
                  )}
                </td>
                <td className="p-2 text-on-surface-variant">{kaynakEtiketi}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
