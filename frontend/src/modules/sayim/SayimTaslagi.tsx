// Sayım taslağı (F9): sayım kurulu (TMY 32/2), iki AYRI seçenek (TMY 32/3 durdurması ve sayım
// için hizmet arası — tasarım §9-10) ve ödünçteki, teslimdeki ve onarımdaki nüsha için kurulun
// seçimi (§9-11, AT-1; onarım — F9 ekleri K2; sınıf kitaplığında "Kayda göre alınır" yok —
// K3). Seçenekler ve kurul YALNIZ taslakta değişir; başlatınca anlık görüntü alınır.
//
// Kural sunucudadır: kurulun seçebildikleri `basis_choices`'tan, seçimin dayanağı kayıtlı
// seçimin `basis_lines` satırından okunur (ekran kural kopyalamaz). Kurulun en az üç kişi
// olması, durdurmanın zorunlu alanları ve tarih sırası sunucuda denetlenir; ret iletisi
// alanın altında gösterilir.

import { useState } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { OnayKutusu } from "../ayiklama/ortak";
import { MetinAlani } from "../kutuphane/ortak";
import {
  HIZMET_ARASI,
  TMY_DURDURMA_KAPSAMAZ,
  TMY_DURDURMA_KAPSAMI,
  TMY_DURDURMASI,
  sayimApi,
} from "./api";
import type { SayimAyrintisi, SayimBicimi, TaslakGovdesi } from "./api";

/** Seçeneklerin ekrandaki açıklamaları (kılavuz aynı cümleleri kullanır). */
export const DURDURMA_ACIKLAMASI =
  "İsteğe bağlıdır. Sayım kurulunun talebi üzerine harcama yetkilisi taşınır giriş ve " +
  "çıkışlarını durdurabilir (Taşınır Mal Yönetmeliği md. 32/3). Durdurma sürerken " +
  `${TMY_DURDURMA_KAPSAMI} yapılamaz. ${TMY_DURDURMA_KAPSAMAZ}`;
export const HIZMET_ARASI_ACIKLAMASI =
  "Okul kararıdır ve yeni ödüncü ve yeni teslimi durdurur: masada ödünç verilmez, sınıf " +
  "kitaplığına ve öğretmene teslim yapılmaz; iade alınır ve teslimden geri alınır. Taşınır Mal " +
  "Yönetmeliğine dayanmaz; ödünç ve iade taşınır giriş ve çıkışı değildir.";
export const IADE_NOTU =
  "İade ve teslimden geri alma hiçbir durumda durmaz (Yönetmelik Md. 23/1-c); sayım sırasında " +
  "iade edilen ya da geri alınan kitap bulunmuş sayılır. İki seçenek birbirinden bağımsızdır " +
  "ve sayım onaylanınca ya da iptal edilince kalkar.";

type Kategori = "loan_basis" | "section_delivery_basis" | "teacher_delivery_basis" | "repair_basis";

const KATEGORILER: Array<{ alan: Kategori; kategori: string; etiket: string }> = [
  { alan: "loan_basis", kategori: "loan", etiket: "Ödünçteki nüsha" },
  {
    alan: "section_delivery_basis",
    kategori: "section_delivery",
    etiket: "Sınıf kitaplığına teslim edilen nüsha",
  },
  {
    alan: "teacher_delivery_basis",
    kategori: "teacher_delivery",
    etiket: "Öğretmene teslim edilen nüsha",
  },
  { alan: "repair_basis", kategori: "repair", etiket: "Onarımdaki nüsha" },
];

/** Kurul seçimi kartının başlığı ve açıklaması (kılavuz aynı adları kullanır). */
export const KURUL_SECIMI_BASLIGI = "Ödünçteki, Teslimdeki ve Onarımdaki Nüshalar";
export const KURUL_SECIMI_ACIKLAMASI =
  "Sayım kurulu, ödünçteki, teslimdeki ve onarımdaki kitabın sayımdan önce toplanacağını " +
  "(geri alınacağını), yerinde sayılacağını ya da kayda göre alınacağını seçer. Ödünçteki, " +
  "öğretmendeki ve onarımdaki kitap noksan sayılmaz. Sınıf kitaplığındaki kitap kayda göre " +
  "alınmaz: yerinde sayılır ya da sayımdan önce toplanır, toplanamayan yerinde aranır ve " +
  "bulunmazsa noksandır.";

