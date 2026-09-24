// Kişiler sayfası (DD kalıbı) — öğrenci, öğretmen ve diğer personel sicillerinin tek
// ekranı. Sicil sekmelerinde arama/filtre + sayfalama, Dialog içinde elle
// ekleme-düzenleme, "Ayrıldı olarak işaretle" (ayrılış yolu; kayıt silinmez) ve
// silme; altta e-Okul listesinden aktarım paneli (önizle → mutabakat → aktar,
// AktarimPaneli). Üçüncü sekme "Ayrılış Havuzu" (F1 eki 7): aktarım kimseyi ayırmaz,
// listede bulunmayan kişi orada karar bekler (AyrilisHavuzu).
// KVKK (tasarım §6.1): TCKN, veli, cinsiyet, fotoğraf, unvan ve branş bu programda
// HİÇ YOKTUR — sicil ad-soyad + okul no + sınıf/şube (personelde üye türü) ile
// yürür. Okul no şifreli saklanır: arama numaranın tamamıyla yapılır. Sekme URL'de
// tutulur (`?tab=personel`, `?tab=havuz`): başka ekranlar doğrudan o sekmeye bağlanır.
// F6: "Üyeler", "Üyelik İstek Listesi" ve "Kart Basımı" sekmeleri `modules/uyelik`tedir.

import { useCallback, useEffect, useState } from "react";

import { useDebounced } from "../../hooks/useDebounced";
import { useFormErrors } from "../../hooks/useFormErrors";
import { useTabParam } from "../../hooks/useTabParam";
import { formatNumber } from "../../lib/format";
import { gradeLevelLabel } from "../../lib/gradeLevels";
import { emptyPage, geriDusulecekOffset } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import type { TabItem } from "../../ui/Tabs";
import TextField from "../../ui/TextField";
import { MEMBER_KIND_TR, okulApi } from "../okul/api";
import type {
  GradeLevelOption,
  MemberKind,
  Personnel,
  PersonnelWriteBody,
  Student,
  StudentWriteBody,
} from "../okul/api";
import IstekListesi from "../uyelik/IstekListesi";
import KartBasimi from "../uyelik/KartBasimi";
import UyelerSekmesi from "../uyelik/UyelerSekmesi";
import AktarimPaneli from "./AktarimPaneli";
import AyrilisHavuzu from "./AyrilisHavuzu";
import { DurumRozeti, ErrorBand, hataOku } from "./ortak";
import type { SayfaHatasi } from "./ortak";

/** Sayfa başına kayıt (CLAUDE.md §7 — liste uçları limit/offset, varsayılan 25). */
const PAGE_SIZE = 25;

// TAB_KEYS[0] varsayılan sekmedir (useTabParam fallback) — başa yeni anahtar EKLEME.
const TAB_KEYS = [
  "ogrenciler",
  "personel",
  "havuz",
  // F6 üyelik (modules/uyelik): üye listesi, şube bazlı istek listesi, kart basımı.
  "uyeler",
  "uyelik-istekleri",
  "kart-basimi",
] as const;
type TabKey = (typeof TAB_KEYS)[number];

// Sözlük: "personel" tek başına öğretmen anlamında kullanılmaz; üye türleri
// "öğretmen" ve "diğer personel"dir. Sekme ikisini birden taşır.
const TABS: TabItem[] = [
  { key: "ogrenciler", label: "Öğrenciler", icon: "school" },
  { key: "personel", label: "Öğretmenler ve Diğer Personel", icon: "badge" },
  { key: "havuz", label: "Ayrılış Havuzu", icon: "pending_actions" },
  { key: "uyeler", label: "Üyeler", icon: "badge" },
  { key: "uyelik-istekleri", label: "Üyelik İstek Listesi", icon: "how_to_reg" },
  { key: "kart-basimi", label: "Kart Basımı", icon: "print" },
];

/** Ayrılış onayının ortak sonucu cümlesi (F1 eki 7: ayrılış kaydı silmez). */
const AYRILIS_SONUCU =
  "Kaydı silinmez; sicilde “Ayrıldı · gg.aa.yyyy” rozetiyle kalır, iade etmediği kitap varsa izlenebilir.";

