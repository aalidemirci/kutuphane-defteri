// Eser künyesi formu (Dialog) — hem katalogdan yeni eser açmak hem ayrıntı
// ekranından künyeyi düzeltmek için. Tek form iki yerde: alan listesi, doğrulama
// ve Türkçe iletiler ikiye ayrılmaz.
//
// Sunucu kuralları burada TEKRARLANMAZ (backend'in kendi kuralıdır): ISBN
// sağlama hatası kaydı ENGELLEMEZ, yalnız uyarı döner; `isbn13`, yer numarası
// tamamlaması ve Türkçe arama anahtarları sunucuda türetilir. Burada yalnız
// "kaynak adı boş olamaz" denetlenir — gerisi backend iletisiyle gelir.

import { useState } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Select from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { CLASSIFICATION_SOURCE_TR, RESOURCE_TYPE_TR, kutuphaneApi } from "./api";
import type { ClassificationSource, ResourceType, Section, Work, WorkBody } from "./api";
import { bolumSecenekleri, kodSecenekleri } from "./ortak";

/** Yayın yılı alanı metin tutulur; boş bırakılabilir, sayı değilse sunucu reddeder. */
function yilGovdesi(deger: string): number | null {
  const temiz = deger.trim();
  if (!temiz) return null;
  const sayi = Number(temiz);
  return Number.isFinite(sayi) ? sayi : null;
}

export default function EserFormu({
  eser,
  bolumler,
  onClose,
  onSaved,
}: {
  /** null → yeni eser; dolu → künye düzeltme. */
  eser: Work | null;
  bolumler: Section[];
  onClose: () => void;
  /** Kaydedilen eser (yeni ya da güncel) ile çağrılır. */
  onSaved: (eser: Work) => void;
}) {
  const [title, setTitle] = useState(eser?.title ?? "");
  const [authors, setAuthors] = useState(eser?.authors ?? "");
  const [translator, setTranslator] = useState(eser?.translator ?? "");
  const [publisher, setPublisher] = useState(eser?.publisher ?? "");
  const [edition, setEdition] = useState(eser?.edition ?? "");
  const [publishYear, setPublishYear] = useState(
    eser?.publish_year == null ? "" : String(eser.publish_year),
  );
  const [isbn, setIsbn] = useState(eser?.isbn ?? "");
  const [subjects, setSubjects] = useState(eser?.subjects ?? "");
  const [classificationCode, setClassificationCode] = useState(eser?.classification_code ?? "");
  const [classificationSource, setClassificationSource] = useState<ClassificationSource>(
    eser?.classification_source ?? "MANUAL",
  );
  const [callNumber, setCallNumber] = useState(eser?.call_number ?? "");
  const [resourceType, setResourceType] = useState<ResourceType>(eser?.resource_type ?? "BOOK");
  const [language, setLanguage] = useState(eser?.language ?? "");
  const [section, setSection] = useState(eser?.section == null ? "" : String(eser.section));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();

  const submit = async () => {
    clearErrors();
    setError(null);
    if (!title.trim()) {
      setFieldError("title", "Kaynak adı yazılmalıdır.");
      return;
    }
    const body: WorkBody = {
      title: title.trim(),
      authors: authors.trim(),
      translator: translator.trim(),
      publisher: publisher.trim(),
      edition: edition.trim(),
      publish_year: yilGovdesi(publishYear),
      isbn: isbn.trim(),
      subjects: subjects.trim(),
      classification_code: classificationCode.trim(),
      classification_source: classificationSource,
      call_number: callNumber.trim(),
      resource_type: resourceType,
      language: language.trim(),
      section: section ? Number(section) : null,
    };
    setBusy(true);
    try {
      const kayit = eser
        ? await kutuphaneApi.updateWork(eser.id, body)
        : await kutuphaneApi.createWork(body);
      snackbar.success(eser ? "Eser güncellendi." : "Eser eklendi.");
      // ISBN sağlama uyarısı kaydı engellemez; kullanıcı yine de görmelidir.
      if (kayit.isbn_warning) snackbar.show(kayit.isbn_warning, { duration: 6000 });
      onSaved(kayit);
    } catch (e) {
      applyApiError(e);
      setError(hataOku(e, "Eser kaydedilemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={eser ? "Künyeyi düzenle" : "Yeni eser"}
      actions={
        <>
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

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            className="sm:col-span-2"
            label="Kaynak adı"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            error={errors.title}
          />
          <TextField
            label="Yazar(lar)"
            value={authors}
            onChange={(e) => setAuthors(e.target.value)}
            error={errors.authors}
            helperText="Ad Soyad sırasıyla; birden çok yazar virgülle ayrılır."
          />
          <TextField
            label="Çevirmen"
            value={translator}
            onChange={(e) => setTranslator(e.target.value)}
            error={errors.translator}
          />
          <TextField
            label="Yayınevi"
            value={publisher}
            onChange={(e) => setPublisher(e.target.value)}
            error={errors.publisher}
          />
          <TextField
            label="Baskı"
            value={edition}
            onChange={(e) => setEdition(e.target.value)}
            error={errors.edition}
          />
          <TextField
            label="Yayın yılı"
            inputMode="numeric"
            value={publishYear}
            onChange={(e) => setPublishYear(e.target.value)}
            error={errors.publish_year}
          />
          <TextField
            label="ISBN"
            value={isbn}
            onChange={(e) => setIsbn(e.target.value)}
            error={errors.isbn}
            helperText="Tireli yazılabilir. Sağlama hatası kaydı engellemez, uyarı verilir."
          />
          <TextField
            className="sm:col-span-2"
            label="Konu(lar)"
            value={subjects}
            onChange={(e) => setSubjects(e.target.value)}
            error={errors.subjects}
            helperText="Birden çok konu virgülle ayrılır."
          />
          <Select
            label="Kaynak türü"
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value as ResourceType)}
            options={kodSecenekleri(RESOURCE_TYPE_TR)}
            error={errors.resource_type}
            helperText={
              eser
                ? "E-kitap ve e-veri tabanında nüsha açılmaz; nüshası olan eserin türü buna çevrilemez."
                : "E-kitap ve e-veri tabanında nüsha açılmaz."
            }
          />
          <Select
            label="Bölüm"
            placeholder="— yok —"
            value={section}
            onChange={(e) => setSection(e.target.value)}
            options={bolumSecenekleri(bolumler)}
            error={errors.section}
          />
          <TextField
            label="Sınıflama kodu"
            value={classificationCode}
            onChange={(e) => setClassificationCode(e.target.value)}
            error={errors.classification_code}
            helperText="Dewey Onlu Sınıflama (DOS) kodu."
          />
          <Select
            label="Sınıflama kaynağı"
            value={classificationSource}
            onChange={(e) => setClassificationSource(e.target.value as ClassificationSource)}
            options={kodSecenekleri(CLASSIFICATION_SOURCE_TR)}
            error={errors.classification_source}
          />
          <TextField
            label="Yer numarası"
            value={callNumber}
            onChange={(e) => setCallNumber(e.target.value)}
            error={errors.call_number}
            helperText="Boş bırakılırsa sınıflama kodu ve yazar kodundan üretilir."
          />
          <TextField
            label="Dil"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            error={errors.language}
          />
        </div>
      </div>
    </Dialog>
  );
}