interface Form {
  fiscal_year: string;
  committee_chair: string;
  committee_property_officer: string;
  committee_members: string;
  tmy_stop: boolean;
  tmy_stop_requested_on: string;
  tmy_stop_by_name: string;
  tmy_stop_on: string;
  service_pause: boolean;
  service_pause_decision: string;
  loan_basis: SayimBicimi;
  section_delivery_basis: SayimBicimi;
  teacher_delivery_basis: SayimBicimi;
  repair_basis: SayimBicimi;
  notes: string;
}

function formdan(s: SayimAyrintisi): Form {
  return {
    fiscal_year: s.fiscal_year ? String(s.fiscal_year) : "",
    committee_chair: s.committee_chair,
    committee_property_officer: s.committee_property_officer,
    committee_members: s.committee_members,
    tmy_stop: s.tmy_stop,
    tmy_stop_requested_on: s.tmy_stop_requested_on ?? "",
    tmy_stop_by_name: s.tmy_stop_by_name,
    tmy_stop_on: s.tmy_stop_on ?? "",
    service_pause: s.service_pause,
    service_pause_decision: s.service_pause_decision,
    loan_basis: s.loan_basis,
    section_delivery_basis: s.section_delivery_basis,
    teacher_delivery_basis: s.teacher_delivery_basis,
    repair_basis: s.repair_basis,
    notes: s.notes,
  };
}

function govde(f: Form): TaslakGovdesi {
  return {
    fiscal_year: f.fiscal_year.trim() ? Number(f.fiscal_year) : null,
    committee_chair: f.committee_chair.trim(),
    committee_property_officer: f.committee_property_officer.trim(),
    committee_members: f.committee_members,
    tmy_stop: f.tmy_stop,
    tmy_stop_requested_on: f.tmy_stop ? f.tmy_stop_requested_on || null : null,
    tmy_stop_by_name: f.tmy_stop ? f.tmy_stop_by_name.trim() : "",
    tmy_stop_on: f.tmy_stop ? f.tmy_stop_on || null : null,
    service_pause: f.service_pause,
    service_pause_decision: f.service_pause ? f.service_pause_decision.trim() : "",
    loan_basis: f.loan_basis,
    section_delivery_basis: f.section_delivery_basis,
    teacher_delivery_basis: f.teacher_delivery_basis,
    repair_basis: f.repair_basis,
    notes: f.notes,
  };
}

/** Başlatma onayının gövdesi: anlık görüntü ve seçilen seçenekler (sonuç cümleleri). */
export function baslatmaMetni(f: Pick<Form, "tmy_stop" | "service_pause">): string {
  const parcalar = [
    "O anki kayıtlar sayımın anlık görüntüsü olur; sayım sürerken yapılan değişiklikler onu değiştirmez. Kurul ve seçenekler bundan sonra değişmez.",
  ];
  if (f.tmy_stop) {
    parcalar.push(`TMY 32/3 durdurması başlar: ${TMY_DURDURMA_KAPSAMI} yapılamaz.`);
  }
  if (f.service_pause) {
    parcalar.push("Sayım için hizmet arası başlar: yeni ödünç ve teslim yapılamaz.");
  }
  parcalar.push("İade ve teslimden geri alma açık kalır.");
  return parcalar.join(" ");
}

