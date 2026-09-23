// Katalog ekranlarının ortak parçaları: bölüm seçicisini besleyen kanca, kod
// listelerinden seçenek üretimi ve nüshanın ödünç durumu rozeti. Katalog listesi
// (KatalogPage), eser ayrıntısı (EserDetayPage), Edinimler ve Bağışlar
// (EdinimlerPage) ile Ayarlar'ın iki sekmesi paylaşır.
//
// Hata bandı ve `hataOku` ui/ErrorBand'dedir (409 `parola_gerekli` dalı orada).

import { useEffect, useId, useState } from "react";

import { formatDate } from "../../lib/format";
import Icon from "../../ui/Icon";
import type { SelectOption } from "../../ui/Select";
import { kutuphaneApi } from "./api";
import type { CommissionDecision, Copy, Section } from "./api";

/**
 * Kod listesini (`{KOD: "Türkçe ad"}`) seçim kutusu seçeneklerine çevirir.
 * Sıra tanımdaki sıradır: kod listeleri mevzuattaki ya da yaşam döngüsündeki
 * sırayı taşır, alfabetik sıralamak o anlamı bozar.
 */
export function kodSecenekleri<K extends string>(map: Record<K, string>): SelectOption[] {
  return (Object.keys(map) as K[]).map((key) => ({ value: key, label: map[key] }));
}

/**
 * Komisyon kararı seçicisinin etiketi: tür + tarih + sayı.
 *
 * BAŞKAN ADI ETİKETE GİRMEZ: kişi adıdır, sunucuda şifreli tutulur ve bir seçim
 * kutusunda gerekmez — kararı tarihi ve sayısı tanımlar.
 */
export function kararEtiketi(karar: CommissionDecision): string {
  const sayi = karar.decision_no ? ` · ${karar.decision_no}` : "";
  return `${karar.decision_type_display} — ${formatDate(karar.decision_date)}${sayi}`;
}

/** Bölüm listesini seçim kutusu seçeneklerine çevirir (sunucu sırası korunur). */
export function bolumSecenekleri(bolumler: Section[]): SelectOption[] {
  return bolumler.map((b) => ({ value: String(b.id), label: b.name }));
}

/**
 * Sayfalanmayan seçicilerin tek isteklik üst sınırı — sunucunun `max_limit`'i.
 *
 * Kontrollü listeler (bölüm) bunun çok altında kalır; edinim partileri ve
 * komisyon kararları ise YILLAR İÇİNDE BÜYÜR ve sınırı aşabilir. Kesilme
 * sessizdir: `Acquisition.Meta.ordering` en yeniden eskiye olduğu için kesilen
 * uç EN ESKİ partilerdir ve kullanıcı eski bir partiye nüsha ekleyemediğini
 * anlamaz. `secimKesildiMi` o durumu yakalar, `SECIM_KESILDI` uyarısı da
 * kullanıcıya nereye gideceğini söyler.
 */
export const SECICI_SINIRI = 200;

/** Seçici sunucunun üst sınırına dayandı mı? (dayandıysa eski kayıtlar listede yok) */
export function secimKesildiMi(adet: number): boolean {
  return adet >= SECICI_SINIRI;
}

/** Kesilen seçicinin yardımcı metni: kullanıcıya eksik olanın nerede olduğunu söyler. */
export function secimKesildiMetni(nereye: string): string {
  return (
    `Liste doldu; yalnız en yeni ${SECICI_SINIRI} kayıt gösteriliyor. ` +
    `Daha eskileri için ${nereye} kullanın.`
  );
}

/**
 * Bölümleri bir kez yükler (seçiciler ve süzgeçler için).
 *
 * Liste ucu sayfalıdır ve bölüm seçicisi kesilirse kullanıcı bölümü BULAMAZ —
 * kesilme sessizdir. Bu yüzden sunucunun üst sınırı (`SECICI_SINIRI`) istenir;
 * bölüm sayısı kontrollü bir listede bunun çok altındadır. Yükleme başarısızsa
 * seçici boş kalır, sayfa açılmaya devam eder (bölüm zorunlu alan değildir).
 *
 * Liste BİR KEZ okunur: bölümler ayrı bir ekrandan (Ayarlar → Bölümler)
 * yönetilir, katalog ekranı açıkken değişmez.
 */
export function useBolumler(): Section[] {
  const [bolumler, setBolumler] = useState<Section[]>([]);

  useEffect(() => {
    let iptal = false;
    kutuphaneApi
      .listSections({ limit: SECICI_SINIRI })
      .then((sayfa) => {
        if (!iptal) setBolumler(sayfa.results);
      })
      .catch(() => {
        if (!iptal) setBolumler([]);
      });
    return () => {
      iptal = true;
    };
  }, []);

  return bolumler;
}

/**
 * Çok satırlı metin alanı (notlar, komisyon katılımcıları).
 *
 * Kitte TextField tek satırlıktır; notlar ve katılımcı listesi satır başına bir
 * kayıt taşır. Biçim `AktarimPaneli`'ndeki metin kutusuyla aynıdır; etiket,
 * yardımcı metin ve hata sözleşmesi TextField'inkini izler.
 */
export function MetinAlani({
  label,
  value,
  onChange,
  rows = 3,
  helperText,
  error,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  rows?: number;
  helperText?: string;
  error?: string;
  placeholder?: string;
}) {
  const id = useId();
  const describedBy = error || helperText ? `${id}-desc` : undefined;
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-label-medium font-semibold text-on-surface-variant"
      >
        {label}
      </label>
      <textarea
        id={id}
        rows={rows}
        value={value}
        placeholder={placeholder}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        onChange={(e) => onChange(e.target.value)}
        className={`block w-full rounded-shape-md border bg-surface-container-lowest px-3 py-2 text-body-medium text-on-surface outline-none placeholder:text-on-surface-variant/60 focus-visible:ring-2 ${
          error
            ? "border-error focus-visible:ring-error"
            : "border-outline-variant focus:border-primary focus-visible:ring-primary/20"
        }`}
      />
      {(error || helperText) && (
        <p
          id={describedBy}
          role={error ? "alert" : undefined}
          className={`mt-1 text-body-small ${error ? "text-error" : "text-on-surface-variant"}`}
        >
          {error || helperText}
        </p>
      )}
    </div>
  );
}

/**
 * Nüshanın ödünç durumu: verilebiliyorsa "Rafta", verilemiyorsa sunucunun
 * gerekçesi (Md. 14/1-a, 16/1 — tek türetim `is_loanable`). Gerekçe metni
 * KİŞİSEL VERİ TAŞIMAZ: masada öğrencinin de gördüğü ekranda durur.
 */
export function OduncDurumu({ nusha }: { nusha: Copy }) {
  if (nusha.is_loanable) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-secondary-container px-2 py-0.5 text-label-medium text-on-secondary-container">
        <Icon name="check_circle" size="sm" />
        {nusha.status_display}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-surface-container-highest px-2 py-0.5 text-label-medium text-on-surface-variant">
      <Icon name="block" size="sm" />
      {nusha.not_loanable_reason || nusha.status_display}
    </span>
  );
}
