// "Bu bilgisayar okul demirbaşıdır" onayı + bilgisayarın demirbaş no'su (tasarım §3,
// §6.1; sözlük: "Demirbaş" yalnız bilgisayar için kullanılır). Kurulum sihirbazının
// okul adımı ve Ayarlar → Okul Bilgileri aynı bileşeni kullanır. Onay kurulumu
// tamamlamanın koşuludur (backend `services/setup.py::missing_school_fields`).

import TextField from "../../ui/TextField";

/**
 * "Bu bilgisayar okul demirbaşıdır" onayı + bilgisayarın demirbaş no'su. Dayanak
 * (docs/mevzuat): Bilgi ve Sistem Güvenliği Yönergesi 11/8 (kişisel bilişim
 * kaynakları kurum ağında izinsiz kullanılamaz) ve 11/23 (Bakanlığa ait veri
 * Bakanlık sistemlerinde barındırılır). Ayarlar → Okul Bilgileri de kullanır.
 */
export default function DemirbasAlanlari({
  onay,
  no,
  errors,
  onOnay,
  onNo,
}: {
  onay: boolean;
  no: string;
  errors: Partial<Record<string, string>>;
  onOnay: (v: boolean) => void;
  onNo: (v: string) => void;
}) {
  return (
    <div className="mt-5 rounded-shape-md bg-surface-container px-4 py-4">
      <label className="flex min-h-12 items-start gap-3 text-body-medium text-on-surface">
        <input
          type="checkbox"
          checked={onay}
          onChange={(e) => onOnay(e.target.checked)}
          aria-invalid={errors.demirbas_onayi ? true : undefined}
          className="mt-0.5 size-5 shrink-0 accent-primary"
        />
        <span>
          Bu bilgisayar okul demirbaşıdır.<span className="text-error"> *</span>
          <span className="mt-1 block text-body-small text-on-surface-variant">
            Program yalnız okulun demirbaşı olan bilgisayara kurulur: kişisel bilgisayarlar kurum
            ağında izinsiz kullanılamaz ve Bakanlığa ait veri Bakanlık sistemlerinde barındırılır
            (Bilgi ve Sistem Güvenliği Yönergesi 11/8, 11/23).
          </span>
        </span>
      </label>
      {errors.demirbas_onayi && (
        <p role="alert" className="mt-1 text-body-small text-error">
          {errors.demirbas_onayi}
        </p>
      )}
      <TextField
        className="mt-3 sm:max-w-sm"
        label="Bilgisayarın demirbaş no'su"
        value={no}
        maxLength={64}
        onChange={(e) => onNo(e.target.value)}
        error={errors.demirbas_no}
        helperText="İsteğe bağlı. Taşınır kaydındaki numara; kurtarma anahtarı çıktısında da basılır."
      />
    </div>
  );
}