export default function SayimTaslagi({
  sayim,
  onDegisti,
  onSilindi,
}: {
  sayim: SayimAyrintisi;
  /** Kaydedildi ya da başlatıldı: güncel sayım. */
  onDegisti: (s: SayimAyrintisi, ileti: string) => void;
  onSilindi: () => void;
}) {
  const [form, setForm] = useState<Form>(() => formdan(sayim));
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, clearErrors, applyApiError } = useFormErrors();
  const confirm = useConfirm();
  const snackbar = useSnackbar();

  const kayitli = formdan(sayim);
  const degisti = JSON.stringify(kayitli) !== JSON.stringify(form);
  const yaz = <K extends keyof Form>(alan: K, deger: Form[K]) =>
    setForm((f) => ({ ...f, [alan]: deger }));

  const kaydet = async (): Promise<SayimAyrintisi | null> => {
    clearErrors();
    setHata(null);
    try {
      return await sayimApi.taslakGuncelle(sayim.id, govde(form));
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Taslak kaydedilemedi."));
      return null;
    }
  };

  const kaydetDugmesi = async () => {
    setBusy(true);
    const guncel = await kaydet();
    setBusy(false);
    if (guncel) {
      setForm(formdan(guncel));
      onDegisti(guncel, "Taslak kaydedildi.");
    }
  };

  const baslat = async () => {
    const onay = await confirm({
      title: "Sayım başlatılsın mı?",
      message: baslatmaMetni(form),
      confirmLabel: "Sayımı başlat",
    });
    if (!onay) return;
    setBusy(true);
    const kaydedilen = degisti ? await kaydet() : sayim;
    if (kaydedilen === null) {
      setBusy(false);
      return;
    }
    try {
      const baslayan = await sayimApi.baslat(sayim.id);
      onDegisti(baslayan, "Sayım başladı.");
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Sayım başlatılamadı."));
      setBusy(false);
    }
  };

  const sil = async () => {
    const onay = await confirm({
      title: "Sayım taslağı silinsin mi?",
      message: "Taslak kaldırılır; nüshalara dokunulmaz.",
      confirmLabel: "Sil",
    });
    if (!onay) return;
    setBusy(true);
    try {
      await sayimApi.taslakSil(sayim.id);
      snackbar.success("Sayım taslağı silindi.");
      onSilindi();
    } catch (e) {
      setHata(hataOku(e, "Taslak silinemedi."));
      setBusy(false);
    }
  };

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      {hata && <ErrorBand hata={hata} />}

      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <h2 className="text-title-medium font-semibold text-on-surface">Sayım Kurulu</h2>
        <p className="text-body-small text-on-surface-variant">
          Sayım, harcama yetkilisinin ya da görevlendirdiği kişinin başkanlığında, taşınır kayıt
          yetkilisinin de katıldığı en az üç kişilik sayım kurulunca yapılır (Taşınır Mal
          Yönetmeliği md. 32/2). Adlar şifreli saklanır ve yalnız sayım tutanağına basılır.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Kurul başkanı"
            value={form.committee_chair}
            onChange={(e) => yaz("committee_chair", e.target.value)}
            error={errors.committee_chair}
            helperText="Harcama yetkilisi ya da görevlendirdiği kişi."
          />
          <TextField
            label="Taşınır kayıt yetkilisi"
            value={form.committee_property_officer}
            onChange={(e) => yaz("committee_property_officer", e.target.value)}
            error={errors.committee_property_officer}
          />
        </div>
        <MetinAlani
          label="Kurul üyeleri"
          value={form.committee_members}
          onChange={(v) => yaz("committee_members", v)}
          error={errors.committee_members}
          helperText="Satır başına bir kişi. Kurul, başkan ve taşınır kayıt yetkilisiyle birlikte en az üç kişidir."
        />
        <TextField
          className="max-w-xs"
          label="Mali yıl (isteğe bağlı)"
          inputMode="numeric"
          value={form.fiscal_year}
          onChange={(e) => yaz("fiscal_year", e.target.value)}
          error={errors.fiscal_year}
          helperText="Boşsa sayımın başladığı yıl yazılır."
        />
      </Card>

      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <h2 className="text-title-medium font-semibold text-on-surface">
          Sayım Sırasındaki Seçenekler
        </h2>
        <section aria-label={TMY_DURDURMASI} className="space-y-2">
          <OnayKutusu
            etiket={<span className="font-semibold">{TMY_DURDURMASI}</span>}
            checked={form.tmy_stop}
            onChange={(d) => yaz("tmy_stop", d)}
          />
          <p className="text-body-small text-on-surface-variant">{DURDURMA_ACIKLAMASI}</p>
          {form.tmy_stop && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <TextField
                label="Kurulun talep tarihi"
                type="date"
                value={form.tmy_stop_requested_on}
                onChange={(e) => yaz("tmy_stop_requested_on", e.target.value)}
                error={errors.tmy_stop_requested_on}
              />
              <TextField
                label="Harcama yetkilisinin adı"
                value={form.tmy_stop_by_name}
                onChange={(e) => yaz("tmy_stop_by_name", e.target.value)}
                error={errors.tmy_stop_by_name}
                helperText="Durdurmayı yapan; şifreli saklanır."
              />
              <TextField
                label="Durdurma tarihi"
                type="date"
                value={form.tmy_stop_on}
                onChange={(e) => yaz("tmy_stop_on", e.target.value)}
                error={errors.tmy_stop_on}
                helperText="Talepten önce ve bugünden sonra olamaz."
              />
            </div>
          )}
        </section>
        <section aria-label={HIZMET_ARASI} className="space-y-2">
          <OnayKutusu
            etiket={<span className="font-semibold">{HIZMET_ARASI}</span>}
            checked={form.service_pause}
            onChange={(d) => yaz("service_pause", d)}
          />
          <p className="text-body-small text-on-surface-variant">{HIZMET_ARASI_ACIKLAMASI}</p>
          {form.service_pause && (
            <TextField
              className="max-w-md"
              label="Okul kararı (isteğe bağlı)"
              value={form.service_pause_decision}
              onChange={(e) => yaz("service_pause_decision", e.target.value)}
              error={errors.service_pause_decision}
              helperText="Kararın tarihi ve sayısı. Kişi adı yazmayın."
            />
          )}
        </section>
        <p className="flex items-start gap-2 rounded-shape-sm bg-surface-container-high px-3 py-2 text-body-small text-on-surface">
          <Icon name="info" size="sm" className="mt-0.5 shrink-0" />
          {IADE_NOTU}
        </p>
      </Card>

      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <h2 className="text-title-medium font-semibold text-on-surface">{KURUL_SECIMI_BASLIGI}</h2>
        <p className="text-body-small text-on-surface-variant">{KURUL_SECIMI_ACIKLAMASI}</p>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {KATEGORILER.map((k) => {
            const kayitliSatir = sayim.basis_lines.find((s) => s.category === k.kategori);
            const ayni = kayitli[k.alan] === form[k.alan];
            return (
              <div key={k.alan} className="space-y-1">
                <Select
                  label={k.etiket}
                  value={form[k.alan]}
                  onChange={(e) => yaz(k.alan, e.target.value as SayimBicimi)}
                  options={sayim.basis_choices[k.alan].map((s) => ({
                    value: s.value,
                    label: s.label,
                  }))}
                  error={errors[k.alan]}
                />
                <p className="text-body-small text-on-surface-variant">
                  {ayni && kayitliSatir
                    ? kayitliSatir.dayanak
                    : "Kaydedince seçimin dayanağı burada yazılır."}
                </p>
              </div>
            );
          })}
        </div>
      </Card>

      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <MetinAlani
          label="Notlar"
          value={form.notes}
          onChange={(v) => yaz("notes", v)}
          error={errors.notes}
          helperText="Sayıma ilişkin notlar. Kişi adı yazmayın."
        />
        <div className="flex flex-wrap gap-2">
          <Button icon="play_arrow" onClick={() => void baslat()} disabled={busy}>
            Sayımı başlat
          </Button>
          <Button
            variant="outlined"
            icon="save"
            onClick={() => void kaydetDugmesi()}
            disabled={busy || !degisti}
          >
            Kaydet
          </Button>
          <Button variant="text" icon="delete" onClick={() => void sil()} disabled={busy}>
            Taslağı sil
          </Button>
        </div>
      </Card>
    </div>
  );
}
