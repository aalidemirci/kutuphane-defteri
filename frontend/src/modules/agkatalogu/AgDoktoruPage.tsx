// Ağ Doktoru (tasarım §5.9) — yalnız yönetici kipinde açılır (görevli kipinde
// KipKapisi rotanın yerine görevli ekranını koyar; uçlar da 403 döner).
//
// Gösterdikleri: Ağ Kataloğu açık mı, port, aday IP'ler ve etkin arayüzler,
// güvenlik duvarı denetiminin beş maddesi, ağ profili, katalog adresi ve QR
// kodu, son hata ve kişisiz günlük sayılar. "Dinleyici bu arayüzde ayakta" öz
// sınaması UYARI METNİYLE gösterilir (güvenlik duvarını ya da VLAN'ı kanıtlamaz)
// ve başka bilgisayar için hazır `Test-NetConnection` komutu verilir (GA-5).
//
// Düğmeler: Kuralı ekle/güncelle (UAC) · Afişi bas · Yer imi dosyalarını üret ·
// PYS talep metnini kopyala · Ağ Hizmeti Bilgi Notu.
//
// Katalog bağlantısı LAN adresiyle kurulur ve harici tarayıcıda açılır
// (`target="_blank"`; §4.1: 127.0.0.1 kullanılmaz, çerezler portlar arasında
// yalıtılmaz). Yönetim portu hiçbir yerde gösterilmez.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { formatDateTime } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import ErrorBand from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { panoyaKopyala } from "../kutuphane/KopruKomutuKarti";
import {
  AFIS_BELGE_ADI,
  AG_DOKTORU_BASLIGI,
  AG_KATALOGU_SEKMESI,
  BILGI_NOTU_BELGE_ADI,
  MADDE_DURUMU_TR,
  SAYAC_TR,
  YER_IMI_BELGE_ADI,
  agKataloguApi,
  agProfiliAdi,
  belgeDosyaAdi,
  katalogKapatilabilir,
  kuralProfiliAdi,
} from "./api";
import type {
  AgDurumu,
  DinleyiciSinamasi,
  GuvenlikDuvari,
  IpAdaylari,
  KatalogEylemi,
  MaddeDurumu,
} from "./api";
import { DurumRozeti, KomutKutusu, MasaustuYokBandi, QrKodu, useAgDurumu } from "./ortak";

/** "Dinleyici ayakta" sınamasının yanında HER ZAMAN duran uyarı (tasarım §5.9, birebir). */
export const DINLEYICI_UYARISI =
  "Güvenlik duvarını ya da VLAN'ı kanıtlamaz. Makinenin kendi IP'sine yapılan bağlantı loopback'ten geçer. Başka bir bilgisayardan deneyin.";

const MADDE_IKONU: Record<MaddeDurumu, { ad: string; renk: string }> = {
  gecti: { ad: "check_circle", renk: "text-success" },
  kaldi: { ad: "cancel", renk: "text-error" },
  uyari: { ad: "warning", renk: "text-tertiary" },
  bilinmiyor: { ad: "help", renk: "text-on-surface-variant" },
};

const BOS_ADAYLAR: IpAdaylari = {
  arayuzler: [],
  varsayilan_ip: null,
  yonlendirme_acik: false,
  uyarilar: [],
  kaynak: "yok",
};

function hataMetni(e: unknown, yedek: string): string {
  return e instanceof ApiError && e.message ? e.message : yedek;
}

function BolumBasligi({ ikon, children }: { ikon: string; children: string }) {
  return (
    <h2 className="flex items-center gap-2 text-title-medium text-on-surface">
      <Icon name={ikon} size="lg" className="text-primary" />
      {children}
    </h2>
  );
}

// ---------------------------------------------------------------------------
// Katalog durumu
// ---------------------------------------------------------------------------

