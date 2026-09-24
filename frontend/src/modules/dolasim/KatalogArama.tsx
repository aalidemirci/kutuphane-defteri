// Görevli ekranında katalog okuma (tasarım §4.4 tablosu: "works ve copies GET, ağ
// kataloğunun alan listesine denk serializer ile"). Masadaki görevli "şu kitap var
// mı, rafta mı?" sorusunu yanıtlar: künye, yer numarası, bölüm ve nüshaların durumu.
// Edinim, fiyat, bağışçı, eski kayıt no ve etiket bilgisi görevliye gelmez (sunucu
// yanıtı daraltır); kimin ödüncünde olduğu hiçbir kipte burada yoktur.
//
// Sorgu parametreleri görevli kipinde sınırlıdır (ara katman: `q`, `limit`,
// `offset`; nüshada `work`) — başka bir parametre 403 alır, bu ekran göndermez.

import { useState } from "react";
import type { FormEvent } from "react";

import { formatNumber } from "../../lib/format";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import PaginationBar from "../../ui/PaginationBar";
import TextField from "../../ui/TextField";
import { KATALOG_SAYFA_BOYUTU, katalogOkumaApi } from "./api";
import type { GorevliEser, GorevliNusha } from "./api";

export const KATALOG_ARAMA_BASLIGI = "Katalogda Ara";

export default function KatalogArama() {
  const [arama, setArama] = useState("");
  const [sorgu, setSorgu] = useState("");
  const [sayfa, setSayfa] = useState<Paginated<GorevliEser> | null>(null);
  const [offset, setOffset] = useState(0);
  const [secili, setSecili] = useState<GorevliEser | null>(null);
  const [nushalar, setNushalar] = useState<GorevliNusha[] | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [yukleniyor, setYukleniyor] = useState(false);

  async function getir(q: string, yeniOffset: number) {
    setYukleniyor(true);
    setHata(null);
    try {
      setSayfa(await katalogOkumaApi.eserAra(q, yeniOffset));
      setOffset(yeniOffset);
      setSorgu(q);
    } catch (e) {
      setHata(hataOku(e, "Katalog aranamadı."));
    } finally {
      setYukleniyor(false);
    }
  }

  async function ac(eser: GorevliEser) {
    setSecili(eser);
    setNushalar(null);
    try {
      setNushalar((await katalogOkumaApi.nushalar(eser.id)).results);
    } catch (e) {
      setHata(hataOku(e, "Nüshalar yüklenemedi."));
    }
  }

  function gonder(e: FormEvent) {
    e.preventDefault();
    if (!arama.trim()) return;
    setSecili(null);
    void getir(arama.trim(), 0);
  }

  return (
    <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <form onSubmit={gonder} className="flex flex-wrap items-end gap-2">
        <TextField
          className="min-w-[16rem] flex-1"
          label="Kaynak adı, yazar, konu ya da ISBN"
          value={arama}
          onChange={(e) => setArama(e.target.value)}
          autoFocus
        />
        <Button type="submit" icon="search" disabled={yukleniyor || !arama.trim()}>
          Ara
        </Button>
      </form>
      {hata && <ErrorBand hata={hata} />}
      {sayfa !== null &&
        (sayfa.results.length === 0 ? (
          <EmptyState compact icon="search_off" title="Aramaya uyan kaynak bulunamadı." />
        ) : (
          <>
            <ul aria-label="Arama sonuçları" className="divide-y divide-outline-variant/60">
              {sayfa.results.map((eser) => (
                <li key={eser.id} className="py-2">
                  <button
                    type="button"
                    className="w-full rounded-shape-sm px-2 py-1 text-left hover:bg-on-surface/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    onClick={() => void ac(eser)}
                    aria-expanded={secili?.id === eser.id}
                  >
                    <span className="block text-title-small text-on-surface">{eser.title}</span>
                    <span className="block text-body-small text-on-surface-variant">
                      {[eser.authors, eser.call_number, eser.section_name]
                        .filter(Boolean)
                        .join(" · ")}
                      {" · rafta "}
                      {formatNumber(eser.available_copy_count)} / {formatNumber(eser.copy_count)}
                    </span>
                  </button>
                  {secili?.id === eser.id && <NushaListesi nushalar={nushalar} />}
                </li>
              ))}
            </ul>
            <PaginationBar
              count={sayfa.count}
              offset={offset}
              pageSize={KATALOG_SAYFA_BOYUTU}
              onOffset={(yeni) => void getir(sorgu, yeni)}
            />
          </>
        ))}
    </Card>
  );
}

function NushaListesi({ nushalar }: { nushalar: GorevliNusha[] | null }) {
  if (nushalar === null) {
    return <p className="px-2 text-body-small text-on-surface-variant">Nüshalar yükleniyor…</p>;
  }
  if (nushalar.length === 0) {
    return <p className="px-2 text-body-small text-on-surface-variant">Nüsha yok.</p>;
  }
  return (
    <ul aria-label="Nüshalar" className="mt-1 space-y-0.5 px-2 text-body-small">
      {nushalar.map((n) => (
        <li key={n.id} className="text-on-surface">
          {[n.section_name, n.status_display].filter(Boolean).join(" · ")}
          {n.status === "AVAILABLE" && n.not_loanable_reason && ` · ${n.not_loanable_reason}`}
        </li>
      ))}
    </ul>
  );
}