export default function KisilerPage() {
  const [active, setActive] = useTabParam<TabKey>("tab", TAB_KEYS, "ogrenciler");

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">Kişiler</h1>
          <p className="kd-page-description">
            Öğrenci, öğretmen ve diğer personel sicili. Kayıtlar e-Okul listesinden toplu
            aktarılabilir ya da tek tek girilebilir. Aktarım kimseyi ayırmaz: listede bulunmayanlar
            Ayrılış Havuzu&apos;nda karar bekler. TCKN, veli bilgisi, unvan ve branş bu programda
            tutulmaz.
          </p>
        </div>
      </div>

      <Tabs
        items={TABS}
        active={active}
        onChange={(key) => setActive(key as TabKey)}
        ariaLabel="Kişiler bölümleri"
        idBase="kisiler"
      />

      <div {...tabPanelProps("kisiler", active)}>
        {active === "ogrenciler" && <OgrencilerSekmesi />}
        {active === "personel" && <PersonelSekmesi />}
        {active === "havuz" && <AyrilisHavuzu />}
        {active === "uyeler" && <UyelerSekmesi />}
        {active === "uyelik-istekleri" && <IstekListesi />}
        {active === "kart-basimi" && <KartBasimi />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Öğrenciler sekmesi
// ---------------------------------------------------------------------------

function OgrencilerSekmesi() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [level, setLevel] = useState("");
  const [section, setSection] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Paginated<Student>>(emptyPage<Student>());
  const [levels, setLevels] = useState<GradeLevelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<SayfaHatasi | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState<Student | null>(null);
  const [creating, setCreating] = useState(false);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  // Sınıf seçicisi sicilden türetilir (kurulum öncesi lise varsayılanı döner).
  useEffect(() => {
    okulApi
      .getGradeLevels()
      .then((r) => setLevels(r.levels))
      .catch(() => setLevels([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    // Geri düşüşte iskelet ekranda kalır: araya boş-durum kartı girip yanıp sönmesin.
    let geriDusuluyor = false;
    setLoading(true);
    okulApi
      .listStudents({
        search,
        classLevel: level ? Number(level) : null,
        classSection: section,
        limit: PAGE_SIZE,
        offset,
      })
      .then((result) => {
        if (cancelled) return;
        const geri = geriDusulecekOffset(result, offset, PAGE_SIZE);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setPage(result);
        setError(null);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(hataOku(e, "Öğrenci listesi yüklenemedi."));
      })
      .finally(() => {
        if (!cancelled && !geriDusuluyor) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [search, level, section, offset, reloadKey]);

  const columns: Column<Student>[] = [
    { header: "Okul no", cell: (s) => s.student_number || "—" },
    { header: "Ad soyad", cell: (s) => s.full_name },
    { header: "Sınıf", cell: (s) => s.class_label || "—" },
    {
      header: "Durum",
      cell: (s) => (
        <DurumRozeti
          aktif={s.status === "ACTIVE"}
          leftAt={s.left_at}
          havuzda={s.leave_candidate_since !== null}
        />
      ),
    },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">Öğrenci Sicili</p>
          {!loading && (
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(page.count)} kayıt
            </p>
          )}
        </div>
        <Button icon="person_add" onClick={() => setCreating(true)}>
          Öğrenci ekle
        </Button>
      </div>

      <Card
        elevation={0}
        className="grid items-end gap-3 p-[var(--kd-panel-padding)] shadow-elevation-1 sm:grid-cols-[minmax(15rem,1fr)_10rem_7rem]"
      >
        <TextField
          className="min-w-60 flex-1"
          label="Ara"
          value={searchInput}
          onChange={(e) => {
            setSearchInput(e.target.value);
            setOffset(0);
          }}
          placeholder="Ad soyad veya okul no…"
          helperText="Okul numarası tam yazılarak aranır."
        />
        <Select
          className="min-w-40"
          label="Sınıf düzeyi"
          placeholder="Tümü"
          value={level}
          onChange={(e) => {
            setLevel(e.target.value);
            setOffset(0);
          }}
          options={levels.map((l) => ({ value: String(l.value), label: gradeLevelLabel(l.value) }))}
        />
        <TextField
          className="w-32"
          label="Şube"
          value={section}
          onChange={(e) => {
            setSection(e.target.value);
            setOffset(0);
          }}
          placeholder="A"
        />
      </Card>

      {error && <ErrorBand hata={error} />}

      {loading ? (
        <SkeletonList rows={5} />
      ) : page.results.length === 0 ? (
        <EmptyState
          icon="school"
          title="Gösterilecek öğrenci yok"
          description="Filtreleri değiştirin ya da aşağıdaki Excel şablonundan öğrenci aktarın."
        />
      ) : (
        <>
          <DataTable<Student>
            columns={columns}
            rows={page.results}
            onRowClick={(s) => setEditing(s)}
            rowLabel={(s) => `${s.full_name} kaydını düzenle`}
          />
          <PaginationBar
            count={page.count}
            offset={offset}
            pageSize={PAGE_SIZE}
            onOffset={setOffset}
          />
        </>
      )}

      <AktarimPaneli kind="students" onImported={reload} />

      {(creating || editing !== null) && (
        <OgrenciFormDialog
          student={editing}
          levels={levels}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditing(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Öğrenci ekleme/düzenleme formu (Dialog)
// ---------------------------------------------------------------------------

function OgrenciFormDialog({
  student,
  levels,
  onClose,
  onSaved,
}: {
  /** null → yeni kayıt; dolu → düzenleme (ayrılış ve silme yalnız bu durumda görünür). */
  student: Student | null;
  levels: GradeLevelOption[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [firstName, setFirstName] = useState(student?.first_name ?? "");
  const [lastName, setLastName] = useState(student?.last_name ?? "");
  const [studentNumber, setStudentNumber] = useState(student?.student_number ?? "");
  const [level, setLevel] = useState(
    student?.class_level == null ? "" : String(student.class_level),
  );
  const [section, setSection] = useState(student?.class_section ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const aktif = student === null || student.status === "ACTIVE";

  const submit = async () => {
    clearErrors();
    setError(null);
    if (!firstName.trim() || !lastName.trim()) {
      if (!firstName.trim()) setFieldError("first_name", "Ad zorunludur.");
      if (!lastName.trim()) setFieldError("last_name", "Soyad zorunludur.");
      return;
    }
    // Boş metin alanları backend'de "" olarak meşru; sayı alanı null olmalı.
    const body: StudentWriteBody = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      student_number: studentNumber.trim(),
      class_level: level ? Number(level) : null,
      class_section: section.trim(),
    };
    setBusy(true);
    try {
      if (student) await okulApi.updateStudent(student.id, body);
      else await okulApi.createStudent(body);
      snackbar.success(student ? "Öğrenci güncellendi." : "Öğrenci eklendi.");
      onSaved();
    } catch (e) {
      applyApiError(e);
      setError(hataOku(e, "Öğrenci kaydedilemedi."));
      setBusy(false);
    }
  };

  const leave = async () => {
    if (!student) return;
    // Başlık soru, gövde sonuç (docs/sozluk.md §3); ad yalnız bu onay penceresinde görünür.
    const ok = await confirm({
      title: "Öğrenci ayrıldı olarak işaretlensin mi?",
      message: `“${student.full_name}” okuldan ayrılmış sayılır ve seçicilerden düşer. ${AYRILIS_SONUCU}`,
      confirmLabel: "Ayrıldı olarak işaretle",
    });
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await okulApi.leaveStudent(student.id);
      snackbar.success("Öğrenci ayrıldı olarak işaretlendi.");
      onSaved();
    } catch (e) {
      setError(hataOku(e, "Öğrenci ayrıldı olarak işaretlenemedi."));
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!student) return;
    const ok = await confirm({
      title: "Öğrenci sicilden silinsin mi?",
      message: `“${student.full_name}” kaydı kalıcı olarak silinir, geri alınamaz. Yanlış girilmiş kayıtlar içindir; okuldan ayrılan öğrenci için “Ayrıldı olarak işaretle”yi kullanın. Yanlışlıkla silerseniz öğrenciyi yeniden ekleyebilir ya da e-Okul listesini yeniden aktarabilirsiniz.`,
      confirmLabel: "Sil",
    });
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await okulApi.deleteStudent(student.id);
      snackbar.success("Öğrenci silindi.");
      onSaved();
    } catch (e) {
      setError(hataOku(e, "Öğrenci silinemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={student ? "Öğrenciyi düzenle" : "Yeni öğrenci"}
      actions={
        <>
          {student && (
            <Button variant="text" icon="delete" onClick={remove} disabled={busy}>
              Sil
            </Button>
          )}
          {student && aktif && (
            <Button variant="text" icon="logout" onClick={leave} disabled={busy}>
              Ayrıldı olarak işaretle
            </Button>
          )}
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={submit} disabled={busy}>
            {busy ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error && <ErrorBand hata={error} />}
        {student && (!aktif || student.leave_candidate_since !== null) && (
          <p className="text-body-medium text-on-surface-variant">
            Durum:{" "}
            <DurumRozeti
              aktif={aktif}
              leftAt={student.left_at}
              havuzda={student.leave_candidate_since !== null}
            />
          </p>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Ad"
            required
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            error={errors.first_name}
          />
          <TextField
            label="Soyad"
            required
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            error={errors.last_name}
          />
          <TextField
            label="Okul no"
            value={studentNumber}
            onChange={(e) => setStudentNumber(e.target.value)}
            error={errors.student_number}
            helperText="İçe aktarma bu numarayla eşleştirir; aktif kayıtlar arasında tekildir."
          />
          <Select
            label="Sınıf düzeyi"
            placeholder="— yok —"
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            options={levels.map((l) => ({
              value: String(l.value),
              label: gradeLevelLabel(l.value),
            }))}
            error={errors.class_level}
          />
          <TextField
            label="Şube"
            value={section}
            onChange={(e) => setSection(e.target.value)}
            error={errors.class_section}
            helperText="Türkçe harfler korunur ve büyütülür (ş → Ş, i → İ). 10/I ile 10/İ ayrı şubelerdir."
          />
        </div>
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Öğretmenler ve diğer personel sekmesi
// ---------------------------------------------------------------------------

function PersonelSekmesi() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Paginated<Personnel>>(emptyPage<Personnel>());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<SayfaHatasi | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState<Personnel | null>(null);
  const [creating, setCreating] = useState(false);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;
    let geriDusuluyor = false;
    setLoading(true);
    okulApi
      .listPersonnel({ search, limit: PAGE_SIZE, offset })
      .then((result) => {
        if (cancelled) return;
        const geri = geriDusulecekOffset(result, offset, PAGE_SIZE);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setPage(result);
        setError(null);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(hataOku(e, "Öğretmen ve diğer personel listesi yüklenemedi."));
      })
      .finally(() => {
        if (!cancelled && !geriDusuluyor) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [search, offset, reloadKey]);

  const columns: Column<Personnel>[] = [
    { header: "Ad soyad", cell: (p) => p.full_name },
    { header: "Üye türü", cell: (p) => MEMBER_KIND_TR[p.member_kind] },
    {
      header: "Durum",
      cell: (p) => (
        <DurumRozeti
          aktif={p.is_active}
          leftAt={p.left_at}
          havuzda={p.leave_candidate_since !== null}
        />
      ),
    },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">Öğretmen ve Diğer Personel Sicili</p>
          {!loading && (
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(page.count)} kayıt
            </p>
          )}
        </div>
        <Button icon="person_add" onClick={() => setCreating(true)}>
          Kişi ekle
        </Button>
      </div>

      <Card
        elevation={0}
        className="grid items-end gap-3 bg-surface-container-lowest p-[var(--kd-panel-padding)] sm:grid-cols-2"
      >
        <TextField
          className="min-w-60 flex-1"
          label="Ara"
          value={searchInput}
          onChange={(e) => {
            setSearchInput(e.target.value);
            setOffset(0);
          }}
          placeholder="Ad soyad…"
        />
      </Card>

      {error && <ErrorBand hata={error} />}

      {loading ? (
        <SkeletonList rows={5} />
      ) : page.results.length === 0 ? (
        <EmptyState
          icon="badge"
          title="Gösterilecek kişi yok"
          description="Aramayı değiştirin ya da e-Okul personel listesini aşağıdaki panelden içe aktarın."
        />
      ) : (
        <>
          <DataTable<Personnel>
            columns={columns}
            rows={page.results}
            onRowClick={(p) => setEditing(p)}
            rowLabel={(p) => `${p.full_name} kaydını düzenle`}
          />
          <PaginationBar
            count={page.count}
            offset={offset}
            pageSize={PAGE_SIZE}
            onOffset={setOffset}
          />
        </>
      )}

      <AktarimPaneli kind="personnel" onImported={reload} />

      {(creating || editing !== null) && (
        <PersonelFormDialog
          personnel={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditing(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

const MEMBER_KIND_OPTIONS = (Object.entries(MEMBER_KIND_TR) as [MemberKind, string][]).map(
  ([value, label]) => ({ value, label }),
);

function PersonelFormDialog({
  personnel,
  onClose,
  onSaved,
}: {
  personnel: Personnel | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [firstName, setFirstName] = useState(personnel?.first_name ?? "");
  const [lastName, setLastName] = useState(personnel?.last_name ?? "");
  const [memberKind, setMemberKind] = useState<MemberKind>(personnel?.member_kind ?? "TEACHER");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const aktif = personnel === null || personnel.is_active;

  const submit = async () => {
    clearErrors();
    setError(null);
    if (!firstName.trim() || !lastName.trim()) {
      if (!firstName.trim()) setFieldError("first_name", "Ad zorunludur.");
      if (!lastName.trim()) setFieldError("last_name", "Soyad zorunludur.");
      return;
    }
    const body: PersonnelWriteBody = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      member_kind: memberKind,
    };
    setBusy(true);
    try {
      if (personnel) await okulApi.updatePersonnel(personnel.id, body);
      else await okulApi.createPersonnel(body);
      snackbar.success(personnel ? "Kayıt güncellendi." : "Kayıt eklendi.");
      onSaved();
    } catch (e) {
      applyApiError(e);
      setError(hataOku(e, "Kayıt kaydedilemedi."));
      setBusy(false);
    }
  };

  const leave = async () => {
    if (!personnel) return;
    const ok = await confirm({
      title: "Kişi ayrıldı olarak işaretlensin mi?",
      message: `“${personnel.full_name}” okuldan ayrılmış sayılır ve seçicilerden düşer. ${AYRILIS_SONUCU}`,
      confirmLabel: "Ayrıldı olarak işaretle",
    });
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await okulApi.leavePersonnel(personnel.id);
      snackbar.success("Kişi ayrıldı olarak işaretlendi.");
      onSaved();
    } catch (e) {
      setError(hataOku(e, "Kişi ayrıldı olarak işaretlenemedi."));
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!personnel) return;
    const ok = await confirm({
      title: "Kişi sicilden silinsin mi?",
      message: `“${personnel.full_name}” kaydı kalıcı olarak silinir, geri alınamaz. Yanlış girilmiş kayıtlar içindir; okuldan ayrılan kişi için “Ayrıldı olarak işaretle”yi kullanın.`,
      confirmLabel: "Sil",
    });
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await okulApi.deletePersonnel(personnel.id);
      snackbar.success("Kayıt silindi.");
      onSaved();
    } catch (e) {
      setError(hataOku(e, "Kayıt silinemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={personnel ? "Kişiyi düzenle" : "Yeni kişi"}
      actions={
        <>
          {personnel && (
            <Button variant="text" icon="delete" onClick={remove} disabled={busy}>
              Sil
            </Button>
          )}
          {personnel && aktif && (
            <Button variant="text" icon="logout" onClick={leave} disabled={busy}>
              Ayrıldı olarak işaretle
            </Button>
          )}
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={submit} disabled={busy}>
            {busy ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error && <ErrorBand hata={error} />}
        {personnel && (!aktif || personnel.leave_candidate_since !== null) && (
          <p className="text-body-medium text-on-surface-variant">
            Durum:{" "}
            <DurumRozeti
              aktif={aktif}
              leftAt={personnel.left_at}
              havuzda={personnel.leave_candidate_since !== null}
            />
          </p>
        )}
        <TextField
          label="Ad"
          required
          value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          error={errors.first_name}
        />
        <TextField
          label="Soyad"
          required
          value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          error={errors.last_name}
        />
        <Select
          label="Üye türü"
          value={memberKind}
          onChange={(e) => setMemberKind(e.target.value as MemberKind)}
          options={MEMBER_KIND_OPTIONS}
          error={errors.member_kind}
          helperText="Ödünç sayı sınırı üye türüne göre uygulanır. Unvan ve branş tutulmaz."
        />
      </div>
    </Dialog>
  );
}