function DurumKarti({
  durum,
  mesgul,
  onEylem,
  onYenile,
}: {
  durum: AgDurumu;
  mesgul: boolean;
  onEylem: (eylem: KatalogEylemi) => void;
  onYenile: () => void;
}) {
  const katalog = durum.katalog;
  const sayaclar = durum.sayaclar.bugun;
  const sonHata = katalog?.son_hata ?? durum.sayaclar.son_hata?.ileti ?? null;
  // Açılamayan (engellendi/hata/bekliyor) ama ayarı açık katalog da kapatılabilir:
  // ayar açık kaldıkça program her açılışta yeniden dener.
  const kapatilabilir = katalog?.durum === "acik" || katalogKapatilabilir(katalog);
  return (
    <Card elevation={1} className="space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <BolumBasligi ikon="lan">Katalog Durumu</BolumBasligi>
        {katalog && <DurumRozeti durum={katalog.durum} />}
      </div>
      {!durum.masaustu && <MasaustuYokBandi />}
      {katalog && (
        <div className="grid gap-4 md:grid-cols-[1fr_auto]">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-body-medium">
            <dt className="text-on-surface-variant">Port</dt>
            <dd className="text-on-surface">{katalog.port}</dd>
            <dt className="text-on-surface-variant">Dinleme</dt>
            <dd className="text-on-surface">
              {katalog.tum_arayuzler
                ? "Bütün ağ bağlantıları"
                : katalog.dinleme_ip
                  ? `Yalnız ${katalog.dinleme_ip}`
                  : "—"}
            </dd>
            <dt className="text-on-surface-variant">Katalog adresi</dt>
            <dd className="text-on-surface">
              {katalog.adres ? (
                <a
                  href={katalog.adres}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary underline underline-offset-2"
                >
                  {katalog.adres}
                </a>
              ) : (
                "Katalog açık değil"
              )}
            </dd>
            <dt className="text-on-surface-variant">Bugün</dt>
            <dd className="text-on-surface">
              {(["sayfa", "arama", "hiz_siniri"] as const)
                .map((olay) => `${sayaclar[olay] ?? 0} ${SAYAC_TR[olay]}`)
                .join(" · ")}
              {katalog.reddedilen_baglanti > 0 &&
                ` · ${katalog.reddedilen_baglanti} bağlantı sınırda kesildi`}
            </dd>
          </dl>
          {durum.qr && (
            <figure className="justify-self-start text-center md:justify-self-end">
              <QrKodu satirlar={durum.qr} boyutPx={112} />
              <figcaption className="mt-1 text-body-small text-on-surface-variant">
                Adres birincildir; QR ikincildir
              </figcaption>
            </figure>
          )}
        </div>
      )}
      {sonHata && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-shape-md bg-error-container px-4 py-3 text-body-medium text-on-error-container"
        >
          <Icon name="error" size="lg" className="mt-0.5 shrink-0" />
          <div>
            <p className="text-label-large">Son hata</p>
            <p>{sonHata}</p>
            {!katalog?.son_hata && durum.sayaclar.son_hata && (
              <p className="text-body-small">{formatDateTime(durum.sayaclar.son_hata.zaman)}</p>
            )}
          </div>
        </div>
      )}
      {katalog && katalog.uyarilar.length > 0 && (
        <ul className="space-y-1 text-body-medium text-on-surface">
          {katalog.uyarilar.map((uyari) => (
            <li key={uyari} className="flex items-start gap-2">
              <Icon name="warning" size="lg" className="mt-0.5 shrink-0 text-tertiary" />
              <span>{uyari}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        {kapatilabilir ? (
          <>
            <Button
              variant="outlined"
              icon="stop_circle"
              disabled={mesgul}
              onClick={() => onEylem("kapat")}
            >
              Ağ Kataloğunu kapat
            </Button>
            <Button
              variant="outlined"
              icon="restart_alt"
              disabled={mesgul}
              onClick={() => onEylem("yeniden_baslat")}
            >
              Yeniden başlat
            </Button>
          </>
        ) : (
          <Button
            icon="play_circle"
            disabled={mesgul || !durum.masaustu}
            onClick={() => onEylem("ac")}
          >
            Ağ Kataloğunu aç
          </Button>
        )}
        <Button variant="text" icon="refresh" disabled={mesgul} onClick={onYenile}>
          Yenile
        </Button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Güvenlik duvarı
// ---------------------------------------------------------------------------

function GuvenlikDuvariKarti({
  duvar,
  platform,
  masaustu,
  mesgul,
  onDenetle,
  onKural,
}: {
  duvar: GuvenlikDuvari | null;
  platform: AgDurumu["platform"];
  masaustu: boolean;
  mesgul: boolean;
  onDenetle: () => void;
  onKural: () => void;
}) {
  const linux = (duvar?.platform ?? platform) === "linux";
  const kurallar = duvar?.kurallar?.length ? duvar.kurallar : duvar?.kural ? [duvar.kural] : [];
  return (
    <Card elevation={1} className="space-y-4 p-6">
      <BolumBasligi ikon="shield">Güvenlik Duvarı</BolumBasligi>
      {linux ? (
        <div className="space-y-3 text-body-medium text-on-surface-variant">
          <p>
            Pardus'ta program güvenlik duvarı kuralı açmaz; paket hazır bir tanım bırakır. Kuralı
            BTR açar.
          </p>
          {duvar?.linux.arac ? (
            <>
              <p className="text-on-surface">
                Bu bilgisayardaki güvenlik duvarı: {duvar.linux.arac} (
                {duvar.linux.etkin === true
                  ? "etkin"
                  : duvar.linux.etkin === false
                    ? "kapalı"
                    : "durumu okunamadı"}
                )
              </p>
              {duvar.linux.komut && (
                <KomutKutusu komut={duvar.linux.komut} etiket="Güvenlik duvarı komutu" />
              )}
            </>
          ) : (
            duvar && <p>Bu bilgisayarda ufw ya da firewalld bulunamadı.</p>
          )}
        </div>
      ) : (
        <>
          <p className="text-body-medium text-on-surface-variant">
            Ağ Kataloğu okul ağına yalnız bu beş denetim geçerse açılır. Biri geçmezse katalog hiç
            dinlemez.
          </p>
          {duvar?.hata && <ErrorBand hata={duvar.hata} />}
          {duvar && duvar.maddeler.length > 0 ? (
            <ul aria-label="Güvenlik duvarı denetimi" className="space-y-2">
              {duvar.maddeler.map((madde) => {
                const ikon = MADDE_IKONU[madde.durum];
                return (
                  <li key={madde.kod} className="flex items-start gap-3">
                    <Icon name={ikon.ad} size="lg" className={`mt-0.5 shrink-0 ${ikon.renk}`} />
                    <div className="min-w-0">
                      <p className="text-label-large text-on-surface">
                        {madde.baslik}: {MADDE_DURUMU_TR[madde.durum]}
                      </p>
                      <p className="text-body-small text-on-surface-variant">{madde.aciklama}</p>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-body-medium text-on-surface-variant">
              {masaustu
                ? "Denetim henüz yapılmadı."
                : "Denetim yalnız masaüstü programında yapılır."}
            </p>
          )}
          {kurallar.length > 1 && (
            <p className="text-body-medium text-on-surface">
              Bu program için {kurallar.length} izin kuralı var; Windows herhangi birine uyan
              bağlantıyı kabul eder.
            </p>
          )}
          {kurallar.map((kural, sira) => (
            <dl
              key={`${kural.ad}-${sira}`}
              aria-label={`Güvenlik duvarı kuralı: ${kural.ad}`}
              className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-body-medium"
            >
              {kurallar.length > 1 && (
                <>
                  <dt className="text-on-surface-variant">Kural</dt>
                  <dd className="break-all text-on-surface">{kural.ad || "—"}</dd>
                </>
              )}
              <dt className="text-on-surface-variant">Uzak adres</dt>
              <dd className="break-all text-on-surface">
                {kural.uzak_adres
                  .map((a) =>
                    a.toLowerCase() === "localsubnet"
                      ? "Yerel alt ağ"
                      : a.toLowerCase() === "any"
                        ? "Her yer"
                        : a,
                  )
                  .join(", ") || "—"}
              </dd>
              <dt className="text-on-surface-variant">Kural profili</dt>
              <dd className="text-on-surface">{kuralProfiliAdi(kural.profil)}</dd>
            </dl>
          ))}
          {duvar && duvar.ag_profilleri.length > 0 && (
            <p className="text-body-medium text-on-surface">
              Ağ profili: {duvar.ag_profilleri.map(agProfiliAdi).join(", ")}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button icon="admin_panel_settings" disabled={mesgul || !masaustu} onClick={onKural}>
              Kuralı ekle/güncelle
            </Button>
            <Button
              variant="outlined"
              icon="fact_check"
              disabled={mesgul || !masaustu}
              onClick={onDenetle}
            >
              Yeniden denetle
            </Button>
          </div>
          <p className="text-body-small text-on-surface-variant">
            Kural güncellemesi Windows'un yönetici onayını (UAC) ister; kütüphane masası hesabında
            BTR'nin kimliği girilir. Kurala Ayarlar → Ağ Kataloğu'ndaki tahta ağı blokları da
            eklenir.
          </p>
        </>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Ağ bağlantıları ve dinleyici sınaması
// ---------------------------------------------------------------------------

function ArayuzlerKarti({ adaylar }: { adaylar: IpAdaylari | null }) {
  return (
    <Card elevation={1} className="space-y-4 p-6">
      <BolumBasligi ikon="settings_ethernet">Ağ Bağlantıları</BolumBasligi>
      {!adaylar ? (
        <p className="text-body-medium text-on-surface-variant">Ağ bağlantıları okunuyor…</p>
      ) : adaylar.arayuzler.length === 0 ? (
        <p className="text-body-medium text-on-surface-variant">
          Okul ağına bağlı bir IP adresi bulunamadı.
        </p>
      ) : (
        <table className="w-full text-left text-body-medium">
          <thead className="text-label-large text-on-surface-variant">
            <tr>
              <th className="py-1 pr-3 font-medium">Bağlantı</th>
              <th className="py-1 pr-3 font-medium">IP adresi</th>
              <th className="py-1 pr-3 font-medium">Ağ profili</th>
              <th className="py-1 font-medium">Not</th>
            </tr>
          </thead>
          <tbody>
            {adaylar.arayuzler.map((a) => (
              <tr key={a.ip} className="border-t border-outline-variant">
                <td className="py-1.5 pr-3 text-on-surface">{a.ad}</td>
                <td className="py-1.5 pr-3 text-on-surface">
                  {a.ip}/{a.onek}
                </td>
                <td className="py-1.5 pr-3 text-on-surface">{agProfiliAdi(a.ag_profili)}</td>
                <td className="py-1.5 text-on-surface-variant">
                  {[
                    a.varsayilan_rota ? "Varsayılan bağlantı" : null,
                    a.tahta_agi ? "Tahta ağı (öğrenci erişimli)" : null,
                    a.yonlendirme ? "IP yönlendirme açık" : null,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {adaylar && adaylar.uyarilar.length > 0 && (
        <ul className="space-y-1 text-body-medium text-on-surface">
          {adaylar.uyarilar.map((uyari) => (
            <li key={uyari} className="flex items-start gap-2">
              <Icon name="warning" size="lg" className="mt-0.5 shrink-0 text-tertiary" />
              <span>{uyari}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function SinamaKarti({
  sinama,
  port,
  ip,
  masaustu,
  mesgul,
  onSina,
}: {
  sinama: DinleyiciSinamasi | null;
  port: number | null;
  ip: string | null;
  masaustu: boolean;
  mesgul: boolean;
  onSina: () => void;
}) {
  const komutIp = ip ?? sinama?.sonuclar[0]?.ip ?? "<IP>";
  return (
    <Card elevation={1} className="space-y-4 p-6">
      <BolumBasligi ikon="network_check">Dinleyici Sınaması</BolumBasligi>
      <div
        role="note"
        className="flex items-start gap-2 rounded-shape-md bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container"
      >
        <Icon name="warning" size="lg" className="mt-0.5 shrink-0" />
        <span>{DINLEYICI_UYARISI}</span>
      </div>
      {sinama && !sinama.acik && (
        <p className="text-body-medium text-on-surface-variant">
          Ağ Kataloğu açık değil; sınanacak dinleyici yok.
        </p>
      )}
      {sinama && sinama.sonuclar.length > 0 && (
        <ul className="space-y-2">
          {sinama.sonuclar.map((s) => (
            <li key={s.ip} className="flex items-start gap-3 text-body-medium">
              <Icon
                name={s.ayakta ? "check_circle" : "cancel"}
                size="lg"
                className={`mt-0.5 shrink-0 ${s.ayakta ? "text-success" : "text-error"}`}
              />
              <span className="text-on-surface">
                {s.ad} ({s.ip}):{" "}
                {s.ayakta ? "dinleyici bu arayüzde ayakta" : "dinleyici bu arayüzde yanıt vermedi"}
              </span>
            </li>
          ))}
        </ul>
      )}
      <Button variant="outlined" icon="lan" disabled={mesgul || !masaustu} onClick={onSina}>
        Dinleyiciyi sına
      </Button>
      <div className="space-y-2">
        <p className="text-body-medium text-on-surface-variant">
          Asıl kanıt başka bir bilgisayardan alınır. Okul ağındaki başka bir Windows bilgisayarda
          PowerShell'i açıp şu komutu çalıştırın; “TcpTestSucceeded : True” görülmelidir:
        </p>
        <KomutKutusu
          komut={`Test-NetConnection ${komutIp} -Port ${port ?? "<port>"}`}
          etiket="Başka bilgisayar için sınama komutu"
        />
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Belgeler
// ---------------------------------------------------------------------------

function BelgelerKarti({
  adaylar,
  masaustu,
  seciliIp,
  onSec,
}: {
  adaylar: IpAdaylari | null;
  masaustu: boolean;
  seciliIp: string;
  onSec: (ip: string) => void;
}) {
  const snackbar = useSnackbar();
  const [calisan, setCalisan] = useState<string | null>(null);
  const [pysMetni, setPysMetni] = useState<string | null>(null);
  const ip = seciliIp.trim() || undefined;

  async function indir(ad: string, uzanti: string, uret: () => Promise<Blob>, ileti: string) {
    setCalisan(ad);
    try {
      saveBlob(await uret(), belgeDosyaAdi(ad, uzanti));
      snackbar.success(ileti);
    } catch (e) {
      snackbar.error(hataMetni(e, `${ad} üretilemedi.`));
    } finally {
      setCalisan(null);
    }
  }

  async function pysKopyala() {
    setCalisan("pys");
    try {
      const { metin } = await agKataloguApi.pysMetni(ip);
      if (await panoyaKopyala(metin)) {
        setPysMetni(null);
        snackbar.success("PYS talep metni panoya kopyalandı.");
      } else {
        setPysMetni(metin);
        snackbar.error("Metin kopyalanamadı; aşağıdaki kutudan seçip elle kopyalayın.");
      }
    } catch (e) {
      snackbar.error(hataMetni(e, "PYS talep metni hazırlanamadı."));
    } finally {
      setCalisan(null);
    }
  }

  return (
    <Card elevation={1} className="space-y-4 p-6">
      <BolumBasligi ikon="description">Belgeler</BolumBasligi>
      <p className="text-body-medium text-on-surface-variant">
        Afiş, yer imleri ve PYS talep metni bu bilgisayarın okul ağındaki adresini taşır. Adres
        değişirse afişi yeniden basın ve yer imlerini yeniden üretin.
      </p>
      {masaustu ? (
        <Select
          label="Belgelerde kullanılacak adres"
          value={seciliIp}
          onChange={(e) => onSec(e.target.value)}
          options={[
            { value: "", label: "Kendiliğinden (Ağ Kataloğunun adresi)" },
            ...(adaylar?.arayuzler ?? []).map((a) => ({ value: a.ip, label: `${a.ip} — ${a.ad}` })),
          ]}
        />
      ) : (
        <TextField
          label="Belgelerde kullanılacak adres"
          value={seciliIp}
          onChange={(e) => onSec(e.target.value)}
          helperText="Boş bırakılırsa Ayarlar → Ağ Kataloğu'ndaki adres kullanılır."
          inputMode="decimal"
        />
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          icon="print"
          disabled={calisan !== null}
          onClick={() =>
            void indir(
              AFIS_BELGE_ADI,
              "pdf",
              () => agKataloguApi.afis(ip),
              "Katalog afişi hazırlandı.",
            )
          }
        >
          Afişi bas
        </Button>
        <Button
          variant="outlined"
          icon="bookmark_add"
          disabled={calisan !== null}
          onClick={() =>
            void indir(
              YER_IMI_BELGE_ADI,
              "zip",
              () => agKataloguApi.yerImleri(ip),
              "Yer imi dosyaları hazırlandı.",
            )
          }
        >
          Yer imi dosyalarını üret
        </Button>
        <Button
          variant="outlined"
          icon="content_copy"
          disabled={calisan !== null}
          onClick={() => void pysKopyala()}
        >
          PYS talep metnini kopyala
        </Button>
        <Button
          variant="outlined"
          icon="assignment"
          disabled={calisan !== null}
          onClick={() =>
            void indir(
              BILGI_NOTU_BELGE_ADI,
              "pdf",
              () => agKataloguApi.bilgiNotu(ip),
              "Ağ Hizmeti Bilgi Notu hazırlandı.",
            )
          }
        >
          Ağ Hizmeti Bilgi Notu'nu bas
        </Button>
      </div>
      {pysMetni && (
        <label className="block space-y-1">
          <span className="text-label-large text-on-surface">PYS talep metni</span>
          <textarea
            readOnly
            value={pysMetni}
            rows={10}
            className="w-full rounded-shape-sm border border-outline-variant bg-surface-container-lowest p-3 text-body-small text-on-surface"
          />
        </label>
      )}
      <ul className="list-disc space-y-1 pl-5 text-body-small text-on-surface-variant">
        <li>
          Afişte adres büyük yazılır; QR kodu küçüktür ve ikincildir, çünkü okul bilgisayarları ve
          tahtalar QR okumaz.
        </li>
        <li>
          Yer imi dosyaları ETAP/Pardus tahtalar için Chromium yer imi politikası ve menü kısayolu,
          Windows bilgisayarlar için internet kısayolu içerir. Dağıtımı BTR yapar.
        </li>
        <li>
          PYS talep metni tahta ağından erişim kapalıysa kullanılır: talep “yerel ağ VLAN
          düzenlemesi” olarak yazılır; “internet ya da site açma” diye yazılırsa başka birime gider.
        </li>
        <li>
          Ağ Hizmeti Bilgi Notu BTR ve okul müdürü imzalar ve okulda saklanır; izin değil bilgi
          notudur.
        </li>
      </ul>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sayfa
// ---------------------------------------------------------------------------

export default function AgDoktoruPage() {
  const { durum, setDurum, hata, yenile } = useAgDurumu();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const [adaylar, setAdaylar] = useState<IpAdaylari | null>(null);
  const [duvar, setDuvar] = useState<GuvenlikDuvari | null>(null);
  const [sinama, setSinama] = useState<DinleyiciSinamasi | null>(null);
  const [seciliIp, setSeciliIp] = useState("");
  const [mesgul, setMesgul] = useState(false);
  const [ayarPortu, setAyarPortu] = useState<number | null>(null);
  const masaustu = durum?.masaustu ?? false;

  // Port ayardan da okunur: katalog kapalıyken (ya da masaüstü dışında) komut yine hazır olsun.
  useEffect(() => {
    let iptal = false;
    agKataloguApi
      .ayar()
      .then((a) => {
        if (!iptal) setAyarPortu(a.port);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  // Aday adresler masaüstü denetçisinden bir kez okunur (PowerShell; birkaç saniye sürebilir).
  useEffect(() => {
    if (!masaustu) return;
    let iptal = false;
    agKataloguApi
      .arayuzler()
      .then((sonuc) => {
        if (!iptal) setAdaylar(sonuc);
      })
      .catch(() => {
        if (!iptal) setAdaylar(BOS_ADAYLAR);
      });
    return () => {
      iptal = true;
    };
  }, [masaustu]);

  // Beş madde de açılışta bir kez okunur (§5.9 "gösterdikleri"); katalog hiç
  // açılmamışsa denetçide son denetim yoktur.
  useEffect(() => {
    if (!masaustu) return;
    let iptal = false;
    agKataloguApi
      .guvenlikDuvari()
      .then((sonuc) => {
        if (!iptal) setDuvar(sonuc);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, [masaustu]);

  async function eylem(ad: KatalogEylemi) {
    setMesgul(true);
    try {
      const sonuc = await agKataloguApi.eylem(ad);
      setDurum(sonuc);
      // Açma/yeniden başlatma denetimi yeniden yapar: artık durumdaki denetim geçerlidir.
      if (sonuc.katalog?.guvenlik_duvari) setDuvar(null);
      const yeni = sonuc.katalog?.durum;
      if (ad === "kapat") snackbar.success("Ağ Kataloğu kapatıldı.");
      else if (yeni === "acik")
        snackbar.success(ad === "ac" ? "Ağ Kataloğu açıldı." : "Ağ Kataloğu yeniden başlatıldı.");
      else snackbar.error(sonuc.katalog?.son_hata ?? "Ağ Kataloğu açılamadı.");
    } catch (e) {
      snackbar.error(hataMetni(e, "İşlem yapılamadı."));
    } finally {
      setMesgul(false);
    }
  }

  async function denetle() {
    setMesgul(true);
    try {
      setDuvar(await agKataloguApi.guvenlikDuvari());
    } catch (e) {
      snackbar.error(hataMetni(e, "Güvenlik duvarı denetlenemedi."));
    } finally {
      setMesgul(false);
    }
  }

  async function kuralGuncelle() {
    const onay = await confirm({
      title: "Güvenlik duvarı kuralı güncellensin mi?",
      message:
        "Windows yönetici onayı (UAC) isteyecek; kütüphane masası hesabında BTR'nin kimliği girilir. Kural yalnız yerel alt ağa ve Ayarlar'daki tahta ağı bloklarına izin verir.",
      confirmLabel: "Kuralı güncelle",
    });
    if (!onay) return;
    setMesgul(true);
    try {
      const sonuc = await agKataloguApi.kuralGuncelle();
      setDurum(sonuc.durum);
      if (sonuc.tamam) {
        snackbar.success(sonuc.ileti);
        setDuvar(await agKataloguApi.guvenlikDuvari());
      } else {
        snackbar.error(sonuc.ileti);
      }
    } catch (e) {
      snackbar.error(hataMetni(e, "Kural güncellenemedi."));
    } finally {
      setMesgul(false);
    }
  }

  async function sina() {
    setMesgul(true);
    try {
      setSinama(await agKataloguApi.dinleyiciSinamasi());
    } catch (e) {
      snackbar.error(hataMetni(e, "Dinleyici sınanamadı."));
    } finally {
      setMesgul(false);
    }
  }

  const katalog = durum?.katalog ?? null;
  const komutIp =
    seciliIp.trim() || katalog?.dinleme_ip || katalog?.guncel_ip || adaylar?.varsayilan_ip || null;

  return (
    <div className="space-y-6">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">{AG_DOKTORU_BASLIGI}</h1>
          <p className="kd-page-description">
            Ağ Kataloğunun okul ağına açılıp açılmadığını denetler: güvenlik duvarı, bu bilgisayarın
            ağ adresleri, dinleyici ve katalog belgeleri. Okulun bilişim teknolojileri rehber
            öğretmeniyle (BTR) birlikte kullanılmak üzere hazırlanmıştır. Ağ Kataloğunun ayarları{" "}
            <Link
              to={`/ayarlar?tab=${AG_KATALOGU_SEKMESI}`}
              className="text-primary underline underline-offset-2"
            >
              Ayarlar → Ağ Kataloğu
            </Link>{" "}
            bölümündedir.
          </p>
        </div>
      </div>

      {hata && <ErrorBand hata={hata} />}
      {!durum && !hata && (
        <p className="text-body-medium text-on-surface-variant">Durum okunuyor…</p>
      )}

      {durum && (
        <>
          <DurumKarti
            durum={durum}
            mesgul={mesgul}
            onEylem={(e) => void eylem(e)}
            onYenile={() => void yenile()}
          />
          <GuvenlikDuvariKarti
            duvar={duvar ?? katalog?.guvenlik_duvari ?? null}
            platform={durum.platform}
            masaustu={masaustu}
            mesgul={mesgul}
            onDenetle={() => void denetle()}
            onKural={() => void kuralGuncelle()}
          />
          {masaustu && <ArayuzlerKarti adaylar={adaylar} />}
          <SinamaKarti
            sinama={sinama}
            port={katalog?.port ?? ayarPortu}
            ip={komutIp}
            masaustu={masaustu}
            mesgul={mesgul}
            onSina={() => void sina()}
          />
          <BelgelerKarti
            adaylar={adaylar}
            masaustu={masaustu}
            seciliIp={seciliIp}
            onSec={setSeciliIp}
          />
        </>
      )}
    </div>
  );
}
