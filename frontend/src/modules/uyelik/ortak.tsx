// Üyelik ekranlarının ortak parçaları: tablo sınıfları, "tümünü seç" kutusu, şube
// seçenekleri ve kişi etiketi. Kişi verisi yalnız yönetici kipindeki ekranlarda
// görünür (görevli kipinde bu ekranlar açılmaz — tasarım §4.4).

import { useEffect, useState } from "react";

import type { SelectOption } from "../../ui/Select";
import { okulApi } from "../okul/api";
import { MEMBER_TYPE_TR } from "./api";
import type { MemberType } from "./api";

export const TH = "p-2 text-left text-label-medium text-on-surface-variant";
export const TD = "p-2 align-top text-on-surface";

/** Sınıf/şube çifti: seçici değeri "9|A" biçimindedir. */
export interface SubeSecimi {
  classLevel: number | null;
  classSection: string;
}

export const BUTUN_SUBELER: SubeSecimi = { classLevel: null, classSection: "" };

export function subeDegeri(s: SubeSecimi): string {
  return s.classLevel === null ? "" : `${s.classLevel}|${s.classSection}`;
}

export function subeOku(deger: string): SubeSecimi {
  if (!deger) return BUTUN_SUBELER;
  const [seviye, sube] = deger.split("|");
  return { classLevel: Number(seviye), classSection: sube ?? "" };
}

const tr = new Intl.Collator("tr");

/**
 * Şube seçenekleri ("9/A"): şube kataloğundan, yinelenmeden, sınıf ve Türk
 * alfabesi sırasıyla. Okunamazsa boş liste (süzgeç yalnız "Tümü"yle kalır).
 */
export function useSubeSecenekleri(): SelectOption[] {
  const [secenekler, setSecenekler] = useState<SelectOption[]>([]);
  useEffect(() => {
    let iptal = false;
    okulApi
      .listClassSections()
      .then((subeler) => {
        if (iptal) return;
        const tekil = new Map<string, { seviye: number; sube: string; etiket: string }>();
        for (const s of subeler) {
          tekil.set(`${s.class_level}|${s.class_section}`, {
            seviye: s.class_level,
            sube: s.class_section,
            etiket: s.class_label,
          });
        }
        const sirali = [...tekil.entries()].sort(
          ([, a], [, b]) => a.seviye - b.seviye || tr.compare(a.sube, b.sube),
        );
        setSecenekler(sirali.map(([deger, s]) => ({ value: deger, label: s.etiket })));
      })
      .catch(() => {
        if (!iptal) setSecenekler([]);
      });
    return () => {
      iptal = true;
    };
  }, []);
  return secenekler;
}

/** Öğrencide sınıf, personelde üye türü (kartta sınıf yazmaz; ekranda bilgi içindir). */
export function kisiEtiketi(satir: { member_type: MemberType; class_label: string }): string {
  return satir.member_type === "STUDENT"
    ? satir.class_label || "—"
    : MEMBER_TYPE_TR[satir.member_type];
}

export const UYE_TURU_SECENEKLERI: SelectOption[] = (
  Object.entries(MEMBER_TYPE_TR) as Array<[MemberType, string]>
).map(([value, label]) => ({ value, label }));

/** Tablo başlığındaki "görünenlerin tümünü seç" kutusu (kısmi seçimde belirsiz). */
export function TumunuSec({
  kimlikler,
  secim,
  onSecim,
  etiket,
}: {
  kimlikler: number[];
  secim: Set<number>;
  onSecim: (s: Set<number>) => void;
  etiket: string;
}) {
  const secilen = kimlikler.filter((id) => secim.has(id)).length;
  const hepsi = kimlikler.length > 0 && secilen === kimlikler.length;
  return (
    <input
      type="checkbox"
      aria-label={etiket}
      checked={hepsi}
      disabled={kimlikler.length === 0}
      ref={(el) => {
        if (el) el.indeterminate = secilen > 0 && !hepsi;
      }}
      onChange={(e) => {
        const yeni = new Set(secim);
        for (const id of kimlikler) {
          if (e.target.checked) yeni.add(id);
          else yeni.delete(id);
        }
        onSecim(yeni);
      }}
      className="size-5 accent-primary"
    />
  );
}

/** Tek satırın seçim kutusu. */
export function SatirSecimi({
  id,
  etiket,
  secim,
  onSecim,
  disabled = false,
}: {
  id: number;
  etiket: string;
  secim: Set<number>;
  onSecim: (s: Set<number>) => void;
  disabled?: boolean;
}) {
  return (
    <input
      type="checkbox"
      aria-label={etiket}
      checked={secim.has(id)}
      disabled={disabled}
      onChange={(e) => {
        const yeni = new Set(secim);
        if (e.target.checked) yeni.add(id);
        else yeni.delete(id);
        onSecim(yeni);
      }}
      className="size-5 accent-primary"
    />
  );
}
