# Keşif raporları — 21.09.2026

> Dokuz paralel salt-okur incelemenin ham çıktısıdır; tasarım belgesinin (`../tasarim/2026-09-21-genel-tasarim.md`) kanıt dayanağıdır.
> Yayın için düzenlendi (son geçiş 23.09.2026): yerel mutlak yollar `../<depo>/` biçimine çevrildi; okulun kurum içi ağ bilgisi (IP blokları, alt ağ maskeleri, host numaraları) `<idari-ağ>` / `<tahta-ağı>` yer tutucularıyla değiştirildi; belirli bir okulun personel alışkanlığını anlatan satırlar genelleştirildi.
> Etiketler: DOĞRULANDI / [D] = dosyada okundu; ÇIKARIM / [Ç] = inceleyenin yorumu. Satır numaraları 21.09.2026 tarihli kaynak ağaçlarına aittir.

## İçindekiler

1. [OYS backend — katalog, içe aktarma, etiket dilimi](#r1)
2. [OYS backend — üyelik, ödünç, komisyon, ayıklama, sayım, rapor dilimi](#r2)
3. [OYS ön yüzü ve kardeş kitlerle karşılaştırma](#r3)
4. [OYS içindeki bağlar, planlar, KVKK saklama, okul çekirdeği](#r4)
5. [Mevzuat ve Bakanlık otomasyon sistemi araştırması](#r5)
6. [kelebek-sinav çıkarım şablonu](#r6)
7. [disiplin-defteri karşılaştırması, okulapp.org yayın alanı, kimlik adlandırma](#r7)
8. [OYS ve kardeşlerin okul ağı (FATİH) deneyimi](#r8)
9. [Yerel ağ katalog mimarisi araştırması](#r9)

<a id="r1"></a>

---

## R1. OYS backend — katalog, içe aktarma, etiket dilimi

## OYS kütüphane backend'i: katalog, içe aktarma ve etiket dilimi (salt okuma raporu)

Kök: `../okulapp/backend/apps/kutuphane/` (aşağıda `K/` diye kısaltıldı). Yalnız kod ve doküman okundu. Hiçbir veri dosyası açılmadı, hiçbir dosya değiştirilmedi.

### 0. Önce bilinmesi gerekenler (kısa)

1. **"AI-import" dış servise bağlanmıyor.** Uygulama kullanıcıya bir Excel şablonu ve hazır bir Türkçe prompt veriyor. Kütüphaneci listeyi kendi AI aracına (ChatGPT/Claude) yapıştırıyor, dönen JSON'u uygulamaya yapıştırıyor. DOĞRULANDI: `K/import_schema.py:3-6`, `K/models.py:464-466`, `frontend/src/modules/kutuphane/ImportPage.tsx:1-6`.
   - Uygulama kendi başına çevrimdışı çalışır.
   - Ancak iş akışı kitap listesinin (kişisel veri değil) buluta çıkmasını **öngörüyor**.
   - **Excel'i doğrudan okuyan bir yol YOK.** `K/` altında `load_workbook` ya da `request.FILES` geçmiyor (grep sonucu 0).
2. **Türkçe büyük/küçük harf sorunu.** Arama `icontains`, eşleştirme `iexact` + `str.lower()` ile yapılıyor.
   - SQLite'ta LIKE yalnız ASCII harflerde büyük/küçük ayrımını görmezden gelir. Masaüstünde "şiir"/"ŞİİR", "ılık"/"ILIK" eşleşmez (ÇIKARIM, SQLite'ın bilinen davranışı).
   - Testlerde Türkçe karakterli arama senaryosu yok.
3. **Etikette yalnız QR var, 1D barkod yok** (`K/label_service.py:23-26, 51`). Lazer (1D) el okuyucular QR okuyamaz; 2D okuyucu gerekir.
4. **İçe aktarmada iki kusur:**
   - `shelf_location` Copy'ye aktarılmıyor (`K/import_service.py:170`).
   - Sunucu tarafında idempotency yok. "Önizlenen metin = uygulanan metin" kapısı yalnız frontend'de (`ImportPage.tsx:67-68`).
5. **Katalogda kişisel veri taşıyan serbest metinler var.** `CommissionDecision.chair_name`/`participants_text`, `StockTake.committee_text`, `Acquisition.source_note` ("bağışçı") gerçek kişi adı taşıyabilir. Buna karşın modellerde `kvkk_personal_data=False`. LAN'daki anonim katalog yüzeyine bu alanlar **asla** açılmamalı.
6. PDF motoru WeasyPrint. Kardeş projeler WeasyPrint 68.0'ı Windows'ta zaten paketliyor (`kelebek-sinav/packaging/windows/dll_kapanisi.py`, `NOTLAR.md:20-21`). Etiket ve üye kartı kodu bu yüzden aynen kullanılabilir.

---

### 1. Modeller (`K/models.py`, 1097 satır)

**Ortak taban.** Tüm modeller `shared.models.BaseModel`'den türer (`shared/models.py:50-105`); iki sayaç tablosu hariç.
- Taban alanlar: `created_at`, `updated_at`, `created_by` ve `deleted_by` (FK → `settings.AUTH_USER_MODEL`, SET_NULL), `deleted_at`.
- `delete()` soft-delete yapar. `objects` yalnız canlı kayıtları, `all_objects` hepsini döner.
- Kardeş projelerde `created_by`/`deleted_by` bilinçli olarak çıkarılmış (`kelebek-sinav/backend/shared/models.py:4`, `disiplin-defteri-codex/backend/shared/models.py:4`). Bu yüzden `created_by=` geçen her çağrı masaüstünde uyarlanmalı.

**Şifreli alan: YOK.** `K/` altında encrypt/fernet araması 0 sonuç verdi.

#### 1a. TextChoices (17 adet)

| Enum | Satır | Değerler / not |
|---|---|---|
| ResourceType | 22-34 | BOOK, PERIODICAL, AV_MATERIAL, EBOOK, EDATABASE. "Danışma" bir tür değil, nüsha bayrağı. |
| ClassificationSource | 37-46 | CATALOG, ESTIMATED, MANUAL (AI-import izlenebilirliği) |
| AcquisitionMethod | 49-64 | MINISTRY, PURCHASE, DONATION, EXCHANGE (Md. 10/5) + INVENTORY_FOUND, EXISTING_STOCK (kayıt içi) |
| CopyStatus | 67-81 | AVAILABLE, ON_LOAN, IN_REPAIR, LOST + terminal: WITHDRAWN_WEEDED/_MISSING/_LOST, TRANSFERRED. OVERDUE bir statü değil, sorguyla türetiliyor. |
| CommissionDecisionType | 84-89 | SELECTION, DONATION_REVIEW, WEEDING |
| CatalogImportStatus | 449-458 | DRY_RUN, APPLIED, DISCARDED. **DRY_RUN ve DISCARDED hiç yazılmıyor** (grep: yalnız tanım ve default). |
| MemberType / MembershipStatus / TerminationReason | 567-589 | STUDENT/TEACHER/STAFF · ACTIVE/TERMINATED (askı yok) · GRADUATED…MANUAL |
| LoanStatus / CaseType / CaseResolution | 592-614 | OPEN/RETURNED/LOST_CONVERTED · LOST/DAMAGED · 7 durumlu çözüm makinesi |
| WeedingBatchStatus / WeedingReason / WeedingOutcome | 803-826 | DRAFT→PROPOSED→APPROVED/REJECTED · kapalı liste Md. 12/1 · WITHDRAW/TRANSFER |
| StockTakeStatus / StockTakeCategory | 945-974 | DRAFT→ROUND1→ROUND2→COMPLETED→APPROVED · FOUND/ON_LOAN/IN_REPAIR/MISSING/EXCESS |

#### 1b. Modeller (18 adet)

| Model | Satır | Alanlar (öne çıkanlar) | FK / kısıt | PII bayrağı |
|---|---|---|---|---|
| **LibraryPolicy** (singleton, pk=1) | 92-150 | loan_period_days (1..15), max_loans_student (1..3), max_loans_teacher (1..5), max_loans_staff (1..5), block_loan_if_overdue, retention_years_after_termination (1..10) | Mevzuat tavanları validator'da (104-138). `load()` kaydetmeden varsayılan döner (147-150). | False |
| **CommissionDecision** | 153-186 | decision_type, decision_date, decision_no, **chair_name**, chair_title, **participants_text**, notes | Index(decision_type, decision_date) | False (ama isim taşıyor) |
| **Acquisition** | 189-236 | method, date, **source_note** (bağışçı/satıcı), unit_price Decimal(10,2), commission_decision FK PROTECT null | **CheckConstraint `ck_acquisition_donation_needs_commission`** (226-232): DONATION ⇒ karar dolu | False |
| **Work** | 239-319 | title(500), authors(500), translator, edition, publisher, publish_year, isbn(20, db_index, **tekil değil**), subjects(500), classification_code(60, serbest metin Dewey), classification_source, call_number(80), resource_type(db_index), language | Index title/authors/subjects (307-311). `is_digital` property (316-319). Sıralama: title. | False |
| **Copy** | 322-413 | work FK PROTECT, acquisition FK PROTECT (zorunlu), accession_no (unique), barcode (20, unique), external_asset_ref (TKYS/MEBBİS), shelf_location, is_reference, is_out_of_print, is_bound_periodical, is_rare_or_manuscript, status, label_printed_at | Index(status), Index(work, status). `is_loanable` (401-413). | False |
| **CopyCounter** / **CardCounter** | 416-441 | year PK, last_no | düz `models.Model` (soft-delete yok) | — |
| **CatalogImportRun** | 461-500 | uploaded_file_name, schema_version ("v1"), status, acquisition FK SET_NULL, stats JSON, report JSON | — | False |
| **LabelSheetTemplate** | 503-559 | name; page_margin_top/left; label_width/height; rows, cols; gutter_x/y; corner_radius; offset_x/y (kalibrasyon, mm, Decimal); is_default | **Partial UK `uq_labelsheet_single_default`** (is_default=True ve canlı) (545-552) | False |
| **Membership** | 617-696 | member_student FK→**"core.Student"** PROTECT (627-634), member_user FK→**"core.User"** PROTECT (635-642), member_type, card_no (unique), status, terminated_at, termination_reason | CheckConstraint XOR kişi (663-669) ve tür↔kişi (671-680). Partial UK: kişi başına tek ACTIVE (682-692). | **True** |
| **Loan** | 699-745 | copy FK PROTECT, membership FK SET_NULL null (anonimleştirme için), loaned_at, due_date (idx), returned_at, lost_at, anonymized_at, status | Partial UK `uq_loan_open_per_copy` (737-741) | **True** |
| **LossDamageCase** | 748-795 | copy, membership null, **responsible_note**, loan, case_type, market_price_amount, resolution, anonymized_at, resolved_at | — | **True** |
| **WeedingBatch** | 829-859 | commission_decision PROTECT, school_year FK→**"core.SchoolYear"** (841-843), status, approved_by FK→"core.User", approved_at, notes | — | False |
| **WeedingItem** | 862-896 | batch CASCADE, copy PROTECT, reason, outcome, transfer_target_note | CheckConstraint: TRANSFER ⇒ LEVEL_MISMATCH (887-892) | False |
| **AnnualLibraryReview** | 899-916 | school_year→core.SchoolYear, summary, submitted_at | — | False |
| **RareWorksSubmission** | 919-937 | school_year→core.SchoolYear, **M2M copies**, sent_at, notes | — | False |
| **StockTake** | 977-1031 | school_year→core.SchoolYear, **committee_text** (≥3 kişi), status, round1/2_started_at, completed_at, approved_by→core.User, is_open_singleton (null/True) | Partial UK `uq_stocktake_single_open` (1023-1027) | False (isim taşıyor) |
| **StockTakeItem** | 1034-1097 | stocktake CASCADE, copy null, status_snapshot, round1_found/round2_found, surplus_description, final_category, created_copy FK SET_NULL | Partial UK (stocktake, copy) (1087-1091) | False |

**Başka app'e giden bağlar.**
- `"core.Student"`: `K/models.py:628`.
- `"core.User"`: `K/models.py:636, 848, 1002`. ADR "AUTH_USER_MODEL" diyor, kod doğrudan `"core.User"` yazıyor. Tutarsız ama işlevsel olarak aynı.
- `"core.SchoolYear"`: `K/models.py:842, 905, 925, 989`.
- Migration bağımlılıkları:
  - 0001-0003 **core'a bağımlı değil**, yalnız AUTH_USER_MODEL'e.
  - 0004-0006 `('core','0034_alter_userrole_role')`'e bağımlı (`migrations/0004:12`, `0005:11`, `0006:11`).

**Admin.** `K/admin.py` 16 modeli kaydediyor; StockTake ve StockTakeItem kayıtlı değil (10-27).

---

### 2. Katalog iş kuralları ve invariantlar

- **Barkod ve demirbaş no** (`K/services.py:27-44`):
  - `CopyCounter` yıl bazlı ve `select_for_update`.
  - `barcode = f"K-{year}-{no:05d}"`, `accession_no = year*100000 + no`. Yeniden kullanılmıyor: soft-silinen nüshada da `unique=True` düz kalıyor (`models.py:342-350`, ADR-0040 karar 5).
  - Tespitler:
    - (a) `timezone.now().year` UTC yılını veriyor. 31 Aralık 21:00'den sonra (İstanbul'da 1 Ocak) önceki yılın numarası üretilir (ÇIKARIM; `timezone.localdate().year` olmalı).
    - (b) Yıllık 99.999'u aşan numarada bir sonraki yılın accession_no değeriyle çakışma olur; koruma yok (pratikte önemsiz).
    - (c) SQLite'ta `select_for_update` etkisizdir. Tek yazar varsayımıyla sorun değil (ÇIKARIM).
- **Nüsha açma guard'ları** (`K/services.py:47-63`, serializer'da tekrarı `K/serializers.py:204-223`):
  - Dijital eser (EBOOK/EDATABASE) → nüsha yok.
  - PERIODICAL → yalnız `is_bound_periodical=True` ise (TMY 15/4).
  - Yeni nüsha her zaman AVAILABLE doğar (`services.py:84`).
- **Ödünç verilebilirlik tek noktada** (`models.py:401-413`): danışma değil, piyasada mevcudu var, süreli yayın değil ve AVAILABLE ise.
- **Bağış → komisyon kapısı:**
  - DB CheckConstraint (`models.py:228-232`), serializer (`serializers.py:93-102`) ve import serializer'ı (`serializers.py:266-273`).
  - **Eksik:** kararın `decision_type == DONATION_REVIEW` olduğu ve tarih sırası denetlenmiyor. ADR'deki "komisyon kabulünden önce Copy yaratılmaz (servis kuralı)" (`docs/adr/0040:74-76`) kodda yok; `services.create_copy` bunu kontrol etmiyor (`services.py:66-93`).
- **Eser silme:** canlı nüshası varsa silinemez (`views.py:217-224`). Nüsha ON_LOAN iken silinemez (`views.py:252-260`).
- **ISBN:** tekil değil, doğrulama yok (checksum/biçim yok). Aramada yalnız tam eşleşme (`selectors.py:56-57`).
- **Sınıflama:**
  - `classification_code` serbest metin (Dewey ya da Bakanlık kodu).
  - `call_number` (yer numarası) = kod + yazar soyadının ilk 3 harfi büyük harfle. Yalnız import'ta türetiliyor (`import_service.py:31-40, 121`); elle açılan eserde otomatik türetme yok.
  - Soyad, ilk virgüle kadarki yazarın **son kelimesi** kabul ediliyor. "Ali, Sabahattin" biçiminde yanlış sonuç verir.
  - `.upper()` Türkçe değil: "Ümit" → "ÜMI" (olması gereken "ÜMİ").
- **Kayıttan düşme** soft-delete değil, terminal statü (ADR-0040 karar 6). Etiket kuyruğu terminal nüshaları dışarıda bırakıyor (`selectors.py:93-95`).
- **Sayım fazlası** INVENTORY_FOUND edinimi ve "Tanımsız kaynak (sayım fazlası)" yer tutucu eseriyle katalog'a giriyor (`K/stocktake.py:216-267`). Kataloğa dokunan tek diğer yazma yolu bu.

---

### 3. İçe aktarma hattı

**Akış.** Şablon xlsx indirilir → prompt kopyalanır → dış AI'da JSON üretilir → JSON metni yapıştırılır → `preview` (yazma yok) → `apply` (tek atomic işlem).

- **Şema v1** (`K/import_schema.py:14-58`): `{"schema_version":"v1","items":[…]}`.
  - Alanlar: title (zorunlu), authors, translator, publisher, edition, publish_year, isbn, subjects, classification_code, classification_source, language, resource_type, copies, shelf_location, corrections[], issues[].
  - Prompt, AI'dan "Milli Kütüphane, TO-KAT" kataloglarında Dewey araştırmasını istiyor; bulamazsa ESTIMATED işaretlemesini istiyor (50-53). Bu, web erişimli bir AI varsayıyor.
  - ADR'de adı geçen `catalog-import.schema.json` dosyası **yok** (glob: 0 sonuç). Şema koddaki `validate_payload` fonksiyonu.
- **Doğrulama** (`import_schema.py:84-144`):
  - Sürüm uymazsa ya da items boşsa → `ImportSchemaError`, yanıt 400.
  - Satır sorunları partiyi düşürmüyor, `issues` listesine ekleniyor.
  - Geçersiz tür → BOOK. Geçersiz sınıflama kaynağı → MANUAL.
  - `copies < 1` → 1. **Üst sınır yok** (ÇIKARIM: 5000 yazılırsa 5000 nüsha açılır).
- **Eşleştirme** (`import_service.py:43-65`):
  - ISBN + normalize başlık tutarsa → `existing`.
  - Aksi halde `title__iexact` + normalize yazar tutarsa → `existing`.
  - Yalnız başlık tutarsa → `suspect` (uygulamada yeni eser açılır).
  - Hiçbiri tutmazsa → `new`.
  - `normalize_text` = `lower()` + boşluk sıkıştırma (`import_schema.py:61-64`). Türkçe değil: "IŞIK".lower() = "işik", "Işık".lower() = "ışık", eşleşmez.
  - `iexact` SQLite'ta ASCII dışında büyük/küçük harf katlamaz. Sonuç: **mükerrer eser** oluşur (ÇIKARIM).
- **Önizleme** (`import_service.py:96-106`): ayrı bir hesaplayıcı. ADR-0034'teki rollback-önizleme deseni (`docs/adr/0034:55-62`) burada kullanılmıyor.
  - Önizleme ile uygulama arasında %100 parite yok.
  - Süreli yayın ya da dijital eser için nüsha açılamaması önizlemede görünmüyor, yalnız apply raporunda çıkıyor.
  - Önizleme `CatalogImportRun` kaydı oluşturmuyor.
- **Uygulama** (`import_service.py:129-189`):
  - Tek Acquisition (method varsayılanı EXISTING_STOCK, `serializers.py:256-258`), gerektiği kadar Work ve `copies` adedi kadar `services.create_copy`.
  - Satır hatası `except Exception` ile raporlanıyor (savepoint içinde, tutarlı).
  - **Hata 1:** `shelf_location` create_copy'ye iletilmiyor (`import_service.py:170`); raf bilgisi kayboluyor.
  - **Hata 2:** süreli yayınlarda `is_bound_periodical` import ile verilemiyor, dolayısıyla nüsha hiç açılamıyor.
  - Mevcut eşleşen eserin metadata'sı güncellenmiyor.
- **Idempotency yok.** Hash ya da `expected_hash` yok. Aynı JSON iki kez uygulanırsa nüshalar ikinci kez açılır (eser `existing`'e düşer ama kopya eklenir). Önizleme-uygulama kapısı yalnız frontend state'inde (`ImportPage.tsx:67-68`).
- **Excel şablonu** (`K/excel_template.py:17-63`): openpyxl ile 10 kolon (`TEMPLATE_COLUMNS`, `import_schema.py:17-28`), bir örnek satır ve kırmızı KVKK notu.
  - `note_row = len(TEMPLATE_COLUMNS) and 4` → her zaman 4. Garip ama zararsız.
- **Çevrimdışı ilkesiyle ilişkisi.** Kodda ağ çağrısı yok. Ancak özelliğin varlık nedeni bulut AI kullanımı. Kişisel veri yok (katalog). Yine de "veri kurumda kalır" ilkesi açısından **kullanıcı kararı gerekiyor**.

---

### 4. Etiket, QR ve üye kartı

- **Kütüphaneler:**
  - `segno==1.6.1` (saf Python QR, SVG data-URI): `label_service.py:17, 23-26`, `member_card.py:13, 35-36`.
  - `weasyprint==63.1` (HTML → PDF, fonksiyon içinde tembel import): `label_service.py:160-164`, `member_card.py:68`. Kaynak: `backend/requirements.txt:52, 69`.
  - reportlab ya da python-barcode **yok**. 1D barkod üretimi yok.
- **Sırt etiketi** (`label_service.py:33-54, 91-140`):
  - İçerik: yer numarası (9pt kalın), QR (11 mm, içerik = düz barkod metni), 5pt barkod metni, okul kısaltması.
  - A4, mm hassasiyetinde absolute konum. `_cell_origin` kenar boşluğu, gutter ve kalibrasyon ofsetini hesaba katıyor (73-88).
  - `start_position` yarım tabakayı değerlendirir. Tabaka dolunca yeni sayfaya geçer.
  - Kalibrasyon sayfası her hücreyi çerçeveli ve numaralı basıyor (143-157).
- **Şablonlar.** `LabelSheetTemplate` + seed migration `0003`: 2 preset, "(teyit bekliyor)" işaretli.
  - 30×25 mm, 10×6, varsayılan.
  - Tanex 64×33, 8×3 (`migrations/0003:13-16`).
  - Tek varsayılan kuralı serviste "önce kapat, sonra ata" ile uygulanıyor (`services.py:231-260`). Serializer'daki otomatik UniqueValidator bilinçli olarak boşaltılmış (`serializers.py:323-326`).
- **Basım durumu:**
  - `label_printed_at` boşsa nüsha kuyrukta.
  - Print ucu `mark` varsayılanı True: PDF üretilir üretilmez nüsha "basıldı" işaretleniyor (`views.py:597-598`). Geri alma `labels/mark` ile.
- **Çıktı biçimi:** yalnız PDF (`inline`).
- **Üye kartı** (`K/member_card.py:39-71`):
  - 85×54 mm kart: ad, tür, kart no, QR(card_no), öğrenci fotoğrafı (`student.photo.thumb_b64`, core'daki StudentPhoto'ya getattr bağımlılığı, 43).
  - Hata: `school_name` view'dan hiç geçirilmiyor (`views.py:750-752`), kart başlığı " — KÜTÜPHANE ÜYE KARTI" olarak basılıyor.
  - `thumb` src'ye kaçışsız ekleniyor (45).
  - Kart no biçimi `UK-{yıl}-{no:05d}` (`services.py:113-124`).

---

### 5. REST uçları: katalog, import, etiket

`/api/v1/` öneki var, kimlik doğrulama JWT (`config/settings/base.py:283-292`).
- Sayfalama: `OysLimitOffsetPagination`, varsayılan 25, üst sınır 500 (`shared/pagination.py`).
- İzin sınıfları (`K/permissions.py`):
  - `CanViewLibrary`: GET görüntüleyicilere (yazarlar + MUDUR), yazma yalnız yazarlara (37-56).
  - `CanManageLibrary`: yalnız yazarlar (ADMIN, KUTUPHANECI, MUDUR_YARDIMCISI) (59-73).

| Yöntem | Yol | İzin | Kaynak | PII |
|---|---|---|---|---|
| GET, PUT | library/policy/ | Manage | views.py:141-162 | yok |
| GET | library/school-years/ | View | 1372-1409 | yok |
| CRUD | library/commission-decisions/ (?decision_type) | View | 165-177 | **isim var** |
| CRUD | library/acquisitions/ (?method) | View | 180-190 | source_note bağışçı adı taşıyabilir |
| CRUD | library/works/ (?q, title, author, subject, isbn, resource_type) | View | 193-224 | **yok** |
| CRUD | library/copies/ (?work, status, barcode) | View | 227-260 | yok (iç alanlar var) |
| GET | library/import-runs/, /{id}/ | View | 410-415 | yok |
| CRUD | library/label-templates/ | View | 423-444 | yok |
| GET | library/import/template/ (xlsx) | Manage | 268-279 | yok |
| GET | library/import/prompt/ | Manage | 282-313 | yok |
| POST | library/import/preview/ | Manage | 316-379 | yok |
| POST | library/import/apply/ (201) | Manage | 382-407 | yok |
| GET | library/labels/queue/ (only_unlabeled, work, acquisition, barcode_from/to) | View | 447-547 | yok |
| POST | library/labels/print/ (PDF; gövde doğrulanmıyor, elle okunuyor) | Manage | 550-622 | yok |
| POST | library/labels/calibration/ (PDF) | Manage | 625-646 | yok |
| POST | library/labels/mark/ | Manage | 649-676 | yok |
| GET | library/stats/ | View | 1229-1342 | agregat |
| GET | library/reports/register-xlsx/ | View | 1345-1353 | yok |
| GET | library/memberships/{id}/card/ (PDF, SENSITIVE_READ) | View | 746-755 | **var** |

**LAN katalog tarama (OPAC) için adaylar.**
- Uygun: `works` (list/retrieve) ve `copies`.
- Ancak `CopyReadSerializer` iç alanları da açıyor: accession_no, acquisition, external_asset_ref, label_printed_at (`serializers.py:146-176`). `WorkSerializer` classification_source ve created_at açıyor.
- **Öneri (ÇIKARIM):** beyaz listeli, salt okunur, ayrı bir `opac/` yüzeyi. İçeriği:
  - Eser: başlık, yazar, yayınevi, yıl, konu, yer numarası, tür.
  - Nüsha özeti: raf, danışma bayrağı, "rafta / ödünçte" durumu. Ödünç alanın kimliği ve iade tarihi gösterilmemeli, çünkü okuma alışkanlığı bilgisi sızabilir.
- Mevcut viewset'ler anonim kullanıma **açılmamalı**, yazma metotları var.
- Kardeş uygulamalar `127.0.0.1` + boş port kullanıyor (`kelebek-sinav/desktop/server.py:1`). LAN için sabit port, 0.0.0.0 bağlama ve güvenlik duvarı kuralı gerekiyor. Bu ayrı ajanın konusu.

---

### 6. Katalog araması

- `selectors.search_works` (`K/selectors.py:33-60`):
  - `q` → `title__icontains | authors__icontains | subjects__icontains`.
  - Eksene özel `icontains` süzgeçleri, `isbn` tam eşleşme, `resource_type` eşit.
  - SearchVector, trigram, sıralama ya da relevance **yok**.
  - `q` içinde ISBN, yayınevi ve çevirmen aranmıyor.
  - Sıralama `Meta.ordering = ["title"]` (`models.py:306`).
- **Türkçe:**
  - OYS PostgreSQL kullanıyor (`base.py:227`). icontains orada `UPPER() LIKE` olur ve veritabanı locale'ine bağlıdır.
  - SQLite'ta LIKE yalnız ASCII için büyük/küçük harf duyarsız. Ş/Ç/Ğ/Ö/Ü/İ/ı çiftleri eşleşmez (ÇIKARIM).
  - SQLite'ın BINARY sıralaması Ç, Ş, Ö, Ü, İ ile başlayan başlıkları Z'den sonraya koyar (ÇIKARIM).
  - Testte Türkçe karakterli arama yok (`tests/test_catalog_api.py:142-151`, yalnız ASCII).
- **N+1:** `WorkSerializer.get_copy_count` annotate bekliyor ama `search_works` annotate etmiyor. Her satırda `copies.count()` çalışıyor (`serializers.py:138-143`).
- **Kardeş projedeki emsal:** kelebek-sinav Türkçe→ASCII katlamalı arama yapıyor (`kelebek-sinav/backend/apps/okul/selectors.py:3-7`, `shared/text.py` `tr_lower`/`tr_upper`).
- **Öneri (ÇIKARIM):**
  - Work'e katlanmış bir `search_text` alanı eklenmeli (başlık, yazar, konu, ISBN, yayınevi, çevirmen; Türkçe→ASCII, küçük harf), `save()` ya da serviste güncellenmeli.
  - Sorgu da aynı şekilde katlanıp `contains` ile aranmalı. Büyük koleksiyonda SQLite FTS5 değerlendirilebilir.
  - Sıralama için katlanmış `sort_title` alanı ya da Python tarafında Türkçe sıralama anahtarı.
  - Böylece `search_works` hem masaüstü hem OPAC için tek selector olarak yeniden kullanılır.

---

### 7. Bağımlılıklar

**Python paketleri** (`backend/requirements.txt`): Django 5.1.4, djangorestframework 3.15.2, drf-spectacular 0.27.2, openpyxl 3.1.5 (:47), segno 1.6.1 (:52), weasyprint 63.1 (:69), celery 5.4.0 ve django-celery-beat (:36-37), simplejwt.
- Kardeşler: Django 5.1.15, weasyprint 68.0, openpyxl, waitress, whitenoise. segno'yu eklemek yeterli.
- `CheckConstraint(condition=…)` Django ≥5.1 gerektirir; kardeşlerin sürümü uygun.

**Celery görevleri** (`K/tasks.py`; beat tanımları `base.py:1077-1091`), tümü K3 (dolaşım) tarafında:
- `scan_overdue_loans` (30)
- `anonymize_expired_library_data` (98)
- `library_membership_safetynet` (134)

Masaüstünde Celery olmayacak: uygulama açılışında ya da günlük zamanlayıcıda çalışan fonksiyonlara çevrilmeli (ÇIKARIM).

**Sinyaller** (`K/signals.py`):
- `apps.bildirim.signals` dinleniyor ve yayılıyor: student_status_changed, kutuphane_uyelik_sonlandirildi, kutuphane_clearance_blocked (31-35, 88-92).
- `apps.core.selectors.users_with_role` (35, 47-50) ve `shared.roles.Role` (38).
- `apps.py:9-12` bu bağlantıları kuruyor.

**Diğer app importları:**
- `apps.denetim.services`: `views.py:26-27`, `circulation.py:18` (SENSITIVE_READ).
- `shared.roles.Role`: `permissions.py:15`.
- `shared.models.BaseModel`: `models.py:19`.
- `shared.letterhead`: `reports.py:45`.
- `apps.core.services`: `reports.py:69`.
- `apps.bildirim.models/services`: `tasks.py:33-35`.
- Runtime `get_model("core", …)`: `services.py:263-270, 318-350`, `selectors.py:232-244, 411-416`, `excel_exports.py:106-117`.
- Katalog, import ve etiket dosyalarının (`import_schema`, `import_service`, `excel_template`, `label_service`) core'a **hiç bağımlılığı yok**. `serializers.py` ve `views.py` dolaşım kısımları üzerinden bağlı.

---

### 8. Testler (toplam 109 test fonksiyonu, `grep def test_`)

| Dosya | Adet | Kapsam |
|---|---|---|
| test_catalog_api.py | 15 | Rol izinleri, politika GET/PUT ve tavan, bağış-komisyon, üç eksenli arama (yalnız ASCII), barkod, dijital/süreli yayın guard'ı, eser silme guard'ı, modül bayrağı 404, school-years |
| test_import.py | 14 | Şema reddi ve temizlik, call_number, kovalar (new/existing/suspect), apply, dijital → Work var nüsha yok, uçlar, bağış guard'ı, izin. **shelf_location, idempotency ve Türkçe eşleştirme testi yok.** |
| test_labels.py | 12 | Kuyruk, işaretle/geri al, PDF (`%PDF` başlığı), tabaka taşması, kalibrasyon, şablon CRUD ve seed, varsayılan devri, izin |
| test_models_services.py | 15 | 8'i K1 (politika, sayaç biçimi ve monotonluk, guard'lar, is_loanable matrisi); 7'si refactor servisleri (ayıklama, sayım, üyelik, etiket varsayılanı) |
| test_membership_circulation / test_stocktake / test_weeding | 20 / 21 / 12 | Diğer dilimler |

Testler `apps.core.tests.factories` (StaffUserFactory, add_role, SchoolYearFactory) ve `force_authenticate` kullanıyor (`test_catalog_api.py:17, 29-50`). Tek kullanıcılı, girişsiz masaüstünde bu fixture'lar yeniden yazılmalı.

---

### 9. Masaüstüne taşıma önerisi (dosya dosya)

| Dosya | Karar | Gerekçe ve yapılacaklar |
|---|---|---|
| models.py | **UYARLA** | Katalog modelleri (Policy, CommissionDecision, Acquisition, Work, Copy, sayaçlar, ImportRun, LabelSheetTemplate) aynen alınabilir.<br>• `created_by`/`deleted_by` düşer (kardeş BaseModel).<br>• `"core.Student"`/`"core.User"`/`"core.SchoolYear"` string-FK'ları yerel Member/SchoolYear modellerine çevrilmeli (diğer ajan).<br>• Work'e `search_text`/`sort_title` eklenmeli.<br>• Kullanılmayan DRY_RUN/DISCARDED ya kullanılmalı ya da kaldırılmalı.<br>• Katalogdaki isim alanları KVKK açısından yeniden etiketlenmeli. |
| services.py | **UYARLA** | Katalog kısmı (1-105) neredeyse aynen alınır, ancak:<br>• yıl `localdate()` ile alınmalı;<br>• `created_by` kaldırılmalı;<br>• bağışta karar türü kontrolü eklenmeli;<br>• `get_model("core")` yardımcıları yerel modele çevrilmeli. |
| import_schema.py | **UYARLA** | Şema ve doğrulama aynen kalabilir.<br>• `normalize_text` Türkçe katlamalı olmalı.<br>• `copies` için üst sınır konmalı.<br>• AI prompt'u opsiyonel hale getirilmeli (kullanıcı kararı). |
| import_service.py | **UYARLA** | • shelf_location hatası düzeltilmeli.<br>• Payload hash'iyle idempotency eklenmeli.<br>• Önizleme rollback deseniyle yapılmalı (ADR-0034 karar 6).<br>• Eşleştirme katlanmış alanla yapılmalı.<br>• Süreli yayın için `is_bound_periodical` import alanı eklenmeli.<br>• AI'sız doğrudan Excel okuma yolu eklenmeli (openpyxl zaten var). |
| excel_template.py | **AYNEN** (küçük düzeltme) | Doğrudan Excel yolu eklenirse şablon↔parser read-back testi yazılmalı. |
| label_service.py | **UYARLA** | Mantık iyi.<br>• İsteğe bağlı Code128 (1D) seçeneği eklenmeli.<br>• Türkçe glif için gömülü font kullanılmalı (ÇIKARIM: `sans-serif` paket fontconfig'ine bağlı).<br>• `school_abbrev` ayarlardan gelmeli. |
| member_card.py | **UYARLA** | Fotoğraf kaynağı yerel olmalı (ya da hiç olmamalı); `school_name` geçirilmeli; src kaçışlanmalı. |
| serializers.py | **UYARLA** | Katalog, import ve etiket kısmı (33-327) aynen. OPAC için ayrı beyaz listeli serializer yazılmalı. Üyelik ve dolaşım kısmı diğer dilimde. |
| views.py | **UYARLA** | İnce view'lar; ancak:<br>• JWT, rol, `_log_sensitive`/denetim kaldırılmalı;<br>• drf-spectacular dekoratörleri atılmalı (masaüstünde şema yok, ÇIKARIM);<br>• `LabelPrintView` gövdesi serializer'la doğrulanmalı;<br>• yeni `opac/` salt okunur, anonim ve throttle'lı uçlar eklenmeli. |
| urls.py | **UYARLA** | Yollar korunabilir; OPAC ayrı önekle (LAN'a yalnız o önek açık olmalı). |
| selectors.py | **UYARLA** | Katalog kısmı (33-106, 326-350) Türkçe katlamayla alınmalı, `copy_count` annotate edilmeli. `get_model("core")` yerel modele çevrilmeli. |
| permissions.py | **ALMA** (yerine yeni) | Rol yok. Yerine "yerel makine = yönetici" ve "LAN = yalnız OPAC okuma" ayrımı gelmeli (host/IP tabanlı kapı, ÇIKARIM). |
| admin.py | **ALMA** | Kardeşlerde Django admin yok (ÇIKARIM); acil müdahale için isteğe bağlı. |
| apps.py | **UYARLA** | `signals.connect()` bildirim app'ine bağımlı; masaüstünde kaldırılmalı ya da yerelleştirilmeli. |
| signals.py, tasks.py | **ALMA** (yerine zamanlayıcı fonksiyonları) | bildirim, SMS, core ve Celery bağımlı. Anonimleştirme ve gecikme taraması açılış görevine çevrilmeli. |
| migrations/0001-0006 | **ALMA** (yeniden üret) | 0004-0006 core'a bağımlı. Yeni `0001_initial` + 0003'teki etiket preset seed'i RunPython olarak taşınmalı (preset'ler "teyit bekliyor"; gerçek Tanex ölçüsü kullanıcıdan alınmalı). |
| tests (catalog/import/labels/models_services) | **UYARLA** | Mantık testleri taşınır; fixture'lar yeniden yazılmalı. Eklenecekler:<br>• Türkçe arama ve eşleştirme,<br>• shelf_location,<br>• idempotency,<br>• OPAC PII sızmama testi. |

---

### 10. Kullanıcıya sorulacak kararlar (bu dilimden)

1. **AI köprüsü:** Kitap listesinin kütüphanecinin kendi bulut AI'ına yapıştırılması "veri kurumda kalır" ilkesiyle uyumlu mu?
   - Seçenekler: (a) opsiyonel olarak kalsın, (b) kaldırılsın.
   - Her iki durumda da AI'sız doğrudan Excel içe aktarma eklensin mi?
2. **Barkod okuyucu:** Okulda hangi el okuyucu var, 1D lazer mi 2D imager mı?
   - 1D ise etikete Code128 eklenmeli. Etiket boyutu (30×25 mm) buna yetiyor mu?
3. **QR içeriği:** Düz barkod metni mi, yoksa telefonla okutunca LAN katalog sayfasını açan bir URL mi?
   - URL seçilirse sunucu IP'si ya da adı değişince basılı etiketler bozulur. Öneri: düz barkod kalsın.
4. **LAN katalog kapsamı:**
   - "Rafta / ödünçte" gösterilsin mi?
   - İade tarihi gösterilsin mi? Öneri: hayır.
   - Arama yalnız eser düzeyinde mi olsun?
   - Öğrenci kendi ödünçlerini görsün mü? Bu giriş gerektirir ve OPAC'ı PII'li hale getirir; öneri: kapsam dışı.
5. **Etiket şablonu:** Eldeki Tanex tabakasının model numarası ve ölçüleri nedir? Seed'deki preset'ler "teyit bekliyor" (`migrations/0003:3-6`).
6. **Mevcut koleksiyonun ilk aktarımı:** Kaç eser ve nüsha var (yüzler mi, binler mi)?
   - Bu sayı arama yöntemini belirler: Python tarafında katlama mı, FTS5 mi.
   - Retrospektif barkod aralığı basımı buna göre planlanır.

<a id="r2"></a>

---

## R2. OYS backend — üyelik, ödünç, komisyon, ayıklama, sayım, rapor dilimi

## OYS Kütüphane: üyelik, ödünç, komisyon, ayıklama, sayım ve rapor dilimi haritası

Kök dizin: `../okulapp/backend/apps/kutuphane/` (kısaca `K/`). Satır numaraları gerçek dosya satırlarıdır. Gerçek kişi verisi içeren hiçbir dosya açılmadı; yalnız kod ve doküman okundu.

---

### 0. Önce bilinmesi gereken kritik bulgular

1. **Resmî PDF'e yanlış madde basılıyor.** DOĞRULANDI: `K/reports.py:252` "Taşınır Mal Yönetmeliği Md. 32/6 — sayım noksanı" yazıyor. Kanonik eşleme tablosu `okulapp/data/mevzuat/tasinir-mal-yonetmeligi-ilgili-maddeler.md:154` doğrusunun **Md. 32/7** olduğunu söylüyor. Aynı dosyaya göre kodda eski 2007 numaraları da kalmış:
   - "Md. 32/4" yazıyor, doğrusu 32/5: `models.py:965,1038`, `stocktake.py:39`.
   - "Md. 10/1-m" yazıyor, doğrusu 34/2-c ve 34/3-a: `excel_exports.py:4,101`, `views.py:1357`.
2. **`IN_REPAIR` (onarımda) durumuna hiçbir kod yolu çıkmıyor.** DOĞRULANDI: grep ile hiçbir servis bu değeri atamıyor. `CopyWriteSerializer` `status`'u salt-okunur yapıyor (`serializers.py:202`). Md. 12/1'deki "onarımı gerekli görülen kaynakların bakımı" için iş akışı yok.
3. **Hasar dosyası (`CaseType.DAMAGED`) hiç açılamıyor.** DOĞRULANDI: yalnız `report_lost` dosya açıyor ve türü sabit `LOST` (`circulation.py:135`). Hasar için ne servis ne uç var.
4. **Kayıp/hasar dosyası için anılan "SchoolConfig kapısı" (Md. 19 yalnız ortaöğretimde geçerli) kodda yok.** DOĞRULANDI: bu kapı yalnız docstring'de geçiyor (`models.py:749`).
5. **İlişik kesme (clearance) arayüzünü ogrenci_isleri hiç çağırmıyor.** DOĞRULANDI: backend'de tüketicisi yok. Tek çağıran kütüphanenin kendi ön yüzü (`frontend/src/modules/kutuphane/OduncPage.tsx:437-440`). `docs/MODULES.md:1674`'teki "ogrenci_isleri servis*" kenarı gerçek değil; üretilmiş tablo (`MODULES.md:1629`) yalnız bildirim ve denetim bağını gösteriyor.
6. **Belgelenen `kutuphane_overdue_parent_reminder` sinyali tanımlı değil.** DOĞRULANDI: `bildirim/signals.py:237-247` yalnız üç kütüphane sinyali tanımlıyor. Veli SMS'i sinyal yerine doğrudan `dispatch_to_parent` çağrısıyla gidiyor (`tasks.py:86`). Belge ile kod ayrışmış: `events.md:16`, `MODULES.md:1538`.
7. **Sayım kilidi delikli.** DOĞRULANDI: `report_lost` ve `resolve_case`, `_ensure_circulation_open()` kontrolünü çağırmıyor (`circulation.py:122-180`). Sayım sürerken bir nüshanın durumu ON_LOAN'dan LOST'a, ya da LOST'tan AVAILABLE'a geçebilir.
8. **ADR-0040 çevrimiçi kataloğu (OPAC) bilinçli olarak kapsam dışı bırakmış.** DOĞRULANDI: `docs/adr/0040-kutuphane-modulu.md:27-28`. Yani yerel ağdan tarayıcıyla katalog tarama tamamen yeni bir kapsam; OYS'de karşılığı yok.

---

### 1. Üyelik ve ödünç işleri

#### 1.1 Üyelik modeli (DOĞRULANDI)

- **`Membership`** (`models.py:617-696`): Üye ya bir öğrenci (`member_student` → `core.Student`) ya bir personel (`member_user` → `core.User`) olabilir, ikisi birden olamaz. Her iki bağ da silinmeye karşı korumalı (PROTECT).
- **Veritabanı kısıtları:**
  - XOR kısıtı `ck_membership_xor_person`.
  - Tür uyumu `ck_membership_type_matches_person`: öğrenci türü yalnız öğrenci bağıyla açılır.
  - Kişi başına tek canlı aktif üyelik: `uq_membership_active_student` / `uq_membership_active_user` (`models.py:655-690`).
- **Üye türü** (`MemberType`, `:567`): STUDENT, TEACHER, STAFF. Durum yalnız ACTIVE ve TERMINATED; askı durumu bilinçli olarak yok (`:575-579`).
- **Sonlandırma nedeni** (`TerminationReason`, `:582`): GRADUATED, TRANSFERRED, DROPPED, STAFF_LEFT, MANUAL.
- **Kart no:** `UK-{yıl}-{no:05d}`. `CardCounter` yıl bazlı sayaçtan `select_for_update` ile üretilir (`services.py:114-124`, `models.py:430`).
- **Açılış:** `create_membership` (`services.py:137-171`) ön-kontrol yapar. Toplu açılışta aktif üyeliği olan atlanır (`:175-193`). Nakil dönüşünde eski satır yeniden açılmaz, yeni satır oluşur (`:147`).
- **Sonlandırma:** `terminate_membership` (`:197-215`) koşulsuzdur; açık ödünç sonlandırmayı engellemez (Md. 16/3). Tekrar çağrılırsa bir şey değişmez (idempotent). Commit sonrası sinyal yayar (`:218-222`).
- **Üye kartı:** `member_card.py` WeasyPrint ile 85×54 mm kart basar. Kartta QR (içeriği kart no) ve varsa öğrenci fotoğrafı bulunur; fotoğraf `student.photo.thumb_b64`'ten gelir (core `StudentPhoto`, `core/models.py:1658`). QR için `segno` kullanılıyor; masaüstü emsallerinin (DD/kelebek) bağımlılıklarında yok, yeni eklenecek.
- **Görünen ad:** `_member_display` (`serializers.py:334-344`) öğrenci adını `student.current_name` (core ad geçmişi, `core/models.py:509`) üzerinden, personel adını `user.get_full_name()` ile alır.

#### 1.2 Ödünç, iade ve uzatma (DOĞRULANDI: `circulation.py`)

| Kural | Kod | Dayanak |
|---|---|---|
| Üyelik ACTIVE olmalı | `:72-73` | Md. 17 |
| Nüsha ödünç verilebilir olmalı (`Copy.is_loanable`): danışma değil, piyasada-yok değil, süreli yayın değil, rafta | `models.py:399-413`; `:75-77` | Md. 16/1 a-c |
| Limit açık ödünç sayısıyla ölçülür: öğrenci ≤3, öğretmen ≤5, personel ≤5 (varsayılan 3) | `:34-40, 78-79`; `LibraryPolicy` `models.py:110-127` | Md. 18 (personel için Md. 13, okul takdiri) |
| Süre ≤15 gün; `due_date = bugün + loan_period_days` | `:101`; `models.py:104-109` | Md. 18 |
| Gecikmiş ödüncü olana blok (`block_loan_if_overdue` varsayılan True); gerekçeli istisna tanınabilir → `denetim.log_audit` | `:80-99` | Politika kararı |
| **Uzatma YOK** | `:66-67` docstring | Kullanıcı kararı |
| Sayım (ROUND1/ROUND2) sürerken ödünç ve iade kilitli | `:69, 112, 194-205` | TMY Md. 32/3 |
| Aynı nüshaya tek açık ödünç (yarış kısıtı) | `uq_loan_open_per_copy`, `models.py:738-744` | — |
| İade üyelik durumuna bakmaz; sonlandırılmış üye de iade edebilir | `:110-119` | Md. 18 |

- **Rol farkı:** yalnız limitte var. Kural farkı yok.
- **Gecikme ayrı bir durum değil, sorguyla türetiliyor:** `OPEN` ve `due_date < bugün` (`selectors.py:172-179`, `serializers.py:431-434`). **Ceza yok** (`circulation.py:6`; ADR-0040 `:23-24,101`: "mevzuatta öngörülmemiştir").
- **Boşluklar (DOĞRULANDI):**
  - İstisna tanınırken `override_reason` boş olabiliyor; kontrol yok (`:80-99`).
  - Üyelik sonlandırma ucunda neden değeri doğrulanmıyor (`views.py:742`, `request.data.get("reason", "MANUAL")`).
- **ÇIKARIM:** İade tarihi tatile ya da yaz dönemine denk gelebiliyor (`:101` düz takvim günü sayıyor). Masaüstünde "dönem sonu ödünç kapanışı" kuralı veya `working_days` emsali düşünülmeli.

#### 1.3 Kayıp/hasar vakası (Md. 19)

- **Kayıp bildirimi:** `report_lost` (`circulation.py:122-139`) şu geçişleri yapar: Loan `OPEN→LOST_CONVERTED`, Copy `→LOST`, ve `LossDamageCase(LOST, PENDING)` açılır.
- **Çözüm:** `resolve_case` (`:142-180`). OYS tahsilat yapmaz; bedel (`market_price_amount`) yalnız kaydedilir (`models.py:775-782`).
- **Üye olmayan sorumlu:** `responsible_note` alanına serbest metin yazılır (`:768`).
- **Ön yüz:** çözüm ekranı `market_price` göndermiyor (ÇIKARIM: `frontend/.../kutuphane/api.ts:617`).

#### 1.4 İlişik kesme (clearance)

- `get_student_clearance(student_id)` ve `get_staff_clearance(user_id)` (`selectors.py:153-164`), `ClearanceResult` döner: `is_clear`, açık ödünç sayısı, `LoanBrief` listesi (yalnız barkod ve vade; **eser adı yok**, veri minimizasyonu, `:114-120`), bekleyen dosya sayısı ve üyelik durumu.
- Açık sayılan dosyalar: PENDING ve PRICE_RECORDED (`:134`).
- Uç: `GET /library/clearance/?student=|?staff=`, erişim günlüğüne (SENSITIVE_READ) yazılır (`views.py:855-917`).
- **Çağıran:** yalnız kütüphane ön yüzündeki `OduncPage` "İlişik Kesme" sekmesi (`OduncPage.tsx:44,78,437-440`).
- Bildirimdeki bağlantı `/kutuphane/uyeler?durum=ilisik-kesme` (`signals.py:62`), ama `UyelerPage` bu parametreyi okumuyor (ÇIKARIM: grep'te `searchParams` yok).
- **"İlişik kesme panosu" adında bir liste seçicisi de yok.** Mevcut seçici üye başına çalışıyor (`selectors.py:167`).

---

### 2. Komisyon, ayıklama, yıl sonu raporu ve nadir eserler

- **`CommissionDecision`** (`models.py:153-186`):
  - Türler: SELECTION, DONATION_REVIEW, WEEDING.
  - Başkan ve katılımcılar serbest metin, çünkü başkan ilçe MEM şube müdürü ve OYS kullanıcısı değil (Md. 10/1).
  - Sistem seçim kriterlerini denetlemiyor, kararı kayıt altına alıyor.
  - Uç: `library/commission-decisions/` (düz CRUD, `views.py:165-177`).
- **Bağış kabulü:** `Acquisition.method=DONATION` iken komisyon kararı zorunlu. Bu kural hem veritabanı kısıtında (`ck_acquisition_donation_needs_commission`, `models.py:226-232`) hem serializer'da (`serializers.py:94-103`) var.
  - **Boşluk (DOĞRULANDI):** Kararın türü denetlenmiyor; `DONATION_REVIEW` olması gerekmiyor.
- **Ayıklama** (`weeding.py`):
  - Parti ve kalem modelleri: `WeedingBatch` / `WeedingItem` (`models.py:829-896`).
  - Gerekçe kapalı liste (Md. 12/1 a-ç): WORN, OBSOLETE, LEVEL_MISMATCH, CRITERIA_MISMATCH.
  - Sonuç: WITHDRAW (kayıttan düşüm) veya TRANSFER (devir). Devir yalnız "kurum düzeyine uygun değil" gerekçesiyle yapılabilir; kural hem veritabanında (`models.py:888-894`) hem serviste (`weeding.py:97-100`) var.
  - Nüsha durumu **yalnız APPROVED anında**, tek atomik işlemle değişir (`:42-76`). Engeller: nadir/yazma eser ayıklanamaz (Md. 12/2, `:54-57`); yalnız rafta ya da onarımda olan nüsha ayıklanır (`:26, 58-61`).
  - Onay rolü `CanApproveLibrary` (`views.py:1005-1020`).
  - **Boşluklar (DOĞRULANDI):**
    - Parti açılırken karar türünün `WEEDING` olması denetlenmiyor (`services.py:274-295`).
    - Kalem silme ucu yok; hatalı kalem ancak partinin tamamı reddedilerek düzeltilebiliyor.
    - Teklifi geri çekme (PROPOSED→DRAFT) yolu yok.
- **Taşınır Mal Yönetmeliği ile ilişki:**
  - Ayıklananın kayıttan düşümü "TMY hükümlerine göre" yapılır (Md. 12/1).
  - Varlık İşlem Fişi OYS dışında, TKYS/MEBBİS'te kalır (ADR-0040 `:20-22`).
  - TMY Md. 28/3 hurdaya ayırmada Kayıttan Düşme Teklif ve Onay Tutanağı istiyor (`tasinir-...md:83`), ama OYS ayıklama için bu tutanağı üretmiyor. Yalnız sayım noksanı için hazırlık çıktısı var (ÇIKARIM).
  - Kayıp düşümü (`WITHDRAWN_LOST`, TMY Md. 27) için de tutanak yok.
- **Yıl sonu raporu (`AnnualLibraryReview`, `models.py:899`, Md. 12/1):** Yalnız serbest metin `summary` ve `submitted_at` alanları var. PDF'e istatistik girmiyor (`reports.py:146-157`), oysa `loan_stats` / `collection_summary` hazır (ÇIKARIM: otomatik doldurulabilir).
- **Nadir eser bildirimi (`RareWorksSubmission`, `models.py:919`, Md. 12/2, Genel Müdürlüğe):** Nüsha ilişkisi çoka-çok (M2M).
  - Seçilen nüshaların `is_rare_or_manuscript` olduğu doğrulanmıyor.
  - Komisyon kararına bağ yok, oysa mevzuat "Komisyon tarafından tespit edilen" diyor (DOĞRULANDI: `serializers.py:562-567`).

---

### 3. Sayım (`stocktake.py`; TMY Md. 32)

- **İki turlu akış:**
  - Başlatma (`begin_round1`, `:60-92`): sayım kurulu en az 3 satır olmalı (Md. 32/2, `:50-57`) ve başka başlatılmış sayım bulunmamalı.
  - Başlatırken canlı nüshaların (AVAILABLE, ON_LOAN, IN_REPAIR, LOST) o anki durumu `StockTakeItem.status_snapshot`'a kopyalanır (`bulk_create`, `:76-86`).
- **Barkod okutma:** `scan` (`:100-128`), `POST /stocktakes/{id}/scan/ {barcode}`.
  - Kayıtlı barkod okutulunca o turun işareti (`round1_found` veya `round2_found`) konur ve "MARKED" döner.
  - 2. turda, 1. turda zaten bulunmuş kalem için "ALREADY_FOUND" döner.
  - Kayıtsız ya da terminal durumdaki barkod fazla kalem sayılır ("EXCESS"). Aynı barkod tek fazla kalem üretir; kaydı `copy=NULL`, `surplus_description=barkod`.
- **2. tura geçiş:** `complete_round1` (`:164-178`). Fiziken sayılması gereken (AVAILABLE veya LOST) ama bulunamayan kalem varsa ROUND2'ye (Md. 32/6), yoksa COMPLETED'a geçer.
  - Ödünçte ve onarımdaki nüshalar sayılmaz; teslim belgeli sayılır (kodda "32/4", doğrusu 32/5).
- **Kategoriler:** `_finalize_categories` (`:131-147`) FOUND, ON_LOAN, IN_REPAIR, MISSING, EXCESS yazar.
- **Onay:** `approve` (`:193-251`) şunları yapar:
  - Noksan (MISSING) nüsha → `WITHDRAWN_MISSING`.
  - Fazla (EXCESS) kalem → `INVENTORY_FOUND` ediniminde yeni nüsha. Nüsha "Tanımsız kaynak (sayım fazlası)" yer tutucu eserine bağlanır ve **yeni barkod** alır; okutulan eski barkod raf konumuna yazılır (`:230-245, 254-267`).
  - `is_open_singleton` NULL yapılır.
- **Fark raporu:** Sayım Tutanağı PDF (`reports.py:205`), Sayım Excel'i (iki sayfa: kalemler ve özet, `excel_exports.py:179`), Kayıttan Düşme Teklif ve Onay Tutanağı hazırlığı (`reports.py:233`).
- **Boşluklar:**
  - Kilit aslında COMPLETED'da kalkıyor, çünkü `LOCKING_STATUSES` yalnız ROUND1/ROUND2 (`models.py:1012`). Docstring "onayda kalkar" diyor.
  - Sayımda bulunan LOST nüsha LOST kalıyor; kayıp dosyasıyla uzlaştırılmıyor (`:205-214`).
  - İptal yolu yok; tek yol ModelViewSet'in varsayılan soft-delete'i.
- **ÇIKARIM (LAN için kritik):** Sayım rafta yapılır. Yerel ağdaki ikinci bir cihazla (dizüstü ya da tablet ve USB/Bluetooth barkod okuyucu) okutma çok işe yarar. Ancak telefon kamerasıyla tarayıcıdan okutma, `http://192.168...` adresi güvenli bağlam sayılmadığı için çalışmaz; kameralı tarama HTTPS ister. Bu işlem bir yazma işlemi ve ayrı bir koruma gerektirir (bkz. §8).

---

### 4. Resmî çıktılar

**Şablon mekanizması (DOĞRULANDI):**
- `templates/` dizini yok ve core'daki `base.html`'e dayanmıyor.
- Tüm PDF'ler `reports.py` içinde satır içi HTML metni ve `_STYLE` (A4, 18/16 mm kenar, `sans-serif`) ile üretiliyor.
- Antet: `shared.letterhead.letterhead_authority` (`:45`) + `core.services.get_letterhead_identity` (`:68-71`; `core/services/school_config.py:90-109`). Önce SchoolConfig, boşsa `.env` kullanılıyor.
- İmza bloğu tablo olarak kurulmuş (`:55-57`).

| # | Belge | Üretici | Dayanak (koddaki) | İmza bloğu |
|---|---|---|---|---|
| 1 | Ayıklama Tutanağı | `reports.py:86` | Md. 12/1 | Kütüphaneci / Müdür Yardımcısı / Komisyon Başkanı (adlar boş) |
| 2 | Devir Listesi PDF + Excel | `reports.py:110`, `excel_exports.py:235` | Md. 12/1; TMY 24 | Kütüphaneci / Müdür Yardımcısı |
| 3 | El Yazması ve Nadir Eserler Listesi | `reports.py:129` | Md. 12/2 | Kütüphaneci / Müdür |
| 4 | Yıl Sonu Kütüphane Raporu | `reports.py:146` | Md. 12/1 | Kütüphaneci / Müdür |
| 5 | Gecikmiş İadeler Listesi | `reports.py:160` | Md. 18 | yok. **Üye adı yok** (barkod, eser, vade) |
| 6 | Sayım Tutanağı PDF + Excel | `reports.py:205`, `excel_exports.py:179` | TMY 32 | Kurul üyeleri, `committee_text` satırlarından |
| 7 | Kayıttan Düşme Teklif ve Onay Tutanağı (HAZIRLIK) | `reports.py:233` | "32/6" basılıyor (**hatalı**, doğrusu 32/7) | Sayım Kurulu / Harcama Yetkilisi |
| 8 | Üye Kartı | `member_card.py:57` | Md. 20 | — |
| 9 | Kütüphane Defteri (Excel) | `excel_exports.py:55` | TMY 9/1-ç | — |
| 10 | Müze/Kütüphane Yönetim Hesabı Cetveli (HAZIRLIK, Excel) | `excel_exports.py:100` | "10/1-m" (doğrusu 34/2-c) | — |

- **Üretilmeyenler (ÇIKARIM):**
  - Taşınır Sayım ve Döküm Cetveli (TMY 32/9).
  - Ayıklama ve kayıp için Kayıttan Düşme Teklif ve Onay Tutanağı (TMY 27, 28/3).
  - Bağış kabul karar tutanağı.
  - "Kütüphaneden ilişiği yoktur" belgesi (nakil ve mezuniyet için pratik).
  - Öğrenciye elden verilecek gecikme hatırlatma pusulası.
- **Masaüstü emsali:** DD ve kelebek WeasyPrint 68'i zaten paketliyor (`disiplin-defteri-codex/backend/requirements.txt:34`).

---

### 5. Durum makineleri (DOĞRULANDI)

**Nüsha (Copy)** (geçişler yalnız circulation, weeding ve stocktake servislerinden yapılıyor):

| Önce | Sonra | Tetik |
|---|---|---|
| (yeni) | AVAILABLE | `services.create_copy` `:67`; `stocktake.approve` fazla kalem `:230-245` |
| AVAILABLE | ON_LOAN | `checkout` `:105` |
| ON_LOAN | AVAILABLE | `return_copy` `:118` |
| ON_LOAN | LOST | `report_lost` `:130` |
| (herhangi, genelde LOST) | AVAILABLE | `resolve_case` FOUND_RETURNED / REPLACED_SAME / CLOSED_SAME_REPURCHASED `:163-168` (mevcut durum denetlenmiyor) |
| LOST | WITHDRAWN_LOST | `resolve_case` CLOSED_OTHER_REPURCHASED / WRITTEN_OFF `:169-170` |
| AVAILABLE, IN_REPAIR | WITHDRAWN_WEEDED / TRANSFERRED | `weeding.approve` `:63-70` |
| AVAILABLE, LOST, IN_REPAIR | WITHDRAWN_MISSING | `stocktake.approve` `:208-214` |
| — | IN_REPAIR | **Yol yok** |

WITHDRAWN_* ve TRANSFERRED terminal durumlardır, soft-delete değildir; defterde görünür kalırlar (`models.py:67-72`).

**Diğer makineler:**
- **Loan:** `OPEN → RETURNED | LOST_CONVERTED` (ikisi de terminal). Gecikme türetilir. Anonimleştirme durum değil, `membership=NULL` ve `anonymized_at` ile yapılır.
- **Membership:** `ACTIVE → TERMINATED` (terminal; yeniden üyelik yeni satır).
- **LossDamageCase:**
  - `PENDING → PRICE_RECORDED` açık kalır; aynı değere yeniden geçilebilir, bedel güncellenir.
  - `PENDING | PRICE_RECORDED →` şu terminal çözümlerden biri: FOUND_RETURNED, REPLACED_SAME, CLOSED_SAME_REPURCHASED, CLOSED_OTHER_REPURCHASED, WRITTEN_OFF (`circulation.py:183-191`).
  - Terminal durumdan çıkış reddedilir (`:158-159`).
- **WeedingBatch:**
  - `DRAFT →` teklif (en az 1 kalem) `PROPOSED`.
  - `PROPOSED →` onay `APPROVED` ya da ret `REJECTED`; onaylayanın `approved_by`/`approved_at` bilgisi yazılır.
- **StockTake:**
  - `DRAFT →` başlatma `ROUND1` (anlık görüntü alınır, kilit başlar, `is_open_singleton=True`).
  - `ROUND1 →` fark varsa `ROUND2`, yoksa `COMPLETED`; `ROUND2 → COMPLETED`.
  - `COMPLETED →` onay `APPROVED` (`is_open_singleton=NULL`).
  - Aynı anda tek başlatılmış sayım kuralı: `uq_stocktake_single_open` (`models.py:1022-1028`).

---

### 6. Celery görevleri, sinyaller ve dış kanallar

**Zamanlanmış görevler** (`config/settings/base.py:1074-1093`) ve masaüstü karşılıkları:

| Görev | Zaman | İş | Masaüstü önerisi |
|---|---|---|---|
| `scan_overdue_loans` (`tasks.py:30-95`) | Her gün 06:50 | Kütüphaneci, müdür yardımcısı ve yöneticiye PII'siz özet; öğretmen/personele bireysel bildirim; bayrak açıksa veliye SMS | **Senkron pano kartı** ("Gecikmiş iadeler: N"), `selectors.overdue_loans()`'tan anlık okunur. DD emsali: "süre taraması senkron panele dönüştü" (`disiplin-defteri-codex/CLAUDE.md:191`) |
| `library_membership_safetynet` (`:134-157`) | Her gece 02:50 | Kaçan sinyal ve personel ayrılışı için aktif üyelikleri tarar | e-Okul ya da personel **içe aktarımından sonra** fark adımı ve açılışta çalıştırılır (idempotent) |
| `anonymize_expired_library_data` (`:98-131`) | Her ayın 1'i 04:25; modül kapalıyken de çalışır | Sonlanış + N yıl sonra Loan ve Case'in üyelik bağını koparır | **Açılışta** çalışır; aylık koruma için son çalışma tarihi tutulur; ayrıca elle "Şimdi uygula" düğmesi |

**Sinyaller:**
- Yaydıkları: `kutuphane_uyelik_sonlandirildi` (entegrasyon), `kutuphane_clearance_blocked` (`signals.py:27-65`, `on_commit`). Alıcılar `core_selectors.users_with_role` ile bulunuyor.
- Dinlediği: `student_status_changed` (`signals.py:68-92`). Yayan yerler: `core/services/students.py:228-236` ve `promotion.py:234-242`.
- **Masaüstünde:** bildirim uygulaması yok. İçe aktarım servisi `terminate_membership`'i doğrudan çağırır. "İlişik kesme bekleyenler" panosu için **yeni bir seçici** gerekir: TERMINATED ve açık yükümlülüğü olan üyeler.

**Veli SMS'i:**
- `MessagingSettings.library_overdue_sms_enabled` (`bildirim/models.py:884`), `dispatch_to_parent` üzerinden gidiyor (`bildirim/services.py:369`).
- Masaüstünde **ALINMAMALI**: dış kanal, bulut yok ilkesine aykırı.
- Yerine metni `tasks.py:24-28`'deki ceza imasız metinden alınan, yazdırılabilir bir **"İade hatırlatma pusulası"** önerilir (öğrenciye elden). Kullanıcıya sorulacak.

---

### 7. KVKK

- **Kişisel veri işaretleri:** `Membership`, `Loan` ("YÜKSEK RİSK PII — okuma alışkanlığı", `models.py:699-705`) ve `LossDamageCase` için `kvkk_personal_data=True`. Katalog, ayıklama ve sayım modelleri `False`.
- **Anonimleştirme:** `tasks.py:115`, `cutoff = now − 365 × retention_years_after_termination` (varsayılan 2, aralık 1..10; `models.py:133-138`). Açık yükümlülüğü olan atlanır (`:122`). Bağ koparılır ve `anonymized_at` yazılır (`:124-127`). Boşluklar (DOĞRULANDI):
  - `Membership` satırının kendisi (kart no ve öğrenci/personel bağı) **hiç anonimleşmiyor**.
  - `responsible_note` serbest metni temizlenmiyor.
  - PRICE_RECORDED'da kalan dosya anonimleştirmeyi **süresiz** engelliyor (`selectors.py:134`).
  - Aktif üyenin ödünç geçmişi süresiz birikiyor (ÇIKARIM).
- **Erişim günlüğü (SENSITIVE_READ):**
  - Tanım `views.py:130-138`. Günlüğe yazılan uçlar: kart (`:749`), geçmiş (`:761`), ilişik kesme (`:910,915`).
  - **Loglanmayanlar:** `GET /library/loans/`, eser adı ve üyelik kimliğini döndüğü hâlde loglanmıyor (`views.py:793-803`); üyelik listesi de loglanmıyor.
  - `_client_ip`, X-Real-IP ve X-Forwarded-For başlıklarına güveniyor (`:117-127`). LAN ayrımında **kullanılmamalı**, çünkü bu başlıklar sahtelenebilir; yalnız `REMOTE_ADDR` esas alınmalı.
- **Denetim (denetim) bağımlılıkları:**
  - `circulation.py:18,89-99` (`log_audit`, gerekçeli istisna).
  - `views.py:26-27,130-138` (`log_access`).
  - `denetim/kvkk_scope.py:169-171`.
  - `denetim/services.py:818-832` (KVKK ihracı).
  - `denetim/management/commands/anonymize_database.py:255-256,579,676-678`.
  - Test: `tests/test_membership_circulation.py:19`.
- **Masaüstü önerisi:**
  - AccessLog/AuditLog kaldırılır (DD emsali: `CLAUDE.md:181`).
  - Gerekçeli istisna **Loan üzerinde yeni bir alanda** tutulur.
  - LAN'a hiçbir kişisel veri çıkmaz, dolayısıyla LAN erişim günlüğü gerekmez.
  - "Üye verisi dökümü" (KVKK md. 11 başvurusu) isteğe bağlı olabilir; kullanıcıya sorulacak.
  - Masaüstünde öğrenci sicili yerel olacak. Öğrenci silinmeye korumalı (PROTECT) olduğundan, ayrılan öğrencinin kaydı imha edilmek istendiğinde üyelik satırı buna engel olur. **Karar gerekir:** üyeliğe ad/sınıf anlık kopyası mı tutulsun, yoksa süre dolunca üyelik de mi anonimleşsin?

---

### 8. Rol ve izin modeli

- **Mevcut model** (`permissions.py`):
  - Yazma yetkisi (`_LIBRARY_WRITERS`): ADMIN, KUTUPHANECI, MUDUR_YARDIMCISI.
  - Görüntüleme: bunlara ek olarak MUDUR.
  - Onay (`_LIBRARY_APPROVERS`): ADMIN, MUDUR_YARDIMCISI, MUDUR (`:17-20`). Teklif ile onayın ayrı kişilerde olması ayıklama ve sayım onayında uygulanıyor.
  - Yetkisizlik 403 yerine 400 `ValidationError("Yetki yok.")` olarak dönüyor; `views.py`'de 11 yerde.
- **Tek kullanıcılı masaüstünde:** DD emsaliyle rol yok (`AllowAny`, `disiplin-defteri-codex/CLAUDE.md:176`).
  - Teklif/onay ayrımı rol olarak değil, **iki adımlı durum makinesi** olarak korunur. `approved_by` (User'a bağ) yerine onaylayanın adı metin olarak tutulur (ya da yerel `Personnel`'e bağlanır). İmzalar zaten kâğıtta atılıyor.
  - İmza bloklarına `CommissionDecision.chair_name` ve kurul adları doldurulabilir.
- **LAN tarafında hâlâ anlamlı ayrımlar:** rol değil, **kanal ayrımı**.
  - (a) PII taşıyan tüm uçlar (üyelikler, ödünçler, dosyalar, ilişik kesme, kart, geçmiş) **yalnız yerel makinede** (127.0.0.1 ve DD'deki oturum belirteci) çalışmalı.
  - (b) Tüm yazma uçları yerelde kalmalı. İstisna olarak kullanıcı isterse sayım okutması LAN'dan, ayrı ve süreli bir "sayım oturumu PIN'i" ile açılabilir.
  - (c) LAN'a açılacak uçlar: salt-okunur katalog ve nüsha müsaitliği. Gösterim: "Rafta", "Ödünçte" (iade tarihi gösterilsin mi: **soru**), "Yalnız kütüphanede okunur" (`is_reference`), raf ve yer numarası. Terminal ve LOST nüshalar gizlenir.
  - (d) Ek aday: `most_read_works` (agregat "Ayın Kitapları", Md. 15/ğ).
  - Emsal bilgisi: DD ve kelebek yalnız 127.0.0.1'e bağlanıyor (`kelebek-sinav/desktop/server.py:8`); LAN dinleme yeni bir tasarım.
- **ÇIKARIM (katalog dilimi dışı ama LAN taramasını doğrudan etkiliyor):** `search_works` `icontains` kullanıyor (`selectors.py:33-60`). SQLite'ın LIKE'ı yalnız ASCII harflerde büyük/küçük harf ayırmıyor; İ/ı/Ş/Ğ/Ç/Ö/Ü eşleşmez. Normalize edilmiş bir arama alanı gerekir; DD'de `apps/okul/normalize.py` ve `selectors.py:~110` emsal olarak var.

---

### 9. REST uçları (bu dilim) ve testler

Tüm uçların önekinde `library/` var (`urls.py`).

| Grup | Uçlar |
|---|---|
| Politika | `policy/` GET, PUT |
| Üyelikler | `memberships/` CRUD (varsayılan silme de açık) + `bulk/` POST · `{id}/terminate/` POST · `{id}/card/` GET PDF · `{id}/history/` GET |
| Ödünç | `checkout/` POST {barcode, card_no, override_*} · `loans/` GET (`?overdue=1&status&copy`) + `{id}/return/`, `{id}/report-lost/` POST |
| Kayıp/hasar | `loss-damage-cases/` GET + `{id}/resolve/` POST |
| İlişik ve gecikme | `clearance/` GET · `reports/overdue-pdf/` GET |
| Komisyon ve edinim | `commission-decisions/` CRUD · `acquisitions/` CRUD |
| Ayıklama | `weeding-batches/` CRUD + `{id}/items/` · `propose` · `approve`* · `reject`* POST · `report`, `transfer-list`, `transfer-list-xlsx` GET |
| Yıl sonu ve nadir eser | `annual-reviews/` CRUD + `{id}/pdf/` · `rare-works/` CRUD + `{id}/pdf/` |
| Sayım | `stocktakes/` CRUD + `begin`, `scan`, `complete-round1`, `complete-round2`, `approve`* POST · `items` (sayfalı), `report-pdf`, `report-xlsx`, `writeoff-proposal-pdf` GET |
| İstatistik ve defter | `stats/` · `reports/register-xlsx/` · `reports/management-account-xlsx/` · `school-years/` |

\* `CanApproveLibrary` gerektirir. Ayıklama ve sayımda gövde elle okunuyor (`views.py:936-958, 1104-1136`; borç: `F-kutuphane-create-dogrulamasiz`).

**Testler (bu dilim: 53):**
- `test_membership_circulation.py`: 20.
- `test_stocktake.py`: 21.
- `test_weeding.py`: 12.
- Modülün toplamı: 109.
- **Eksik testler:** `scan_overdue_loans`, sayım sırasında `report_lost`, DAMAGED, çözüm sırasında nüsha durumu.
- Testler `apps.core.tests.factories` (StudentFactory, StaffUserFactory, SchoolYearFactory, add_role), `denetim.AccessLog` ve `shared.roles.Role` kullanıyor; masaüstüne taşırken uyarlanmaları gerekecek.

---

### 10. Dosya bazında öneri ve dış bağların karşılığı

| Dosya | Öneri | Gerekçe |
|---|---|---|
| `circulation.py` | **UYARLA (küçük)** | Mantık aynen kalır. `denetim` importu kalkar, gerekçeli istisna `Loan.override_reason` alanına yazılır. `by_user`/`created_by` kalkar (DD BaseModel'de bu alanlar yok: `disiplin-defteri-codex/backend/shared/models.py:4`). `report_lost`/`resolve_case`'e sayım kilidi eklenir. İstisna gerekçesi zorunlu olur. |
| `services.py` (üyelik, ayıklama, sayım kısmı) | **UYARLA** | `get_model("core","Student"/"User"/"SchoolYear")` yerine yerel `okul.Student`/`Personnel`/`SchoolYear` gelir (DD `apps/okul/models.py:77,201,318`). Sayaçlar aynen kalır; SQLite'ta `select_for_update` hiçbir şey yapmaz ama tek yazar olduğu için sorun değil (DD kabul etmiş). Karar türü denetimi eklenir. |
| `weeding.py` | **AYNEN** (+`approved_by_name`) | Saf iş kuralı. Kalem silme ve teklifi geri çekme eklenmeli. |
| `stocktake.py` | **AYNEN** (+madde düzeltmesi) | 32/4→32/5 ve 32/6→32/7 docstring'leri düzeltilir; LOST olup bulunan nüshaların uzlaştırılması eklenir. |
| `reports.py` | **UYARLA** | `_identity()` yerel SchoolConfig'ten beslenir (DD `shared/letterhead.py` var). **`:252` düzeltilir.** İmza adları doldurulur. Gecikmiş listesine üye adı/sınıfı eklensin mi: soru. Ayıklama ve kayıp için düşüm tutanağı eklenmesi düşünülür. |
| `excel_exports.py` | **AYNEN** | Yalnız SchoolYear kaynağı değişir; "10/1-m" düzeltilir. |
| `member_card.py` | **UYARLA** | Fotoğraf isteğe bağlı olur; ad yerel modelden gelir; `segno` bağımlılığı eklenir. |
| `selectors.py` | **AYNEN** + ekler | `_school_year_bounds`/`list_school_years` yerel modele bağlanır. Yeni: `pending_clearances()`, PII'siz `opac_search` ve `opac_copy_availability`, Türkçe duyarlı arama. |
| `signals.py` | **ALMA** | bildirim ve core sinyal altyapısı yok; içe aktarım farkından doğrudan servis çağrısı yapılır. |
| `tasks.py` | **UYARLA → `jobs.py`** | Celery kalkar, düz fonksiyon olur; açılış ve içe aktarım kancası ile pano. SMS kısmı ALMA. |
| `events.md` | **ALMA** | Yerine kısa bir "süreç içi kancalar" notu. |
| `permissions.py` | **ALMA** | Yerine LAN kanal koruması (salt `REMOTE_ADDR`, OPAC önek listesi). |
| `serializers.py` (dilim) | **UYARLA** | `_member_display` yerel modelden; `created_by` kalkar; PII'siz OPAC serializer'ları eklenir. |
| `views.py` (dilim) | **UYARLA** | `extend_schema` kalkar (DD'de drf-spectacular yok). `_log_sensitive`/`_client_ip` ve rol kontrolleri kalkar. Sonlandırma nedeni doğrulanır. Tehlikeli varsayılan `destroy`/`update` kapatılır. |
| `urls.py` | **UYARLA** | Yerel `library/` ve LAN `opac/` ayrı URL yapılandırmaları. |
| migrations 0004-0006 | **ALMA** | Hedef modeller değişiyor (core.* ve AUTH_USER); yeni projede temiz `0001` üretilir. |
| tests (53) | **UYARLA** | Fabrikalar yerele taşınır; rol ve AccessLog testleri çıkar; LAN koruma testleri ve eksik senaryolar eklenir. |

**Dış bağlar ve masaüstü karşılıkları:**
- **core:**
  - `core.Student` → yerel öğrenci sicili. Kaynak e-Okul içe aktarımı (DD/kelebek emsali). Durum değerleri DD'de ACTIVE/LEFT (`apps/okul/models.py:313`); OYS'deki GRADUATED/TRANSFERRED/DROPPED nedenleri için eşleme kararı gerekir.
  - `core.User` (personel üye) → giriş yapmayan `Personnel` kaydı. Ayrılışı izlemek için "aktif/ayrıldı" bayrağı eklenmeli; DD'nin Personnel modelinde bu alan yok.
  - `core.SchoolYear` → yerel.
  - `get_letterhead_identity` → yerel SchoolConfig.
  - `users_with_role` / `shared.roles` → kalkar.
  - Ön yüzde `/students/?q=`, `/users/lookup/` (`api.ts:534-542`) → yerel arama uçları.
  - `student_status_changed` → içe aktarım farkı.
- **bildirim:** üç sinyal, `EventType.LIBRARY_*` (`bildirim/models.py:168-169`), SMS bayrağı ve `notification_routes.py:40-41` → hepsi **pano kartı ve yazdırılabilir pusula**.
- **denetim:** `log_audit` → Loan alanı; `log_access` → yok; KVKK ihracı → isteğe bağlı "üye verisi dökümü"; `anonymize_database` → yok (masaüstünde anonim demo veritabanı gerekmiyor).
- **raporlar:** kod bağı **yok** (`MODULES.md:1688-1697`, "hayalet kenar"). Karşılığa gerek yok; agregat seçiciler yerel "İstatistik" sayfasında kullanılır.
- **ogrenci_isleri:** kod bağı **yok** (yalnız niyet). Masaüstünde ilişik kesme kendi ekranında kalır ve bir "İlişiği yoktur" belgesi eklenebilir.
- **nobet:** yalnız ön yüz bağı var (`KutuphaneNobetPage.tsx:18-19,42,73`; kulüp öğrencilerinin kütüphane nöbeti) → **ALMA** (nöbet motoru yok). İstenirse basit bir nöbetçi öğrenci listesi olabilir.
- **sosyal_etkinlikler:** yalnız ön yüzde `/clubs/?limit=100` çağrısı (`KutuphaneNobetPage.tsx:61`) → **ALMA**.

---

### Kullanıcıya sorulacaklar

1. **Mevcut veri:** OYS kütüphane modülünde canlı veri (katalog, üye, ödünç) var mı? Varsa OYS'den aktarım yolu gerekir.
2. **LAN'da görünecekler:** "Ödünçte" yanında iade tarihi gösterilsin mi? "Ayın Kitapları" LAN'a açılsın mı?
3. **Sayım okutması:** İkinci bir cihazdan yerel ağ üzerinden yapılsın mı? Yapılacaksa PIN korumalı olmalı, ve telefon kamerasıyla okutma HTTP üzerinden çalışmaz.
4. **Gecikme takibi:** SMS yerine yazdırılabilir pusula uygun mu? Gecikmiş listesinde öğrenci adı ve sınıfı yer alsın mı?
5. **Üyelik kaydının saklanması:** Süresi dolunca üyelik satırı da mı anonimleşsin, yoksa öğrenci sicilinden bağımsız ad kopyası mı tutulsun? Aktif üyelerin ödünç geçmişine de bir saklama süresi uygulansın mı?
6. **Personel üyeliği:** Öğretmen/personel üyeliği `Personnel` kaydıyla mı yürüsün? Ayrılış elle mi işaretlensin?
7. **Eksik çıktılar ve akışlar:** Şunlar bu sürümde yapılsın mı?
   - Ayıklama ve kayıp için Kayıttan Düşme Teklif ve Onay Tutanağı.
   - Taşınır Sayım ve Döküm Cetveli.
   - "İlişiği yoktur" belgesi.
   - Onarım (IN_REPAIR) ve hasar (DAMAGED) akışı.
8. **Kayıp/hasar dosyası kapsamı:** Md. 19 yalnız ortaöğretim için; okul türüne göre açılıp kapanan bir kapı eklensin mi, yoksa yalnız ortaöğretim mi hedefleniyor?

<a id="r3"></a>

---

## R3. OYS ön yüzü ve kardeş kitlerle karşılaştırma

## OYS Kütüphane ön yüz haritası ve kardeş masaüstü projelerle karşılaştırma

Kısaltmalar: **KS** = kelebek-sinav, **DD** = disiplin-defteri-codex. Satır sayıları PowerShell `Measure-Object -Line` ile alındı, boş satırlar dahil değil.

### 0. Öne çıkan sonuçlar

1. **Tasarım dili taşımayı zorlaştırmıyor.** Kütüphanenin kullandığı 12 ortak bileşenin hepsi KS/DD kitinde de var ve prop'ları aynı. Kütüphane Mürekkep'e özgü hiçbir token ya da bileşen kullanmıyor. Sayfalar KS kitine neredeyse hiç değişmeden oturur (ayrıntı §4).
2. **Sayfalama eksik.** Backend sayfa başına 25 kayıt döndürüyor, ön yüzde sayfalama arayüzü yok. Katalogda, bir eserin nüshalarında ve açık ödünç listesinde ilk 25'ten sonrası sessizce görünmüyor. Açık ödünç 25'i geçince bazı kitapların **iadesi arayüzden alınamaz**, çünkü "barkodla iade" diye bir işlev yok (§2, §5).
3. **Barkod okuyucuya uygun değil.** Yalnız sayım ekranı Enter tuşunu işliyor. Ödünç verme ekranında Enter yok, alana kendiliğinden odaklanma yok, barkodla iade yok. Kamera ile okuma hiç yok. Etiketler ve üye kartları **yalnız QR** basıyor, bu yüzden 1D lazer okuyucu işe yaramaz; 2D okuyucu gerekir (§2).
4. **Tek kullanıcılı, girişsiz uygulamada iki kural boşa düşüyor.** OYS'de "teklif ≠ onay" ayrımı ve okuma geçmişine sınırlı erişim rollerle sağlanıyor. Tek kullanıcılı, girişsiz uygulamada bu ayrım kendiliğinden ortadan kalkar. Bu bir karar konusu (§7).
5. **Ağdan katalog tarama (OPAC) için öneri:** sunucu tarafında basit HTML, ayrı bir URL kümesi ve ayrı bir dinleyici. İkinci seçenek ayrı bir Vite derlemesi. Aynı SPA içinde ayrı rota ağacı önerilmez (§5).

---

### 1. Kütüphane ön yüz sayfaları

Dizin: `okulapp/frontend/src/modules/kutuphane/`. Toplam yaklaşık 4.740 satır sayfa/yardımcı, 777 satır `api.ts` ve 753 satır test. Hepsi TanStack Query kullanıyor; tek istisna `KutuphaneNobetPage`, o `useEffect` ile çalışıyor.

**Ortak bileşen kısaltmaları:** Btn = Button · Crd = Card · Dlg = Dialog · Ic = Icon · Sel = Select · Sk = SkeletonList · Snk = useSnackbar · Cnf = useConfirm · TF = TextField · Tab = Tabs · AC = Autocomplete · HFC = HubFeatureCard.

| Sayfa | Satır | İşlevi | API uçları (`/api/v1` altında) | Ortak katman |
|---|---|---|---|---|
| KutuphaneHub | 80 | 11 kartlık ana sayfa | — | HFC |
| KatalogPage | 289 | Eser listesi, `q` araması, tür süzgeci, yeni eser. `WorkDialog` ve `EMPTY_WORK_FORM` buradan dışa verilir | `GET/POST library/works/` | Btn Crd Dlg Ic Sel Sk Snk TF · useAuth, roles |
| EserDetayPage | 391 | Eser künyesi (düzenle/sil) + nüsha listesi, nüsha ekle/sil | `works/{id}` GET/PATCH/DELETE · `copies/?work=` GET/POST · `copies/{id}` DELETE · `acquisitions/` GET | Yukarıdakiler + Cnf |
| EdinimlerPage | 374 | İki sekme: edinim partileri, komisyon kararları | `acquisitions/`, `commission-decisions/` GET/POST | + Tab |
| ImportPage | 415 | Dış yapay zekâ köprüsü: şablon, prompt kopyalama, JSON önizleme, uygulama | `import/template/` (blob) · `import/prompt/` · `import/preview/` · `import/apply/` · `import-runs/` · `commission-decisions/` | `saveBlob`, `navigator.clipboard` (:142) |
| EtiketlerPage | 485 | Baskı kuyruğu (QR sırt etiketi PDF'i) + şablon yönetimi + hizalama sayfası | `labels/queue/` · `labels/print/` · `labels/calibration/` · `label-templates/` CRUD | + Tab, Cnf |
| UyelerPage | 473 | Üye aç, toplu üye, sonlandır, üye kartı PDF'i, bireysel ödünç geçmişi | `memberships/` (+`bulk`, `terminate`, `card`, `history`) · çekirdek uçlar `students/?q=` ve `users/lookup/` | + AC |
| OduncPage | 508 | Dört sekme: ödünç ver, açık ödünçler (iade/kayıp), kayıp-hasar, ilişik kesme | `checkout/` · `loans/` (+`return`, `report-lost`) · `loss-damage-cases/` (+`resolve`) · `clearance/` · `reports/overdue-pdf/` · `students/` · `users/lookup/` | + AC Tab Cnf |
| KomisyonPage | 431 | Üç sekme: ayıklama partileri, yıl sonu raporu, nadir eserler | `weeding-batches/` · `annual-reviews/` (+pdf) · `rare-works/` (+pdf) · `commission-decisions/` · `school-years/` | + Tab |
| AyiklamaDetayPage | 312 | Kalem ekleme (barkod → nüsha), teklif/onay/red, tutanak ve devir çıktıları | `weeding-batches/{id}/` (+`items`, `propose`, `approve`, `reject`, `report`, `transfer-list`, `transfer-list-xlsx`) · `copies/?barcode=` | CAN_APPROVE_LIBRARY |
| SayimPage | 158 | Sayım listesi, yeni sayım | `stocktakes/` · `school-years/` | — |
| SayimDetayPage | 327 | İki turlu sayım yaşam döngüsü, raf tarama, çıktılar | `stocktakes/{id}/` (+`begin`, `scan`, `complete-round1`, `complete-round2`, `approve`, `items`, `report-pdf`, `report-xlsx`, `writeoff-proposal-pdf`) | CAN_APPROVE_LIBRARY |
| RaporlarPage | 160 | İstatistik panosu, Kütüphane Defteri ve Yönetim Hesabı Cetveli Excel'leri | `stats/` · `reports/register-xlsx/` · `reports/management-account-xlsx/` | — |
| AyarlarPage | 140 | Politika: ödünç süresi, limitler, gecikme kuralı | `policy/` GET/PUT | — |
| KutuphaneNobetPage | 122 | Kulüp öğrencileri için nöbet çizelgesi | `nobetApi` + `clubs/` | **`../nobet/StudentDutySection` (899 satır) + `nobet/api.ts` (454) + `siniflar/api` + `ui/Badge`** |
| _shared.tsx | 45 | `formatDate`, `errMessage`, `CopyStatusBadge` | — | `lib/api`, `lib/format` |
| useSchoolYears.ts | 30 | Ders yılı seçenekleri. Komisyon, Sayım ve Raporlar kullanıyor | `library/school-years/` | react-query |
| api.ts | 777 | Elle yazılmış tipler ve uç fonksiyonları, `/library/` öneki | — | `lib/api`, `lib/pagination` |

Doğrulananlar:
- İçe aktarma (import) taraması betikle yapıldı; `useSchoolYearOptions` kullanımı `KomisyonPage.tsx:34`, `SayimPage.tsx:22` ve `RaporlarPage.tsx:17`'de.
- Rotaların tamamı `App.tsx:221-240` aralığında, `RequireModule flag="kutuphane"` ve `RequireRole CAN_VIEW_LIBRARY` altında.
- Kütüphanede hiçbir sayfa `DataTable` ya da `<table>` kullanmıyor; bütün listeler `<ul>` içinde Card. Bu 36 px yoğunlukta binlerce eserlik bir katalog için verimsiz.

Sayfa içi kusurlar (masaüstünde düzeltilmeli):
- **Katalog yer numarasıyla aranamıyor.** Arama kutusunun örneği "813.54" diyor (`KatalogPage.tsx:113`), ama `q` yalnız başlık, yazar ve konu alanlarında arıyor (`backend/apps/kutuphane/selectors.py:49`). Sınıflama kodu, yer numarası ve ISBN aranmıyor. Arayüzde ISBN süzgeci de yok.
- **Her tuşta yeni istek gidiyor.** Arama gecikmesi yok, önceki sonuç da korunmuyor (`KatalogPage.tsx:59-66`). ÇIKARIM: her tuşta iskelet görünüp liste boşalıyor.
- **"Etiketlendi" işareti baskıdan önce konuyor.** PDF üretilirken `mark: true` gönderiliyor (`EtiketlerPage.tsx:108`). Yazıcı sıkışırsa nüshalar kuyruktan düşer. Geri alacak `labelApi.mark` tanımlı (`api.ts:430`) ama hiçbir yerde kullanılmıyor, yani başlık yorumundaki "geri alınabilir" özelliğinin arayüzü yok.
- **"Toplu üye" sınıf seçerek çalışmıyor.** Başlık yorumu "sınıf/şube" diyor. Uygulamada öğrenciler Autocomplete ile tek tek ekleniyor (`UyelerPage.tsx:319-357`).

---

### 2. Barkod okuyucu (klavye-wedge) ve kamera

DOĞRULANDI:
- **Sayım (SayimDetayPage `ScanPanel`):** Enter gönderiyor (`SayimDetayPage.tsx:327-329`, "Okut ve Enter"). Alana kendiliğinden odaklanma yok. Başarılı okumada alan temizleniyor (`:307`).
  - ÇIKARIM: Hızlı raf taramasında önceki istek dönmeden sonraki barkod okutulursa, `onSuccess` içindeki `setBarcode("")` yeni yazılan barkodu siler ve okuma kaybolur. `submit()` bekleyen isteği de denetlemiyor. Çözüm: değeri gönderim anında alıp alanı hemen temizlemek ve okumaları kuyruğa almak.
- **Ödünç verme (OduncPage `CheckoutTab`):** Kart no ve barkod için iki TextField var (`OduncPage.tsx:131-142`). Enter işleyicisi yok, form öğesi yok, odak kendiliğinden geçmiyor, gönderim otomatik değil; kütüphaneci her seferinde "Ödünç ver" düğmesine tıklamak zorunda. Kart no ardışık ödünç için korunuyor (`:110`).
- **İade:** Barkodla iade yok. İade yalnız "Ödünçler" listesindeki düğmeyle yapılıyor (`OduncPage.tsx:290-296`). Liste `circulationApi.loans({status:"OPEN"})` ile çekiliyor; limit ve sayfalama yok. Backend `LoanViewSet` varsayılan sayfalamayı kullanıyor (`views.py:793-803`, `PAGE_SIZE: 25` → `config/settings/base.py:292`). Sonuç: **26. açık ödünç arayüzden iade edilemez.** Backend'de `loans/?copy=` süzgeci var (`views.py:803`), yani "barkodu okut → nüshayı bul → açık ödüncü iade et" akışı yalnız ön yüz işi.
- **Ayıklama kalemi ekleme:** Barkodla nüsha buluyor (`copyApi.list({barcode})`) ama Enter işlemiyor.
- **Kamera:** OYS ön yüzünde `getUserMedia`, `BarcodeDetector`, zxing veya html5-qrcode yok; `src/` ve `package.json` taraması boş döndü.
- **Etiket içeriği yalnız QR:** Sırt etiketi `label_service.py:1-51`, üye kartı `member_card.py:36` (segno). Code128 gibi 1D barkod üretilmiyor.

Masaüstü için öneriler (ÇIKARIM):
- **Okuyucu donanımı:** 2D (imager) USB okuyucu şart; 1D lazer okuyucu QR okumaz.
- **Türkçe Q klavye tuzağı (bilinen durum, cihazla doğrulanmalı):** Okuyucu ABD düzeninde tuş kodu gönderir. TR-Q düzeninde "-" tuşu "*" yazar, böylece `K-2026-00001` alana `K*2026*00001` olarak düşer. Ön yüzde ortak bir `normalizeBarcode()` yardımcısı (`*`→`-`, büyük harfe çevirme, boşluk temizleme) ve aynısının backend'de karşılığı gerekir. Alternatif: okuyucuyu "Turkish Q" klavye moduna ayarlamak.
- **Ortak `BarcodeInput` bileşeni:** kendiliğinden odak, Enter ile gönderim, gönderimde alanı hemen temizleme, sesli/görsel geri bildirim. Ödünç, iade, sayım, ayıklama ve etiket kuyruğu aynı bileşeni kullanır. Ödünç ekranında akış "kartı okut → odak barkoda geçer → barkodu okut → otomatik ödünç" olmalı.
- **Kamera ile okuma:**
  - Masaüstü penceresinde (WebView2, `http://127.0.0.1` güvenli bağlam sayılır) teknik olarak mümkün. Ama Windows Chromium'da `BarcodeDetector` yok, bu yüzden zxing-js gibi bir kütüphane gerekir. ÇIKARIM: pywebview'da kamera izni ayrıca ele alınmalı.
  - Ağdaki telefonlarda `http://192.168.x.x` güvenli bağlam değil; tarayıcı kamerayı açmaz. Yani ağdaki tarayıcılarda kamerayla tarama HTTPS olmadan olmaz.

---

### 3. Ortak katman bağımlılığı ve sökülmesi gerekenler

**Kullanılan ui bileşenleri (12):** Button, Card, Dialog, Icon, Select, Skeleton (`SkeletonList`), SnackbarProvider, ConfirmProvider, TextField, Tabs (+`tabPanelProps`), Autocomplete, HubFeatureCard. Mürekkep 2 bileşenlerinin hiçbiri kullanılmıyor (Badge, Alert, Checkbox, FormField, DataTable v2, PageHeader…); tek istisna Nöbet sayfasının dolaylı `Badge` bağımlılığı.

**Kullanılan lib yardımcıları:**
- `lib/api` (`api`, `ApiError`)
- `lib/pagination` (`Paginated`)
- `lib/download` (`saveBlob`)
- `lib/format` (`formatCurrency`)
- `lib/roles` (`CAN_MANAGE_LIBRARY`, `CAN_APPROVE_LIBRARY`, `CAN_MANAGE_DUTY`, `hasAnyRole`)
- `api-types.ts` kullanılmıyor; tipler bilerek elle yazılmış (`api.ts:4-5`).

**OYS'ye özgü olup sökülecekler (DOĞRULANDI):**

| Öğe | Nerede | Masaüstünde ne olur |
|---|---|---|
| `useAuth()` + `hasAnyRole(...)` | 11 sayfa, yaklaşık 97 `canManage`/`canApprove`/`canCreate` referansı | Rol yok. Ya dallar silinir ya ince bir "yetki modu" kancası kalır (§7) |
| `RequireModule flag="kutuphane"` + `RequireRole` | `App.tsx:221-222`, `auth/RequireModule.tsx:14` | Kalkar |
| `module_flags` / nav `canKutuphane` | `shell/AppShell.tsx:83,118,195-199` | Kalkar. Gezinme KS'deki gibi `NAV_ITEMS` olur, Hub kartları kenar çubuğuna iner |
| `memberLookupApi.users` → `/users/lookup/` | `api.ts:538-542`, Üyeler ve Ödünç | Masaüstünde kullanıcı yok. KS'deki `/personnel/?q=` ile değiştirilir (`kelebek okul/api.ts:643`) |
| `memberLookupApi.students` → `/students/?q=&only_active=true` | `api.ts:534-537` | KS'de `/students/` var (`okul/api.ts:614`); parametre adları eşlenmeli |
| `/library/school-years/` | `useSchoolYears.ts` | KS'de `/school-years/?limit=200` (`okul/api.ts:580`) |
| KutuphaneNobetPage | nobet, clubs, siniflar, Badge | v1'de çıkarılmalı (yaklaşık 1.500 satırlık yabancı bağımlılık) |
| Sayfalardaki "← Kütüphane" geri düğmesi + kök `p-6` | 14 sayfa | KS kabuğu içerik alanına zaten dolgu veriyor (`AppShell.tsx:215`), yani çift dolgu olur. Geri düğmesi `ModuleHeader`'a döner ya da kalkar |
| `@sentry/react` | OYS `package.json:27` | Kardeşlerde çıkarılmış (`kelebek main.tsx` yorumu). Telemetri ilkesi gereği taşınmamalı |

Bildirim modülüne ön yüzden bağımlılık yok. Denetim kaydı (`SENSITIVE_READ`) yalnız yorumlarda ve backend'de geçiyor. İlişik kesme ekranındaki "denetim kaydına işlenir" bandı (`OduncPage.tsx:451-454`) backend kararına göre güncellenmeli.

---

### 4. Tasarım dili farkı ve hangi yolun daha ucuz olduğu

DOĞRULANDI:
- **OYS:** Mürekkep. `--oys-*` önekli 154 değişken, Inter Variable yazı tipi kendi içinden sunuluyor (`@fontsource-variable/inter`, `index.css:3`), `tailwind.config.js:145`. Mürekkep token **adlarını** korudu (`bg-primary`, `text-title-medium`, `rounded-shape-sm`; ADR-0048:57-58).
- **KS ve DD:** M3 kökenli, masaüstü için sıkılaştırılmış kit. `--md-*` önekli 139 değişken; KS'de ayrıca 28 `--ks-*`, DD'de `--dd-*` yoğunluk değişkeni (kontrol 2.25rem, alan 2.5rem). Segoe UI sistem yazı tipi, `@fontsource` yok (`index.css:1`). KS ile DD'nin ui dosyaları neredeyse aynı (fark 0-16 satır).
- **API uyumu:** 12 bileşenin OYS ve KS prop arayüzleri bire bir aynı. `Dialog` (open, onClose, title, children, actions, wide, full), `Select` (label, options, placeholder, helperText, error), `TextField` (label, helperText, error), `Tabs` (items, active, onChange, ariaLabel, idBase + tabPanelProps), `Autocomplete` (label, placeholder, selected, search, onSelect, onClear, getLabel, getKey, ariaLabel…), `Card` (elevation 0|1|2), `SkeletonList` (rows), `Snackbar` (success/error/show), `Confirm` (message, title, confirmLabel), `HubFeatureCard` (to, icon, title, description) ve Icon boyut kümesi aynı.
  - Farklar yalnız OYS'ye eklenmiş özelliklerde: Button `size`, TextField `size="touch"`, Dialog `dismissible`. Kütüphane bunların hiçbirini kullanmıyor; `size=` yalnız `Icon` üzerinde (`sm`, `xl`) ve o KS'de de var.
- **Token uyumu:** Kütüphane sayfalarındaki 132 benzersiz sınıfın token olanlarının hepsi KS'nin `tailwind.config.js` dosyasında var (`shape-lg/md/sm`, `title-small`, `headline-small`, `label-small`, `*-container`, `elevation-1`). Mürekkep 2'ye özgü `success`, `warning`, `info`, `surface-nav` kullanılmıyor. Kütüphane pratikte "M3 token adlarıyla" yazılmış; `KutuphaneHub.tsx:4` ve `_shared.tsx:2` yorumları hâlâ "M3 token'ları" diyor.

**(a) Kütüphane sayfalarını KS kitine uyarlamak.** Tahmini maliyet (ÇIKARIM):
- **ui:** Sayfalarda sıfır değişiklik; import yolları (`../../ui/X`) aynen çalışır. KS'nin `ui/` dizini (23 bileşen ve testleri), `index.css`, `tailwind.config.js` ve kabuğu olduğu gibi alınır.
- **lib:** `format.ts`'e `formatCurrency` eklenir (KS/DD'de yok; OYS'de `format.ts:47`, yaklaşık 17 satır). `download.ts` KS'deki sürüm alınır: OYS sürümü nesne URL'sini hemen bırakıyor, bu da "WebView'de indirmeyi iptal edebilir" (KS `download.ts:11-13`). `api.ts` ve `pagination.ts` imza olarak uyumlu.
- **Mantık uyarlaması:** Yaklaşık 11 sayfa rol dallarını kaybeder. 2 sayfada (Üyeler, Ödünç) personel araması değişir. Üç sayfanın kullandığı `useSchoolYears` hook'u yeniden yazılır. Nöbet sayfası çıkar. Hub gezinmeye taşınır. 14 başlık sadeleşir.
- **Testler:** 8 dosyadaki auth mock'ları ve rol testleri silinir; örnek olarak KatalogPage'de 5 testin 2'si rol testi (`KatalogPage.test.tsx:103-115`).
- **Etkilenen dosya:** yaklaşık 17 kaynak + 8 test. Değişikliklerin çoğu mekanik.

**(b) Mürekkep ui katmanını da taşımak.**
- OYS `ui/` 42 dosya (FormField, useFocusTrap, gridStyles dahil) + `index.css` (345 satır) + Tailwind yapılandırması + Inter yazı tipi + `tokenContrast.test.ts`.
- Asıl maliyet başka yerde: kardeşlerden hazır alınacak altyapı modülleri (kurulum yaklaşık 650-730 satır, ayarlar yaklaşık 860-900, güvenlik yaklaşık 900, güncelleme, hakkında, bakım, kişiler yaklaşık 1.250) KS kitine yazılmış. Bunların bir kısmı OYS'de **farklı API'li** bileşenlere dayanıyor: `DataTable` OYS'de 322 satır, KS'de 65; `Stepper` 68'e karşı 100; KS'ye özgü `DensitySwitcher`, `UyariBandi`, `ModuleHeader`.
- Yani (b) yolunda ya bu modüllerin yaklaşık 20-30 dosyası Mürekkep'e uyarlanır ya da iki kit yan yana yaşar.

**Öneri: (a).** Daha az iş çıkarır ve kullanıcının masaüstü aile görünümüyle (kelebek, DD) tutarlı olur. Mürekkep'in asıl kazancı olan tablo yoğunluğu, katalog ve ödünç listelerine KS'nin `DataTable` bileşeni uygulanarak alınabilir.

---

### 5. Ağdan katalog tarama (OPAC)

**Mevcut engeller (DOĞRULANDI):**
- Kardeşlerde sunucu `127.0.0.1` adresine bağlanıyor (`kelebek desktop/server.py:30`).
- `SessionTokenMiddleware` belirteç taşımayan **her** isteği 403 ile reddediyor. Sıralama çerez > `X-KS-Token` başlığı > `?t=`; her açılışta yeni belirteç üretiliyor (`desktop/session_guard.py:59-99`; `main.py:200`).
- Ön yüz belirteç eklemiyor. İlk istek `?t=` ile geliyor, sonra HttpOnly çerez taşınıyor ("frontend'de değişiklik gerektirmez", `session_guard.py:10-11`; `lib/api.ts:40-48`'de yalnız Content-Type var).
- Parola kuruluyken `AppLockMiddleware` bütün `/api/` isteklerine 423 döndürüyor (`apps/okul/lock_middleware.py:35-44`).
- ADR-0040:28 OPAC'ı açıkça kapsam dışı sayıyor.

Bu yüzden ağdaki istemcilerin mevcut SPA'yı ya da API'yi kullanması mümkün değil. OPAC ayrı bir dinleyicide, belirteç ve kilit ara katmanlarının **dışında** kalan ayrı bir URL kümesi olmalı. Bu backend ve masaüstü işi; ön yüz tercihi bunu izler.

**Yeniden kullanılabilecekler (DOĞRULANDI):**
- KatalogPage'den arama kartı (`:107-124`) ve sonuç satırı biçimi (`:142-175`).
- EserDetayPage'den `InfoRow` (`:33-44`), künye ızgarası (`:231-241`), yönetim düğmeleri çıkarılmış nüsha listesi (`:273-306`).
- `_shared`'den `CopyStatusBadge`. OPAC'ta çekilmiş nüshalar (`WITHDRAWN_*`, `TRANSFERRED`) hiç gösterilmemeli.
- `api.ts`'ten `Work`/`Copy` tiplerinin bir alt kümesi ve `RESOURCE_TYPE_LABELS`.
- Hepsi yaklaşık 150 satırlık JSX; hepsinde `useAuth` ve yazma mantığı iç içe.

**Seçenekler:**

| Seçenek | Artılar | Eksiler |
|---|---|---|
| **A. Sunucu tarafı basit HTML** (Django şablonu, GET formu, `?q=&sayfa=`) | JS gerektirmez, her tarayıcıda çalışır (eski laboratuvar bilgisayarı, telefon, kiosk). Salt okur kolayca garanti edilir; DRF ve yazma ucu yok. Yönetim koduna yanlışlıkla bağlanamaz. Sayfalama doğal gelir. Django test istemcisiyle test edilir. Ekip PDF'ler için zaten Django şablonu yazıyor | Anlık arama yok (Enter ile arama yeterli). Palet ayrıca küçük bir CSS dosyasına kopyalanır. Türkçe biçimlendirme Python'da tekrarlanır |
| **B. Ayrı Vite derlemesi** (`opac.html` + `src/opac/main.tsx`, **ayrı `outDir`**, örneğin `dist-opac/`) | ui kiti, token'lar ve tipler ortak. Anlık arama ve zengin arayüz. Vitest ile test | İstemcide modern tarayıcı şart (Vite 6 varsayılanı yaklaşık Chrome 87+). Tek derlemede çok girişli olursa ortak parçalar `dist/assets` içinde karışır; sunucunun ön yüz manifest'ine göre izin listesi tutması gerekir. Ayrı derleme bunu çözer ama iki derleme hattı demek |
| **C. Aynı SPA'da `/opac/*` rotaları** | Kurulumu en az | Ağdaki istemci bütün yönetim paketini indirir. `main.tsx`/`App.tsx`'teki `GuvenlikKapisi`/`KurulumKapisi` sarmalı (`App.tsx:30-65`) yeniden kurulmak zorunda. `index.html` belirteçten muaf tutulursa yönetim arayüzü ağda yüklenir ve 403 hatalarıyla dolar. Güvenlik sınırı yalnız sunucu yapılandırmasına kalır. **Önerilmez** |

**Öneri:** v1 için A. Hafif, salt okur, en sağlam ve en güvenli ayrım. Zengin arayüz istenirse ikinci adım B.

**OPAC ön yüzünde dikkat edilecekler (ÇIKARIM):**
- Sayfalama ve toplam sayı gösterimi zorunlu (§2'deki 25 kayıt tuzağı).
- Türkçe büyük/küçük harf ve aksan katlama. Arama `icontains` ile yapılıyor (`selectors.py:49`). SQLite'ta `LIKE` yalnız ASCII için büyük/küçük harfe duyarsız; "şiir" ile "Şiir", ya da "İ" ile "i" eşleşmeyebilir. KS'de `shared/text.py` içinde `tr_lower` var; aranabilir, katlanmış bir `search_key` alanı önerilir. Bu backend işi ama OPAC deneyimini doğrudan belirler.
- Gösterilecekler: yer numarası, raf konumu, durum ("Rafta", "Ödünçte", "Danışma — ödünç verilmez"). **Ödünç alanın kim olduğu asla gösterilmez.** İade tarihinin gösterilip gösterilmeyeceği karar konusu.
- Kiosk ya da dokunmatik kullanım varsa 48 px hedef (ADR-0048'deki kiosk istisnası). İsteğe bağlı: yeni gelenler, en çok okunanlar (toplu veri), Dewey ana sınıflarına göre gezinme.

---

### 6. Testler ve OpenAPI tip üretimi

DOĞRULANDI:
- **Kütüphane vitest:** 8 dosya, **22 test**: Katalog 5, Üyeler 4, Komisyon 3, Nöbet 3, Import 2, Ödünç 2, Sayım 2, Raporlar 1. EserDetay, Etiketler, Edinimler, SayimDetay, AyiklamaDetay ve Ayarlar sayfalarının testi yok. Testler `vi.hoisted` API mock'u ve `AuthContext` mock'u kullanıyor (`KatalogPage.test.tsx:13-29`).
- **Kardeşler (yaklaşık, `it(`/`test(` sayımı):** KS 79 dosya ve yaklaşık 608 test; DD 51 dosya ve yaklaşık 380 test.
- **KS kapsam kapısı:** satır 82, dal 78, fonksiyon 55 (`vitest.config.ts`, "scripts/gates.sh --coverage").
  - ÇIKARIM: yaklaşık 5.500 satırlık kod 22 testle taşınırsa bu eşik büyük olasılıkla tutmaz. Taşıma planına test yazımı gerçek bir kalem olarak girmeli; öncelik barkod akışları, iade ve sayfalama.
- **Sürümler:** OYS React 18.3.1 / router 6.30.3 / React Query 5.100 / Vite 5.4 / Vitest 2.1 / Tailwind 3.4.17. KS ve DD React 18.3.1 / **router 7.18.2** / React Query 5.101 / **Vite 6.4** / **Vitest 3.2** / Tailwind 3.4.19. Kütüphanenin kullandığı `useNavigate`, `useParams` ve `MemoryRouter` v7'de de `react-router-dom`'dan aynı şekilde geliyor.
- **OpenAPI:** OYS'de `gen:api` betiği `openapi/schema.yaml`'dan `src/lib/api-types.ts` üretiyor (`package.json:19`), ama kütüphane bunu kullanmıyor (`api.ts:4-5`). KS/DD'de `gen:api` betiği yok, `openapi/` dizini yok; yalnız `.prettierignore`'da kalıntı satırlar var. Keşif raporu drf-spectacular'ı "ALINMAYACAK" listesine koyuyor (`kelebek docs/kesif/2026-08-29-kesif-raporlari.md:136`). Masaüstünde tipler elle yazılmaya devam eder; `api.ts` olduğu gibi taşınabilir.
  - Backend notu: `views.py:805,815` gibi yerlerde `@extend_schema` dekoratörleri var; taşımada kaldırılmalı.
  - ÇIKARIM: tip ile serializer arasında kayma olmasın diye backend'e alan listesi anlık görüntü testi (snapshot) önerilir.

---

### 7. Kullanıcıya sorulacaklar (ön yüzü doğrudan etkileyen kararlar)

1. **Masada kim çalışacak?** Nöbet sayfası, masada kulüp öğrencilerinin çalıştığını gösteriyor. Girişsiz uygulamada masadaki öğrenci okuma geçmişine, üye kartlarına, ilişik kesmeye ve onay işlemlerine erişir. Seçenekler:
   - "Görevli modu" (yalnız ödünç ve iade) ile PIN'li "Yönetici modu".
   - Ya da tek mod; kütüphaneci her zaman kendisi.
2. **Teklif ≠ onay ayrımı** (ayıklama Md. 12, sayım onayı; `lib/roles.ts:532-558`) tek kullanıcıda nasıl korunacak? Seçenekler: onaylayanın adı ve tarihi elle girilir, basılı tutanakta imza alanı bırakılır; ya da yönetici PIN'i istenir.
3. **Mevcut kitapların etiketi var mı?** Barkod biçimi sabit: `K-{yıl}-{no}`, sayaçtan üretilir (ADR-0040:53-57). Retrospektif aktarımda bütün kitaplar yeniden etiketlenir. Eski barkod ya da demirbaş numarası korunacak mı?
4. **Ödünç listesinde üye adı görünsün mü?** Şu an görünmüyor; yalnız `membership` id (`api.ts:476-490`). Masaüstünde kütüphaneci için ad göstermek olağan. KVKK açısından karar sizde.
5. **OPAC'ta ödünçteki kitabın iade tarihi** gösterilsin mi? Ayırtma (rezervasyon) olsun mu? ADR-0040 ayırtmayı kapsam dışı sayıyor.
6. **Kamera ile okuma** gerekli mi, yoksa USB 2D okuyucu yeterli mi? Sırt etiketindeki QR içine OPAC adresi yazılsın mı? Yazılırsa telefonun kamerası kitabın sayfasını doğrudan açar; ama etiket biçimi değişir ve masadaki okuyucunun adresten barkodu ayıklaması gerekir.
7. **Nöbet modülü** v1'den çıkarılsın mı? Öneri: evet.

### 8. Başka ekiplere not (ön yüzle kesişen, "düşünülmemiş olabilecek" konular) — ÇIKARIM

- **Ağ dinleyicisi:** `0.0.0.0` adresine bağlanınca Windows Güvenlik Duvarı sorar ve ağ profili "Genel" ise istemciler bağlanamaz; kurulum programında yönetici haklı bir güvenlik duvarı kuralı gerekir.
- **Adres bulunabilirliği:** DHCP ile IP değişebilir; bilgisayar adıyla adres daha sağlam. Ayarlar'da "Katalog adresi" ve bu adresin yazdırılabilir QR'ı gösterilmeli.
- **Yayının sürekliliği:** Pencere kapanınca OPAC da kapanır.
- **Kilit etkisi:** Uygulama kilitliyken (423) OPAC çalışmaya devam etmeli; katalog alanları şifrelenmemeli.
- **Güncelleme denetimi:** KS'deki güncelleme bandı GitHub'a istek atıyor (`guncelleme/api.ts`; `AppShell.tsx:217-219`). "Bulut yok" ilkesiyle nasıl bağdaştırılacağı kararlaştırılmalı; kapatılabilir olmalı.
- **Yıl devri:** e-Okul'dan yeniden içe aktarmada ayrılan ve mezun olan öğrenciler için üyelik sonlandırma, ilişik listesi ve açık ödünçler. DD'de `yildevri` modülü emsal. Tatillerde ödünç ve son tarih hesabı da karar konusu (DD'de "Tatiller" adımı var).
- **Mevzuat dili:** ADR-0040:16-19 yönetmeliğin "Bakanlıkça belirlenen otomasyon sistemi"ni zorunlu kıldığını söylüyor. Müstakil uygulama, OYS gibi bir "hazırlık/kontrol aracı" olarak konumlandırılmalı; mevzuat incelemesi yapan ekip bunu doğrulamalı.

**İlgili dosyalar:**
- `../okulapp/frontend/src/modules/kutuphane/` (tümü)
- `../okulapp/frontend/src/App.tsx`
- `../okulapp/frontend/src/lib/roles.ts`
- `../okulapp/frontend/src/lib/pagination.ts`
- `../okulapp/backend/apps/kutuphane/views.py`
- `../okulapp/backend/apps/kutuphane/selectors.py`
- `../okulapp/docs/adr/0040-kutuphane-modulu.md`
- `../okulapp/docs/adr/0048-murekkep-masaustu-tasarim-dili.md`
- `../okulapp/docs/adr/0049-murekkep-2-durum-paleti-ve-bilesen-sozlugu.md`
- `../okulapp/docs/adr/0059-react-query-veri-katmani.md`
- `../kelebek-sinav/frontend/src/{ui,lib,App.tsx,AppShell.tsx,KurulumKapisi.tsx}`
- `../kelebek-sinav/desktop/{session_guard.py,server.py}`
- `../kelebek-sinav/backend/apps/okul/lock_middleware.py`
- `<kardeş proje deposu>/frontend/src/{ui,lib}`

<a id="r4"></a>

---

## R4. OYS içindeki bağlar, planlar, KVKK saklama, okul çekirdeği

## OYS kütüphane modülünün OYS'ye bağları, planları ve yeni masaüstü uygulamaya aktarım haritası

**Kaynağın güncelliği.** Yerel `okulapp`, `origin/main` ile aynı yerde (`5eafa42e`, 29.08.2026). `.git/FETCH_HEAD` bugünkü tarihi (21.09.2026) taşıyor. Yani okunan kod bayat değil. Hiçbir dosya değiştirilmedi. Gerçek veri içeren dosyalar (xlsx/db/yedek) açılmadı.

**Modülün boyutu.** DOĞRULANDI.
- Backend: 21 `.py` dosyası, 6181 satır. En büyükleri `models.py` 1097, `views.py` 1409 ve `serializers.py` 645 satır.
- 6 migration, 7 test dosyası.
- Frontend: `frontend/src/modules/kutuphane/` altında 26 dosya, 6792 satır.

---

### 1. Bağ haritası

#### 1a. Kütüphaneden OYS'nin geri kalanına giden bağlar

| # | Bağ | Kanıt | Ne işe yarıyor | Masaüstünde karşılığı |
|---|---|---|---|---|
| 1 | `Membership.member_student` → `core.Student` (FK, PROTECT) | DOĞRULANDI: `models.py:627-634` | Öğrenci üyeliği | Uygulamanın kendi `okul.Student` modeline FK (kelebek kalıbı) |
| 2 | `Membership.member_user` → `core.User` (FK) | DOĞRULANDI: `models.py:635-642` | Öğretmen/personel üyeliği. XOR kısıtı `:663-679`'da | `okul.Personnel`'e FK. Giriş yapan kullanıcı olmadığı için User kalkar |
| 3 | `WeedingBatch.school_year`, `AnnualLibraryReview.school_year`, `RareWorksSubmission.school_year`, `StockTake.school_year` → `core.SchoolYear` | DOĞRULANDI: `models.py:841, 904, 924, 988` | Ders yılı bağı | `okul.SchoolYear` (kelebek `models.py:260`) |
| 4 | `WeedingBatch.approved_by`, `StockTake.approved_by` → `core.User` | DOĞRULANDI: `models.py:847, 1001` | Teklif ile onay ayrımı (Md. 12, TMY 32) | ÇIKARIM: girişsiz uygulamada "onaylayan" bir kullanıcı olamaz. Serbest metin ya da `SchoolConfig.principal_name` + onay tarihi olur (karar gerekir, bkz. §7) |
| 5 | `BaseModel.created_by/deleted_by` → User | DOĞRULANDI: `shared/models.py:55-64`. `views.py`'de `serializer.save(created_by=request.user)` (ör. `:215, :250`) | Kim yarattı | Kelebek `BaseModel` bu alanları bilerek çıkarmış (kelebek `shared/models.py:4`). Bütün `created_by=` çağrıları silinir |
| 6 | Çekirdek modellerin `get_model` ile çalışma anında çözülmesi | DOĞRULANDI: `services.py:263-270` (SchoolYear), `:318-340` (Student/User), `:343-350` (toplu). `selectors.py:232-245, :411-416`. `excel_exports.py:115-118` | Modül sınırı kuralı (ADR-0002) | Aynı uygulama içinde doğrudan import edilir, dolambaca gerek kalmaz |
| 7 | Üye adı: `student.current_name` (StudentNameHistory) / `user.get_full_name()` | DOĞRULANDI: `serializers.py:334-344` | Ekranda ve kartta ad | `Student.full_name` / `Personnel.full_name`. Kelebekte ikisi de şifreli (kelebek `models.py:560-561, 347-348`) |
| 8 | Öğrenci fotoğrafı `student.photo.thumb_b64` | DOĞRULANDI: `member_card.py:39-45` | Üye kartında fotoğraf (Md. 20) | Kelebek `services/photos.photo_data_uris()` (`photos.py:126`). Fotoğraf şifreli ve yeniden kodlanmış JPEG |
| 9 | Rol sistemi: `shared.roles.Role` (KUTUPHANECI/MUDUR_YARDIMCISI/MUDUR/ADMIN) | DOĞRULANDI: `permissions.py:15-20`, `signals.py:38`, `tasks.py:39`. `shared/roles.py:29` | Yazma, görme ve onay yetkileri | Tek kullanıcılı, girişsiz uygulamada rol olmaz. Ağ erişimi ayrıca ele alınır (bkz. §7) |
| 10 | Denetim: `audit.log_audit` (gecikmişe rağmen ödünç verme gerekçesi) | DOĞRULANDI: `circulation.py:18, 89-99` | Kütüphaneci sorumluluğunun izi | ÇIKARIM: gerekçe `Loan` üzerinde bir alan olarak tutulur (ör. `override_reason`). AuditLog yok |
| 11 | Denetim: `audit.log_access(SENSITIVE_READ)` (kart, geçmiş, ilişik) | DOĞRULANDI: `views.py:26-27, 130-138, 749, 761, 910-915` | Hassas okuma günlüğü | ÇIKARIM: tek kullanıcıda anlamı azalır. Yerel ağ istemcileri bu uçlara zaten erişmemeli |
| 12 | Antet: `core.services.get_letterhead_identity` + `shared.letterhead.letterhead_authority` | DOĞRULANDI: `reports.py:43-50, 68-71`. Çekirdek: `core/services/school_config.py:90-109` | 5 resmî PDF'in anteti | Kelebek `services/setup.get_letterhead_identity` (OYS ikamesi, `.env` yedeği yok) + `shared/letterhead.py` |
| 13 | Bildirim sinyalleri (tanımlar `bildirim/signals.py`'de) | DOĞRULANDI: `signals.py:31-63` (clearance_blocked, uyelik_sonlandirildi); `tasks.py:35, 57-76` (loan_overdue). Tanımlar: `bildirim/signals.py:237-247` | Kütüphaneci ve idareye uygulama içi bildirim | ÇIKARIM: uygulama içi panel/rozet (ana sayfada "gecikenler", "ilişiği açık ayrılanlar") |
| 14 | Veli SMS'i: `bildirim.services.dispatch_to_parent` + `MessagingSettings.library_overdue_sms_enabled` + `EventType.LIBRARY_LOAN_OVERDUE` | DOĞRULANDI: `tasks.py:33-34, 78-93`. `bildirim/models.py:166-169, 884`. `bildirim/services.py:369` | Gecikmede veliye SMS (bayrakla açılır, varsayılan kapalı) | Kaldırılır. Veli telefonu toplanmaz, SMS altyapısı yok. Yerine yazdırılabilir gecikme listesi (`OverdueListPdfView` zaten var) |
| 15 | Celery beat: 3 görev | DOĞRULANDI: `config/settings/base.py:1074-1094`. Bayrakla kapatma muafiyeti `:1097-1110` | Günlük gecikme taraması (06:50), gece güvenlik ağı (02:50), aylık anonimleştirme (ayın 1'i 04:25) | ÇIKARIM: açılış görevi. Kelebek `desktop/main.py:127-140 prepare_data` zincirine "günde bir kez" koşan saklama görevi eklenir. Gecikme bir sorgu olduğu için göreve gerek yok |
| 16 | Dış kütüphaneler: `segno` (QR), WeasyPrint, openpyxl | DOĞRULANDI: `label_service.py:1,161`, `member_card.py:13,68`, `excel_exports.py:15` | Etiket, kart, rapor | WeasyPrint ve openpyxl kelebek `requirements.txt`'te var. **`segno` yok, eklenmesi gerekir** (saf Python) |

#### 1b. OYS'nin geri kalanından kütüphaneye gelen bağlar

| # | Bağ | Kanıt | Ne işe yarıyor | Masaüstünde karşılığı |
|---|---|---|---|---|
| 17 | `core.student_status_changed` sinyali → `_on_student_status_changed` → `terminate_membership` | DOĞRULANDI: yayanlar `core/services/students.py:228-240` ve `promotion.py:234-246`. Dinleyen `kutuphane/signals.py:68-92`, `apps.py:10` | Öğrenci ayrılınca üyelik sonlanır (Md. 16/3) | Kelebek `persons.register_student_forget_hook` (`persons.py:25`). **Ancak** kelebek kancası fotoğrafı ve bağlı veriyi kalıcı siler (`:31-35, :51-53`). Kütüphanede açık ödünç varken kişi silinmemeli. Kanca yalnız üyeliği sonlandırmalı |
| 18 | `ModuleFlagMiddleware` + `MODULE_KUTUPHANE_ENABLED` | DOĞRULANDI: `core/middleware.py:92-93`, `settings/base.py:853`, `core/serializers.py:252` | Modülü açıp kapatma | Kaldırılır (müstakil uygulama) |
| 19 | Frontend kablolaması | DOĞRULANDI: `lib/roles.ts:16, 532-558` (CAN_VIEW/MANAGE/APPROVE_LIBRARY), `shell/AppShell.tsx:118, 196-201`, `App.tsx:89-108, 221-240` (16 rota), `auth/RequireModule.tsx:14`, `auth/AuthContext.tsx:32` | Menü, rota, rol görünürlüğü | Rol ve bayrak katmanı düşer. Rotalar kalır |
| 20 | Frontend çekirdek uçları: `/students/?q=&only_active=true`, `/users/lookup/` | DOĞRULANDI: `frontend/.../kutuphane/api.ts:533-543` | Üye eklerken kişi arama | Kelebek `selectors.student_list` / `personnel_list` (`selectors.py:221, 118`). Ad şifreli olduğu için arama Python katmanında yapılır |
| 21 | Kütüphane nöbeti (Tur 620): `nobet.DutySchedule.student_source=CLUB` + `sosyal_etkinlikler.services.club_student_roster/club_brief` + `CanManageStudentDuty` | DOĞRULANDI: `nobet/models.py:74-79, 219-230`; `sosyal_etkinlikler/services/clubs.py:55-90`; `nobet/permissions.py:43-65`; FE `KutuphaneNobetPage.tsx:1-19` (`nobet/api`, `StudentDutySection`'ı import ediyor) | Kütüphanecilik Kulübü öğrencilerinin günlük nöbeti | ÇIKARIM: en ağır bağ bu. Nöbet motoru ve kulüp modeli gerektiriyor. **Önerim: V1'de alınmasın** (bkz. §7) |
| 22 | KVKK md. 11 ihracı | DOĞRULANDI: `denetim/kvkk_scope.py:168-171`; `denetim/services.py:817-832` (üyelik → ödünç → dosya zinciri) | "Verilerimi ver" talebi | ÇIKARIM: "kişi dökümü" dışa aktarımı (öğrenci no → üyelik, ödünç, dosya) |
| 23 | Geliştirme ortamı anonimleştirmesi | DOĞRULANDI: `anonymize_database.py:255-256` (`responsible_note` redakte, `card_no` temizlenir), `:579` (Loan kişisel veri taşımaz), `:676-678` | Test veritabanı | Kelebeğin veri sızıntısı kapıları (`packaging/depo_sizintisi.py`) |
| 24 | İlişik kesme çağrıları | DOĞRULANDI: `get_student_clearance`'ı yalnız kütüphanenin kendi görünümü (`views.py:909`) ve frontend (`api.ts:619`) çağırıyor. **`ogrenci_isleri`'nde çağrı yok.** Docstring (`selectors.py:153-154`) ve MODULES.md:1532 bu arayüzü "ogrenci_isleri nakil/mezuniyet için" diye tanımlıyor ama bağlanmamış | İlişik sorgusu | Uygulama içi "ilişik kesme" ekranı. ÇIKARIM: yazdırılabilir ilişik belgesi PDF'i eklenebilir (şu an yalnız JSON dönüyor, `views.py:918-928`) |
| 25 | `raporlar` modülü | DOĞRULANDI: bağ yok (grep'te yalnız `template.Library()` çıktı) | — | — |

---

### 2. Öğrenci verisinin kullanımı ve en az veri önerisi

**OYS'de fiilen kullanılan alanlar.** DOĞRULANDI.
- **Ad-soyad.** Ekran ve kart (`serializers.py:334-344`, `member_card.py:49`).
- **Fotoğraf.** Yalnız kartta, varsa (`member_card.py:40-45`).
- **Durum (ACTIVE/ayrıldı).** Üyelik sonlandırma ve güvenlik ağı (`tasks.py:145-151`, `signals.py:70-83`).
- **Okul no + sınıf etiketi.** Yalnız üye ararken seçicide görünüyor (`api.ts:519-524`). Kartta ve modelde yok.
- **Veli bağı.** Yalnız SMS için, dolaylı olarak `dispatch_to_parent(student_id)` (`tasks.py:86-91`).
- **Kullanılmayanlar.** TCKN, doğum tarihi, adres, cinsiyet, veli telefonu kütüphane kodunda doğrudan okunmuyor.

**Kartın içeriği.** DOĞRULANDI: ad, üye türü, kart no (`UK-{yıl}-{no:05d}`, `services.py:114-124`), QR (kart no) ve fotoğraf. Sınıf ve okul no yok.

**Önerilen en az veri seti.** ÇIKARIM (kelebek `Student` ile birebir örtüşüyor):

| Alan | Gerekçe | Not |
|---|---|---|
| Ad-soyad (şifreli) | Md. 20 kullanıcı kartı, ilişik | Kelebekte şifreli |
| Okul no (açık) | e-Okul eşleştirme anahtarı, arama | Kelebekte upsert anahtarı |
| Sınıf/şube (açık) | Toplu üyelik ve gecikme listesinde sınıfa göre dağıtım | |
| Durum + ayrılış tarihi | Md. 16/3 üyelik sonlandırma, saklama süresinin başlangıcı | Kelebekte yalnız ACTIVE/LEFT var, **tarih yok**. Tarih `Membership.terminated_at` ile karşılanabilir (`models.py:648`) |
| Fotoğraf (isteğe bağlı, şifreli) | Kart | Kelebek kalıbı: ayrılınca kalıcı silinir |
| **Alınmayacaklar** | TCKN, veli adı/telefonu, cinsiyet, doğum tarihi | SMS kalkınca veliye gerek kalmıyor |

**Personel için:** ad-soyad (şifreli), unvan/görev ve aktiflik. Unvandan TEACHER (limit 5) ile STAFF (limit 3) ayrımı türetilebilir (`models.py:116-127`, kelebek `models.py:349-351`).

---

### 3. OPAC, öğrenci/veli girişi, rezervasyon ve dış ISBN sorgusu

**Kapsam dışı bırakılış.** DOĞRULANDI, `docs/adr/0040-kutuphane-modulu.md:27-28`:
> "frontend + öğrenci/veli login + OPAC + rezervasyon + dış ISBN sorgusu kapsam dışıdır (LAN-only)."

Ayrı ve uzun bir gerekçe metni yok. Tek gerekçe parantezdeki **"LAN-only"** (sunucu dışarıya çıkmaz). Frontend daha sonra yapıldı (Tur 605-610). Öteki kalemler hâlâ yapılmadı.

**İlk plan (requirements.md §13.1, satır 670-689).** Taslak kapsam:
- Veli görünümü: "çocuğunun ödünç aldığı kitaplar" (`:676`).
- "En çok okuyan öğrenci", "sınıf bazlı okuma karnesi" (`:677`).
- "Rezervasyon / istek listesi" (`:678`).
- Hazırlık: `User.can_login`, `/ogrenci-girisi` ve `/veli-girisi` rotaları, öğrenci/veli için ayrı KVKK aydınlatma metni (`:681-684`).
- `:623`, `:724-725` kararları: V1'de öğrenci/veli girişi yok, "kütüphane modülü ile V2'de aktive".

**Bayrağın durumu.** OYS `CLAUDE.md:77-78` ve `:285-289`'a göre V2'de "kütüphane öğrenci/veli login + OPAC → `features.STUDENT_PARENT_LOGIN`" açılacaktı. DOĞRULANDI: bu bayrak **kodda yok**. Backend ve frontend grep'i boş döndü. `docs/proje-degerlendirme-2026-06.md:142-146, 199-201` de aynı eksikliği yazıyor: bayrak tasarımı ve JWT saklama stratejisi "kütüphane modülünden önce karara bağlanmalı" denmiş, bağlanmamış.

**Uygulananlar (KVKK yönünde daraltılmış hâli).** DOĞRULANDI:
- "En çok okuyan öğrenci" yerine PII'siz `most_read_works` (eser bazlı) yapıldı. Okuma karnesi yok.
- ADR-0040 K10: öğretmenler yalnız toplu sayıları görür (`adr/0040:78-83`).

**Dış ISBN sorgusu yerine "dış yapay zekâ köprüsü".** DOĞRULANDI: OYS hiçbir servise bağlanmıyor. Kütüphaneci Excel'i kendi AI aracına veriyor. Hazır komut, Dewey kodunu "Milli Kütüphane" kataloğundan aramasını istiyor. Dönen JSON sisteme yükleniyor (`import_schema.py:1-6, 35-50`, CHANGELOG Tur 601 `:32333-32366`).

**Mevzuat dayanağı.** DOĞRULANDI:
- Uygulama kılavuzu "Ayın Kitapları" panosunu "otomasyon sisteminden elde edilen verilerle" öneriyor (`meb-okul-kutuphaneleri-yonetmeligi-uygulama-kilavuzu.md:370`).
- Eylülde "otomasyon sistemi öğrencilere tanıtılır" (`:464`).
- ÇIKARIM: öğrenciye dönük katalog taramanın mevzuatla çelişen bir yanı yok, destekleyen ifadeler var.

---

### 4. KVKK saklama süreleri (kütüphane)

**Kod.** DOĞRULANDI:
- `LibraryPolicy.retention_years_after_termination`: varsayılan **2 yıl**, 1 ile 10 arası ayarlanabilir (`models.py:133-138`).
- Aylık görev: `TERMINATED` ve `terminated_at < şimdi − 365×N gün` olan üyeliklerde `Loan` ve `LossDamageCase` satırlarının kişi bağı koparılıyor (`membership=NULL`, `anonymized_at`). **Açık yükümlülüğü olan üyelik atlanıyor** (`tasks.py:98-131`).
- Bu görev bayrakla kapatılamaz, modül pasifken de koşar (`settings/base.py:1087-1094, 1103-1108`).

**ADR-0055.** DOĞRULANDI: kütüphaneye ait ayrı bir süre koymuyor. Kütüphaneyi yalnız kişi eksenli saklamaya **emsal** olarak anıyor: "`kutuphane` (ayrılış + N yıl)" (`adr/0055:39`). Genel eksen "mezuniyet/ayrılış + 5 yıl" (D1, `:30-44`). ADR-0040 K10 "2 yıl" diyor (`adr/0040:81-82`).

**Kodla belge arasındaki boşluklar:**
- **Aydınlatma metninde kütüphane hiç geçmiyor.** DOĞRULANDI: `docs/kvkk-aydinlatma-metni.md`'de "kütüphane/ödünç/kitap" araması boş, §6 saklama tablosunda satır yok. requirements.md `:684`'teki "kütüphane veri kullanımı eklenir" vaadi yerine getirilmemiş.
- **Anonimleştirme eksik kalıyor.** DOĞRULANDI: görev `Membership` satırının kendisine (öğrenci FK'sı ve `card_no`) ve `LossDamageCase.responsible_note` serbest metnine **dokunmuyor**. Bu iki alan yalnız geliştirme komutunda temizleniyor (`anonymize_database.py:255-256`).
- ÇIKARIM: müstakil uygulamada öğrenci kaydı kütüphanenin kendi verisi. OYS'deki kalıcı kimlik gerekçesi (ADR-0055 D2 düzeltmesi, `:61-73`, md. 219 arşiv) okul sicili içindir, kütüphane uygulaması için geçerli değildir. Süre dolunca Student, Membership ve not metni de silinmeli ya da anonimleştirilmeli.

---

### 5. Açık borçlar, bilinen hatalar, son değişiklikler

**Açık teknik borçlar** (`docs/technical-debt.md`). DOĞRULANDI:
- **`F-kutuphane-loanlist-sensitiveread` (`:280`, Düşük).** Genel ödünç listesi eser adı döndürüyor ama hassas okuma olarak loglanmıyor.
- **`F-kutuphane-commission-pii` (`:281`, Düşük).** Komisyon başkanı ve katılımcı serbest metinleri gerçek ad taşıyabilir. Model `kvkk_personal_data=False`.
- **`F-kutuphane-clearance-roleguard` (`:282`, Düşük).** Ödünç ekranındaki ilişik sekmesinin frontend'de ayrı rol kontrolü yok.
- **`F-govde-elle-okunan-uclar` (`:268`, Orta, ilk adı `F-kutuphane-create-dogrulamasiz`).** Ayıklama partisi ve sayım oluşturma uçları gövdeyi doğrulamadan `request.data.get()` ile okuyor.
- **`F-emit-kalan-moduller` (`:229`).** Kütüphane sinyalleri hâlâ `Signal.send()` ile gönderiliyor (hataya dayanıklı `send_robust` değil).
- **`F-kvkk-ogrenci-erisimi` (`:189`).** `Student.user` NULL. İhraç ve imha komutları öğrenciye bu yolla ulaşamıyor (Tur 814'te ayrı öğrenci girişiyle çözülmüş, `denetim/services.py:300-315`).

**Kodda bulunan hatalar ve eksikler.** DOĞRULANDI:
1. **Üye kartında okul adı boş basılıyor.** `views.py:750-752` çağrısı `school_name` geçmiyor, varsayılan `""` (`member_card.py:61`). Kart başlığı " — KÜTÜPHANE ÜYE KARTI" çıkıyor.
2. **Kart tek tek basılıyor.** Fonksiyon çoklu kart tabakası destekliyor (`member_card.py:57-71`) ama yalnız tekli uç var. Her kart ayrı bir A4 sayfası.
3. **"Sınıf listesinden toplu üyelik" hikâyesi karşılanmıyor.** Hikâye CHANGELOG `:32272`'de. Arayüzde şube seçimi yok, öğrenciler tek tek ekleniyor (`UyelerPage.tsx:308-330`).
4. **Kayıp/hasar dosyasındaki "ortaöğretim" (SchoolConfig) kapısı uygulanmamış.** Md. 19 yalnız ortaöğretim hükmü. Docstring kapıdan söz ediyor (`models.py:749`) ama kodda `SchoolConfig` kontrolü yok (grep boş).
5. **Katalog araması `icontains`.** `selectors.py:47-60`. PostgreSQL'de çalışıyor, ama **SQLite'ta LIKE yalnız ASCII için büyük/küçük harf duyarsız**. "şiir" araması "Şiir"i bulmaz. Yerel ağ katalog taraması (OPAC) için kritik. Çözüm önerisi: katlanmış bir arama anahtarı sütunu (kelebek `shared/text.tr_upper` / `normalize.tr_sort_key`).
6. **ISBN hiç normalize edilmiyor**, yalnız `strip()` uygulanıyor (`import_schema.py:130`). Arama tam eşleşme (`selectors.py:57`). ÇIKARIM: tireli kayıt, barkod okuyucudan gelen tiresiz ISBN-13 ile eşleşmez.
7. **Saha provası yapılmamış.** Kütüphane maddesi B3 (`saha-prova-kilavuzu.md:154-157`) ve Tanex etiket ölçüsü teyidi D6 (`:234`) işaretsiz. Etiket şablonları "(teyit bekliyor)" (CHANGELOG `:32361-32363`). Modül gerçek veriyle hiç denenmedi.

**Git geçmişi (20 commit).** DOĞRULANDI:
- **15.07.2026, tek günde 11 commit.** Tur 600-604 backend K1-K5, Tur 605-610 frontend KF1-KF6.
- **16.07.** Tur 613: görünüm içindeki ORM çağrıları selectors/services katmanına taşındı. Tur 615: frontend konsolidasyonu.
- **17.07.** Tur 620: kütüphane nöbeti.
- **Sonrası yalnız bakım.** Tur 738 tasarım dili (04.08), Tur 800 bildirim linkleri (14.08), Tur 837/841 OpenAPI şema sözleşmesi (18-19.08), Tur 887 para biçimi (22.08), Tur 889 olay sözlüğü (22.08).
- Temmuzdan sonra işlev değişikliği yok.

---

### 6. Kelebek-sınav'dan hangi okul çekirdeği alınabilir

**Kaynak.** `../kelebek-sinav/backend/apps/okul` (149 commit, son sürüm `2026.9.0-beta.12`).

| Parça | Dosya | Kütüphane için | Durum |
|---|---|---|---|
| Okul künyesi + antet | `models.py:132 SchoolConfig`, `services/setup.py` (`get_letterhead_identity`), `shared/letterhead.py` | Rapor antetleri, kart okul adı | Olduğu gibi alınır |
| Ders yılı ve dönem | `models.py:260, 291`, `services/school_year.py`, `services/terms.py` | Sayım/ayıklama `school_year` FK'sı, yıl istatistiği | Olduğu gibi alınır |
| Öğrenci | `models.py:542-606`: ad şifreli, okul no ve sınıf/şube açık, ACTIVE/LEFT. TCKN ve veli yok | En az veri setiyle örtüşüyor (§2) | Olduğu gibi. `gender` alanı kütüphanede gereksiz, alınmayabilir |
| Fotoğraf | `models.py:609-647`, `eokul_foto.py` (e-Okul **OOG01001R080**), `services/photos.py` | Üye kartı | Hazır (19.09.2026) |
| Personel | `models.py:339-369`: ad şifreli, unvan, branş, `is_active` | Öğretmen/personel üyeliği | Olduğu gibi |
| Şube kataloğu | `models.py:407 ClassSection`, `services/sections.py` | Şube bazlı toplu üyelik | Olduğu gibi |
| **e-Okul öğrenci aktarımı** | `eokul.py` (**OOG01001R020** sınıf listesi, şube bloklarını düzleştirir), `excel_ogrenci.py` (xlsx + xls + pano), `normalize.py`, `services/imports.py` (önizle, sonra uygula, `ImportRun`) | **Hazır** | Olduğu gibi |
| **e-Okul personel aktarımı** | `eokul.py` (**OOK01001R1** personel listesi), `excel_personel.py` (Adı / Soyadı / Görevi / Branşı), `services/imports.py:326 _ingest_personnel` (ada göre upsert) | **Hazır** | Olduğu gibi |
| Yedek, geri yükleme, uygulama parolası, kilit | `services/backup_restore.py`, `encrypted_backup.py`, `app_password.py`, `lock_middleware.py`, `restart_gate.py`, `desktop/backup.py` | Veri güvenliği | Olduğu gibi. **Kilit bütün API'yi 423 ile kesiyor** (`lock_middleware.py`). Yerel ağ katalog taraması için karar gerekir |
| Sürüm denetimi | `services/updates.py` (GitHub Release, yalnız kullanıcı istediğinde) | | Olduğu gibi |

**Kelebekten kütüphaneye taşınırken dikkat edilecekler:**
- **Ayrılan öğrenci otomatik işaretlenmiyor.** DOĞRULANDI: `_ingest_students` yalnız ekleyip güncelliyor, yeni listede olmayan öğrenciyi LEFT yapmıyor (`services/imports.py:235-300`). Kütüphane için (Md. 16/3 üyelik sonlandırma, OYS'deki güvenlik ağının karşılığı) **"listede artık olmayanlar" mutabakat adımı** gerekir. ÇIKARIM: bu yeni iş. Önizlemede "N öğrenci listede yok, ayrıldı sayılsın mı?" diye sorulabilir.
- **Ayrılışta kalıcı silme.** DOĞRULANDI: LEFT durumunda `_forget_student_data` fotoğrafı ve kancalı verileri kalıcı siliyor (`persons.py:31-35, 51-53`). Kütüphanede ayrılan öğrencinin kaydı ve ödünç izi, açık yükümlülük kapanana ve saklama süresi dolana kadar **tutulmalı**. Kancanın sırası ve semantiği uyarlanmalı.
- **Ağ erişimi yok.** DOĞRULANDI: sunucu `127.0.0.1` ve rastgele port kullanıyor (`desktop/server.py:1-12, 30`), belirteç `X-KS-Token` ile fail-closed (`desktop/session_guard.py:1-17`). Yerel ağdan erişim bu kalıba **ters**. Yönetim ve katalog için ayrı dinleyici/yüzey ve sabit port gerekir (bkz. §7).
- **Personelde e-posta ve rol yok.** Personel ada göre upsert ediliyor. Kütüphanede sorun değil.

**Disiplin-defteri'nin öğrenci modeli neden daha az uygun?** Orada Student TCKN, veli adı/telefonu/adresi taşıyor (`disiplin-defteri-codex/backend/apps/okul/models.py:342-367`). Kelebek, kütüphane için daha doğru çekirdek.

---

### 7. Karar gerektiren ve gözden kaçabilecek konular

Kodda karşılığı olan riskler:

1. **"Bakanlıkça belirlenen otomasyon sistemi" şartı.** DOĞRULANDI: Yönetmelik Md. 9/2, 11/2, 16/2 işlerin "Bakanlıkça belirlenen kütüphane otomasyon sistemi üzerinden" yürütülmesini istiyor (`meb-okul-kutuphaneleri-yonetmeligi.md:131, 167, 256`). Kılavuz belirli bir sistemin adını vermiyor. ADR-0040 "OYS bu okulun otomasyon sistemidir" diyor (`:18-19`), ama bu bir iddia, dayanak değil. ÇIKARIM: İlçe MEM'e sorulmalı. Bakanlık bir sistem belirlemişse, bu uygulama TKYS emsali gibi "hazırlık/yardımcı araç" olarak konumlanır.
2. **Onay zinciri tek kullanıcıda.** ÇIKARIM: teklif ile onayın ayrılması (ayıklama ve sayım: `permissions.py:19-20`, `models.py:847, 1001`) girişsiz uygulamada teknik olarak zorlanamaz. Seçenekler:
   - (a) onaylayan adı ve tarihi serbest metin olur, resmî imza kâğıtta atılır;
   - (b) müdür için ayrı bir onay parolası konur.
3. **Yerel ağ yüzeyi yalnız katalog olmalı.** ÇIKARIM: katalog verisi (Work/Copy) kişisel veri taşımaz (`kvkk_personal_data=False`, `models.py:248, 330`). Üyelik, ödünç ve kayıp dosyası taşır (`:625, 708, 755`). Ağa açılacak uçlar salt okunur bir beyaz liste olmalı. "Ödünçte, iade tarihi" gösterilebilir, **ödünç alanın kimliği asla**. Diğer riskler:
   - FATİH ağında VLAN ayrımı ve istemci izolasyonu, `.local` adının çözülmemesi (`okulapp/docs/fatih-ag-kurulum.md:16-40, 83-105`).
   - Windows Güvenlik Duvarı'nın "Ortak ağ" profili.
   - Kelebeğin rastgele port kullanması (sabit port gerekir).
   - Uygulama parolası kilidi (katalog kilitliyken açık kalsın mı?).
   - Uygulama kapalıyken katalog erişilemez.
4. **Yerel ağdan öğrencinin kendi ödünçlerini görmesi.** ÇIKARIM: kimlik doğrulama gerektirir. OYS'nin bile ertelediği konu bu (§3). Kart no + PIN gibi zayıf yöntemler okuma alışkanlığı verisini (yüksek risk, ADR-0040 K10) sızdırabilir. Kapsam dışı tutulması öneriliyor.
5. **Üyelik otomatik mi, istek üzerine mi?** DOĞRULANDI: Md. 17/1 "üye olmak **isteyen**" diyor (`yonetmelik.md:263`). Tüm öğrencileri otomatik üye yapmak bu ifadeyle gerilim yaratır. Şube bazlı toplu üyelik "istek listesi" üzerinden kurgulanabilir.
6. **Kütüphane nöbeti (Tur 620).** Nöbet motoru ve kulüp modeline bağlı (#21). V1'de alınmaması ya da "nöbetçi öğrenci listesi" gibi basit bir forma indirilmesi önerilir.
7. **Veli SMS'i ve bildirimler.** Kaldırılmalı, yerine ekran rozeti ve PDF liste gelmeli (#13-15). Bu değişiklik veli verisi toplama ihtiyacını tamamen ortadan kaldırıyor.
8. **Aydınlatma metni.** Yeni uygulama için kütüphaneye özgü kısa bir aydınlatma metni gerekiyor (§4). OYS'de böyle bir metin hiç yazılmadı.
9. **Türkçe arama ve ISBN normalizasyonu.** SQLite'a geçişte yerel ağ katalog taramasının temel kalitesini belirliyor (§5, 5-6. maddeler).
10. **Veri geçişi.** ÇIKARIM: OYS'de modül açık (varsayılan `True`) ama saha provası yapılmamış (§5, 7. madde). OYS'de gerçek kütüphane verisi olup olmadığı bilinmiyor. Varsa OYS'den aktarım aracı gerekir, yoksa sıfırdan başlanır. Kullanıcıya sorulmalı.

<a id="r5"></a>

---

## R5. Mevzuat ve Bakanlık otomasyon sistemi araştırması

## Kütüphane masaüstü uygulaması: mevzuat ve Bakanlık otomasyon sisteminin durumu (araştırma raporu, 21.09.2026)

### 0. Özet

- **Otomasyon şartı:** Yönetmelik, kütüphane işlerinin **"Bakanlıkça belirlenen kütüphane otomasyon sistemi"** üzerinden yürütülmesini şart koşuyor: teknik hizmetler, kataloglama, ödünç, üyelik, kart ve iade (Md. 9/2, 11/2, 16/2-3, 17, 20-23). Ama sistemin adını ve adresini vermiyor.
- **Bakanlığın sistemi:** İkincil basına göre (13.09.2026) MEB, 14.09.2026'dan önce **"Okul Kütüphaneleri Otomasyon Sistemi"**ni devreye aldı. Buna karşılık **meb.gov.tr veya dhgm.meb.gov.tr'de resmî bir duyuru, adres ya da veri aktarım biçimi bulunamadı.** Bakanlığın zaten bir web otomasyonu var: **Z-Kütüphane Otomasyonu** (z-kutuphane.meb.gov.tr). Ulusal sistemin bu olup olmadığı DOĞRULANAMADI.
- **Değişiklik:** RG 23.11.2024/32731 künyesi doğrulandı. Lexpera'nın konsolide metnine göre değişiklik yok. mevzuat.gov.tr bu oturumda 404 döndü.
- **OYS'deki varsayım:** OYS ADR-0040, kendini "okulun kütüphane otomasyon sistemi" olarak konumluyor (`docs/adr/0040-kutuphane-modulu.md:16-19`). Bakanlık kendi sistemini devreye aldıysa bu varsayım **zayıflıyor**. Müstakil uygulama "yardımcı / yerel araç" olarak konumlanmalı ve veri aktarımına hazır olmalı.
- **Ağ erişiminde yeni bir mevzuat alanı:** **MEB Bilgi ve Sistem Güvenliği Yönergesi**, kurum ağına izinsiz cihaz veya hizmet eklemeyi, form ile veri toplamayı ve dosya paylaşım portlarını kısıtlıyor (Md. 11/7, 11/8, 11/16, 11/22, 11/25). Bu yüzden ağa açılan kısım **salt okunur** ve **kişisel veri içermeyen** olmalı. Kurumun bilişim sorumlusunun bilgisi de gerekiyor.

---

### 1. Kaynaklar ve künye doğrulaması

| Kaynak | Durum |
|---|---|
| Okul Kütüphaneleri Yönetmeliği, RG 23.11.2024/32731 | DOĞRULANDI: `okulapp/data/mevzuat/meb-okul-kutuphaneleri-yonetmeligi.md:1-8`. Resmî Gazete sayfasında başlık, tarih ve sayı teyit edildi: https://www.resmigazete.gov.tr/eskiler/2024/11/20241123-1.htm |
| Değişiklik var mı | DOĞRULANDI (Lexpera): konsolide metinde "Değişik/Ek/Mülga" ibaresi yok, son hâl RG 23.11.2024 (https://www.lexpera.com.tr/mevzuat/yonetmelikler/milli-egitim-bakanligi-okul-kutuphaneleri-yonetmeligi-1). "…Yönetmeliğinde Değişiklik…" araması yalnız 2001 yönetmeliğine yapılan 2006 değişikliğini buldu. mevzuat.gov.tr (MevzuatNo=4845) bu oturumda 404 verdi, **resmî konsolide kaynaktan teyit edilemedi**. |
| Uygulama Kılavuzu (Ankara 2025) | DOĞRULANDI: yerel dosya `...uygulama-kilavuzu.md:1-12`. DHGM duyurusu 16.10.2025, kılavuz tarihi 02.10.2025 (https://dhgm.meb.gov.tr/www/okul-kutuphaneleri-yonetmeligi-uygulama-kilavuzu-yayimlandi/icerik/1183/tr) |
| Taşınır Mal Yönetmeliği (9014, RG 10.10.2024/32688), madde alıntıları | DOĞRULANDI: `tasinir-mal-yonetmeligi-ilgili-maddeler.md:1-12` |
| Okul Kütüphaneleri Standart Yönergesi (TD Kasım 2006/2590) | DOĞRULANDI (PDF okundu): https://dhgm.meb.gov.tr/dosyalar/Yonerge/2006_2590.pdf. Dayanağı **mülga** 2001 yönetmeliğinin 6. maddesi (Md. 3). Yeni yönetmelik Md. 6/1 "standartlar yönerge ile belirlenir" diyor, yeni bir yönerge bulunamadı. Teftiş rehberi bu yönergeye hâlâ atıf yapıyor (aşağıda). |
| MEB Bilgi ve Sistem Güvenliği Yönergesi | DOĞRULANDI (PDF okundu): https://osmaniye.meb.gov.tr/meb_iys_dosyalar/2018_07/06102858_Bilgi_Ve_Sistem_Guvenligi_Yonergesi.pdf. Onay tarihi metinde yok, 11.04.2012 tarihli ve 565 sayılı Olur'u kaldırıyor (Md. 20). Daha yeni bir sürüm olup olmadığı KONTROL EDİLMEDİ. |

---

### 2. Okul Kütüphaneleri Yönetmeliği: uygulamayı etkileyen hükümler

(Tüm satır numaraları `../okulapp/data/mevzuat/meb-okul-kutuphaneleri-yonetmeligi.md` dosyasına aittir.)

#### 2.1 Otomasyon zorunluluğu (tam ifadeler)

| Madde | Metin | Satır |
|---|---|---|
| 4/1-h (tanım) | "Otomasyon sistemi: Kaynakların yönetimi, **paylaşımı** ve kaynaklardan **faydalanma** işlemlerinin dijital ortam üzerinden yapılmasını sağlayan sistemi" | 64 |
| 8/1-a | Kütüphaneci "Bakanlıkça belirlenen kataloglama ve sınıflama sistemini kullanır" | 100 |
| 9/2 | "Birinci fıkrada yer alan iş ve işlemler Bakanlıkça belirlenen kütüphane otomasyon sistemi üzerinden yürütülür." (9/1: seçim-sağlama, kataloglama-sınıflama, bakım-onarım-ayıklama) | 131 |
| 11/1 | "…Bakanlıkça belirlenen kataloglama ve sınıflama sistemi kullanılır. Kataloglar; yazar adı, kaynak adı ve konularına göre alfabetik olarak düzenlenir. Yapılan işlemler bilgisayar ortamına aktarılır." | 165 |
| 11/2 | "İşlemler kütüphane otomasyon sistemi üzerinden yürütülür." | 167 |
| 16/2 | "…yararlanma süreci ve ödünç verme hizmeti kütüphane otomasyon sistemi üzerinden yürütülür." | 256 |
| 16/3 | Okuldan ayrılan öğrenci ve öğretmenin "otomasyon sistemindeki üyelikleri sonlandırılır." | 258 |
| 17/1 | Üyelik işlemleri "otomasyon sistemi üzerinden yürütülür." | 263 |
| 20/1 | Kullanıcı kartı "kütüphane otomasyon sistemi üzerinden" düzenlenir | 278 |
| 21/1 | Ödünç kitaplarla ilgili iş ve işlemler otomasyon sistemi üzerinden yapılır (başlık hâlâ "numara fişi") | 283 |
| 22/1 | Ödünç kitapların kontrolü otomasyon sistemi üzerinden takip edilir (başlık "kitap kontrol fişi") | 288 |
| 23/1 | a) kart görevliye verilir, b) kitap ve ödünç tarihi sisteme kaydedilir, c) iade sistem üzerinden alınır | 293-299 |

**Dikkat:** Md. 9/2 "Bakanlıkça belirlenen" diyor. Md. 11/2, 16/2, 17 ve 20-23 ise yalnız "(kütüphane) otomasyon sistemi" diyor. ÇIKARIM: Lafzen en sıkı bağ teknik hizmetlerde (9/2) ve kataloglama/sınıflama *sisteminde* (11/1). Ödünç ve üyelik maddeleri Bakanlık sistemine açık atıf yapmıyor, ama bütünsel yorumla aynı sistem kastediliyor.

#### 2.2 Katalog ve sınıflama

- **Üç katalog ekseni:** yazar adı, kaynak adı, konu; alfabetik düzen (Md. 8/1-a:100, 11/1:165).
- **"Bakanlıkça belirlenen kataloglama ve sınıflama sistemi":** 2024 metni sistemi adlandırmıyor. **Mülga** 2001 yönetmeliğinin 11. maddesinde "AAKK II kullanılır. Sınıflamada Dewey Onlu Sınıflama Sistemi kullanılır." hükmü vardı (https://www.memurlar.net/haber/58323/…). Yeni bir Bakanlık belirlemesi BULUNAMADI. ÇIKARIM: Fiilî standart Dewey (DOS). Uygulama yer/sınıflama numarasını serbest alan olarak tutmalı, tek bir sisteme sabitlememeli.
- **Kaynak türleri:** kültür yayınları, süreli yayınlar, e-veritabanı, e-kitap, e-dergi, dijital görsel-işitsel (Md. 4/1-ç:52).
- **Alan bölümleri:** Ortaöğretimde okul türüne göre "alan" bölümleri vardır (Md. 4/1-a:46, 6/1:84). Bu, konum veya bölüm alanı gerektirir.
- **Danışma dermesi:** ders kitabı, ansiklopedi, sözlük, atlas, **kataloglar** vb. (Md. 14/1-a:196). Dijital nüshalar imkânlar dahilinde sunulur (14/1-b:198).

#### 2.3 Üyelik ve ödünç

| Konu | Hüküm | Satır |
|---|---|---|
| Kullanıcılar | Öğrenci ve öğretmen "doğal kullanıcı". Ödünç yalnız "**üye olmak koşuluyla**" öğrenci ve öğretmene (16/1). Kullanıcı hizmetleri "öğrenci, öğretmen ve diğer personel"i kapsar (13/1). ÇIKARIM: diğer personelin ve velinin ödünç alması düzenlenmemiş. | 246, 189 |
| Ödünç verilmeyenler | danışma kaynakları, piyasada mevcudu bulunmayan kitaplar, süreli yayınlar (16/1-a,b,c) | 248-254 |
| Süre ve adet | 15 gün. Öğrenciye bir defada en fazla 3, öğretmene en fazla 5 kitap. **Süre uzatma, gecikme cezası, rezervasyon hükmü yok.** | 268 |
| Takip | İade edilmeyen kitabın takibi kütüphaneci veya sorumlu öğretmende (18) | 268 |
| Ayrılma | Üyelik sonlandırılır ve ödünç kitabın iadesi sağlanır (16/3, 18). Bu, ilişik kesme işlevi gerektirir. | 258, 268 |
| Kart | Kart kütüphane yöneticisince sistem üzerinden düzenlenir (20). Ödünçte kart görevliye verilir (23/a). | 278, 295 |

#### 2.4 Kayıp ve hasar (Md. 19, satır 273)

"**Ortaöğretim** okul kütüphanelerinde" kaynak kişiden temin edilir. Temin edilemezse "o günkü piyasa bedeli" alınır. Bedelle aynısı ya da başka eser alınır, kaybolanın kaydı silinir. ÇIKARIM: İlkokul ve ortaokul için hüküm yok. Tahsilat usulü de belirtilmemiş. OYS, "para tahsil etmez, yalnız kaydeder" kararı almıştı (`docs/adr/0040-kutuphane-modulu.md:23-25`).

Bağlantılı disiplin hükmü: Ortaöğretim Kurumları Yönetmeliği Md. 164/1-g'ye göre kütüphaneden alınan kitabı "eksik vermek veya kötü kullanmak" **kınama** gerektirir (`ortaogretim-kurumlari-yonetmeligi.md:4567`). ÇIKARIM: Uygulama bunu kaydedebilir, disiplin sürecini kendisi başlatmamalı.

#### 2.5 Seçim ve Ayıklama Komisyonu, bağış, edinim

- **Kuruluş:** İlçe MEM şube müdürü başkanlığında. Üyeler: okul müdürü, sorumlu müdür yardımcısı, kütüphaneci veya sorumlu öğretmen, zümre başkanları, kütüphanecilik kulübü danışmanı (Md. 4/1-ı:66). Şube müdürü katılamazsa okul müdürü başkanlık eder (10/1:136).
- **Seçim ölçütleri:** 10/1-a…f (138-150). Özel eğitim materyali bulundurulur (10/2:154). Uygun olmayan kitap bulundurulamaz (10/4:158).
- **Bağış:** Komisyon değerlendirir (10/3:156).
- **Edinim yolları:** Bakanlıktan gönderilen, satın alma, bağış, değişim (10/5:160). Bu, edinim yöntemi listesini belirler.
- **Ayıklama (Md. 12/1, satır 172-182):**
  - Her ders yılı sonunda kaynaklar gözden geçirilir ve **raporla okul müdürlüğüne** bildirilir.
  - Ayıklama nedenleri: yıpranma, bilimsel değer kaybı, düzeye uygunsuzluk, 10. madde ölçütlerine aykırılık.
  - Ayıklananlar **tutanakla** tespit edilir, TMY'ye göre kayıttan düşülür.
  - 10/1-b'ye (yaş/gelişim) uymayan kaynaklar uygun okullara **devredilir**.
- **Nadir eserler:** El yazmaları ve nadir eserler listesi **Genel Müdürlüğe gönderilir** (12/2:184).

#### 2.6 Personel ve görevler

- **Kütüphaneci ataması:** Kitap sayısı **10.000'i aşan** okula kütüphaneci atanır, yoksa görevlendirme yapılır. Yardımcı memur görevlendirilir ve memura başka görev verilmez (Md. 7:91-93). ÇIKARIM: Toplam kitap sayısı raporu bu eşiği izlemek için işe yarar.
- **Kütüphaneci / sorumlu öğretmen görevleri (Md. 8/1-a…ğ, satır 100-116):** kayıt, bibliyografik kimlik, katalog, envanter ve koleksiyon yönetimi, ödünç ve iade takibi. Ayrıca 8/1-ğ: "…faaliyetleri ve bunlarla ilgili raporları okul yönetimi, öğretmenler, öğrenciler ve velilerle paylaşır."

#### 2.7 Kulüp, etkinlik ve öğrencinin katalog kullanımı

- **Kulüp:** Kütüphanecilik kulübü öncülüğünde iş birliği (Md. 15/1:207). Kulüp, Sosyal Etkinlikler Yönetmeliği EK-4 çizelgesinde yer alıyor (`meb-egitim-kurumlari-sosyal-etkinlikler-yonetmeligi-ekleri.md:60-63`). Kütüphaneler Haftası (Mart ayının son pazartesisini içeren hafta) EK-8'de (`…:278-282`). **"Nöbetçi öğrenci" veya öğrenci görevli hükmü yönetmelikte YOK.**
- **15/1-a (209):** Her öğretim yılı başında öğrencilere danışma kaynakları "ile varsa elektronik kaynakların kullanımını öğretir".
- **15/1-ğ (225):** "çok okunan ve okunmasında fayda görülen kitaplar listesini belirli aralıklarla ilan" eder.
- **15/1-n (241):** Öğrencileri basılı ve dijital kaynaklara erişim çalışmalarına yönlendirir.
- **8/1-ç (106):** Araştırma ve kaynaklara erişmede rehberlik eder.
- **14/1 (194):** Danışma hizmeti "olanaklar ölçüsünde elektronik ortamlarla da karşılanır".
- **Teknolojik altyapı:** "Teknolojik kaynak için gerekli düzenlemeler yapılır ve teknolojik altyapı kurulur." (Md. 6/2:86)
- **Çalışma saatleri (Md. 24:304-308):** Eğitim-öğretim ve mesai saatlerinde açık olmak esastır. Proje ve ödev için müdürlükçe belirlenen ek saatler olabilir. Yatılı okullarda ayrı plan yapılabilir.

#### 2.8 Rapor ve istatistik yükümlülükleri (kime, ne zaman)

| Ne | Kime | Ne zaman | Dayanak |
|---|---|---|---|
| Kaynakların gözden geçirme raporu | Okul müdürlüğü | Her ders yılı sonu | Md. 12/1 (172) |
| Kitap durumu, kazandırılan ve ayıklanan kaynaklar | Okul yönetimi | Her eğitim-öğretim yılı sonu | Kılavuz 2.4 (`…kilavuzu.md:165`) |
| El yazması ve nadir eser listesi | Genel Müdürlük (DHGM) | Komisyon tespitinde | Md. 12/2 (184) |
| Faaliyet ve okuma verileri raporları | Yönetim, öğretmen, öğrenci, veli (paylaşım) | Belirtilmemiş | Md. 8/1-ğ (116) |
| Çok okunan kitaplar listesi | İlan | "Belirli aralıklarla" | Md. 15/1-ğ (225) |
| Okuma ile ders başarısı raporu | Kurullar ve zümreler | Yıl sonu, **öneri** | Kılavuz 7 (`…kilavuzu.md:481-485`) |

Yönetmelikte **Bakanlığa veya ilçeye düzenli istatistik gönderme yükümlülüğü YOK.** ÇIKARIM: Merkezî sistem bunu kendiliğinden toplayacaktır.

#### 2.9 Uygulama Kılavuzu'nda otomasyon ve katalog

(Yerel dosya: `…uygulama-kilavuzu.md`)

- **Satır 370:** "Ayın Kitapları" panosu "otomasyon sisteminden elde edilen verilerle" hazırlanır.
- **Satır 464:** Eylül ayı "Kütüphane Tanıtım Günleri"nde öğrencilere "otomasyon sistemi, ödünç alma kuralları tanıtılır". ÇIKARIM: Kılavuz, öğrencinin otomasyonun kullanıcı yüzüyle tanışmasını öngörüyor.
- **Satır 93 (1.3) ve 402:** Dijital erişim ve dijital okuryazarlık ilkesi. **Satır 105 (1.6):** erişilebilirlik.
- **Satır 253 (4.2):** Öğrenci ve öğretmenin kitap taleplerinin komisyonca dikkate alınması önerilir.
- **Satır 482:** Otomasyon verisiyle aktif okuyucuların ders başarısı izlenebilir. **Satır 485:** En çok okuyan öğrenciler ödüllendirilebilir. İkisi de **öneri** niteliğinde, KVKK açısından hassas (bkz. §6-d).

---

### 3. Taşınır Mal Yönetmeliği (kayıttan düşme ve sayım)

(`tasinir-mal-yonetmeligi-ilgili-maddeler.md`)

- **Md. 9/1-ç (41):** Kütüphane Defteri; her taşınır için ayrı kayıt.
- **Md. 15/4 (49):** Süreli yayına Varlık İşlem Fişi düzenlenmez, yalnız ciltlenenler kayda girer.
- **Md. 17 (55):** Sayım fazlası girişi.
- **Md. 27 (71):** Kayıp ve sayım noksanında Kayıttan Düşme Teklif ve Onay Tutanağı ile Varlık İşlem Fişi düzenlenir.
- **Md. 28 (79-89):** Hurda veya imha; en az 3 kişilik komisyon ve harcama yetkilisi onayı.
- **Md. 24 ve 31 (61, 95):** Devir.
- **Md. 32 (103-119):** Yıl sonu sayımı, en az 3 kişilik kurul. Fark çıkarsa bir kez daha sayılır (32/6). Noksan ve fazla işlemleri 32/7'de. Teslim belgeli taşınırlar sayılmaz (32/5). ÇIKARIM: Ödünçteki kitaba bu kıyasla uygulanır.
- **Md. 34/2-c ve 34/3-a (133-137):** Kütüphane Yönetim Hesabı Cetveli.

ÇIKARIM: Resmî taşınır kaydı Bakanlığın (MEB'in) otomasyonunda değil, Hazine ve Maliye Bakanlığının KBS/TKYS sisteminde tutulur. OYS de TKYS/MEBBİS'in yerine geçmediğini ve yalnız hazırlık çıktısı ürettiğini söylüyor (`docs/adr/0040-kutuphane-modulu.md:21-22, 99-101`). Müstakil uygulama da aynı konumda kalmalı.

---

### 4. Diğer bağlayıcı veya ilgili metinler

- **Teftiş:** Lise ve Dengi Okullar Denetim Rehberi, 3. kriter: "MEB Okul Kütüphaneleri Yönetmeliği Md. 6-8, 10, 11, 12; Okul Kütüphaneleri Standart Yönergesi Md. 6" (`lise-ve-dengi-okullar-denetim-rehberi.md:31`). ÇIKARIM: Müfettiş katalog, komisyon kararları, ayıklama tutanakları ve yıl sonu raporuna bakar. Uygulamanın çıktıları denetimde kanıt olur.
- **Ortaöğretim Kurumları Yönetmeliği:**
  - Md. 94/1-b: kütüphane memuru (`…:3421`).
  - Md. 100: hâlâ **mülga 2001 yönetmeliğine** atıf yapıyor (`…:3512-3514`). Bu eskimiş bir atıf, uygulamada 2024 metni esas alınmalı.
- **Standart Yönergesi (2006):** Kütüphanede öğrencilerin kullanımına bilgisayar ve "öğrencilerin ve personelin kullanımına açık internet bağlantısı" bulunur (Md. 8/1-d, g). Bilgisayar masası ve sandalyesi temel donanımda yer alır (Md. 7/1-a-3,4). Kitap sayısı standardı: 200-999 öğrenciye 6000-10000 kitap, 1000'den fazla öğrencide öğrenci başına 10 kitap (Md. 9/3). ÇIKARIM: Bu hükümler kütüphanede öğrenci kullanımına açık bilgisayar bulunmasını, dolayısıyla katalog tarama terminalini dolaylı destekliyor.
- **e-Okul:** "Kurum İşlemleri > Okuduğu Kitaplar" menüsünde Sınıf Kitaplığı Oluşturma ve Öğrenci Kitap Bilgileri bölümleri var. Bu kayıtlar karnede "Okuduğu Kitap Sayısı" olarak görünür. 04.04.2011'den beri kullanımda (https://eokul.meb.gov.tr/Dokumanlar/OGR_OKUDUGU_KITAPLAR.pdf). Bu bir kütüphane otomasyonu değil. ÇIKARIM: Güncel e-Okul'da hâlâ varsa, "okuduğu kitaplar" verisi kütüphane ödünç kaydıyla karıştırılmamalı.
- **MEB Bilgi ve Sistem Güvenliği Yönergesi** (ağ erişimi için belirleyici):
  - Md. 11/7: "Kurum ağına sistem yöneticisinin bilgisi dışında herhangi bir aktif ağ cihazı eklenemez."
  - Md. 11/8: Kişisel bilişim kaynakları kurum ağında izinsiz kullanılamaz.
  - Md. 11/16: Kurumsal ağdaki bilgisayarlara erişim hakkı yetkisiz kişilere verilemez.
  - Md. 11/20: İzinsiz kablosuz erişim noktası takılamaz; izinliler şifresiz kullanılamaz.
  - Md. 11/21: DHCP, DNS, Proxy, NAT kullanımı yasak.
  - Md. 11/22: Portları Başkanlık belirler. Uzaktan erişim ve dosya-yazıcı paylaşımına izin yok; 80 ve 443 numaralı portlara öncelik verilir.
  - Md. 11/23: Veriler Bakanlık sistemlerinde barındırılır, buluta aktarılmaz.
  - **Md. 11/25: "Başkanlığın mevcut anket programı hariç anket programları veya formlar veri toplama ve depolama amacıyla kullanılamaz."**
  - Md. 14/3: Bakanlığa ait olmayan sunucularda web hizmeti yayını yapılamaz (internet sitesi barındırma bağlamında).
  - Md. 5/8: Öğrenci, veli ve öğretmen kişisel bilgileri üçüncü kişilerle paylaşılamaz.

---

### 5. Bakanlığın kütüphane otomasyon sistemi: web araştırması

| Bulgu | Kaynak ve tarih | Güvenilirlik |
|---|---|---|
| Yönetmelik duyurusu: "tüm bu işlemler kütüphane otomasyon sistemi üzerinden yürütülecek". Sistemin adı ve adresi yok. | meb.gov.tr haber 35539; dhgm icerik/1100; AA 3402196 (23.11.2024) | Resmî. **Ad yok.** |
| Kılavuz duyuruları: otomasyondan yalnız rapor bağlamında söz ediliyor, sistem adı ve adresi yok. 81 ilde sorumlu öğretmenlere çevrim içi toplantılar planlanmış. | meb.gov.tr haber 38724 (22.10.2025); dhgm icerik/1183 (16.10.2025) | Resmî |
| **"Okul Kütüphaneleri Otomasyon Sistemi"** 14.09.2026 öncesinde devreye alındı. Anlatılan işlevler: kataloglama, sınıflama, ödünç ve iade, yazar/eser/konuya göre alfabetik tarama, **aranan kitabın kütüphanede bulunup bulunmadığının sorgulanması**, tek merkezden anlık takip, okuma alışkanlığı analizi ve ödüllendirme. **URL, altyapı (MEBBİS/e-Okul), veri aktarım biçimi ve resmî yazı sayısı verilmemiş.** | haberaktuel 3474530 (15.08.2026); mebpersonel h142939, egitimsitesi 11464, haberaktuel 3489159, webdeogren (13.09.2026) | **İkincil basın.** Eşdeğer bir meb.gov.tr veya dhgm duyurusu **bulunamadı** (alan adı kısıtlı aramalar sonuçsuz). Haberler birbirinin tekrarı, kılavuz metnini yeniden işliyor görünüyor. |
| **Z-Kütüphane Otomasyon Sistemi:** DHGM Ders Kitapları ve Yayımlar Daire Başkanlığı; 1.447 okul kayıtlı, 47.799 eser kataloglanmış; Z-Kütüphanelerin "hem bütünleşik hem de bağımsız olarak yönetilebilmesi" için. | dhgm icerik/473 (24.05.2019) | Resmî (2019) |
| z-kutuphane.meb.gov.tr, "Otomasyon Giriş": kullanıcı işlemleri, kitap ekleme ve ödünç verme yapılan web sitesi. Şifre için 0312 413 21 39 / zkutuphane_otomasyon@meb.gov.tr; destek 0312 413 21 41. | Yalnız arama sonucu özeti. Site bu oturumda **DNS çözülemedi** (ENOTFOUND). | **DOĞRULANAMADI.** Tüm okullara açılıp açılmadığı bilinmiyor. |
| MEBBİS modül listesinde kütüphane modülü yok. | bilgitik.com (04.09.2026) | Zayıf ikincil kaynak |
| İl ve ilçe MEM'lerin dağıttığı yerel programlar: Niğde "OKA" v4.0 (masaüstü, Windows ve Pardus, Android eki; yayın 28.08.2025, güncelleme 25.05.2026; arama özetine göre Excel ile toplu yükleme); Ordu "OMEM Kütüphane" (22.06.2022, güncelleme 17.09.2024); Gümüşhacıköy (20.04.2022). Hiçbiri Bakanlık sistemiyle ilişkisini açıklamıyor. | nigde.meb.gov.tr icerik/2495; ordu.meb.gov.tr icerik/4974; gumushacikoy.meb.gov.tr icerik/1274 | Resmî (il ve ilçe) |

**Açık bilinmeyenler:** Bakanlık sistemine hangi adresten girileceği, e-Okul'dan öğrenci aktarımı olup olmadığı, okulların mevcut kataloglarını Excel veya MARC ile aktarıp aktaramayacağı, yerel yazılımların durumu (yasak mı, serbest mi, paralel kullanım mı). Bunlar için **resmî bir kaynak bulunamadı. Uydurulmadı.** Öneri: İlçe MEM veya DHGM Eğitim Müzeleri, Kütüphaneler ve Öğretmenevleri Daire Başkanlığına sorulmalı (DHGM iletişim: 0312 413 26 80/81, dhgm icerik/1183 sayfasından), ya da okula gelmiş bir resmî yazı varsa (DYS) o incelenmeli.

---

### 6. Sonuç

#### (a) Müstakil yerel uygulamanın hukuki konumu

- **DOĞRULANDI:** Md. 9/2 ve 11/1 "**Bakanlıkça belirlenen**" sistem ve kataloglama/sınıflama sistemi istiyor. Okulun kendi yaptığı bir yazılım, Bakanlık belirlemedikçe bu tanıma girmez.
- **ÇIKARIM:**
  - OYS'nin "bu okulun otomasyon sistemi" iddiası (`docs/adr/0040-kutuphane-modulu.md:18-19`), Bakanlık bir sistem belirlemediği dönemde savunulabilirdi. Basına göre Eylül 2026'da Bakanlık sistemi devrede. Bu doğrulanırsa **yerel uygulama Bakanlık sisteminin yerine geçmez.** Resmî ödünç ve katalog kaydı Bakanlık sisteminde tutulmalı. Aksi hâlde denetimde (Denetim Rehberi kriter 3) "Md. 9/2, 11/2, 16/2 gereği işlemler Bakanlık sistemi üzerinden yürütülmüyor" tespiti riski var.
  - Uygulama için savunulabilir konumlar:
    - **(i) Hazırlık ve kataloglama aracı:** toplu kayıt, etiket ve barkod, sayım; Bakanlık sistemine **dışa aktarım**.
    - **(ii) Komisyon, ayıklama ve TMY hazırlık çıktıları:** Bakanlık sistemi bunları kapsamayabilir.
    - **(iii) Ağdan salt okunur katalog tarama:** Bakanlık sisteminin okul içinde bu işi ne kadar yaptığı bilinmiyor.
    - **(iv) Bakanlık sistemi erişilemezse veya henüz yaygınlaşmadıysa geçici birincil araç** (il MEM'lerin yerel program dağıtması bu fiilî durumun emsali).
  - Veri aktarımı: Biçim bilinmediği için uygulama **açık ve belgelenmiş dışa aktarım** sunmalı (CSV/XLSX; ISBN, eser adı, yazar, yayınevi, yıl, demirbaş no, sınıflama no, konu). Uygun görülürse MARC21 de eklenebilir. Bakanlık formatı öğrenildiğinde eşleme eklenebilir.

#### (b) Mevzuatın gerektirdiği işlevler (madde atıflı)

1. **Katalog:** Bibliyografik kayıt; yazar, eser adı ve konuya göre alfabetik dizin ve tarama; bilgisayar ortamında kayıt (8/1-a, 11/1). Sınıflama numarası alanı, Dewey sabitlenmeden (11/1; eski hüküm 2001 Md. 11).
2. **Kaynak türleri ve bayraklar:** basılı, süreli (yalnız ciltli olan envantere girer), e-kaynak (4/1-ç; TMY 15/4). Bayraklar: "danışma", "piyasada mevcudu yok", "süreli yayın" (ödünç verilemez, 16/1). Alan veya bölüm konumu (4/1-a, 6/1).
3. **Edinim:** Bakanlık, satın alma, bağış, değişim (10/5). Bağış komisyon kararına bağlıdır (10/3).
4. **Üyelik:** yalnız öğrenci ve öğretmen (16/1, 17). Okuldan ayrılışta üyeliğin sonlandırılması ve açık ödünçlerle ilişik kesme (16/3, 18). Kullanıcı kartı basımı (20).
5. **Ödünç ve iade:** tarih kaydı (23/b), iade (23/c), 15 gün süre, öğrenciye 3 ve öğretmene 5 kitap sınırı (18), gecikme takibi (18, 8/1-f). **Ceza veya harç yok; uzatma ve rezervasyon düzenlenmemiş.**
6. **Kayıp ve hasar kaydı:** ortaöğretimde aynısını temin veya piyasa bedeli; kaydın düşülmesi ve yerine eser alınması (19). Tahsilat uygulama dışında kalır.
7. **Komisyon ve ayıklama:** Komisyon kararları; ayıklama tutanağı ve gerekçeleri (12/1-a…ç); devir (12/1; TMY 24/31); nadir eser listesi (12/2).
8. **TMY hazırlık çıktıları:** Kütüphane Defteri görünümü (9/1-ç); sayım ve iki turlu sayım (32); kayıttan düşme tutanağı taslağı (27, 28); yönetim hesabı cetveli taslağı (34).
9. **Raporlar:** yıl sonu gözden geçirme raporu (12/1; Kılavuz 2.4); çok okunan kitaplar listesi (15/1-ğ; Kılavuz "Ayın Kitapları"); koleksiyon sayısı ve 10.000 kitap eşiği (7/1).
10. **Dışa aktarım:** Bakanlık sistemine aktarım (bkz. a).

#### (c) Ağdan katalog taramanın mevzuatla ilişkisi

- **Açık bir "çevrim içi katalog" hükmü YOK.** Ancak aşağıdaki hükümler öğrencinin katalog ve elektronik kaynak kullanımını **teşvik ediyor**:
  - Otomasyon tanımı "paylaşım" ve "faydalanma"yı kapsıyor (4/1-h).
  - Kaynaklara "sağlıklı erişim" hedefi (8/1-a).
  - Elektronik kaynak kullanımının öğretilmesi (15/1-a), elektronik ortamda danışma hizmeti (14/1), teknolojik altyapı (6/2), erişime rehberlik (15/1-n, 8/1-ç).
  - Kılavuz: öğrencilere otomasyonun tanıtılması (satır 464), dijital okuryazarlık (1.3).
  - Basına göre Bakanlık sistemi de "aranan kitabın kütüphanede olup olmadığı" sorgusunu sunuyor.
- **ÇIKARIM:** Ağdan katalog tarama mevzuatın amacıyla uyumlu. Ama **MEB Bilgi ve Sistem Güvenliği Yönergesi** sınırlar koyuyor:
  - Okul ağına hizmet açmadan önce **okul veya ilçe bilişim sorumlusunun bilgisi ve izni** gerekir (Md. 11/7, 11/8).
  - Uygulama **Bakanlık demirbaşı bir bilgisayarda** çalışmalı; kişisel dizüstü, 11/8 ve 11/23 açısından risklidir.
  - Ağ tarafı **salt okunur** olmalı. "Kitap öner" gibi bir veri toplama formu **11/25 ile çelişebilir**. Kılavuz 4.2 bunu önerse de kişisel veri almayan veya yalnız masaüstünde çalışan bir yol seçilmeli.
  - Uygulama kendi Wi-Fi erişim noktasını kurmamalı ve DHCP/DNS sunmamalı (11/20, 11/21).
  - FATİH ve öğrenci cihazları ayrı sanal ağlarda (VLAN) olabilir, istemci yalıtımı da açık olabilir; ağ erişimi garanti değildir.
  - Bu hizmet internete değil, yalnız okul ağına açık olmalı. Md. 14/3 "Bakanlık dışı sunucuda web yayını" yasağı internet siteleri için. Ağ içi bir katalog bu kapsamda görünmüyor, ama yoruma açık.
- **Telif (FSEK):** Ağdan e-kitap veya PDF **dosyası dağıtılmamalı**; yalnız katalog kaydı ve konum gösterilmeli (Bilgi Güvenliği Yön. 11/3-f; Yönetmelik 14/1-b "imkanlar dahilinde"). Kapak görselleri internetten çekilmemeli; bu hem çevrimdışı ilkesine hem telife aykırı.

#### (d) KVKK: ödünç kaydının niteliği ve ağa açılmaması gereken veriler

- **Nitelik (ÇIKARIM):**
  - Ödünç geçmişi = **okuma alışkanlığı verisi**. KVKK Md. 6/1 listesinde doğrudan yok, ama bireysel okuma profili **felsefi inanç, din, mezhep, siyasi düşünce** hakkında çıkarım üretebilir.
  - 7499 sayılı Kanun ile değişen Md. 6/3'te (ikincil kaynağa göre RG 12.03.2024; RG sayısı teyit edilmedi) "hukuki yükümlülük" şartı **yok**. Bu yüzden veri özel nitelikli sayılacak biçimde işlenirse (konuya göre öğrenci profili, "din konulu okuma" analizi) kanunda açıkça öngörülme ya da açık rıza gerekir. Yönetmelik bir kanun değildir.
  - Güvenli yol: Ödünç kaydını yalnız Yönetmelik Md. 16/2 ve 23/b'nin gerektirdiği **hukuki yükümlülük** kapsamında (KVKK 5/2-ç) genel kişisel veri olarak işlemek; **bireysel konu profili çıkarmamak**.
  - Veriler çocuğa ait; ölçülülük ilkesi (KVKK Md. 4) sıkı uygulanmalı.
- **Saklama:** Yönetmelikte süre yok. Üyelik sonlanınca (16/3) amaç biter. Belli bir süre sonra kişiyle ödünç arasındaki bağ **anonimleştirilmeli**, agregat istatistik kalmalı (KVKK Md. 7). OYS'deki emsal: üyelik sonu + 2 yıl sonra anonimleştirme, bireysel geçmişe yalnız yetkili rol erişir, öğretmenler yalnız agregat görür (`docs/adr/0040-kutuphane-modulu.md:78-83`).
- **Kılavuz 7'nin ders başarısı analizi:** Not verisi uygulamaya **aktarılmamalı**. Böyle bir analiz yalnız sınıf veya okul düzeyinde agregat yapılabilir.
- **Ağa asla açılmaması gerekenler:**
  - Üye listesi; ad, soyad, sınıf, numara, T.C. kimlik no, telefon.
  - "Kimde" bilgisi ve bireysel ödünç geçmişi.
  - Gecikenler listesi (teşhir riski).
  - Kayıp ve hasar bedeli kayıtları.
  - Adlı "en çok okuyan öğrenciler" sıralaması. Kılavuz satır 485'teki ödül uygulaması yalnız masaüstünde, iç rapor olarak yapılmalı. Eski OYS gereksinimlerindeki "en çok okuyan öğrenci / okuma karnesi" maddesi (`requirements.md:677`) de bu kapsamda.
  - Komisyon ve personel bilgileri; yedek ve dışa aktarım uçları; yönetim ekranları.
- **Ağa açılabilecekler:** Bibliyografik veri, konum veya yer numarası, "rafta / ödünçte" durumu, eser bazlı çok okunanlar listesi (15/1-ğ). İade tarihinin gösterilmesi düşük riskli ama bir karar noktası.

---

### 7. Kullanıcıya sorulması önerilen karar noktaları

1. **Bakanlık sistemi:** Okula veya ilçeye bu sistemle ilgili bir resmî yazı gelmiş mi (adres, geçiş tarihi, aktarım biçimi)? Uygulama birincil araç mı olacak, yardımcı ve hazırlık aracı mı?
2. **Ağ erişimi izni:** Ağdan katalog tarama için okul veya ilçe bilişim sorumlusunun onayı alınabilir mi? Uygulama hangi bilgisayarda çalışacak (demirbaş mı)?
3. **Katalogda ödünç durumu:** Ağdaki katalogda "ödünçte" durumu gösterilsin mi? İade tarihi de gösterilsin mi?
4. **Diğer personel ve veli:** Ödünç verilecek mi? (Yönetmelik yalnız öğrenci ve öğretmeni sayıyor.)
5. **Kayıp ve hasar:** Ortaöğretim dışındaki kademeler için nasıl davranılacak? (Md. 19 yalnız ortaöğretim için.)
6. **Sınıflama:** Dewey mi kullanılacak, yoksa serbest yer numarası mı? (Bakanlık belirlemesi bulunamadı.)

---

### 8. Kaynak URL'leri

- RG 23.11.2024/32731: https://www.resmigazete.gov.tr/eskiler/2024/11/20241123-1.htm
- Lexpera konsolide metin: https://www.lexpera.com.tr/mevzuat/yonetmelikler/milli-egitim-bakanligi-okul-kutuphaneleri-yonetmeligi-1
- MEB haber 35539: https://www.meb.gov.tr/milli-egitim-bakanligi-okul-kutuphaneleri-yonetmeligi-resmi-gazetede-yayimlandi/haber/35539/tr
- DHGM icerik/1100: https://dhgm.meb.gov.tr/www/milli-egitim-bakanligi-okul-kutuphaneleri-yonetmeligi-resmi-gazete039de-yayimlandi/icerik/1100
- MEB haber 38724: https://meb.gov.tr/okullardaki-kutuphanelerin-verimliligini-artirmak-icin-calisma-baslatildi/haber/38724/tr
- DHGM kılavuz duyurusu: https://dhgm.meb.gov.tr/www/okul-kutuphaneleri-yonetmeligi-uygulama-kilavuzu-yayimlandi/icerik/1183/tr
- Z-Kütüphane (DHGM, 2019): https://dhgm.meb.gov.tr/www/genel-mudurlugumuz-ders-kitaplari-ve-yayimlar-daire-baskanligi-tarafindan-1447-z-kutuphanenin-kurulumu-tamamlanarak-1-milyon-ogrencinin-hizmetine-sunuldu/icerik/473
- Z-Kütüphane sitesi (erişilemedi): https://z-kutuphane.meb.gov.tr/
- Basın haberleri (ikincil):
  - https://www.haberaktuel.com/mebden-okul-kutuphanelerine-dijital-otomasyon-3474530
  - https://www.haberaktuel.com/meb-okul-kutuphanelerinde-dijital-donusumu-sagladi-3489159
  - https://mebpersonel.com/meb-personel/meb-duyurdu-okul-kutuphanelerinde-yeni-donem-h142939.html
  - https://egitimsitesi.net/haber/mebden-okullara-tarihi-kutuphane-devrimi-basili-ve-dijital-eserler-artik-tek-tikla-takip-edilecek-11464
- AA haberleri:
  - https://www.aa.com.tr/tr/egitim/mebe-bagli-okullardaki-kutuphanelerde-otomasyon-sistemi-kullanilacak/3402196
  - Eğitim takvimi (14.09.2026 başlangıç): https://www.aa.com.tr/tr/gundem/meb-2026-2027-egitim-ogretim-yili-takvimini-belirledi/3966122
- İl ve ilçe MEM yerel programları:
  - https://nigde.meb.gov.tr/www/okul-kutuphane-takip-programi-windows-7-8-10-11-ve-pardus-uyumlu/icerik/2495
  - https://ordu.meb.gov.tr/www/kutuphane-kitap-takip-programi/icerik/4974
  - https://gumushacikoy.meb.gov.tr/www/kutuphane-otomasyon-programi-amasyagumushacikoy/icerik/1274
- Standart Yönergesi 2006: https://dhgm.meb.gov.tr/dosyalar/Yonerge/2006_2590.pdf
- Bilgi ve Sistem Güvenliği Yönergesi: https://osmaniye.meb.gov.tr/meb_iys_dosyalar/2018_07/06102858_Bilgi_Ve_Sistem_Guvenligi_Yonergesi.pdf
- e-Okul Okuduğu Kitaplar: https://eokul.meb.gov.tr/Dokumanlar/OGR_OKUDUGU_KITAPLAR.pdf
- 2001 yönetmeliği (Md. 11, Dewey ve AAKK II): https://www.memurlar.net/haber/58323/mill-egitim-bakanligi-okul-kutuphaneleri-yonetmeligi.html

İncelenen yerel dosyalar (hiçbiri değiştirilmedi):
- `../okulapp/data/mevzuat/meb-okul-kutuphaneleri-yonetmeligi.md`
- `../okulapp/data/mevzuat/meb-okul-kutuphaneleri-yonetmeligi-uygulama-kilavuzu.md`
- `../okulapp/data/mevzuat/tasinir-mal-yonetmeligi-ilgili-maddeler.md`
- `../okulapp/data/mevzuat/ortaogretim-kurumlari-yonetmeligi.md`
- `../okulapp/data/mevzuat/lise-ve-dengi-okullar-denetim-rehberi.md`
- `../okulapp/data/mevzuat/meb-egitim-kurumlari-sosyal-etkinlikler-yonetmeligi-ekleri.md`
- `../okulapp/docs/adr/0040-kutuphane-modulu.md`
- `../okulapp/requirements.md`

<a id="r6"></a>

---

## R6. kelebek-sinav çıkarım şablonu

## Kelebek Sınav: OYS'den masaüstüne çıkarma şablonu (kütüphane projesi için)

Kaynak depo: `../kelebek-sinav`. Sürüm `2026.9.0-beta.12` (VERSION), 149 commit, 29.08.2026 ile 21.09.2026 arası.
Etiketler: **DOĞRULANDI** kodda veya belgede okundu demek, **ÇIKARIM** benim yorumum demek.
Gerçek veri dosyası açılmadı. `backend/apps/okul/tests/veri/*.xls` sentetik örneklerdir, onlar da açılmadı.

---

### 1. Depo iskeleti ve kütüphaneye aktarım listesi

```
kelebek-sinav/
├── CLAUDE.md · AGENTS.md · README.md · VERSION · LICENSE · .gitignore · .gitattributes
├── .github/workflows/kapilar.yml     her PR ve main push'ta scripts/gates.sh
├── .github/workflows/paketleme.yml   v* etiketi → Linux+Windows paketi, Release, R2
├── backend/
│   ├── config/  settings.py (TEK dosya) · urls.py (/api/v1 + SPA catch-all) · wsgi.py
│   ├── shared/  crypto.py · exceptions.py · models.py · pdf.py · letterhead.py · text.py
│   ├── apps/okul/     okul çekirdeği (aşağıda)
│   ├── apps/dersler/ · apps/sinav/   alan mantığı (kütüphanede katalog/ödünç karşılığı)
│   ├── templates/ documents/base.html · print/_design.css · <alan>/…
│   └── pyproject.toml · requirements(-dev).txt · conftest.py · manage.py
├── desktop/    kabuk: main, server, session_guard, lock, backup, backup_crypto, restore,
│               integrity, paths, window, version, errors, dialogs, logging_setup,
│               django_bootstrap + tests/
├── frontend/   React18+TS+Vite+Tailwind; ui/ (M3 kiti, 24 dosya), lib/, hooks/, modules/
├── packaging/  pyinstaller/ (spec, giris.py, rthook_ks.py, fonts.*) · windows/ (build.ps1,
│               dll_kapanisi.py, .iss, NOTLAR.md) · linux/ (build.sh, docker-build.sh,
│               kap-ici-test.sh, test-kurulum.sh, apt_dene.sh, control.tmpl, postinst/prerm,
│               .desktop, kur/kaldir.sh) · fontlar/ (DejaVu) · ikonlar/ · depo_sizintisi.py ·
│               veri_sizintisi.py · tests/
├── scripts/gates.sh
├── docker-compose.yml · docker/backend.Dockerfile
├── data/       pakete gömülü referans verisi (KS'de MEB çizelgeleri)
└── docs/       tasarim/ · kesif/ · degerlendirme/ · plan/ · mevzuat/ · sozluk.md · teknik-borc.md · kurulum.md
```

#### `shared/` dosyaları (DOĞRULANDI, modül docstring'leri)

- **`models.py`**: FK'sız `BaseModel`.
  - Alanlar `created/updated/deleted_at`, yöneticiler `objects`/`all_objects`.
  - `delete()` soft-delete yapar; `hard_delete()` ve `restore()` vardır.
  - OYS'deki `created_by` bilinçli olarak düşürüldü.
- **`exceptions.py`**: `{code,message,fields}` hata sözleşmesi, `ks_exception_handler`. Django `ValidationError`'ı 400'e çevirir.
- **`crypto.py`**: `EncryptedChar/TextField`, Argon2id, Fernet ve süreç-genel `_holder` anahtar tutucusu (`crypto.py:222`).
- **`pdf.py`**: WeasyPrint'in tek kapısı, `html_to_pdf` (`pdf.py:41`). Süreç kilidi (`pdf.py:37`) ve paylaşılan `FontConfiguration` burada.
- **`letterhead.py`**: resmî antet.
- **`text.py`**: `tr_upper`, `tr_lower`, `tr_title`.

#### `apps/okul/` dosyaları (DOĞRULANDI)

**Kurulum ve ayar**
- `services/setup.py`: SchoolConfig tekil kayıt (pk=1), `update_school_config`, `mark_setup_completed`, `get_letterhead_identity`.
- `views.SetupStatusView` (`views.py:85`): hem arayüzdeki kurulum kapısı hem masaüstü sağlık denetimi bu ucu kullanır.

**Ders yılı**
- `services/school_year.py`: yıl oluşturma ve tek-aktif kuralı (DB'de koşullu unique).
- `services/terms.py`: dönemler.
- **Yıl devri servisi yok.** DD'deki `year_rollover` ALMA sınıfındadır (tasarım:1144).

**Kişiler ve içe aktarma**
- `services/persons.py`: öğrenci ve personel CRUD, `register_student_forget_hook`.
- `services/imports.py`, `eokul.py`, `excel_*.py`, `normalize.py`: e-Okul xls/xlsx/pano içe aktarımı. Akış önizleme → commit, sha256 uyarısı.
- `services/templates.py`: indirilebilir xlsx şablonları.
- `services/photos.py`, `eokul_foto.py`: öğrenci fotoğrafı.
- `services/sections.py`, `departments.py`, `bell.py`: şube, zümre ve ders saati. Kütüphanede büyük ölçüde gereksiz.

**Güvenlik**
- `services/app_password.py`: parola kurma, açma, değiştirme, kaldırma, kurtarma; yarım kalan geçişi tamamlama.
- `lock_middleware.py`: kilitliyken 423 döner.
- `management/commands/app_password.py`: konsol kurtarma aracı.

**Yedek ve güncelleme**
- `services/backup_restore.py`: düz ve şifreli `.ksbak` geri yükleme çekirdeği. ORM kullanmaz.
- `services/live_restore.py` ve `restart_gate.py`: çalışan program içinden geri yükleme, ardından 503 `restart_required`.
- `services/encrypted_backup.py`: istek üzerine şifreli yedek indirme.
- `management/commands/restore_backup.py`: konsol geri yükleme aracı.
- `services/updates.py`: GitHub Release üzerinden güncelleme.

#### Kütüphane için aktarım tablosu (ÇIKARIM)

Kesif §8 kalıbı esas alındı (`docs/kesif/2026-08-29-kesif-raporlari.md:495-518`).

| Parça | Karar | Not |
|---|---|---|
| `desktop/` 15 modül + testler | **AYNEN** | Yalnız kimlik sabitleri değişir. İstisna: `server.py` ve `session_guard.py` LAN için **UYARLA** (§2) |
| `packaging/` tamamı, `veri_sizintisi.py`, `depo_sizintisi.py`, `scripts/gates.sh`, docker, workflows | **AYNEN + kimlik** | Yeni AppId GUID, AppMutex, `.XXbak` + MAGIC |
| `config/settings.py`, `config/urls.py` | **UYARLA** | env öneki, INSTALLED_APPS, LAN host ve güvenlik ayarları |
| `shared/` | **AYNEN** | `pdf.py`/`letterhead.py` yalnız PDF evrakı gerekiyorsa alınır |
| `apps/okul` çekirdeği (SchoolConfig + sihirbaz, SchoolYear/Term, Personnel, Student, ImportRun + e-Okul parser'ları, app_password, backup_restore, live_restore, restart_gate, updates) | **UYARLA** | Fotoğraf, zümre, zil ve vardiya alınmaz |
| FE: `ui/`, `lib/`, `hooks/`, `KurulumKapisi`, `modules/guvenlik`, `guncelleme`, `bakim`, `hakkinda`, `kilavuz` | **AYNEN / UYARLA** | Koruma testleri `format.test.ts` (tarih) ve `App.test.tsx` (M3 token) mutlaka birlikte gelir |
| `apps/dersler`, `apps/sinav`, `data/ders-cizelgeleri` | **ALMA** | Yerine OYS kütüphane modülü gelir |

---

### 2. Açılış sırası, süreç modeli ve LAN'da kırılan noktalar

#### Açılış sırası (DOĞRULANDI: `desktop/main.py:3-12`, `run` 166-214, `prepare_data` 127-140, `serve` 143-163)

1. `resolve_paths` → `paths.ensure()` → `configure_logging` → rthook uyarısı günlüğe → `get_app_version` → `enable_crash_log` (`main.py:183`) → `check_sync_hazard` (engellemez, yalnız uyarır).
2. `--geri-yukle` verilmişse `run_restore`'a sapar (`main.py:188-192`): pencere açılmaz, migrate ve bütünlük denetimi koşmaz.
3. `SingleInstanceLock.acquire()`:
   - Windows'ta `msvcrt.locking`, POSIX'te `flock`.
   - Ek olarak Windows mutex `KelebekSinav` açılır (`lock.py:29,97-111`). Bu yalnız Inno `AppMutex` denetimine sinyaldir.
4. `generate_session_token()` → `os.environ[KS_SESSION_TOKEN]`. Bu adım **ayarlar okunmadan önce** gelir (`main.py:198-201`).
5. `prepare_data`, sırasıyla:
   - `ensure_stamp_compatible` (surum.json)
   - `check_database_integrity` (`PRAGMA integrity_check(1)`)
   - `encrypt_legacy_backups` → `daily_backup` → `rotate_backups`
   - `prepare_django` → bekleyen göç varsa `pre_migrate_backup` → `run_migrations` → `write_version_stamp`
   - Bütünlük denetimi yedekten **önce** koşar: bozuk veriyle rotasyon sağlam eski yedekleri silmesin.
6. `serve`:
   - `build_wsgi_application` → `assert_session_guard_installed` (fail-closed; `django_bootstrap.py`).
   - `BackgroundServer.start` → `wait_until_ready` → `check_health` → `require_window_runtime` (WebView2 kayıt defteri denetimi) → `open_window` (bloklar).
   - Pencere kapanınca `finally: server.stop()`. **Sunucunun ömrü pencerenin ömrüne bağlıdır** (`main.py:150-163`).

#### waitress (DOĞRULANDI: `desktop/server.py`)

- Ayarlar: `DEFAULT_HOST = "127.0.0.1"` (:30), `DEFAULT_THREADS = 6` (:31), `port=0` ile boş portu işletim sistemi seçer (:104).
- Diğer parametreler: `ident=None`, `clear_untrusted_proxy_headers=True` (:101-108). Thread adı `ks-wsgi`, daemon.
- `base_url = f"http://{self._host}:{port}"` (:90-92). `wait_until_ready` doğrudan `create_connection((self._host, port))` yapar (:138).
- `check_health` (:172-206) iki istek atar:
  - belirteçsiz istek **403 dönmek zorunda**; dönmezse açılış durur (:195-199),
  - belirteçli istek 2xx dönmeli.
- `HEALTH_PATH = /api/v1/setup/status/` (:32).

#### SPA sunumu (DOĞRULANDI)

- WhiteNoise `WHITENOISE_ROOT = FRONTEND_DIR` ve `WHITENOISE_INDEX_FILE=True` (`settings.py:170-174`).
- `urls.py:39` catch-all `^(?!api/|static/).*$` → `index.html`. Derlenmemişse 503 ve Türkçe açıklama (:23-36).
- FE istemcisi göreli `/api/v1` kullanır (`frontend/src/lib/api.ts`, `API_BASE`).

#### Oturum belirteci (DOĞRULANDI: `desktop/session_guard.py`)

- Üretim: `secrets.token_urlsafe(32)` (:49-51). Pencere URL'si `/?t=<token>` (:54-56).
- Middleware kaynak sırası: çerez `ks_oturum` > `X-KS-Token` başlığı (`HTTP_X_KS_TOKEN`) > `?t=` (:88-99).
- Karşılaştırma `hmac.compare_digest` ile (:72); eşleşmezse 403 JSON döner.
- Belirteç sorgudan geldiyse `HttpOnly` + `SameSite=Strict` + `secure=False` çerez yazılır (:76-85).
- Env boşsa `MiddlewareNotUsed` (:63-66): testlerde ve geliştirmede hiç yüklenmez.
- Middleware `MIDDLEWARE.insert(0, …)` ile en başa, yalnız env doluyken eklenir (`settings.py:104-105`). Belirteç SPA dahil **her** isteği korur.

#### Host, CSRF ve CSP (DOĞRULANDI)

- `ALLOWED_HOSTS = ["127.0.0.1","localhost","backend"]` (`settings.py:54`).
- `SECRET_KEY` sabit geliştirme varsayılanı (:41-44). `DEBUG` varsayılanı False (:49).
- CSRF, CSP, SessionMiddleware ve CORS **yok**: `git grep` sonuçsuz. MIDDLEWARE: Security, WhiteNoise, Common, RestartRequired, AppLock (:82-95).
- DRF ayarı `AUTHENTICATION_CLASSES: []`, `AllowAny`, `UNAUTHENTICATED_USER: None` (:191-199).

#### LAN'a açılınca kırılan noktalar

Her maddede kanıt DOĞRULANDI, sonuç ÇIKARIM.

1. **Bağlanma adresi.** `DEFAULT_HOST=127.0.0.1` (`server.py:30`) ve test `test_server.py:53` bunu kilitler. `0.0.0.0` yapılırsa bu kez `base_url`, `wait_until_ready` ve `check_health` `0.0.0.0`'a bağlanmaya çalışır; Windows'ta bu bağlantı başarısız olur. Dinleme adresi ile yerel erişim adresi ayrılmalı.
2. **Rastgele port** (`port=0`, `server.py:104`). LAN kullanıcısına kalıcı bir adres gerekir. Sabit ama ayarlanabilir bir port ve çakışmada Türkçe hata gerekir.
3. **Belirteç her isteği 403'ler**, kök `/` ve statik dosyalar dahil. Başka bilgisayardaki tarayıcı açılışa özel belirteci bilemez. İki sunucu veya iki yüzey gerekir:
   - masaüstü tam API (belirteçli, yalnız loopback),
   - ayrı bir salt-okur katalog yüzeyi (izin listesi, belirteçsiz ya da sabit erişim kodlu).
4. **`ALLOWED_HOSTS`** (`settings.py:54`): LAN IP'si veya bilgisayar adıyla gelen istek `DisallowedHost` hatasıyla 400 alır. DHCP ile IP değişebildiği için tam IP listesi kırılgandır.
5. **Tam API LAN'a açılırsa felaket olur.** Her uç `AllowAny`. Yalnız okul ucu örnekleri:
   - `backups/encrypted/`: DB dışa aktarımı,
   - `backups/restore/`: DB'nin değiştirilmesi,
   - `security/*`: parola deneme ve kaldırma,
   - `updates/latest/installer/`: 250 MB indirmeyi tetikler,
   - `students/`, `personnel/`: kişisel veri.
   (`okul/urls.py`.) LAN tarafı ayrı bir URLconf veya middleware izin listesiyle **yalnız GET katalog uçlarını** görmeli.
6. **Anahtar ve kilit süreç-geneldir.** Kilit bir kez açılınca hem masaüstü hem LAN istekleri çözülmüş veriyi görür (`crypto.py:222`, `app_password.is_locked` :330). `lock_middleware` yalnız süreç durumuna bakar. Parolalı kurulumda kilitliyken katalog da 423 alır (`lock_middleware.py:37,70`). Katalog kişisel olmayan veri ise bu kapıdan muaf tutulmalı; ödünç veya üye bilgisi ise LAN'a hiç çıkmamalı.
7. **CSRF yok.** Loopback'te `SameSite=Strict` çerez korur; LAN'da yazma ucu açılırsa CSRF ve DNS rebinding riski doğar. LAN yüzeyi salt-okur olmalı, Host denetimi yapmalı ve katı CSP almalı.
8. **Güvenlik duvarı.** Inno `PrivilegesRequired=lowest` (`kelebek-sinav.iss:51`): kurucu güvenlik duvarı kuralı yazamaz. `%LOCALAPPDATA%\Programs` altındaki exe `0.0.0.0`'a bağlanınca Windows Defender izin istemi çıkar ve standart kullanıcı onaylayamaz. Seçenekler:
   - yönetici kurulumu ile `netsh advfirewall` kuralı,
   - ayrı "LAN'a aç" yardımcısı,
   - kullanıcıya belgeli el adımı.
   Pardus'ta ufw veya firewalld durumu da belgelenmeli.
9. **Sunucu pencereye bağlı** (`main.py:150-163`). Görevli pencereyi kapatınca katalog kapanır. Seçenekler: tepsi, küçültülmüş kip veya ayrı "yalnız sunucu" kipi. Bilgisayarın uyku ve güç ayarları da gündeme gelir.
10. **Eşzamanlılık.** 6 thread, SQLite WAL ve `transaction_mode=IMMEDIATE` (`settings.py:137-144`). Okuma yükü için yeterli. Ancak PDF kilidi süreç-geneldir (`pdf.py:37`); LAN'dan PDF üretimi açılırsa masaüstü evrakı sıraya girer. LAN'a PDF ucu verilmemeli.
11. **Günlük.** Erişim logu kasıtlı kapalı (`logging_setup.py`, `_ACCESS_LOGGERS`). LAN'da kimin ne sorguladığı izlenemez. Katalog kişisel değilse bu kabul edilebilir; arama dizgesi yine `PiiSafeFormatter` ile kırpılır.
12. **TLS yok** (`session_guard.py:83`). LAN'da düz HTTP akar. Katalogda parola ya da üye kimliği istenirse ağda açık metin gider.
13. **Settings docstring'i ve kurulum belgesi** "LAN/internet servisi sunmaz" der (`settings.py:3-7`, `docs/kurulum.md:83-84`). Yeni projede tasarım kararı açıkça ters çevrilmeli ve belgelenmeli.
14. **Güvenlik sayılan sabit `SECRET_KEY`** (`settings.py:41-44`) imza ve oturum kullanılmadığı için zararsızdı. LAN'da imzalı bir şey (erişim kodu çerezi vb.) kullanılırsa kurulum başına rastgele anahtar veri dizinine yazılmalı.

---

### 3. Güvenlik modeli (DOĞRULANDI)

**Katmanlar**
- Oturum belirteci (§2).
- Opsiyonel uygulama parolası.
- Fernet alan şifrelemesi.
- Şifreli yedek.
- Tasarım gerekçesi: tasarım §5 (`genel-tasarim.md:338-384`), CLAUDE.md §1.4.

**Parola** (`apps/okul/services/app_password.py`)
- Durum dosyası `guvenlik.json` veri dizinindedir, DB'de değil. İçinde KDF parametreleri, parola sarmalı, kurtarma sarmalı ve geçiş durumu (`TAMAM`/`SIFRELENIYOR`/`COZULUYOR`, :80-90) bulunur. DB'de yalnız anahtarın parmak izi durur.
- Parola en az 8 karakter (:92).
- Veri anahtarı (DEK) iki kez sarmalanır: parolayla ve kurtarma anahtarıyla. Kurtarma anahtarı 20 bayt, base32 ile 32 karakter, 8 dörtlü grup (:95-98).
- Yanlış denemede kalıcı kilitlenme yok; süreç içi artan gecikme `(0,0,1,2,4)` sn (:101, :311). Argon2id maliyeti yaklaşık 0,2 sn.
- Geçiş sırası: geçiş öncesi yedek → `guvenlik.json` → tek DB işlemi → damga. Her kesinti noktası yeniden okunabilir ve `resume` ile tamamlanabilir (docstring 25-39).

**Alan şifrelemesi** (`shared/crypto.py`)
- Parolasız kipte alanlar düz yazılır. Aynı alan sınıfı iki kipte de çalışır.
- Anahtar süreç ömrü boyunca bellekte kalır. Kilitleme programı kapatmak ya da `security/lock` ile olur.
- Şifreli alanda DB filtresi, LIKE ve sıralama çalışmaz; Python selector'ı gerekir (TB3).

**Kilit (423)**
- `AppLockMiddleware` parola kurulu ve kilit kapalıysa `/api/` isteklerini `423 locked` ile keser (`lock_middleware.py:70`).
- Muaf ön ekler (:37): `/api/v1/security/`, `/api/v1/setup/status/` (sağlık denetimi), `/api/v1/updates/`. SPA ve statik dosyalar serbesttir.
- `RestartRequiredMiddleware` kilitten önce durur: geri yükleme sonrası tüm API'yi 503 ile keser (`restart_gate.py:58`).

**Yedek şifreleme** (`desktop/backup_crypto.py`)
- DEK'ten HKDF ile X25519 özel anahtar türetilir. Açık anahtar `yedekleme.json`'dadır; bu sayede parola sorulmadan açılış yedeği alınabilir.
- İçerik geçici X25519 anahtarı + AES-256-GCM ile şifrelenir. MAGIC `b"KSBAK\x02"` (:24), HKDF info metinleri `KelebekSinav/backup/...` (:30-31). Kurtarma başlığı olarak `guvenlik.json` kopyası gömülür. Yazım atomiktir (`.tmp` → replace).

---

### 4. Yedek, geri yükleme, güncelleme, günlük ve kimlik sabitleri (DOĞRULANDI)

#### Yedek (`desktop/backup.py`)

- Dosya kopyalanmaz. Görüntü `Connection.backup()` ile RAM'de alınır; `serialize` yoksa (Pardus 21'deki SQLite 3.34) 0700 izinli geçici dizine yazılır (:60-84).
- **Kip seçimi** (:99-124, K9):
  - `yedekleme.json` yoksa düz yedek,
  - varsa şifreli yedek,
  - varsa ama bozuksa **yedek alınmaz**, düz kopya sızdırılmaz.
- Adlandırma ve saklama:
  - `gunluk-YYYY-MM-DD.ksbak` günde bir kez alınır ve aynı gün yeniden üretilmez.
  - `pre-migrate-<sürüm>-<tarih>.ksbak` yalnız bekleyen göç varsa alınır.
  - Rotasyon: günlükler 14 gün, pre-migrate son 5 adet. Desen dışı dosyalara dokunulmaz (:41-45, :225-264).
- **Medya yedeğe girmez** (TB11, K3 kararı). Eksik dosya indirilirken `media_missing` 404 döner.

#### Geri yükleme

- **Açılamayan program için:** `--geri-yukle` kipi (`desktop/restore.py`).
  - Kendi konsolunu açar (AllocConsole), çünkü paket `console=False` ile derlenir (`spec:261`).
  - Yedek listeden seçilir; parola ya da kurtarma anahtarı sorulur.
  - Eski DB `db-onceki-*` adıyla saklanır.
  - Inno "Yedekten Geri Yükle" Başlat kısayolunu kurar (`.iss:91`).
- **Çalışan program içinden:** `backups/restore/` → `live_restore` → restart gate.
- **Destek için:** `manage.py restore_backup`.

#### Güncelleme (`apps/okul/services/updates.py`)

- **indir.okulapp.org'dan değil, GitHub API'den okur**:
  - `api.github.com/repos/aalidemirci/kelebek-sinav/releases/latest`; ön-sürümde liste ucuna düşer (:27-30, :223-262).
  - URL izin listesi yalnız `github.com` ve `api.github.com` (:166).
- İndirme ve doğrulama:
  - Önbellek 15 dk. Kurucu en çok 250 MB.
  - SHA-256 önce varlığın `digest` alanından, yoksa `SHA256SUMS.txt`'ten alınır (:294-315).
  - Kurucu FileResponse ile kullanıcıya verilir (`views.py:787-804`). Uygulama kendisi kurmaz.
- Yalnız Windows'ta çalışır (`installer_supported` :265-272). Linux'ta paketle güncellemeye yönlendirir.
- Çevrimdışı ilkesiyle uzlaşma: denetim açılış zincirinde yoktur, yalnız arayüz isteğiyle koşar. Ağ yoksa Türkçe hata verir, banner sessizce yutar (docstring :7-8, README).
- **Çelişki:** `packaging/README.md:145-146` "MEB ağında GitHub sık sık engellidir" diyor. ÇIKARIM: uygulama içi denetim okul ağında büyük olasılıkla çalışmıyor. Kütüphanede sürüm bildirimi `indir.okulapp.org` altında bir manifest (`<uygulama>-release.json` + SHA256SUMS) üzerinden tasarlanmalı.

#### Günlük (`desktop/logging_setup.py`)

- `logs/uygulama.log`: 1 MB × 3 dönen dosya.
- `PiiSafeFormatter` sorgu dizesini `?…` ile kırpar.
- waitress ve django.server erişim logları susturulur. `django.request` politikası `django.setup()` ve `get_wsgi_application()` sonrasında **yeniden** uygulanır.
- `cokme.log`: `faulthandler`, tüm thread'ler, yalnız kod konumu; 500 KB'ta döner.

#### Çıkış kodları (`desktop/errors.py`)

| Kod | Anlamı |
|---|---|
| 0 | başarılı |
| 1 | beklenmeyen hata |
| 2 | program zaten açık |
| 3 | DB bozuk |
| 4 | şema çok yeni |
| 5 | göç hatası |
| 6 | sunucu açılamadı |
| 7 | WebView2 yok |
| 8 | PDF duman testi |
| 9 | geri yükleme |
| 10 | bağımlılık duman testi |

#### Kimlik sabitleri (hepsi yeniden üretilmeli)

- **env:** `KS_*` (19 ad):
  - `SESSION_TOKEN`, `APP_HOME`, `APP_VERSION`, `DATA_DIR`, `FRONTEND_DIR`, `BACKEND_DIR`,
  - `DEBUG`, `SECRET_KEY`, `CATALOG_DIR`, `COURSE_ALIAS_FILE`, `UPDATE_REPOSITORY`, `SECURITY_DIR`,
  - `BACKUP_DIR`, `MAX_UPLOAD_SIZE_MB`, `RTHOOK_UYARI`, `WITH_QT`, `DLL_DIR`, `SKIP_PIP`, `BUILD_IMAGE`.
- **Dizin adları:** `KelebekSinav` (Windows) ve `kelebek-sinav` (XDG) (`paths.py:24-25`). Aynı ad `updates.py:118,121`'de **ikinci kez** yazılı.
- **Belirteç:** çerez `ks_oturum`, başlık `X-KS-Token`.
- **Yedek:** `.ksbak` + `KSBAK\x02` + HKDF info metinleri.
- **Windows kabuğu:** AppUserModelID `KelebekSinav.Desktop` (`window.py:33`, `.iss:34`), AppMutex `KelebekSinav` (`lock.py:29`, `.iss:66`), Inno AppId `{96DC5FCC-…}` (`.iss:41`).
- **Diğer:** logger adı `kelebek_sinav`.
- **İki kopya:** `version_key` iki yerde tutulur (`desktop/version.py`, `updates.py`) ve **aynı kalmalıdır**.

---

### 5. Kalite kapıları ve yayın hattı (DOĞRULANDI)

**`scripts/gates.sh` sırası**
1. depo sızıntısı (KVKK). Host `git ls-files -z` üretir, çünkü imajda git yok.
2. pytest (`--cov=apps --cov=shared --cov-fail-under=75`, `pyproject.toml:45`) → ruff → ruff format → mypy strict.
3. `desktop` + `packaging` pytest **ayrı süreçte** (`-w /repo --no-cov`; günlük yapılandırması çakışmasın) → desktop ruff/mypy → packaging ruff/mypy.
4. FE tsc → eslint → prettier.
5. vitest + kapsam; eşikler 82/78/55 (`vitest.config.ts:32`).

**Kapı betiğinin güvenceleri**
- Her adım bir nöbetçi satırı (`KAPI_OK_<ad>`) basar ve betik bunu arar. Gerekçe: bu makinede `docker compose run` çıkış kodunu aralıklı yutuyor.
- vitest için JSON raporunda `success:true`, kapsam özet satırının **varlığı** ve "does not meet" satırının **yokluğu** aranır (:85-115).

**KVKK sızıntı kapıları**
- `depo_sizintisi.py`:
  - izlenen dosyalarda riskli uzantı ve dizin arar, TCKN sağlama kuralına uyan 11 haneli sayıları bulur,
  - bulguyu yalnız yol ve satırla basar, değeri basmaz,
  - muafiyetler dosya adıyla tutulur, joker kullanılmaz.
- `veri_sizintisi.py`:
  - paket ağacını yol bazında denetler,
  - yasak uzantılar `.sqlite/.sqlite3/.xls/.xlsx/.ksbak` (:15),
  - yasak dizinler `backend/data` ve `data/media`,
  - yasak dosyalar `guvenlik.json`, `yedekleme.json`, `surum.json`.
  - İki platform derlemesinde de koşar (`build.ps1:129`).

**CI iş akışları**
- `kapilar.yml`: her PR ve main push'ta gates.sh'ı olduğu gibi çağırır.
- `paketleme.yml`, işler sırasıyla:
  - `arayuz` (node 24),
  - `linux` (`python:3.12-bullseye`),
  - `linux-kurulum` (debian 11 ve 12 temiz kurulum, `--autotest`, `--pdf-duman`),
  - `windows` (msys2 DLL kapanışı, PyInstaller, `--bagimlilik-duman`, `--pdf-duman`, `--autotest`, portable zip, Inno),
  - `yayin` (yalnız v* etiketinde).
- Etiket ile VERSION eşleşme kapısı vardır.

**Sürüm ve yayın hattı**
- CalVer `YYYY.M.N[-beta.N]`. `v*` etiketi `SHA256SUMS.txt` üretir, `gh release create` çalıştırır (ön-sürümse `--prerelease`) ve R2'ye yükler: `okulapp-indirme/<uygulama>/`, `SHA256SUMS-<sürüm>.txt`.
- **Secret'lar tanımlı değil** (19.09.2026). R2 adımı uyarı basıp atlanıyor, yükleme geliştirme makinesinden wrangler OAuth ile elle yapılıyor (`packaging/README.md:160-181`).
- Elle kalan son iş: okulapp.org deposunda `src/data/ks-release.json`. Bu adım okulapp.org "Ortak çalışma düzeni" kurallarına tabidir (CLAUDE.md:661-667).

---

### 6. Faz planı şablonu (DOĞRULANDI: tasarım §12, `genel-tasarim.md:1149-1169`)

| Faz | İçerik | Kapı |
|---|---|---|
| F0 İskelet | DD'den türetme, kimlik sabitlerinin toplu değişimi, boş Django+FE, PDF bağımlılığı **F0'da** | Windows exe açılır/kapanır, çıkış kodu testleri, `--pdf-duman`, gates yeşil |
| F1 Çekirdek veri | SchoolConfig + sihirbaz + sağlık ucu, SchoolYear, Personnel, Student, **şifreleme doğuştan**, import boru hattı, referans veri tohumu | dry-run/commit parite, tohum idempotentliği, TR sütun eşleme, şifreli kipte ad selector testleri |
| F2-F7 Alan | Motor → akış → evrak → alt modüller | Her faz kendi değişmez-kural testleri. Eklerde "mevcut testler DEĞİŞMEDEN yeşil" şartı |
| F8 Bakım | Günlük yedek + rotasyon (iki kip), KVKK saklama/anonimleştirme (elle tetik), surum.json, updates + UpdateBanner | Eski exe yeni DB'yi açmaz; anonimleştirme sonrası yeniden basım kırılmaz |
| F9 Paketleme | PyInstaller onedir + Inno (yeni GUID, WebView2 gömülü) + .deb (bullseye), kap-ici-test, veri_sizintisi ×2 | Temiz Win11 ve Pardus 21'de kurulum → sihirbaz → içe aktarma → çekirdek akış → PDF uçtan uca |

Ayrıca her sapma "F<n> eki (tarih)" satırıyla aynı tabloya işlenir. Faz, kapısı geçilmeden kapanmaz (CLAUDE.md:668).

**Kütüphane için (ÇIKARIM):**
- F0'a "loopback + LAN iki yüzey iskeleti" eklenmeli.
- Ayrı bir **"F-LAN" fazı** açılmalı. Kapıları:
  - LAN'dan yalnız izin listesindeki GET uçları 200 döner, geri kalan her uç (yedek, güvenlik, kişi) 403/404 döner (test),
  - Host başlığı denetimi,
  - güvenlik duvarı kuralı prova edilir,
  - pencere kapalıyken sunucu kipi,
  - gerçek ikinci bilgisayardan tarayıcı testi.

---

### 7. Dersler ve tuzaklar: kütüphanede baştan önlenecekler

Kaynaklar DOĞRULANDI: CLAUDE.md §2, teknik-borc.md, degerlendirme §3/§6, kesif §7.

1. **hiddenimports (K7).** Backend pakete kaynak ağaç olarak girer. Her yeni bağımlılık üç yere elle eklenir: spec `hiddenimports`, `test_spec_kapsami.DAGITIM_IMPORT_ESLEME`, `giris.RUNTIME_MODULES`. `--bagimlilik-duman`, `xlrd` eklenince ortaya çıkan boşluktan sonra geldi (CLAUDE.md:48-54).
2. **PDF motoru eşzamanlılığı.** Paralel WeasyPrint çağrıları Pango'da yerel çöküş yaptı. Çözüm tek kapı ve kilit (`shared/pdf.py`) artı `cokme.log`. Ayrı süreçte PDF üretimi ertelendi (TB15). LAN işin içine girince bu kilit daha da kritik.
3. **Fontconfig çift düzeltme** (rthook + build.ps1 adım 4b). DOCTYPE'lı fonts.conf sessizce reddedilir, evrak bozuk Türkçeyle basılır.
4. **Parolasız kipte yedek atlanıyordu.** DD şablonundaki bu dal KS'de K9 ile düzeltildi. `backup.py` KS sürümünden alınmalı, DD'den değil.
5. **Bullseye'ın desteği bitti** (TB13). Güvenlik deposu tarihli arşive sabitlendi. Pardus 21 desteğinin ne zaman bırakılacağı kullanıcı kararıdır; kütüphane başlarken sorulmalı.
6. **Şifreli alan sorguları** (TB3). Ad üzerinden arama, sıralama ve teklik Python'da yapılır. Kütüphanede kitap adı gibi kişisel olmayan alanlar şifrelenmemeli; yalnız üye adı ve iletişim şifrelenmeli. Aksi hâlde katalog araması ölür.
7. **TR sıralama.** SQLite `order_by` BINARY'dir; kullanıcıya gösterilen her liste `*_sorted()` selector'ıyla verilir (CLAUDE.md:169-172). Katalogda kritik.
8. **Soft-delete tuzakları.** İleri FK ve `select_related` silinmiş kaydı geri getirir; `PROTECT` ve `SET_NULL` hiç tetiklenmez. Canlılık tek bir yardımcıdan sorulmalı (CLAUDE.md:173-177, :252-254).
9. **Tarih ve Türkçe büyük harf.** `toISOString().slice(0,10)` yasak (`todayIso()`), `text-transform:uppercase` yasak, çıplak `.upper()` yasak. Koruma testleri F0'da gelir.
10. **DRF tuzakları.** Tek alanlı UniqueConstraint alan düzeyinde validator türetir. `{# #}` yorumu tek satırlıktır, yoksa şablon çıktısına sızar. `?format=` DRF'e ayrılmış olduğu için `?kind=` kullanılır.
11. **İç kod sızıntısı.** Kullanıcı metninde K5, R10, `id=` gibi kodlar görünüyordu; bağlayıcı `docs/sozluk.md` baştan kurulmalı. Uyarılarda öğrenci adı yerine okul no/üye no yazılmalı.
12. **Sayfa bütçesi testleri gerçek uzunlukta verilerle koşmalı.** Kısa fixture'lar bütçe testini yanlış yeşil verdi.
13. **CI kapısı sonradan eklendi** (18.09). Kütüphanede kapilar.yml F0'da hazır olmalı.
14. **Ön-sürüm sıralaması** `beta.10 < beta.9` hatası verdi. İki `version_key` kopyası aynı tutulmalı ya da teke indirilmeli.
15. **Kimlik kalıntıları.** Kurtarma anahtarı çıktısında "DİSİPLİN DEFTERİ" başlığı kalmıştı (degerlendirme:193). `git grep` ile toplu tarama F0 kapısına eklenmeli.
16. **Joker muafiyet yasağı.** Sentetik fixture muafiyeti dosya adıyla yazılır. TCKN örneği test kaynağına yazılmaz, çalışma anında üretilir (CLAUDE.md:210-215).
17. **Yayın işi dışa açık bir işlemdir.** Etiket, push ve site kartı otonom oturumda yapılamadı (degerlendirme:392, :491-503). Planda kullanıcı adımı olarak gösterilmeli.
18. **`services.py` 2.800 satıra şişti** (TB12). Kütüphanede servisler baştan alt modüllere bölünmeli.
19. **Güncelleme GitHub'a bağımlı, MEB ağında GitHub engelli** (§4). Baştan R2 manifesti tasarlanmalı.
20. **Docker Desktop bayat soket sorunu** bu makinede kapıları durdurdu (degerlendirme:366-369). Ortam notu proje hafızasındadır.

---

### 8. Kelebek'te LAN, `0.0.0.0`, uzak erişim veya tahta var mı?

`git grep` ile aranan terimler: LAN, `0.0.0.0`, yerel ağ, uzak erişim, akıllı/etkileşimli tahta, başka bilgisayar, ağ üzerinden, çok kullanıcı, ağ servisi, 127.0.0.1.

**Özellik yok.** Tersine, loopback'e kapalılık bir **mimari değişmez** olarak yazılmış (DOĞRULANDI):

- `settings.py:3-7`: "bu program LAN/internet servisi sunmaz, tek kullanıcı tek bilgisayarda çalıştırır"; `:38`: "ağ üzerinden erişilmez".
- `server.py:8`: "`host=127.0.0.1`: LAN'dan erişilemez". Test `test_server.py:53` bunu kilitler.
- `docs/kurulum.md:83-84`: "hiçbir port dışarıya açılmaz".
- `docker-compose.yml:4-5`: "masaüstü uygulama ağ servisi sunmaz"; compose port açmaz.
- CLAUDE.md:25-28: "Tek kullanıcılı, girişsiz, çevrimdışı masaüstü"; "Auth yok / CSRF yok" bulgu sayılmaz.
- Kesif §5 (`kesif-raporlari.md:803`): OYS'nin "Docker/LAN yapılandırması" **ALINMAMALI** listesinde. Bu, OYS'den ağ katmanını taşımama kararıdır.

Ayrı bir kullanıcı "LAN reddi" kararı veya ADR **bulunmadı**. Karar ürün tanımının ("tek kullanıcılı, girişsiz") doğal sonucu olarak yerleşmiş.

İlgisiz eşleşmeler:
- "akıllı tahta" salon mobilyası türüdür (`sinav/models.py:35`, `layout.py:16`).
- `window.py:42` içindeki `0.0.0.0` WebView2 sürüm damgasıdır.
- FE yorumlarındaki "LAN SPA" ifadeleri (`useTheme.ts:13`, `queryClient.ts:7`) OYS kalıntısıdır.
- Dockerfile'daki `runserver 0.0.0.0:8000` yalnız geliştirme kabı içindir.

**Kütüphane için sonuç (ÇIKARIM).** LAN katalog isteği, kardeş projelerdeki bu değişmezi bilinçli olarak kırar. Kullanıcıya sorulacak karar noktaları:

1. **LAN'da hangi veri görünecek?** Yalnız katalog ve raf/mevcut durumu mu, yoksa ödünç ya da üye bilgisi de mi? KVKK açısından önerim: kişisel veri LAN'a hiç çıkmasın.
2. **Erişim kodu mu, açık erişim mi?** LAN katalog yüzeyi erişim kodsuz mu olsun, yoksa sabit bir "kurum kodu" mu istesin?
3. **Sunucu hangi bilgisayarda, ne zaman açık?** Pencere kapanınca sunucu dursun mu, tepside mi çalışsın? Bilgisayarın açık kalma düzeni ne olacak?
4. **Yönetici kurulumu kabul edilebilir mi?** Güvenlik duvarı kuralı için gerekiyor. Alternatif, kılavuzla elle kural eklemek.
5. **Port ve adres.** Sabit port ve bilgisayar adıyla adres (`http://<bilgisayar-adı>:<port>`) yeterli mi?
6. **Pardus 21 desteği sürecek mi?** TB13 nedeniyle bullseye tabanı risk taşıyor.
7. **Güncelleme kaynağı:** GitHub mı, indir.okulapp.org manifesti mi?

<a id="r7"></a>

---

## R7. disiplin-defteri karşılaştırması, okulapp.org yayın alanı, kimlik adlandırma

## Bulgu raporu: masaüstü ve paketleme temeli, okulapp.org yayın alanı ve kimlik adlandırması

### 0. Kısa özet

- **Temel olarak kelebek-sinav (KS) alınmalı.** KS, disiplin-defteri'nden (DD) türetildi. DOĞRULANDI: `git -C kelebek-sinav log`, commit `50699ec` "F0 — iskelet fazı (DD şablonundan türetme)". Sonrasında masaüstü ve paket katmanında 10'dan fazla gerçek kusuru kapattı. DD'de 5 commit var ve sürümü `2026.7.0-beta.1`. KS'de 149 commit var ve sürümü `2026.9.0-beta.12`; sahada da kullanılıyor.
- DD'den ayrıca alınmaya değer olanlar yalnız alan katmanında: iş günü ve tatil takvimi (`working_days.py`, `calendar.py`) ile yıl devri (`year_rollover.py`). Masaüstü ve paket katmanında DD'nin KS'den üstün olduğu bir dosya yok.
- **Yerel ağdan (LAN) katalog, mevcut güvenlik mimarisiyle doğrudan çelişiyor.** Sunucu sabit olarak 127.0.0.1'e bağlanıyor, portu rastgele seçiyor, belirteçsiz her isteği 403 ile reddediyor, `ALLOWED_HOSTS` sabit ve `SECRET_KEY` sabit bir varsayılan. LAN için ikinci, dar kapsamlı ve salt okunur bir sunucu yüzeyi tasarlanmalı (bkz. §A9).
- okulapp.org'da kütüphane için yeni bir alan sahipliği satırı gerekiyor. İlk ekleme commit'i, KS öncülüne (`44de4d2`) uyarak ortak dosyalara (BaseLayout, global.css, CLAUDE.md) bir kez dokunur.
- Önerilen kısaltma **`KT`**: `KT_*`, `kt_oturum`, `X-KT-Token`, `.ktbak`, `kt-release.json`, palet `kt`.

---

### A. Masaüstü ve paketleme karşılaştırması

#### A1. desktop/ klasörü, dosya dosya

İki klasördeki 15 ortak dosya diff ile karşılaştırıldı. `restore.py` yalnız KS'de var.

| Dosya | Fark | Sonuç |
|---|---|---|
| `window.py` | Yalnız adlar değişmiş (8 satır). WebView2 kayıt defteri denetimi ve MSHTML'e düşüşün engellenmesi iki depoda aynı. DOĞRULANDI: `kelebek-sinav/desktop/window.py:37-100`. | Ad değişikliğiyle alınır |
| `server.py`, `session_guard.py`, `paths.py`, `dialogs.py`, `backup_crypto.py` | Yalnız adlar ve sabitler değişmiş | Ad değişikliğiyle alınır. `server.py` ve `session_guard.py` LAN için değişecek (§A9) |
| `lock.py` | KS, dosya kilidine ek olarak `CreateMutexW("KelebekSinav")` ekledi. DOĞRULANDI: `lock.py:29`, `:96-110`. DD'nin Inno betiğindeki `AppMutex=DisiplinDefteriKurulum` (`disiplin-defteri.iss:63`) uygulamada hiç üretilmiyor; yani kurucunun "program açık mı" denetimi DD'de ölü. KS'de düzeltildi (`kelebek-sinav.iss:66`). | KS alınır |
| `backup.py` | Üç iyileştirme var. (1) K9: parolasız kipte de her gün yedek alınıyor. DD bu kipte yedeği hiç almıyordu (`backup.py:1-15`). (2) Pardus 21/bullseye'da SQLite 3.34'te `Connection.serialize` yok; geçici dizine yedekleme yoluna düşülüyor (`backup.py:64`). Bu kusur F9'da `--autotest` çöküşüyle bulundu. (3) Parola sonradan konursa eski düz yedekler şifreleniyor. | KS alınır |
| `restore.py` (yalnız KS, 308 satır) | `--geri-yukle` kipi. Kendi konsol penceresini açar (AllocConsole). Parolayı ekrana yansıtmadan msvcrt ile okur; `getpass` tuzağı açıklanmış (`restore.py:242-275`). Inno Başlat menüsüne "Yedekten Geri Yükle" kısayolu koyar. | KS alınır |
| `integrity.py`, `django_bootstrap.py` | Hata ipuçları elle `db.sqlite3` kopyalatmak yerine `--geri-yukle`ye yönlendiriyor. Elle kopyalama şifreli yedekte zaten çalışmıyordu (`integrity.py:26-40`). | KS alınır |
| `logging_setup.py` | `enable_crash_log`: `faulthandler` ile C katmanı çöküşleri `logs/cokme.log`a yazılıyor; KVKK gereği yalnız kod konumu tutuluyor (`logging_setup.py:93-130`, çağrı `main.py:183`). | KS alınır |
| `version.py` | `_pre_key`: ön sürümler doğal sıralanıyor (beta.10 > beta.9) (`version.py:60`). Aynı fonksiyonun ikinci kopyası `okul/services/updates.py`de; ikisi aynı kalmalı. | KS alınır |
| `errors.py` | Yeni çıkış kodları: 9 (geri yükleme), 10 (`--bagimlilik-duman`) | KS alınır |
| `main.py` | `--geri-yukle`, `--parola`, `--kurtarma-anahtari`, `--evet` bayrakları ve crash log çağrısı | KS alınır |
| `tests/` | KS'de ek olarak `test_restore.py` var | KS alınır |

#### A2. backend/shared/ klasörü

| Modül | Durum |
|---|---|
| `pdf.py` (yalnız KS) | WeasyPrint'e tek kapıdan gidiliyor: süreç genelinde kilit ve paylaşılan `FontConfiguration` (`shared/pdf.py:37-51`). Koruma testi başka bir `write_pdf` çağrısına izin vermiyor (`shared/tests/test_pdf.py`). Dayanak 19.09.2026 çöküşü: eşzamanlı basımda Pango `libpangoft2` erişim ihlali verdi, 0xC0000374 hatası görüldü (commit `62cffbe`). **LAN'da eşzamanlı istek artacağı için bu modül zorunlu.** |
| `exceptions.py` | KS'nin `ks_exception_handler`'ı servis katmanındaki Django `ValidationError`'ı 400'e çeviriyor. DD'de bu durum 500 dönüyordu ("A5" vakası). Açıklayıcı alan mesajları da `message`e taşınıyor. **KS alınır** |
| `text.py` | KS'de `tr_upper`, `tr_lower`, `tr_title` var. DD'de yalnız `mask_tckn` var. **Kütüphane TCKN toplamamalı, `mask_tckn` gereksiz. KS alınır.** Katalog aramasında Türkçe normalizasyon için `tr_lower` gerekli. |
| `letterhead.py` | KS'de `tr_upper` ile büyütülmüş ilçe adı ve resmî yazışmaya uygun `unit_line` var; DD'de ölü `OYS_*` geri düşüşleri duruyor. **KS alınır** |
| `crypto.py` | Yalnız açıklama metni ve parmak izi etiketi farklı (`ks-anahtar-parmak-izi`). DOĞRULANDI: şifreli alanlarda veritabanı tarafında filtre, LIKE ve sıralama çalışmıyor (`kelebek-sinav/backend/shared/crypto.py:29-37`). **Katalog alanları asla şifrelenmemeli**, yoksa LAN araması çalışmaz. |
| `working_days.py` (yalnız DD) | İş günü aritmetiği. İade tarihi tatile denk gelirse ötelenecekse gerekir. ÇIKARIM: bu bir kullanıcı kararı. |

#### A3. packaging/ klasörü

| Parça | KS iyileştirmesi | Dayanak |
|---|---|---|
| `giris.py` | `--bagimlilik-duman` eklendi: `RUNTIME_MODULES` listesindeki modüller paket içinde gerçekten import ediliyor. `--pdf-duman` kipine JPEG gömme denetimi eklendi. | giris.py:11-20, 314. Bağımlılık üç yere yazılıyor: spec, `test_spec_kapsami.py::DAGITIM_IMPORT_ESLEME` ve `RUNTIME_MODULES` (KS CLAUDE.md §2) |
| `.spec` | `clr` ve `pythonnet` açıkça eklendi (W9 sigortası), `xlrd`, `PIL.JpegImagePlugin`/`PngImagePlugin` eklendi; hiç bağlanmamış `filetype` ve `platformdirs` atıldı | spec diff |
| `build.ps1` | Ara dizinler platforma özel (`paket-win`, `_build-win`), bağımlılık dumanı önce koşuyor, WebView2 kurucusu yerelde de indiriliyor, gömülü veri dosyasının varlığı denetleniyor | build.ps1 diff |
| `.iss` | Yeni AppId GUID, AppMutex düzeltmesi, geri yükleme kısayolu. WebView2 kurucusu yoksa derleme `#pragma warning` basıyor; önceden sessizce onsuz çıkıyordu. | iss diff |
| `linux/apt_dene.sh` (yalnız KS) | apt 404 hatasında listeleri silip 3 kez yeniden deneme; `bullseye-security` kaynağı `snapshot.debian.org/.../20260903T000000Z` arşivine sabitlendi | apt_dene.sh:28, 50; commit `31bbfa2` |
| `linux/docker-build.sh` | `MSYS_NO_PATHCONV=1` (Git Bash'ten derleme) | diff |
| `depo_sizintisi.py` (yalnız KS) | Depoda KVKK kapısı: izlenen dosyalarda TCKN sağlaması ve veri biçimi arıyor; bulguyu yalnız konumuyla raporluyor | KS CLAUDE.md §1.6 |
| `tests/` | `test_apt_dene`, `test_depo_sizintisi`, `test_spec_kapsami` | — |
| `dll_kapanisi.py` | Birebir aynı | diff 0 satır |
| CI | KS'de `kapilar.yml` var (her PR'da gates.sh koşuyor). `paketleme.yml` PR süzgeci `backend/**` ve `desktop/**` yollarını da kapsıyor (`paketleme.yml:26-34`); R2 yüklemesi de burada | — |

#### A4. DD'de olup KS'de olmayan değerli şeyler

- `backend/apps/okul/services/calendar.py` (152 satır): `Holiday` tohumu. Dini bayramlar gömülü statik tablodan geliyor; Diyanet'in yayınladığı yıllar "teyitli", sonrası "tahmini" bayrağı taşıyor. `holidays` paketi reddedilmiş (DD tasarım §7). Ödünç iade takvimi için gerekebilir.
- `year_rollover.py` (325 satır): yıl devri sihirbazı. Kütüphanede öğrencilerin sınıf atlaması ve mezunların pasifleşmesi için yararlı. ÇIKARIM.
- `shared/working_days.py` ile `test_working_days.py` ve `test_letterhead.py`.
- `SECURITY.md`: herkese açık depo için şablon olabilir.
- Almaya değmeyenler: `website/` ve `pages.yml` (GitHub Pages yönlendirmesi, artık gereksiz), `excel_veli.py` (veli verisi kütüphaneye gerekmez; KVKK gereği veri en aza indirilmeli).

#### A5. Karar ve alınacak dosyalar

**KS'den ad değişikliğiyle kopyalanacaklar:**
- `desktop/` klasörünün tamamı (restore.py dahil) ve `desktop/tests/`
- `backend/shared/` içinden `pdf.py`, `exceptions.py`, `text.py`, `letterhead.py`, `crypto.py`, `models.py`
- `backend/apps/okul/`: `lock_middleware.py`, `restart_gate.py`; `services/` altında `app_password.py`, `encrypted_backup.py`, `backup_restore.py`, `live_restore.py`, `updates.py`, `school_year.py`, `setup.py`
- `packaging/` klasörünün tamamı (apt_dene, depo_sizintisi, üç test dahil)
- `.github/workflows/kapilar.yml`, `paketleme.yml`, `scripts/gates.sh`, `docker/`

**DD'den ek olarak:** `shared/working_days.py`, `okul/services/calendar.py`, `okul/services/year_rollover.py`.

KS'de kimlik kalıntısına sıfır tolerans kuralı var (KS CLAUDE.md:267-269). Kütüphanede de F0 kapısına şu testler eklenmeli:
- `KS_`, `ksbak`, `kelebek`, `DD_`, `ddbak` kalıntısı taraması
- veri dizini adının DD ve KS ile çakışmadığının testi (`paths.py:21-23` yorumundaki kalıp)

#### A6. Windows tuzakları

**W1-W9 durumu.** DOĞRULANDI (KS `NOTLAR.md` başlığı): KS'nin 29.08.2026 CI koşusu W1 ve W5'i doğrudan, W2-W4 ile W6-W8'i dolaylı doğruladı. W9 (pythonnet ile WebView2 zinciri) 30.08.2026'da Windows 11'de gerçek pencereyle doğrulandı.

**Hâlâ açık olanlar:**
- DD teknik borç D6 ve NOTLAR çek-listesinin 5-8. maddeleri: WebView2'siz makinede açılış (çıkış kodu 7), ikinci kopyanın açılması, antivirüs taraması. ÇIKARIM: KS belgelerinde bunların doğrulandığına dair kayıt yok.
- DD D8 (paketli pencerede dosya indirme) kodla kapatıldı (`ALLOW_DOWNLOADS`, `window.py:266-270`).

**Tuzaklar:**
1. **WebView2.** Kurucu kayıt defteri denetimi yapıyor ve Inno [Run] adımında `/silent /install` ile kuruyor (`kelebek-sinav.iss:98-104`, [Code]). Gömülü dosya 1.78 MB; bu Evergreen önyükleyicisi demek (DOĞRULANDI: dosya boyutu). ÇIKARIM: önyükleyici internet ister; ağı kısıtlı ya da çevrimdışı okul bilgisayarında kurulum başarısız olur. Tasarımda sözü geçen Fixed-Version "full zip" ya da Standalone kurucu hiçbir projede üretilmiyor (DD `NOTLAR.md` §4). Program yine de beyaz ekran vermiyor; Türkçe yönlendirme gösterip 7 koduyla çıkıyor.
2. **SmartScreen ve imzasız exe.** USB ya da yerel ağla dağıtımda Mark-of-the-Web oluşmuyor (DD tasarım §5.1:239). ÇIKARIM: `indir.okulapp.org`dan tarayıcıyla indirilen dosyada MotW oluşur ve SmartScreen uyarısı çıkar; KS `docs/kurulum.md:34` bunu belgeliyor. İmzalama v2'ye bırakılmış (Azure Trusted Signing veya SignPath).
3. **Antivirüs.** onedir seçimi yanlış pozitifi azaltıyor; fiilî tarama kaydı yok.
4. **PyInstaller.**
   - `console=False` olduğundan `sys.stdout` None; PowerShell GUI exe'yi beklemiyor, bu yüzden `Start-Process -Wait` kullanılıyor (NOTLAR §2).
   - K7 borcu: backend pakete kaynak ağaç olarak giriyor, her yeni bağımlılık `hiddenimports`a elle yazılmalı (DD `teknik-borc.md` K7).
   - Kurucu düzeltmeler: PS1 dosyasında BOM gerekliliği; MSYS2'nin python'u setup-python'ı gölgeliyor, bu yüzden mingw PATH'in **sonuna** ekleniyor (`paketleme.yml:219-221`).
5. **GTK ve WeasyPrint DLL'leri.**
   - DLL kapanışı MSYS2 ve `ntldd` ile hesaplanıyor; `WEASYPRINT_DLL_DIRECTORIES` rthook'ta ayarlanıyor.
   - Paket içi `fonts.conf` build.ps1 adım 4b'de yazılıyor; yalnız gömülü DejaVu kullanılıyor.
   - Windows'ta fontconfig önbelleği hiç yazılmıyor (KS TB15).
   - Tanı düzeneğinde `SetDllDirectoryW(_internal)` şart; yoksa PATH'teki GTK3-Runtime DLL'leri karışıyor (KS CLAUDE.md §2).
   - Aynı süreçte eşzamanlı basım çöküşe yol açıyor; çözüm `shared/pdf.py` kilidi. PDF'i ayrı süreçte basma ertelendi (TB15).
6. **Veri dizini.** Veri `%LOCALAPPDATA%` altında, Roaming ya da OneDrive'da değil. Eşitlenen klasör belirtileri günlüğe uyarı olarak yazılıyor (`paths.py:36-48`, `139-152`).
7. **Canlı geri yükleme.** Windows'ta açık SQLite bağlantısı varken `os.replace` başarısız oluyor; bu yüzden önce bağlantılar kapatılıyor (`live_restore.py` açıklaması).

#### A7. Linux .deb durumu

Doğrulananlar:
- Derleme `python:3.12-bullseye` kabında yapılıyor (glibc 2.31, Pardus 21 tabanı).
- Temiz `debian:11` ve `debian:12` kaplarında kurulum provası ve `--autotest` yeşil.
- `.deb` yaklaşık 155 MB, `.tar.gz` yaklaşık 217 MB (`ks-release.json:22-27`).

Doğrulanmayanlar (KS `packaging/README.md:56-74`, DD D3/D5):
- Qt penceresi hiç açılmadı.
- Wayland oturumunda `QT_QPA_PLATFORM=xcb` gerekebilir.
- Eski sürümün üstüne yükseltme sınanmadı.

Diğer notlar:
- **TB13:** Debian 11 LTS 31.08.2026'da bitti. Güvenlik deposu arşive sabitlendi; sıradaki kırılma ana deponun arşive taşınması olacak. Pardus 21 desteğinin ne zaman bırakılacağı kullanıcı kararı.
- Pardus'ta uygulama içinden güncelleme indirme yok (`updates.py:268-320`).

#### A8. LAN kataloğu masaüstü katmanında neyi değiştirir

Tespitlerin tamamı DOĞRULANDI ve dosya/satırla verildi; öneriler ÇIKARIM.

| Mevcut durum | LAN'a etkisi | Öneri |
|---|---|---|
| `DEFAULT_HOST="127.0.0.1"`, `port=0` (`server.py:30`, `104`) | Diğer bilgisayarlar erişemez; rastgele port yer imine eklenemez | Yönetim sunucusu 127.0.0.1'de ve rastgele portta **kalsın**. Katalog için **ikinci bir `BackgroundServer`** açılsın: `0.0.0.0` ya da seçilen arayüz, **sabit ve ayarlanabilir port**, çakışmada Türkçe ileti |
| `base_url` ve `wait_until_ready` bağlanma adresi olarak `self._host`u kullanıyor (`server.py:92`, `138`) | ÇIKARIM: host 0.0.0.0 yapılırsa Windows'ta 0.0.0.0'a bağlanılamaz; pencere ve sağlık denetimi kırılır | Katalog sunucusunda bağlanma adresi ile dinleme adresi ayrılsın |
| `SessionTokenMiddleware` belirteçsiz her isteği 403'lüyor (`session_guard.py:70-73`); `check_health` 403 bekliyor (`server.py:195`) | Katalog istekleri reddedilir | Katalog WSGI sarmalayıcısı iki şeyi birlikte yapsın: **yol beyaz listesi** (yalnız `/katalog/**` ve salt okunur API, yalnız GET/HEAD) ve environ işareti. Middleware yalnız bu ikisi birlikteyken muaf tutsun. Sağlık denetimine "katalog portundan yönetim API'si 403/404 döner" adımı eklensin (fail-closed kalsın) |
| `ALLOWED_HOSTS` sabit (`settings.py:54`) | LAN'dan gelen Host başlığı 400 alır | Katalog yüzeyi için yerel IP'ler ve bilgisayar adı ya da yalnız o yüzeye özgü `*` |
| `SECRET_KEY` sabit ve güvensiz varsayılan (`settings.py:41-44`) | Ağa açılınca imzalı bir şey kullanılırsa risk | Kurulumda rastgele üretilip veri dizininde saklansın |
| Pencere kapanınca `server.stop()` (`main.py:156-163`) | Katalog yalnız kütüphaneci programı açıkken çalışır | Karar gerekli (§D-3) |
| Tek süreç, tek kilit | Ödünç işlemi LAN'dan yapılamaz | v1'de LAN yalnız okusun (istek zaten bu) |
| Şifreli alan araması çalışmıyor (crypto.py) | Katalog araması kırılır | Kitap ve katalog alanları şifrelenmesin; yalnız okuyucu (öğrenci/personel) alanları şifrelensin |
| SQLite `LIKE` yalnız ASCII için büyük/küçük harf duyarsız (ÇIKARIM) | "ığdır/IĞDIR" gibi aramalar kaçar | `tr_lower` ile normalize edilmiş arama sütunu |
| waitress 6 iş parçacığı (`server.py:31`) | 20-30 istemci için yeterli (ÇIKARIM) | Katalog sunucusuna ayrı iş parçacığı sayısı; PDF kilidi zaten var |
| Erişim günlüğü susturuluyor (`apply_access_log_policy`) | KVKK açısından iyi | LAN IP'si ve arama terimi günlüğe yazılmasın (DD'nin `?search=` sızıntısı dersi: DD `teknik-borc.md:39`) |

Yeni Windows ve ağ tuzakları (hepsi ÇIKARIM, sahada doğrulanmalı):
- Döngü adresi dışında dinlemeye başlayınca **Windows Defender Güvenlik Duvarı** izin penceresi çıkar. Yönetici olmayan kullanıcı izin veremez; iptal ederse Windows engelleme kuralı yazabilir.
- `PrivilegesRequired=lowest` kurucu (`kelebek-sinav.iss:51`) güvenlik duvarı kuralı ekleyemez. Seçenekler:
  - Inno'da isteğe bağlı yönetici görevi (`PrivilegesRequiredOverridesAllowed`) ile port kuralı eklemek,
  - bilişim sorumlusu için tek satırlık `netsh` talimatı.
- Okul ağı çoğunlukla "Ortak/Public" profilde görünür.
- DHCP IP değiştirir. Adres ekranda bilgisayar adı, IP ve QR kodu ile gösterilsin; bilişimden IP rezervasyonu istensin.
- Pardus'ta güvenlik duvarı varsayılanı sahada kontrol edilmeli.
- İstemci tarayıcıları için: KS Vite 6 kullanıyor; varsayılan derleme hedefi es2020 çağı (ÇIKARIM). Eski Pardus Firefox ESR'de sınanmalı. Sunucuda üretilen HTML ile yapılmış bir katalog en geniş uyumu sağlar.
- Güncelleme denetimi `api.github.com`a gidiyor (`updates.py:29-30`). MEB ağında GitHub engelli (okulapp.org `CLAUDE.md:127-130`), bu yüzden denetim sessizce başarısız olur.

---

### B. okulapp.org ortak yayın alanı

DOĞRULANDI: `git fetch` yapıldı, yerel `main` ile `origin/main` eşit, son commit `4bc490f`. Hiçbir dosya değiştirilmedi.

#### B1. Ortak çalışma düzeni (bağlayıcı, `okulapp.org/CLAUDE.md:40-79`)

1. **Tek yazar ilkesi.** Her alanın tek üretici projesi var; başka projenin alanına dokunulmaz.
2. **Taze taban.** İşe `git fetch origin` ile güncel `origin/main`den başlanır, push'tan hemen önce yeniden çekilir. Eski tabandan açılmış dal güncellenmeden birleştirilmez (29.08.2026 vakası: arşiv 5 setten 3'e düştü).
3. **Canlıya yalnız `main` gider.** Cloudflare Workers Builds'te "Version command" alanı `npx wrangler versions upload` olarak kalır, **`deploy` yazılmaz**.
4. **Commit başlığı alanı söyler.** Örnek: "Kelebek Sınav: …". Kütüphane için "Okul Kütüphanesi: …" gibi bir önek.
5. **Push'tan 1-2 dakika sonra canlı sayfa doğrulanır.**

Ek bağlayıcı kurallar:
- Sitede gerçek kişi verisi ve **gerçek ekran görüntüsü** olmaz (`:167-168`); ekran görüntüleri yalnız sentetik veriyle alınır.
- Harici CDN, font ya da analytics eklenmez (`:172`).
- Kullanıcının genel CLAUDE.md'si: kamuya açık metinde unvan ve kurum adı geçmez.
- `*-release.json` deseni yalnız GitHub sürümü olan projelere verilir (`:98-100`).

#### B2. Alan sahipliği tablosu (`CLAUDE.md:51-58`)

| Alan | Tek yazar |
|---|---|
| `public/evrak/**` ve `src/data/evrak-arsivi.json` | evrakmotoru (üretilir) |
| `oz-release.json` | okulzili |
| `dd-release.json` | disiplin-defteri-codex |
| `ss-release.json` | sorumluluk-sinavi |
| `ks-release.json` ve `src/pages/kelebek-sinav/**` | kelebek-sinav |
| sayfalar, layout, stil, bileşenler | sitenin kendi oturumları |

**Kütüphane için önerilen satır:** `src/data/kt-release.json`, `src/pages/<slug>/**` ve `public/<slug>/**` (ekran görüntüleri) ile sahibi kütüphane deposu. ÇIKARIM: KS satırı `KSLayout.astro`, `public/kelebek-sinav.png` ve `content/projects/kelebek-sinav.md` dosyalarını kapsamıyor. Kütüphane satırına layout, logo ve proje kartını da yazmak belirsizliği kaldırır.

#### B3. Sürüm JSON biçimi (`ks-release.json`, `dd-release.json`)

```json
{ "available": true, "version": "2026.9.0-beta.12", "name": "Kelebek Sınav v…",
  "published_at": "ISO-8601Z", "prerelease": true,
  "releaseUrl": "https://github.com/aalidemirci/<depo>/releases",
  "assets": [ {"kind": "windows_installer|windows_portable|linux_deb|linux_archive|checksums",
               "url": "https://indir.okulapp.org/<önek>/<dosya>", "size": <bayt>} ] }
```

- DD'de ek olarak `driveUrl` alanı var ve özet dosyası sabit adlı `SHA256SUMS.txt`.
- KS'de özet dosyası sürümlü: `SHA256SUMS-<sürüm>.txt`.
- `.deb` adında `~` yerine `.` kullanılıyor (`paketleme.yml:254-262`).
- `check-releases.mjs`, `releaseUrl`den GitHub deposunu çıkarıyor (`:25-28`). Depo herkese açık değilse ya da sürüm yoksa dosya "denetlenemedi" kalır.

#### B4. Sayfa yapısı ve proje kartı

- Proje kartı `src/content/projects/<depo-adı>.md` dosyasında. Şema `content.config.ts`de: `title, description, repoUrl, language, topics, featured, order, siteUrl, accent, badge`.
- Bölüm sayfaları `src/pages/<slug>/{index,kilavuz,gizlilik}.astro`. İndirme kartı `index.astro`da `import release from '../../data/ks-release.json'` ile üretiliyor.
- Her proje kendi `<XX>Layout.astro` dosyasını kullanıyor; `BaseLayout palette="ks"`.
- Logo `public/<slug>.png`, ekran görüntüleri `public/<slug>/*.webp`.

#### B5. Kütüphane siteye eklenirken yapılacaklar

Öncül: KS'nin ilk ekleme commit'i `44de4d2`, 10 dosyaya dokundu.

1. `git fetch` yap, güncel `origin/main`den dal aç.
2. `src/content/projects/<depo>.md` dosyasını oluştur (`npm run sync` taslak üretir; `featured`, `order: 5`, `accent`, `badge` alanlarını doldur).
3. `src/data/kt-release.json` ekle. Sürüm yoksa `available: false`.
4. `src/layouts/KTLayout.astro` ekle.
5. `src/pages/<slug>/index|kilavuz|gizlilik.astro` ekle. Gizlilik sayfası LAN kataloğunu dürüstçe anlatmalı: hangi veri ağda görünür, hangisi görünmez.
6. `public/<slug>.png` ekle.
7. `BaseLayout.astro:16` palet tipine `'kt'` ekle.
8. `global.css` içinde **üç blok** yaz: açık tema, `prefers-color-scheme: dark`, `data-theme='dark'`.
9. `CLAUDE.md` tablosuna satırı, "Kardeş depolar" listesine depoyu, 4. kurala commit önekini ekle.
10. `npm run build`, iç bağlantı ve çapa taraması, 375 px ve 1280 px düzen, WCAG AA kontrast kontrolü.
11. Push et, 1-2 dakika sonra canlıda doğrula.

Not: 7-9. adımlar sitenin ortak alanına dokunuyor. KS öncülünde bu, tek seferlik bir ekleme commit'inde proje önekiyle yapıldı; sonraki sürümlerde yalnız kendi alanına yazıldı.

#### B6. Sitedeki bayat belgeler (düzeltme kütüphane işi değil, bilgi amaçlı)

- `CLAUDE.md:108-114` palet tablosunda `ks` satırı yok, ama `global.css:143` içinde tanımlı.
- `README.md:19-25` paletin "dört değer" aldığını söylüyor.
- `CLAUDE.md:140-141` "Sürüm verisi ELLE tutulur" bölümünde `ks` yok.
- Kullanıcının genel CLAUDE.md'sindeki "siteye yazan projeler" listesinde kelebek-sinav yok. Bu kullanıcının özel dosyası; öneri olarak iletilmeli, düzenlenmemeli.

#### B7. KS yayın hattı özeti (`kelebek-sinav/packaging/README.md:141-181`, `paketleme.yml:234-320`)

- `v*` etiketi şu sırayı tetikler: `SHA256SUMS.txt` üretimi, GitHub Release, **Cloudflare R2** yüklemesi (kova `okulapp-indirme`, önek `kelebek-sinav/`, dağıtım `indir.okulapp.org`). Özet dosyası sürümlü adla yüklenir; dosya türleri `case` bloğunda tanımlı.
- Gereken secret'lar: `CLOUDFLARE_API_TOKEN` (R2 Object Read & Write) ve `CLOUDFLARE_ACCOUNT_ID`. Tanımlı değilse adım uyarıyla atlanır ve koşu yine **yeşil** biter.
- **19.09.2026 itibarıyla secret'lar tanımsız.** Yükleme geliştirme makinesinden elle yapılıyor:
  - `gh release download`
  - `sha256sum -c`
  - `npx wrangler@4 r2 object put … --remote` (wrangler OAuth oturumuyla)
  - beş dosya için `curl -I`: 200 ve doğru boyut.
- Sonrasında elle kalan iş: okulapp.org'daki `*-release.json` dosyası.
- Kütüphane için: `R2_ONEK=<slug>`; aynı kova kullanılır.

---

### C. Kimlik adlandırma kalıbı ve öneri

Kullanılan kısaltmalar: DD, KS, OZ, SS (paletler ve sürüm dosyaları), OYS (`OYS_*`). `KT_`, `ktbak` ve `X-KT` için sibling projelerde grep yapıldı, çakışma bulunmadı.

| Öğe | DD | KS | Kütüphane önerisi |
|---|---|---|---|
| Ortam değişkeni öneki | `DD_*` (17 adet) | `KS_*` (19 adet: DATA_DIR, APP_HOME, BACKEND_DIR, SESSION_TOKEN, SECRET_KEY, DEBUG, APP_VERSION, RTHOOK_UYARI, FRONTEND_DIR, WITH_QT, DLL_DIR, SKIP_PIP, BUILD_IMAGE, …) | `KT_*`; ek olarak `KT_KATALOG_PORT`, `KT_KATALOG_HOST` |
| Veri dizini | `DisiplinDefteri` / `disiplin-defteri` | `KelebekSinav` / `kelebek-sinav` (`paths.py:24-25`) | Ayırt edici bir ad, ör. `OkulKutuphanesi` / `okul-kutuphanesi`. Tek başına "Kutuphane" başka yazılımlarla çakışabilir (ÇIKARIM) |
| Çerez ve başlık | `dd_oturum`, `X-DD-Token` | `ks_oturum`, `X-KS-Token` (`session_guard.py:31-35`) | `kt_oturum`, `X-KT-Token` (`HTTP_X_KT_TOKEN`) |
| Yedek | `.ddbak`, `DDBAK\x02`, `DisiplinDefteri/backup/...` | `.ksbak`, `KSBAK\x02`, HKDF bilgisi `KelebekSinav/backup/...` | `.ktbak`, `KTBAK\x02`, `OkulKutuphanesi/backup/private/v1` |
| Anahtar parmak izi | `dd-anahtar-parmak-izi` | `ks-anahtar-parmak-izi` | `kt-anahtar-parmak-izi` |
| Logger ve iş parçacığı | `disiplin_defteri`, `dd-wsgi` | `kelebek_sinav`, `ks-wsgi` | `okul_kutuphanesi`, `kt-wsgi`, `kt-katalog-wsgi` |
| Windows | AppId `F0ACB44A…`, AppMutex (ölü) | AppId `96DC5FCC…`, AppMutex `KelebekSinav`, AUMID `KelebekSinav.Desktop` | **Yeni GUID üretilmeli**; AppMutex `OkulKutuphanesi` (`lock.py` ile birebir aynı); AUMID `OkulKutuphanesi.Desktop` |
| Paket dosyaları | `disiplin_defteri.spec`, `rthook_dd.py` | `kelebek_sinav.spec`, `rthook_ks.py` | `okul_kutuphanesi.spec`, `rthook_kt.py` |
| DRF hata işleyicisi | `dd_exception_handler` | `ks_exception_handler` | `kt_exception_handler` |
| Ön yüz anahtarları | — | `ks-page-title`, `ks:yeniden-baslat-gerekli` | `kt-…`, `kt:…` |
| Site | `dd` palet, `dd-release.json` | `ks`, `ks-release.json`, R2 `kelebek-sinav/` | `kt`, `kt-release.json`, R2 `<slug>/` |

---

### D. Kullanıcıya sorulması gereken kararlar

1. **Ürün adı ve kısa adı.** Örnek: "Okul Kütüphanesi" ve `okul-kutuphanesi`. Veri dizinini, exe adını, AppId'yi, R2 önekini ve sayfa yolunu belirler; sonradan değiştirmek pahalı.
2. **Kısaltma `KT` uygun mu?**
3. **Katalog ne zaman erişilebilir olacak?**
   - (a) Yalnız kütüphaneci programı açıkken (en basit).
   - (b) Oturum açılışında otomatik başlayan, penceresiz bir sunucu kipi (Inno'da yönetici gerektirmeyen "başlangıçta çalıştır" görevi). Tek kopya kilidiyle etkileşimi tasarlanmalı.
   - (c) Sistem tepsisi. pywebview'da tepsi yok; ek bağımlılık gerekir.
4. **LAN'da görünecek bilgiler.** Önerim: arama, kitap künyesi, raf yeri, rafta/ödünçte durumu. Ödünç alanın adı ve sınıfı gösterilmesin. İade tarihi gösterilsin mi? Ayırtma olsun mu? v1 için önerim: hayır.
5. **Güvenlik duvarı izni** kurulumda isteğe bağlı yönetici adımıyla mı verilsin, yoksa bilişim sorumlusuna talimat mı yazılsın?
6. **Katalog portu.** Sabit ve ayarlanabilir; varsayılan değer seçilmeli.
7. **Katalog arayüzü.** Mevcut React SPA'nın ikinci girişi mi, yoksa eski tarayıcılarda da çalışan sunucu tarafı HTML mi?
8. **Parola ve şifreleme kapsamı.** Yalnız okuyucu alanları mı? Katalog alanları şifrelenirse arama çalışmaz.
9. **İade tarihleri** tatil ve iş günü takvimine bağlı mı? Bağlıysa DD'nin `calendar.py` ve `working_days.py` dosyaları gelir.
10. **Pardus 21 desteği** sürecek mi (TB13)?
11. **Güncelleme denetimi.** GitHub API yerine `indir.okulapp.org`da bir sürüm manifesti kullanılsın mı? MEB ağında GitHub engelli.
12. **Depo GitHub'da herkese açık olacak mı?** okulapp.org'daki `check-releases` bunu gerektiriyor.

İncelenen başlıca dosyalar:
- `../kelebek-sinav/desktop/`
- `../kelebek-sinav/packaging/`
- `../kelebek-sinav/backend/shared/pdf.py`
- `../kelebek-sinav/backend/config/settings.py`
- `<kardeş proje deposu>/docs/tasarim/2026-07-23-genel-tasarim.md`
- `<kardeş proje deposu>/docs/teknik-borc.md`
- `../okulapp.org/CLAUDE.md`
- `../okulapp.org/src/data/ks-release.json`

<a id="r8"></a>

---

## R8. OYS ve kardeşlerin okul ağı (FATİH) deneyimi

## MEB okul ağı ve LAN'dan katalog erişimi: OYS ve kardeş projelerden çıkan bulgular

**Kısaltmalar (yol kökleri):** `OYS/` = `../okulapp` · `OZ/` = `../okulzili` · `DD/` = `../disiplin-defteri-codex` · `KS/` = `../kelebek-sinav` · `SS/` = `../sorumluluk-sinavi`
**Etiketler:** **[D]** = DOĞRULANDI (dosya:satır okundu) · **[Ç]** = ÇIKARIM (teknik değerlendirme, doğrulanmadı) · **[B]** = belgenin kendisi BELİRSİZ diyor

### 0. Kısa özet

1. **OYS kataloğu ağa hiç açmadı.** ADR-0040 "OPAC … kapsam dışıdır (LAN-only)" diyor. Konu yeni zemin. [D] `OYS/docs/adr/0040-kutuphane-modulu.md:27-28`
2. **Sahada iki ayrı ağ bloğu var.** Öğretmen bilgisayarları `<idari-ağ>`, Pardus tahtalar `<tahta-ağı>` bloğunda. İkisi farklı alt ağlarda. [D] `OYS/CHANGELOG.txt:31082-31083`
   - Tahtadan sunucuya erişim **sahada hiç doğrulanmadı**. [D] `OYS/docs/tahta-kiosk-kurulum.md:10-12`, `OYS/docs/saha-prova-kilavuzu.md:235,241-242`
   - Bu IP blokları kurum içi bilgidir; kamuya açık depo, belge ya da site metnine yazılmamalı. [Ç]
3. **Kardeş masaüstü uygulamaların hepsi bilinçli olarak ağa kapalı.** Güvenlik modelleri buna dayanıyor: girişsiz, yalnız 127.0.0.1'de dinliyor, yerel oturum belirteci kullanıyor. LAN'a açmak bu modeli bozar. Yönetim arayüzü ile herkese açık katalog **ayrı yüzeyler** olmalı. [D] `DD/CLAUDE.md:170-179`, `DD/desktop/session_guard.py:1-13`
4. **Kütüphane bilgisayarında dört kesin engel var.** Windows güvenlik duvarında gelen trafik kuralı, bu kural için yönetici yetkisi, IP'nin sabit kalması ve bilgisayarın uykuya geçmesi. Belgelerden ve çıkarımdan geliyor; ayrıntı §4'te.
5. **OYS'nin en pahalı operasyonel yükü kendi imzaladığı TLS sertifikasının cihazlara dağıtımıydı.** Katalog kişisel veri taşımıyor [D] `OYS/backend/apps/kutuphane/models.py:10`. Bu yüzden yalnız okunur katalog için düz HTTP savunulabilir; yönetim arayüzü ise asla LAN'a açılmamalı. [Ç]

---

### 1. MEB okul ağlarının gerçek kısıtları (OYS belgelerinden)

| # | Kısıt | Bulgu | Kaynak |
|---|---|---|---|
| 1 | **İdari ağ ile tahta ağı ayrı** | Ayrı VLAN'lar, ayrı IP blokları. Tahtalar internete ayrı bir VLAN'dan çıkar. | [D] `OYS/docs/fatih-ag-kurulum.md:20-22, 88-90` |
| 1a | Sahadaki bloklar | Öğretmen PC `<idari-ağ>`, tahta `<tahta-ağı>`. OYS sunucusu `<idari-ağ>` bloğunda, yani öğretmen alt ağında. | [D] `OYS/CHANGELOG.txt:31082-31084` |
| 2 | **Aktif ağ cihazları merkezden yönetilir** | Switch, erişim noktası ve router'ı MEB/YEĞİTEK uzaktan yapılandırır. VLAN, VLAN'lar arası yönlendirme, ACL ve AP-isolation **okulda değiştirilemez**. BT rehber öğretmeninin (BTR) yetkisi: statik IP, `/etc/hosts`, sertifika, proxy istisnası, FATİH PYS talebi. | [D] `fatih-ag-kurulum.md:102-105` |
| 3 | **Kablolu bağlantı esas** | Tahta, idari oda ve dizüstüler için kablosuz FATİH ağının kullanılmaması, kablo kullanılması isteniyor. Tavandaki Cisco cihazlar erişim noktasıdır. | [D] `fatih-ag-kurulum.md:91-93` |
| 4 | **İnternet çıkışı merkezî** | TTVPN üzerinden MEB veri merkezine bağlanılıyor; merkezî içerik filtresi ve SSL denetimli proxy var; istemcilere MEB kök sertifikası (fatihca) kuruluyor. Filtrenin ürün adı [B]. | [D] `fatih-ag-kurulum.md:94-97` |
| 5 | **Aynı VLAN içi trafik merkeze uğramaz** | Switch'te yerel olarak iletilir, filtreye takılmaz. Sorunun kaynağı büyük olasılıkla filtre değil: VLAN ayrımı, istemci yalıtımı (client isolation), `.local` adının çözülememesi ve sertifika güveni. | [D] `fatih-ag-kurulum.md:98-101`; belge bunu "mühendislik değerlendirmesi" diye işaretliyor `:362-364` [B] |
| 6 | **IP dağıtımı** | Genelde DHCP; çakışmada BTR elle statik IP verir. VLAN ID'leri ve bloklar okula göre değişir [B]. | [D] `fatih-ag-kurulum.md:106-107` |
| 7 | **Tahtaların işletim sistemi** | Faz 1/2/3 tahtaları çoğunlukla kısıtlı kullanıcılı Windows imajı. Yeni dağıtım Pardus ETAP; merkezden **Liderahenk** ile yönetiliyor, hosts dosyası ve sertifika toplu gönderilebilir. Ağ ayarları yönetici kilidi arkasında. | [D] `fatih-ag-kurulum.md:108-111` |
| 7a | Sahada sık görülen düzen | Tahtalar kablolu ağa bağlı olabilir ve ETAP yaygınlaşmaktadır. Birçok okulda tahtada ortak hesap kullanımı görülür; bu, kiosk ve kimlik tasarımını etkiler. | [D] `OYS/docs/adr/0032-akilli-tahta-kiosk.md:24-25`, `0047-tahta-pin-kimligi.md:29-37` |
| 8 | **Tahta tarayıcısı belirsiz** | Kiosk için `chromium`/`chromium-browser` önkoşul. Chromium'un kurulabilirliği sahada soru olarak duruyor (D7). ETAP'ın QR girişi hakkında güvenilir teknik belge yok. | [D] `tahta-kiosk-kurulum.md:21`, `saha-prova-kilavuzu.md:235`, `0047:43-45` |
| 9 | **Kullanıcıların yönetici hesabı yok** | "Okul bilgisayarlarında öğretmenin yönetici hesabı çoğunlukla yoktur." Bu yüzden kardeş kurulumlar `PrivilegesRequired=lowest` kullanıyor. | [D] `KS/packaging/windows/kelebek-sinav.iss:7-9,51`, `DD/.../disiplin-defteri.iss:51` |
| 10 | **Win10 okul imajında WebView2 garanti değil** | Açılışta tespit ediliyor, eski MSHTML'e düşmek kodla engelli (React 18 onda çalışmıyor). | [D] `DD/docs/tasarim/2026-07-23-genel-tasarim.md:234-236` |
| 11 | **MEB ağında GitHub engelli** | Dağıtım kaynağı `indir.okulapp.org`. | [D] `OZ/CLAUDE.md:59-61, 69-71` |
| 12 | **Google OAuth özel IP'yi reddediyor** | Web OAuth'ta `10.x` redirect URI'si "device_id … required for private IP" hatası veriyor. Bu MEB değil Google kuralı, ama MEB LAN'ında pratik sonucu var. | [D] `OYS/CHANGELOG.txt:31115-31118`, `OYS/CLAUDE.md:144-149` |
| 13 | **Telefon kanalı** | LAN'daki sunucuya mobil veriyle erişilemez. Öğretmen telefonu yalnız personel Wi-Fi'si sunucu VLAN'ına geçiyorsa ve sertifika telefona güvenilen olarak eklenirse çalışır. Öğrenci ve velinin OYS'ye girişi zaten yok (`can_login=False`). | [D] `OYS/docs/adr/0018-yoklama-uc-kanal-giris.md:34`, `OYS/docs/runbook.md:153-156`, `sunucu-altyapi-raporu.md:73-74` |
| 14 | **Talep kanalı** | FATİH PYS'de "Ağ Altyapı" kategorisi. Talep "internet ya da site açma" diye değil, **"yerel ağ VLAN düzenlemesi"** diye yazılmalı; yoksa filtre birimine gider. Zincir: BTR → Müdür → PYS → İl/İlçe → YEĞİTEK + yüklenici. Süre okulun elinde değil. | [D] `fatih-ag-kurulum.md:37-41, 268-301` |

**Belgelerde olmayanlar:** Engelli port listesi, merkezî filtrenin LAN içi portlara etkisi, öğrenci Wi-Fi'si ve istemci yalıtımının gerçek durumu. OYS bunları okulda bir keşif adımıyla (`fatih-ag-kurulum.md:115-151`) çözmeyi öneriyor.

---

### 2. OYS kısıtları nasıl aştı

#### 2a. İşe yarayan ya da kurulan çözümler

- **Dışa açık tek kapı nginx.** Yalnız 80 ve 443 bütün arayüzlerde dinliyor; Postgres, Redis, Django ve Vite `127.0.0.1`'de. 80'e gelen istek 443'e yönleniyor. [D] `fatih-ag-kurulum.md:51-54`, `OYS/nginx/conf/oys.prod.conf:10-23`, `CHANGELOG.txt:31084-31087`
- **Bağlantı tek yönlü.** İstemciden sunucuya gidiyor; sunucu istemciye bağlanmıyor. Bu, ağ talebini "tek yön, yalnız 443" diye daraltmayı sağladı. [D] `fatih-ag-kurulum.md:55-57`
- **Windows güvenlik duvarı kuralı kaynak adreslerle sınırlandı.** Komut: `New-NetFirewallRule … -LocalPort 443,80 -RemoteAddress <idari-ağ>,<tahta-ağı>`. Kuralı kullanıcı elle kurdu (sunucu o dönem Docker Desktop ile Windows'taydı). [D] `CHANGELOG.txt:31110-31113`. Sunucu sonra Ubuntu'ya taşındı [D] `sunucu-altyapi-raporu.md:286`.
- **API adresi göreli (`/api/v1`).** IP değişince arayüz bozulmuyor. Mutlak URL gömmek "bilinen tuzak". [D] `fatih-ag-kurulum.md:68-69`, `OYS/docs/development.md:626-628`
- **Kurulum Doktoru.** Tarayıcının kullandığı host/IP'yi `ALLOWED_HOSTS` ve sertifika SAN'ı ile karşılaştırıp düzeltme komutu veriyor. Her ağ bölümünden bu ucu açmak, erişimin en hızlı kanıtı. [D] `fatih-ag-kurulum.md:309-311, 322-324`
- **Sahada hatayı Türkçe durdurma.** Panel yanlış adresten açılınca kurulum paketi/kodu üretilmiyor, anlaşılır hata dönüyor. Geçmişte `https://backend:8000` gömülü paket saha hatası olmuştu. [D] `OYS/backend/apps/tahta/views.py:73-116`
- **İdempotent tahta kurulumu.** "MEB yeniden-imaj gerçeği" yüzünden kurulum betiği tekrar çalıştırılabilir yazıldı. [D] `tahta-kiosk-kurulum.md:67-68`

#### 2b. Önerilen ama sahada kanıtlanmamış

- **Dört ağ alternatifi:**

  | Yol | Ne demek |
  |---|---|
  | A | Ortak segment |
  | B | Dual-homed: sunucuya iki ağ kartı, her VLAN'a bir bacak (önerilen) |
  | C | VLAN'lar arası yönlendirme + ACL (PYS talebi) |
  | D | Ayrı ağ adası |

  Karar ağacı `:155-175`. D seçeneğinde tahtayı adaya almak EBA/internet bağlantısını koparır, "pratikte kabul görmez". [D] `fatih-ag-kurulum.md:24-35, 204-209`
- **Tek hostname stratejisi.** `oys.local` her ağ bölümünde o bölümdeki IP'ye çözülüyor, sertifika SAN'ı tek isimle kalıyor. Birden çok IP'li SAN bilinçli olarak ertelendi. [D] `fatih-ag-kurulum.md:213-226`, `CHANGELOG.txt:32507-32512`

#### 2c. Reddedilen ya da bilinçli uzak durulan

| Çözüm | Karar | Gerekçe ve kaynak |
|---|---|---|
| **mDNS/avahi yayını** | Yapılmadı | "`oys.local` mDNS/avahi ile YAYINLANMAZ". `.local` mDNS ile çakışabilir, ad çözümü operatöre bırakıldı (router/DNS, hosts, doğrudan IP). mDNS'in VLAN sınırını aşamaması [B]. [D] `fatih-ag-kurulum.md:65-67, 362-364`, `tahta-kiosk-kurulum.md:132-134` |
| **Google OAuth** | Uykuya alındı | Özel IP redirect URI'si reddedildi; yerine yerel kullanıcı adı + şifre geldi (ADR-0041). [D] `OYS/CLAUDE.md:144-149` |
| **sslip.io köprüsü** (genel DNS → özel IP) | Geçici denendi | MEB DNS'inin rebind koruması engellerse yedek plan hosts dosyası ya da yerel DNS kaydıydı. Dış DNS bağımlılığı çevrimdışı ilkeyle çelişiyor [Ç]. [D] `CHANGELOG.txt:31115-31125` |
| **Tahtaya paylaşımlı/anonim hesap** | Reddedildi | Denetim izi kişisizleşir. [D] `adr/0018:99-101` |
| **Mobil uygulama/mağaza** | Reddedildi | LAN-only yapı ve kurulum yükü; responsive web yeterli. [D] `adr/0018:34, 98` |

#### 2d. HTTP mi HTTPS mi

OYS'de LAN içinde bile TLS zorunlu: nginx kendi imzaladığı yaprak sertifikayı üretiyor, kök CA yok, 730 gün geçerli, tek ek IP SAN'ı var. [D] `OYS/CLAUDE.md:173-175`, `OYS/nginx/entrypoint.sh:27-37`

Bunun maliyeti belgelerde açık:

- Her cihaza güven dağıtımı gerekti: Windows kök deposu, ETAP'ta sistem deposu **ve kullanıcı başına Chromium NSS deposu**, telefona elle ekleme. [D] `fatih-ag-kurulum.md:258-261`, `development.md:644-650`, `runbook.md:153-156`
- ETAP her öğretmene ayrı hesap açtığı için sertifika tek kullanıcıya yazıldığında sonradan açılan hesaplar kiosk'u açamıyordu; saha hatası oldu. [D] `adr/0047-tahta-pin-kimligi.md:159-162`
- Sertifikaya IP eklemek volume silip yeniden üretmeyi gerektiriyor. [D] `development.md:636-643`

---

### 3. Kardeş masaüstü projelerin ağ kararları

| Proje | Ağ durumu | Gerekçe ve kaynak |
|---|---|---|
| **disiplin-defteri** | waitress, `127.0.0.1`, rastgele boş port (`bind(0)`), girişsiz. `ALLOWED_HOSTS = ["127.0.0.1","localhost","backend"]`. | "tek kullanıcılı, girişsiz, ağa hiç açılmayan yerel bir masaüstü uygulamasıdır". Girişsiz DRF, koda gömülü SECRET_KEY, CORS/CSP/HSTS yokluğu ve AuditLog yokluğu **bu varsayıma dayanıyor**. [D] `DD/CLAUDE.md:56, 170-181`, `DD/backend/config/settings.py:38-54`, `DD/desktop/server.py:1-11,30` |
| | Yerel oturum belirteci | Aynı makinedeki başka işlemin 127.0.0.1'e istek atmasına karşı sigorta; "ağ güvenliği iddiası değil". [D] `DD/desktop/session_guard.py:1-13` |
| | Erişim logu kapalı | `?search=<öğrenci adı>` sızdırır. [D] `DD/desktop/logging_setup.py:5-6,33`, `DD/desktop/tests/test_logging_setup.py:47` |
| **kelebek-sinav** | disiplin-defteri ile aynı desen (`KS_SESSION_TOKEN`). Keşif raporu OYS'den "Docker/LAN yapılandırması"nı **ALINMAMALI** listesine koydu. | [D] `KS/backend/config/settings.py:5,54,99-104`, `KS/docs/kesif/2026-08-29-kesif-raporlari.md:803` |
| | Sağlık denetimi | Belirteçsiz isteğin 403 dönmesini bekliyor (fail-closed), `threads=6`. [D] `kesif-raporlari.md:437` |
| **okulzili** | Ağ servisi yok | "uygulama kendiliğinden ağa çıkmaz". Bilinçli iki istisna: MEB ses indirme (`*.meb.gov.tr`) ve varsayılan kapalı SNTP. `test_packaging.py` diğer modüllerde `socket/urllib/http.client/asyncio` gibi importları reddediyor. [D] `OZ/CLAUDE.md:34-37`, `OZ/MIMARI.md:90`, `OZ/tests/test_packaging.py:184-194` |
| | Yerel ağ web arayüzü | **Faz 3 opsiyonel** listede: "ayrı tehdit modeli, yetkilendirme ve lisans incelemesi yapılmadan" kapsama alınmayacak. Tasarlanmış ama ertelenmiş bir ret. [D] `OZ/PLAN.md:211-218` |
| | Kurucu ve pencere | Kurucu **yönetici yetkisi istiyor** (`PrivilegesRequired=admin`), otomatik başlatma görevi var. Çarpı düğmesi uygulamayı kapatmıyor, tepsiye gizliyor. Bu desen kütüphane için önemli. [D] `OZ/packaging/windows/okul-zili.iss:16,29-30`, `OZ/MIMARI.md:84` |
| **sorumluluk-sinavi** | Tam ret | "Uygulama hiçbir ağ isteği yapmaz"; telemetri, güncelleme denetimi, uzak yedek eklenemez, istenirse yeni karar kaydı gerekir. Gerekçe: veri cihazdan çıkmazsa aktarım, işleyen sıfatı ve sözleşme tartışmaları baştan kalkar; okul ağı çalışmazken de uygulama çalışır. [D] `SS/kararlar/0001-cevrimdisi-ve-yerel-veri.md:12-28`, `SS/CLAUDE.md:16-17` |

**Sonuç [Ç]:** "LAN'a açılma" dört projenin hiçbirinde yok. Kütüphane için bu yeni ve bilinçli bir istisna olacak. sorumluluk-sinavi ve okulzili emsaline göre **ayrı bir karar kaydıyla** (ADR) gerekçelendirilmesi ve bir testle sınırlandırılması tutarlı olur. Örneğin: dinleyici yalnız katalog uçlarını sunar; yönetim uçları loopback dışından 403 döner.

Mevzuat dayanağı:
- Okul Kütüphaneleri Yönetmeliği md. 14/1: danışma hizmeti "olanaklar ölçüsünde elektronik ortamlarla da karşılanır". [D] `OYS/data/mevzuat/meb-okul-kutuphaneleri-yonetmeligi.md:194`
- md. 11/1: katalog yazar, eser adı ve konuya göre düzenlenir. [D] `:165`

---

### 4. Kataloğa erişimin önündeki engeller ve çözüm seçenekleri

#### 4.1 Kütüphane bilgisayarı tarafındaki engeller

| # | Engel | Kanıt | Seçenekler |
|---|---|---|---|
| H1 | **Windows güvenlik duvarı gelen trafiği keser** | OYS'de de elle kural gerekti [D] `CHANGELOG.txt:31111-31112`. Yerel sunucuyu bile güvenlik yazılımı engelleyebiliyor [D] `DD/desktop/server.py:145,192`, `KS/docs/kurulum.md:257` | (a) Kurucuda isteğe bağlı, yönetici yetkisiyle "Ağ erişimini aç" adımı: `New-NetFirewallRule`, yalnız uygulamanın exe'si ve portu, `-RemoteAddress LocalSubnet` ya da tanımlı bloklar [Ç]. (b) Kural yoksa uygulama bunu tespit edip Türkçe yönlendirme göstersin [Ç]. |
| H2 | **Kuralı kurmak yönetici ister, kullanıcıda bu yetki yok** | [D] `KS/.../kelebek-sinav.iss:7-9` | (a) Kurucu varsayılanda `lowest` kalsın, ağ modu ayrı ve yükseltilmiş bir yardımcıyla açılsın. sorumluluk-sinavi'nin `PrivilegesRequiredOverridesAllowed=dialog` emsali var [D] `SS/yapim/sorumluluk_sinavi.iss:48`. (b) okulzili gibi tamamen yönetici kurulumu [D] `OZ/.../okul-zili.iss:16`. (c) Kuralı BTR kursun, belgeye komut yazılsın [Ç]. |
| H3 | **Windows ağ profili "Ortak/Genel" ise gelen trafik varsayılan kapalı** | [Ç] | Kural `-Profile Private,Domain,Public` ile yazılsın ya da profil değiştirilsin. Profil değişikliği sistem ayarıdır, BTR/yönetici yapar [Ç]. |
| H4 | **IP değişkenliği (DHCP)** | BTR'den statik IP ya da DHCP rezervasyonu isteniyor [D] `fatih-ag-kurulum.md:106,147,234` | Rezervasyon zorunlu kılınsın. Uygulama açılışta LAN IP'lerini algılayıp ekranda **URL ve QR** göstersin, değişince uyarsın [Ç]. Birden çok ağ kartında (Wi-Fi + Ethernet + Hyper-V/WSL sanal kartları) doğru IP'yi seçme sorunu var; OYS bunu `LAN_HOST_IP` değişkeniyle elle çözdü [D] `OYS/docker-compose.lan.yml:66-69`. |
| H5 | **Rastgele port** | Kardeş uygulamalar `bind(0)` kullanıyor [D] `DD/desktop/server.py:30`, `DD/docs/tasarim/...:257` | LAN dinleyicisi **sabit port** kullanmalı. Port 80 URL'yi kısaltır ama başka servisle çakışabilir; 8080 gibi bir port URL'yi uzatır ve VLAN ACL talebinde ayrıca adı geçmeli. OYS'nin PYS talebi "yalnız TCP/443" idi [D] `fatih-ag-kurulum.md:278-285` [Ç]. |
| H6 | **`ALLOWED_HOSTS` yalnız loopback** | [D] `DD/backend/config/settings.py:54`. OYS'de yanlış Host tam arıza sebebiydi [D] `fatih-ag-kurulum.md:62-64` | Açılışta algılanan IP'ler ve ayarlanan hostname dinamik olarak eklensin. `*` kullanılmasın; Host denetimi DNS-rebinding'e karşı da korur [Ç]. |
| H7 | **Girişsiz güvenlik modeli LAN'a taşınamaz** | [D] `DD/CLAUDE.md:170-179` | **İki yüzey [Ç]:** 1) yönetim SPA'sı 127.0.0.1'de, belirteçle, kardeş desenle aynen; 2) katalog ayrı dinleyici ya da ayrı WSGI uygulaması, yalnız okunur, beyaz listeli uçlar. Aynı WSGI uygulamasını iki sokette açmak tehlikeli (her uç iki yüzeyde de görünür). Katalog yanıtında üye, ödünç alan kişi ya da gecikme bilgisi olmamalı. |
| H8 | **Uygulama kapanınca ya da bilgisayar uyuyunca katalog düşer** | pywebview kapanınca waitress da kapanır [Ç] | okulzili deseni: çarpı tepsiye gizler, oturum açılışında otomatik başlar [D] `OZ/MIMARI.md:84`. Sunarken uyku engellenmeli (`SetThreadExecutionState`) [Ç]. |
| H9 | **Eski ya da farklı tarayıcılar** | Faz 1/2 Windows tahtalar; MSHTML'de React 18 çalışmıyor [D] `fatih-ag-kurulum.md:108`, `DD/docs/tasarim/...:234-236` | LAN katalogu **sunucu tarafında üretilen sade HTML** olsun (Django şablonu, JS gerektirmeyen arama formu). React SPA yalnız yönetim penceresinde kalsın [Ç]. |
| H10 | **TLS dağıtım yükü** | §2d | Katalog yalnız okunur ve kişisel veri taşımıyorsa **düz HTTP + doğrudan IP**. HTTPS gerekiyorsa OYS'nin sertifika dağıtım yükü aynen geri gelir [Ç]. Chrome'un HTTPS öncelikli varsayılanlarının özel IP'yi muaf tutup tutmadığı doğrulanmalı [Ç, doğrulanmadı]. |
| H11 | **İmzasız exe + dinleyen port → SmartScreen/antivirüs** | SmartScreen uyarısı zaten bekleniyor [D] `OZ/KURULUM.md:8`. USB/yerel ağ dağıtımında Mark-of-the-Web oluşmaz iddiası [D] `DD/docs/tasarim/...:239` | Kullanıcı belgesine SHA256 doğrulaması ve güvenlik duvarı açıklaması eklensin [Ç]. |
| H12 | **Kütüphane bilgisayarını nöbetçi öğrenciler de kullanıyor olabilir** | OYS'de kütüphane nöbeti var [D] `CHANGELOG.txt:31127` | Girişsiz yönetim arayüzü üye/ödünç kişisel verisini öğrenciye açar. disiplin-defteri'nin "opsiyonel açılış parolası + Kilitle" deseni [D] `DD/docs/tasarim/...:28, 310-319` kütüphanede **varsayılan açık** düşünülmeli [Ç]. |

#### 4.2 İstemci tarafındaki engeller (kim, nereden erişecek)

| İstemci | Olası engel | Seçenekler |
|---|---|---|
| **İdari/öğretmen PC** (kütüphane bilgisayarı aynı `<idari-ağ>` bloğundaysa) | Aynı alt ağ içi trafik merkeze uğramaz [D] `fatih-ag-kurulum.md:98-99`. Engel neredeyse yalnız H1-H4. | `http://<IP>:<port>` masaüstü kısayolu. Test: `Test-NetConnection <IP> -Port <p>` [D] `fatih-ag-kurulum.md:316`. |
| **Tahtalar** (`<tahta-ağı>`) | 1) VLAN'lar arası yönlendirme ya da ACL izni var mı, **bilinmiyor** (OYS'de de doğrulanmadı). 2) Tahta tarayıcısında MEB proxy'si ayarlıysa yerel IP isteği proxy'ye gidebilir; proxy istisnası BTR yetkisinde [D] `fatih-ag-kurulum.md:105`, [Ç] etki. 3) Ağ ayarları yönetici kilidinde. | (a) Önce OYS'nin keşif adımı: tahtada `ip route`, ardından tarayıcıda URL denemesi [D] `fatih-ag-kurulum.md:129-143`. (b) Kapalıysa OYS'nin PYS dilekçe şablonu hedef IP + port değiştirilerek kullanılır [D] `:273-301`. (c) Kütüphane bilgisayarını tahta VLAN'ındaki bir porta bağlamak ya da ikinci ağ kartı (OYS B yolu) [D] `:186-197`. (d) Kısayol/yer imi Liderahenk ile toplu gönderilir [D] `:109-111,150`. |
| **Öğrenci telefonu** | Mobil veriyle LAN'a erişilemez [D] `adr/0018:34`. Kablosuz FATİH ağı kullanılmamalı [D] `fatih-ag-kurulum.md:91-93`. Personel Wi-Fi'si olsa bile öğrenciye açılması ayrı politika konusu. Wi-Fi'de istemci yalıtımı telefonları sunucudan ayırır [D] `:100`, [Ç] etki. | (a) Telefon kanalını **V1 dışı** bırakmak (OYS emsali) [Ç]. (b) Kütüphaneye internetsiz, yalnız kataloğa açık ayrı erişim noktası (OYS D yolu). Okul yönetimi onayı, SSID/parola yönetimi ve mevzuat kontrolü gerekir [Ç]. (c) Okuldaki cep telefonu kısıtları mevzuat açısından **kullanıcıya sorulmalı** [Ç, doğrulanmadı]. |
| **Telefonla raf etiketi QR'ı okutma** | OYS etiketindeki QR içeriği yalın barkod, URL değil [D] `OYS/backend/apps/kutuphane/label_service.py:3-4`. Tarayıcıda kamera erişimi güvenli bağlam (HTTPS) ister; HTTP'de web tabanlı barkod okuyucu çalışmaz [Ç]. | QR'a URL gömmek etiketi IP'ye kalıcı bağlar, IP değişince basılı etiketler bozulur [Ç]. Etikette barkod kalsın, katalog sayfasında elle barkod arama olsun [Ç]. |
| **Kütüphane içi tarama istasyonu** (ikinci PC ya da tahta) | Aynı ağ bölümündeyse en kolay senaryo. | Tarayıcı kiosk kipinde katalog URL'si açılır; OYS'nin Chromium `--kiosk` deneyimi var [D] `tahta-kiosk-kurulum.md:70-84` [Ç]. |

#### 4.3 Hostname ile IP

| Seçenek | Durum |
|---|---|
| **mDNS/`.local`** | OYS emsaliyle yapılmamalı [D] `fatih-ag-kurulum.md:65-67`. VLAN'lar arasında çalışmaz [B]; Android/Windows çözümleme davranışı değişken [Ç]. |
| **Yerel DNS A kaydı** | Merkezî ağ yönetimi yüzünden okulda yapılamayabilir. BTR ve MEB'e bağlı [D] `fatih-ag-kurulum.md:102-105`. |
| **hosts dosyası** | Her cihaza tek tek ya da tahtalara Liderahenk ile toplu. Telefonlarda yapılamaz [Ç]. |
| **Doğrudan IP + DHCP rezervasyonu** | En az bağımlılık. Kullanıcıya dönük kısım kısayol, afiş QR'ı ve uygulamanın gösterdiği QR ile gizlenir [Ç]. |

---

### 5. Kullanıcıya sorulması gereken kararlar

1. **Erişim kapsamı:** Kataloğa kim erişecek? Yalnız öğretmen PC'leri mi, tahtalar da mı, öğrenci telefonları da mı? Tahta ve telefon ağ talebi, hatta donanım gerektirebilir.
2. **Kütüphane bilgisayarının fiziksel ağ yeri:** İdari VLAN mı, tahta VLAN'ı mı, ağ bağlantısı yok mu? Önce §4.2'deki keşif adımı yapılmalı.
3. **Yönetici yetkisi:** Güvenlik duvarı kuralını kim kuracak? Kurucu yönetici mi istesin, ayrı bir "ağ modunu aç" adımı mı olsun, BTR mi kursun?
4. **HTTP mi HTTPS mi:** Katalog için düz HTTP kabul mü? Kişisel veri yok, ama kamera ile tarama ve PWA gibi özellikler dışarıda kalır.
5. **Ağdan görünecek alanlar:** Katalogda nüsha durumu (rafta/ödünçte) görünsün mü? Ödünç alan kişi asla görünmemeli. Kitap ayırtma olacak mı? Ayırtma kimlik gerektirir, girişsiz modeli bozar.
6. **Açılış parolası:** Kütüphane bilgisayarını öğrenciler kullanıyorsa yönetim arayüzüne parola varsayılan olsun mu?
7. **Katalog ne zaman erişilebilir:** Yalnız uygulama açıkken mi, bilgisayar açıldığında otomatik mi? Tepsi, otomatik başlatma ve uyku engelleme buna bağlı.
8. **Ağ modu varsayılanı:** "LAN'dan erişim" varsayılan kapalı gelip ayarlardan mı açılsın? Kardeş projelerdeki çevrimdışı ilkesiyle uyumlu olan bu [Ç].
9. **Mevzuat:** Yönetmelik md. 9/2, 11/2 ve 16/2 "Bakanlıkça belirlenen kütüphane otomasyon sistemi" diyor [D] `OYS/docs/adr/0040-kutuphane-modulu.md:16-19`. OYS kendini okulun otomasyon sistemi sayıyordu; müstakil uygulamanın bu konumu ayrıca değerlendirilmeli.

### 6. Gözden kaçabilecek teknik noktalar [Ç]

- **Performans:** 40 tahta ve PC aynı anda sorgulasa bile waitress `threads=6` ve SQLite WAL okumalarda yeterli olur. Arama uçlarına basit bir istek sınırı (IP başına) konmalı.
- **Loglar:** Arama sorgusu logu kişisel veri içermese de kardeş desenle erişim logu kapalı kalsın. İstatistik isteniyorsa yalnız toplam sayaç tutulsun.
- **Ağ Doktoru ekranı:** OYS'deki Kurulum Doktoru'nun karşılığı olarak algılanan IP'ler, dinlenen port, güvenlik duvarı kuralının varlığı, ağ profili, URL/QR ve kendi kendine erişim testi gösterilsin.
- **Testler:** Loopback dışından yönetim uçlarının 403 döndüğünü ve katalog yanıtında kişisel veri alanı bulunmadığını doğrulayan testler yazılsın. okulzili'nin `test_packaging` ağ denetimi emsali var.
- **Bilgi sızıntısı:** Uygulama çalışırken yönetim portu rastgele kalmalı ve dışarıya hiçbir şekilde ilan edilmemeli.

<a id="r9"></a>

---

## R9. Yerel ağ katalog mimarisi araştırması

## Kütüphane masaüstü uygulaması: yerel ağda salt-okur katalog taraması için mimari araştırması

### 0. Kısa öneri

1. **İki ayrı sunucu olsun (seçenek b).** Yönetim sunucusu kelebekteki gibi kalır: 127.0.0.1, rastgele port, oturum belirteci. Katalog için ayrı bir waitress sunucusu açılır. Kendi iş parçacığı havuzu olur ve 0.0.0.0'da sabit bir portu dinler. Bu sunucu **Django'nun istek zincirini kullanmayan küçük bir WSGI uygulaması** olur: middleware yok, URLconf yok. Veritabanına `mode=ro` ile bağlanır ve sorguyu her istekte açıp kapatır. Yalnız bir `opac_*` SQL görünümünü okur. Buna bir sqlite3 authorizer izin listesi ve `PRAGMA query_only` eklenir.
2. **Güvenlik duvarı kuralı kurulumda, yönetici modunda eklenir.** Kural program, TCP, port ve `remoteip=localsubnet` ile sınırlanır. Kural yoksa program 0.0.0.0'ı **hiç dinlemez**. Aksi hâlde yönetici olmayan kullanıcıda Windows'un iletişim kutusu kalıcı bir engelleme kuralı yazar. Bu kurallar izin kurallarından önce gelir.
3. **Erişim yolu: IP adresi + QR kod.** QR ekranda ve basılı afişte gösterilir. Bilişim sorumlusundan DHCP rezervasyonu istenir. mDNS ya da bilgisayar adı yalnız ikincil kolaylık olabilir.
4. **Kişisel veri sıfır olmalı ve bu testlerle korunmalı.** Arayüz sunucu tarafında üretilen HTML olur, JavaScript olmaz. Katı bir CSP, yalnız GET/HEAD, erişim günlüğü yok. Durum yalnız "Rafta / Ödünçte / Kütüphanede okunur" olarak gösterilir.
5. **Katalog yalnız program açıkken çalışır (Faz 1).** Faz 2'de sistem tepsisi ve oturum açılışında otomatik başlatma eklenebilir. Windows hizmeti önerilmez.

---

### 1. Kelebek'te sunucu şu an nasıl kurulu

| Konu | Durum | Kanıt |
|---|---|---|
| Dinleme adresi | Yalnız `127.0.0.1`, `port=0`: boş portu işletim sistemi seçer | DOĞRULANDI: `kelebek-sinav/desktop/server.py:30,101-108` |
| waitress ayarları | 6 iş parçacığı, `ident=None`, `clear_untrusted_proxy_headers=True` | DOĞRULANDI: `server.py:31,106-107` |
| Tek güvence | Oturum belirteci (32 bayt) açılış adresinde gelir, sonra `HttpOnly` ve `SameSite=Strict` çereze yazılır. Belirteçsiz istek 403 alır | DOĞRULANDI: `session_guard.py:49-51,70-86` |
| Güvence yoksa açılmama | Middleware zincirde değilse açılış durur. Sağlık denetiminde belirteçsiz istek 403 **dönmezse** açılış durur | DOĞRULANDI: `django_bootstrap.py:77-92`, `server.py:172-206` |
| Middleware ekleme | Ortam değişkeni doluysa `MIDDLEWARE.insert(0, SessionTokenMiddleware)` ile **bütün** isteklere uygulanır | DOĞRULANDI: `backend/config/settings.py:104-105` |
| ALLOWED_HOSTS | `["127.0.0.1","localhost","backend"]`. Paketli programda "backend" gereksiz | DOĞRULANDI: `settings.py:54` |
| SQLite | WAL, `busy_timeout=5000`, `synchronous=NORMAL`, `transaction_mode=IMMEDIATE` | DOĞRULANDI: `settings.py:128-146` |
| SPA catch-all | `^(?!api/|static/).*$` deseni `index.html` döndürür | DOĞRULANDI: `backend/config/urls.py:39` |
| Erişim günlüğü | waitress ve django.server susturulmuş, sorgu dizesi kırpılıyor | DOĞRULANDI: `desktop/logging_setup.py:41,48-53,133-154` |
| Tek kopya | Dosya kilidi + Inno için `KelebekSinav` mutex'i. İkinci açılış hata iletisi verir | DOĞRULANDI: `desktop/lock.py:29-31,80-94`, `.iss:66` |
| Kurulum yetkisi | `PrivilegesRequired=lowest` ve `{autopf}`, yani `%LOCALAPPDATA%\Programs`. **Yönetici yok** | DOĞRULANDI: `packaging/windows/kelebek-sinav.iss:47,51` |
| Veri yeri | `%LOCALAPPDATA%\<Ad>`, kullanıcıya özel | DOĞRULANDI: `desktop/paths.py:114-123` |
| Program içinden geri yükleme | Dosya değişmeden önce `connections.close_all()` çağrılıyor. Windows'ta açık bağlantı varken `os.replace` hata verir | DOĞRULANDI: `backend/apps/okul/services/live_restore.py:12-14,108` |

disiplin-defteri-codex aynı modeli kullanıyor. DOĞRULANDI: `disiplin-defteri-codex/desktop/server.py:30-31`, `backend/config/settings.py:54`.

**Kurulum yetkisiyle çatışma:** Kelebek'in yönetici istemeyen kurulumu, güvenlik duvarı kuralı ekleyemez. Makine genelindeki güvenlik duvarı kuralları yükseltilmiş yetki ister ([MS KB947709](https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/netsh-advfirewall-firewall-control-firewall-behavior)). Ağ özelliği bu yüzden kurulum modelini değiştirir (§3).

---

### 2. Dinleme modeli

#### Doğrulanmış waitress gerçekleri
- `listen` boşlukla ayrılmış birden çok `host:port` alır ([waitress arguments](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html)).
- Çoklu soketlerde `create_server` bir `MultiSocketServer` kurar. Soketlerin hepsi **tek bir `ThreadedTaskDispatcher`** (iş parçacığı havuzu) ve **tek bir WSGI uygulaması** paylaşır. Sokete göre ayrı uygulama verilemez. DOĞRULANDI: [waitress server.py](https://raw.githubusercontent.com/Pylons/waitress/main/src/waitress/server.py).
- `SERVER_PORT` isteğin geldiği sunucu nesnesinin `effective_port` değerinden gelir. İstemci bunu değiştiremez. `REMOTE_ADDR = channel.addr[0]`. DOĞRULANDI: [waitress task.py](https://raw.githubusercontent.com/Pylons/waitress/main/src/waitress/task.py). `trusted_proxy` verilmediği sürece X-Forwarded-For dikkate alınmaz (`server.py:107`).
- Girdi/çıktıyı tek bir ana iş parçacığı yürütür. İşçi iş parçacıkları ağ işi yapmaz, istek tamamen alındıktan sonra işe başlar. Yavaş istemciler işçileri tüketmez, ama yavaş uygulama kodu havuzu kilitleyebilir ([waitress design](https://docs.pylonsproject.org/projects/waitress/en/stable/design.html)).
- Varsayılanlar: `threads=4`, `connection_limit=100`, `channel_timeout=120`, `max_request_body_size` 1 GB ([arguments](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html)).

#### Karşılaştırma

| | (a) Tek waitress 0.0.0.0 + izin listesi middleware'i | (b) İki ayrı sunucu (önerilen) | (c) waitress'in çoklu `listen` özelliği |
|---|---|---|---|
| Ağa açılan yüzey | **Bütün yönetim API'si** ağa açılır. Tek güvence belirteç ve izin listesidir | Yalnız katalog uygulamasının birkaç ucu | (a) ile aynı. Uygulama tek, ayrım `SERVER_PORT` ile kodda yapılır |
| Yönetim ucunu yanlışlıkla açma riski | **Yüksek.** `SessionTokenMiddleware` bütün isteklere uygulandığı için (`settings.py:104-105`) katalog için bir muafiyet yazmak gerekir. Muafiyetteki bir hata yönetimi açar. `ALLOWED_HOSTS` de değişken IP yüzünden `"*"` olmak zorunda kalır | **Yapısal olarak düşük.** Yönetim sunucusu koda 127.0.0.1 olarak sabitlenir. Katalog uygulaması Django URLconf'unu hiç yüklemez | Orta-yüksek. Yönlendirmedeki bir hata yönetimi ağa açar |
| Kaynak yalıtımı | Yok | İki havuz, iki bağlantı sınırı, iki zaman aşımı | **Havuz ortak**: 50 öğrenci yönetim arayüzünü yavaşlatabilir. Bağlantı ve zaman aşımı ayarları iki soket için ortaktır |
| Bakım | Az kod ama kırılgan | Yaklaşık 200-400 satırlık ayrı modül. Şema değişince bu sorgular da güncellenir, test gerekir | Az kod ama kırılgan |
| Sonuç | Önerilmez | **Önerilir** | Önerilmez |

**Katalog uygulaması için (b)'nin alt seçenekleri:**
- **b1: ikinci bir Django işleyicisi** (`request.urlconf` ile). Önerilmez. `MIDDLEWARE` genel bir ayar olduğu için belirteç middleware'i ağdan gelen her isteğe 403 verir. Bunu aşmak için ya muafiyet yazılır (riskli) ya da `load_middleware` Django iç yapısına dayanarak ezilir (kırılgan).
- **b2: Django'suz saf WSGI + stdlib `sqlite3`. Önerilir.** HTML, Django'nun şablon motoruyla ya da escape disipliniyle üretilir. Django zaten ayakta olduğu için şablon motoru kullanılabilir. Middleware, URLconf ve ORM kullanılmaz. ÇIKARIM.

#### SQLite eşzamanlılığı (b2)
- WAL modunda "okuyucular yazarı, yazar okuyucuları engellemez". Aynı anda tek yazar vardır. WAL **ağ dosya sisteminde çalışmaz**, yani aynı makinede kalmalıdır ([sqlite wal](https://www.sqlite.org/wal.html)). Katalog aynı süreçte okuduğu için sorun yok. DOĞRULANDI.
- `mode=ro` URI ile salt-okur bağlantı açılabilir ([Python sqlite3](https://docs.python.org/3/library/sqlite3.html)). WAL veritabanında salt-okur açmak için `-shm` dosyasının var olması ya da dizinin yazılabilir olması gerekir ([wal.html](https://www.sqlite.org/wal.html)). Veri dizini aynı kullanıcıya ait olduğu için bu koşul sağlanır.
- `check_same_thread`: bağlantı iş parçacıkları arasında paylaşılmamalı. **Her istekte bağlantı aç ve kapat.** SQLite'ta bu işlem ucuzdur (ÇIKARIM). Asıl sebep şudur: kelebekteki program içi geri yükleme, dosyayı değiştirmeden önce yalnız Django bağlantılarını kapatıyor (`live_restore.py:108`). Katalog kalıcı bağlantı tutarsa Windows'ta `os.replace` başarısız olur (`live_restore.py:12-14`). Geri yükleme akışı katalog sunucusunu da durdurmalı ve yeniden başlatma kapısına (`restart_gate`) bağlanmalıdır.
- Çok katmanlı savunma: bağlantı kurulunca `set_authorizer` ile yalnız izin verilen tablo ve sütunlarda okuma serbest bırakılır, gerisi `SQLITE_DENY` alır. `set_progress_handler` uzun sorguyu keser ([Python sqlite3](https://docs.python.org/3/library/sqlite3.html)). DOĞRULANDI. Bunlara `PRAGMA query_only=ON` eklenir. Bir Django migration'ı `RunSQL` ile yalnız herkese açık sütunları içeren `opac_eser` ve `opac_nusha` görünümlerini kurar. ÇIKARIM.
- Kontrol noktası tıkanması: sürekli üst üste binen okuyucular WAL dosyasının şişmesine yol açabilir ([wal.html](https://www.sqlite.org/wal.html)). Kısa sorgularla okuyucular arasında boşluk olur. Uzun okuma işlemi açık tutulmamalı.
- **Alternatif (KVKK açısından en katı):** Katalog ayrı bir `katalog.sqlite3` anlık kopyasını okur. Böylece ağa bakan kod kişisel veri içeren dosyayı hiç açmaz. Bedeli: eşitleme kodu, kısa gecikme, Windows'ta açık dosyanın üzerine yazma sorunu (sürümlü dosya adı gerekir). Kullanıcıya karar olarak sunulabilir.

#### Performans (50 öğrenci)
- Katalog sunucusu için öneri: `threads=4..6`, `channel_timeout=20..30`, `max_request_body_size≈1 KB`, `max_request_header_size≈8 KB`.
- **`connection_limit`'i 100'de bırakmayın.** 50 cihaz × 2-6 keep-alive bağlantı, 120 saniyelik zaman aşımıyla 100'ü aşar. Sınıra ulaşınca waitress yeni bağlantı kabul etmez. 300 civarı ve kısa zaman aşımı önerilir. ÇIKARIM. Windows'ta `select()` sınırı yaklaşık 512 soket. ÇIKARIM, CPython derleme sabiti, doğrulanmadı.
- `LIKE '%x%'` birkaç on bin eserde tam tarama yapar. Milisaniyeler düzeyinde olması beklenir. ÇIKARIM, ölçülmeli. İki sunucu aynı süreçte olduğu için GIL ortaktır: yönetim tarafında PDF üretimi sırasında katalog yavaşlar. Kabul edilebilir.

#### Windows'ta port ele geçirme (gözden kaçmaması gereken)
- waitress `SO_REUSEADDR` ayarını **koşulsuz** koyar. DOĞRULANDI: [wasyncore.py `set_reuse_addr`](https://raw.githubusercontent.com/Pylons/waitress/main/src/waitress/wasyncore.py).
- Microsoft'a göre ilk bağlanma joker adres + varsayılan ayarla yapıldıysa, **aynı kullanıcıya ait başka bir süreç belirli bir IP'ye aynı portla bağlanabilir**. Bu durumda gelen bağlantının hangi sokete düşeceği belirsizdir. "All server applications must set SO_EXCLUSIVEADDRUSE" ([MS: SO_REUSEADDR/SO_EXCLUSIVEADDRUSE](https://learn.microsoft.com/en-us/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse)). DOĞRULANDI.
- Çözüm: soket kendimiz açılır, `SO_EXCLUSIVEADDRUSE` konup bağlanır ve waitress'e `sockets=[sock]` ile verilir. Önceden bağlanmış soketler `bind_socket=False` ile kullanılır (DOĞRULANDI, server.py). Yan kazanç: port doluysa bağlanma kesin olarak hata verir, program da Türkçe "port kullanımda" iletisi gösterir. waitress'in ardından koyduğu `SO_REUSEADDR` denemesi `except OSError: pass` ile yutulur. ÇIKARIM, test edilmeli.

---

### 3. Windows Güvenlik Duvarı

#### Doğrulanmış davranış ([MS: Windows Firewall Rules](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/rules))
- İzin kuralı yoksa, program ilk kez dinlemeye başladığında bir iletişim kutusu çıkar.
- Yönetici "Hayır" derse ya da iptal ederse engelleme kuralları oluşur, "typically ... one each for TCP and UDP".
- **Yönetici olmayan kullanıcıda seçimden bağımsız olarak engelleme kuralı oluşur.** Kural silinmedikçe iletişim kutusu bir daha çıkmaz.
- **Engelleme kuralları çakışan izin kurallarından önce gelir.** Kurulumda eklenen izin kuralı, daha önce oluşmuş engelleme kuralını geçemez.
- Joker karakterli program yolu desteklenmez; tam yol gerekir. Uygulamanın yolu değişirse kural geçersiz olur ([comcomponent](https://comcomponent.com/en/blog/windows-firewall-business-apps/)).
- Önerilen yöntem: kuralı ilk açılıştan **önce**, kurulumda eklemek. "Private ve Public profilde remote address = Local Subnet" kısıtı önerilir.
- 127.0.0.1'e bağlanmak iletişim kutusunu tetiklemez, 0.0.0.0 tetikler ([cyclonedds #2090](https://github.com/eclipse-cyclonedds/cyclonedds/issues/2090)). Kelebekte hiç iletişim kutusu çıkmamasının sebebi budur. İkincil kaynak.
- İletişim kutusu dinleyen exe adına çıkar. PyInstaller onedir paketinde bu `kutuphane.exe` olur. ÇIKARIM.

#### Ağ profili
- Windows 11'de ağ profilini Genel'den Özel'e çevirmek **yönetici yetkisi ister** ([Pureinfotech](https://pureinfotech.com/change-network-profile-windows-11/), ikincil). Okul ağının Genel görünmesi olasıdır. ÇIKARIM.
- Kural yalnız `profile=private,domain` ile eklenirse Genel ağda çalışmaz ([comcomponent](https://comcomponent.com/en/blog/windows-firewall-business-apps/)).
- Öneri: `profile=domain,private,public` ve `remoteip=localsubnet`. Açılan yüzeyde kişisel veri olmadığı için Genel profilde de kabul edilebilir. Karar kullanıcının.
- Öğrenci Wi-Fi'si ayrı bir VLAN'daysa `localsubnet` onları dışarıda bırakır. Bu durumda kurala ek alt ağ (`remoteip=localsubnet,<ek-alt-ağ>` gibi) eklenmelidir. Okul ağı öğrenilmeli.

#### netsh sözdizimi (MS KB947709 örneklerinden)
Kural adı ASCII olmalı. netsh'in kod sayfası Türkçe karakterleri bozabilir; kelebek de bakım betiklerinde bu yüzden ASCII kullanıyor (`packaging/linux/postinst:3-5`).
```
netsh advfirewall firewall add rule name="Kutuphane Katalog" dir=in action=allow ^
  program="C:\Program Files\Kutuphane\kutuphane.exe" protocol=TCP localport=8765 ^
  remoteip=localsubnet profile=domain,private,public enable=yes
netsh advfirewall firewall delete rule name="Kutuphane Katalog"
```
Önceki bir iletişim kutusunun bıraktığı engelleme kurallarını temizlemek için: `netsh advfirewall firewall delete rule name=all dir=in program="...\kutuphane.exe"`, ardından yeniden `add`. ÇIKARIM: `name=all` ile program süzgecinin birlikte çalıştığı test edilmeli.

Kural tipi: program + TCP + port birlikte kullanılır. Yalnız port kuralı aynı portu dinleyen başka süreçlere de izin verir ([comcomponent](https://comcomponent.com/en/blog/windows-firewall-business-apps/)).

#### Inno Setup
- `PrivilegesRequiredOverridesAllowed=dialog` kurulumda "tüm kullanıcılar (yönetici) / yalnız ben" seçimini sunar ([Inno doc](https://jrsoftware.org/ishelp/topic_setup_privilegesrequiredoverridesallowed.htm)).
- [Run] satırlarında `postinstall` bayrağı yoksa, satır kurulumun (yükseltilmiş) kimliğiyle çalışır (`runascurrentuser`). `runhidden` bayrağı konsol penceresini gizler. [UninstallRun] için `RunOnceId` gerekir ([Inno Run](https://jrsoftware.org/ishelp/topic_runsection.htm)). DOĞRULANDI.
```
[Tasks]
Name: "agkatalog"; Description: "Yerel ağdan katalog taraması için güvenlik duvarı izni ekle"; Check: IsAdminInstallMode
[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=all dir=in program=""{app}\kutuphane.exe"""; Flags: runhidden waituntilterminated; Tasks: agkatalog
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""Kutuphane Katalog"" dir=in action=allow program=""{app}\kutuphane.exe"" protocol=TCP localport=8765 remoteip=localsubnet profile=domain,private,public enable=yes"; Flags: runhidden waituntilterminated; Tasks: agkatalog
[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Kutuphane Katalog"""; Flags: runhidden; RunOnceId: "FwKatalogSil"
```
- Yönetici kurulumu `Program Files`'a yazar. Kullanıcının yazabildiği `%LOCALAPPDATA%\Programs` yolundaki bir exe için izin kuralı açmaktan daha güvenlidir: oradaki exe'yi değiştiren herhangi bir süreç kuralı devralır. ÇIKARIM.
- Veri yine `%LOCALAPPDATA%`'da kalır, `paths.py` değişmez.

#### Açılış akışı
1. "Ağ paylaşımı" ayarı varsayılan olarak **KAPALI**.
2. Kullanıcı açınca program önce kural var mı diye bakar. `netsh ... show rule name="Kutuphane Katalog"` komutunun yönetici olmadan çalıştığı ÇIKARIM, test edilmeli.
3. Kural yoksa program **0.0.0.0'a bağlanmaz.** "Bilişim sorumlusu kurulumu yönetici olarak yenilemeli" yönlendirmesi gösterilir. Seçenek olarak yükseltilmiş bir yardımcı düğme sunulabilir: `ShellExecute "runas"` ile netsh çalıştırılır, UAC parola ister (ÇIKARIM).
4. Kural varsa dinleyici başlar. Ayar kapatılınca `server.close()` çağrılır. Hiçbir şey dinlemediği sürece kuralın durması zararsızdır.
5. Port ayardan değiştirilirse kural da değişmelidir. Bu yüzden port sabit kalmalı ve değişikliği yalnız yükseltilmiş yardımcı yapabilmelidir.

Ek not: bazı okullarda üçüncü parti antivirüs güvenlik duvarı Windows kurallarını yok sayar. Kurulum belgesine eklenmeli. ÇIKARIM.

---

### 4. İstemciler adresi nasıl bulur

| Yöntem | Durum | Sonuç |
|---|---|---|
| **IP + QR** | Her cihazda çalışır | **Birincil yöntem.** Program ekranında "Ağ adresi" kutusu ve QR gösterilir, A4 afiş basılır. PDF motoru (WeasyPrint) yığında zaten var (`logging_setup.py:97-100`). QR için saf Python `segno` kullanılabilir (ÇIKARIM) |
| DHCP'de IP değişmesi | Afiş bayatlar | Bilişim sorumlusundan **DHCP rezervasyonu** istenir. Program son basılan afişteki IP'yi saklar, açılışta IP değiştiyse "afişi yeniden basın" uyarısı verir. ÇIKARIM |
| Bilgisayar adı (NetBIOS/LLMNR) | Microsoft NetBIOS ve LLMNR'yi aşamalı olarak kapatıp mDNS'e geçiyor ([MS Tech Community](https://techcommunity.microsoft.com/blog/networkingblog/aligning-on-mdns-ramping-down-netbios-name-resolution-and-llmnr/3290816)). Tek etiketli adlarda mDNS devreye girmez ([comcomponent](https://comcomponent.com/en/blog/windows-name-resolution-order-hosts-dns-cache-llmnr-mdns-doh/)). Telefonlarda çalışmaz | Güvenilmez. "DESKTOP-4F7K2QX" gibi adlar da kullanışsız |
| mDNS `.local` | Android 12 ve sonrasında sistem çözücüsü `.local` adlarını çözüyor ([Esper](https://www.esper.io/blog/android-dessert-bites-26-mdns-local-47912385)). iOS'ta yerleşik. Windows 10/11'de yerleşik çözümleme var. Windows'un **kendi adını mDNS ile yayınladığı** ÇIKARIM, sahada denenmeli. mDNS yerel bağlantıyla sınırlıdır, **VLAN'lar arasında çalışmaz** | En fazla ikincil kolaylık. Python'dan `zeroconf` ile ad yayınlamak ek bir UDP 5353 kuralı, ad çakışması ve ek bağımlılık getirir. Faz 1'de önerilmez |
| Port | 8080/8000/5000/3000 yaygın geliştirme portları, çakışma riski var. 80 portu Linux'ta root ister, Windows'ta IIS/http.sys ile çakışabilir | Ayarlanabilir sabit port, varsayılan **8765**. IANA'da eski bir ürüne (ultraseek-http) kayıtlı, pratikte boş olması beklenir. `SO_EXCLUSIVEADDRUSE` ile çakışma kesin algılanır |
| Birden çok ağ arayüzü | Hyper-V, VirtualBox, VPN ve mobil erişim noktası sanal kartları yanlış IP gösterebilir | Varsayılan rotayı veren arayüzün IP'si alınır (UDP `connect` + `getsockname`, paket gönderilmez). 127/8 ve 169.254/16 atılır. Aday IP'ler listelenir, kütüphaneci seçer, seçim hatırlanır. ÇIKARIM |

HTTP tarayıcı davranışı: Chrome 154 (Ekim 2026) "Always Use Secure Connections" ayarını varsayılan olarak açıyor, ama yerel IP'ler ve tek etiketli adlar gibi **özel sitelerde uyarı göstermiyor** ([Google blog](https://blog.google/security/https-by-defau/)). DOĞRULANDI. `.local` adların "özel" sayılıp sayılmadığı ve standart dışı portlu IP'de HTTPS denemesinin geri düşüşü **test edilmeli** (ÇIKARIM). Bu da IP + QR önerisini güçlendirir.

---

### 5. Salt-okur katalog için güvenlik tasarımı

**Kişisel veri sıfır: alan izin listesi.** OYS modellerine göre:
- Açılabilir: `Work.title`, `authors`, `translator`, `edition`, `publisher`, `publish_year`, `isbn`, `subjects`, `classification_code`, `call_number`, `resource_type`, `language`; `Copy.shelf_location`, `status`, `is_reference`. DOĞRULANDI: `okulapp/backend/apps/kutuphane/models.py:252-301,358-381`.
- **Asla açılmaz:**
  - `Acquisition.source_note`: "Bağışçı/satıcı" serbest metni, bağışçı adı içerebilir (`models.py:201-207`)
  - `unit_price` (`:208`)
  - `Copy.external_asset_ref` (`:351-357`)
  - `accession_no` ve `barcode`: gereksiz
  - `Loan` ve `Membership` tablolarının tamamı
- Durum eşlemesi (`models.py:74-81`):
  - `AVAILABLE` → "Rafta"
  - `ON_LOAN` → "Ödünçte"
  - `IN_REPAIR` → "Geçici olarak kullanım dışı"
  - `is_reference` → "Yalnız kütüphanede okunur"
  - `LOST`, `WITHDRAWN_*`, `TRANSFERRED` → **listelenmez**

**İade tarihi:** `Loan.due_date` kişiye bağlı bir kaydın alanıdır (`models.py:722`). Varsayılan: **gösterilmez.** Açılırsa authorizer yalnız `due_date`, `copy_id` ve `status` sütunlarına izin verir. Karar maddesi.

**Diğer önlemler:**
- **Yalnız GET/HEAD**, diğer yöntemler 405. `q` en fazla 100 karakter. Sayfa boyutu sınırlı. Parametreli sorgu kullanılır, `%` ve `_` karakterleri `ESCAPE '\'` ile kaçırılır. Yol eşlemesi yalnız sabit bir sözlükle yapılır. Dosya sistemi yolu birleştirilmez, bu yüzden dizin geçişi olmaz. CSS bellekte gömülüdür. `WHITENOISE_ROOT` katalog sunucusuna **bağlanmaz** (`settings.py:173-174`).
- **Güvenlik başlıkları:** `Content-Security-Policy: default-src 'none'; style-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. JavaScript yok. Kitap adları Excel veya dış kaynaktan aktarılabildiği için kalıcı XSS'e karşı otomatik kaçırma şart.
- **Host ve DNS rebinding:** Yönetim ucu için mevcut model yeterli. Kötü bir sayfa 127.0.0.1'e yeniden bağlasa bile belirteç çerezi yalnız WebView2 profilinde `SameSite=Strict` olarak durur ve gönderilmez (`session_guard.py:78-85`). Yapılacak küçük iş: paketli yapıda `ALLOWED_HOSTS`'tan "backend"i çıkarmak (`settings.py:54`). Katalog tarafında sızacak veri olmadığı için Host denetimi isteğe bağlı: IP ve bilinen adlarla sınırlanabilir.
- **Hız sınırlama:** `REMOTE_ADDR` başına bellekte token-bucket, örneğin 5 istek/s ve 20 istekte patlama. Diske yazılmaz. `REMOTE_ADDR` güvenilir (§2).
- **Hata sayfaları:** `DEBUG=False` (`settings.py:49`), waitress `expose_tracebacks=False` varsayılan, `ident=None`. Katalogda sabit Türkçe 404/500 sayfaları. Açılışta "katalog portunda `/api/v1/...` isteği 404 dönmeli" diye kendi kendini denetler; dönmezse dinleyiciyi kapatır. Bu, `server.py:172-206`'daki kalıbın aynısı.
- **Günlük:** erişim günlüğü yok. IP ya da arama terimi yazılmaz. Arama terimleri okuma ilgisini, dolayısıyla özel nitelikli veriyi ele verebilir. IP, başka verilerle birleşince kişiyi belirlenebilir kılar (ÇIKARIM; KVK Kurulu dayanağı gösterilmedi). En fazla kişisiz günlük sayaçlar tutulur.
- **TLS:** Yerel ağda ve kişisel veri yokken HTTP kabul edilebilir (ÇIKARIM). Adres çubuğunda "Güvenli değil" ibaresi görünür; Chrome yerel IP için ayrıca uyarı sayfası göstermez (§4).
- **Kod imzası:** İmzasız ve ağı dinleyen bir exe'ye antivirüs sezgisel tepki verebilir. Kelebek bunu v2 işi olarak not etmiş (`packaging/windows/NOTLAR.md:61-64`).

---

### 6. Program kapalıyken erişim

| Seçenek | Karmaşıklık | Sorunlar | Karar |
|---|---|---|---|
| Yalnız program açıkken | Yok | Kütüphaneci kapatınca katalog da kapanır | **Faz 1** |
| (a) Sistem tepsisi | Orta | pywebview'da `closing` işleyicisi False dönerse kapanma iptal olur. `hide()`/`show()` ve `hidden` parametresi var ([pywebview API](https://pywebview.flowrl.com/api/)). Tepsi simgesi için `pystray` (Windows) ya da Qt `QSystemTrayIcon` (Linux; Linux'ta Qt kullanılıyor, `window.py:87`). **Tek kopya kilidiyle çatışma:** ikinci açılış şu an "zaten çalışıyor" hatası veriyor (`lock.py:31`). Tepside gizliyken bu kafa karıştırır, var olan pencereyi öne getiren bir kanal gerekir. Güncellemede `AppMutex` kurucuyu durdurur (`.iss:66`), tepsiden "Çık" gerekir | Faz 2 |
| (c) Oturum açılışında başlat | Düşük | HKCU `Run` ya da `{userstartup}` kısayolu + `--tepside` parametresi. Yönetici gerekmez. Yalnız oturum açıkken çalışır | Faz 2, (a) ile birlikte |
| (b) Windows hizmeti (pywin32/NSSM) | **Yüksek** | Hizmet oturum 0'da, farklı bir hesapla çalışır: `%LOCALAPPDATA%` farklı olur, verinin `ProgramData`'ya taşınması ve ACL ayarı gerekir (`paths.py:114-123`). Program ve hizmet iki ayrı süreç olur (WAL aynı makinede buna izin verir), kilit modeli yeniden tasarlanır. Yönetici kurulumu gerekir. NSSM üçüncü parti bir ikili dosyadır. ÇIKARIM | **Önerilmez** |

---

### 7. İsteğe bağlı genişlemeler: ayrı faz ve ayrı karar olmalı

"Kendi ödünçlerimi gör" ve ayırtma (rezervasyon) özellikleri **kimlik doğrulama** gerektirir. Bunların nedenleri:
- Kart numarası + doğum tarihi zayıf bir ikilidir. Numaralar sıralı ve tahmin edilebilir, doğum tarihini sınıf arkadaşları bilir. Sonuç: başkasının okuma geçmişini görme riski.
- HTTP üzerinden kimlik bilgisi okul Wi-Fi'sinde dinlenebilir. TLS gerekir. Kendinden imzalı sertifika her cihazda uyarı çıkarır; yerel bir CA dağıtmak okulda zordur.
- "Kişisel veri sıfır" varsayımı çöker. KVKK md. 12 güvenlik tedbirleri, günlük tutma, aydınlatma metni, deneme sınırlama ve oturum yönetimi devreye girer. Bu bölümün (§2-5) bütün "düşük risk" gerekçesi ortadan kalkar.
- Kimliksiz ayırtma kötüye kullanıma açıktır. Kütüphaneci onaylı "talep" daha az risklidir.

Öneri: Faz 1'in dışında tutulsun. İstenirse ayrı bir risk değerlendirmesiyle ele alınsın.

---

### 8. Linux (.deb)

- Kelebekte `postinst` güvenlik duvarına dokunmuyor ve ASCII yazılmış (`packaging/linux/postinst:1-21`).
- **ufw:** Paket `/etc/ufw/applications.d/kutuphane` profili bırakır (`title=`, `description=`, `ports=8765/tcp`). Kural otomatik açılmaz; `ufw app default` zaten `skip` ([ufw man](https://manpages.ubuntu.com/manpages/noble/en/man8/ufw.8.html)). Kullanıcıya gösterilecek komut: `sudo ufw allow from 192.168.1.0/24 to any app Kutuphane`.
- ufw'nin Pardus'ta varsayılan olarak kurulu ya da açık olmadığı yönünde **zayıf bir kaynak** var (arama özeti, Pardus sunucu bağlamı). Sahada `systemctl is-active ufw` ile denetlenmeli. ÇIKARIM.
- **firewalld:** `/usr/lib/firewalld/services/kutuphane.xml` bırakılır; `firewall-cmd --permanent --add-service=kutuphane`. ÇIKARIM.
- **avahi:** `avahi-daemon` kuruluysa `makine-adı.local` zaten yayınlanır. `/etc/avahi/services/kutuphane.service` ile `_http._tcp` DNS-SD kaydı eklenebilir ama tarayıcılar DNS-SD taramaz, getirisi düşük. ÇIKARIM.
- 1024'ün altındaki portlar root ister, 8765 sorunsuz. Linux'ta yetki iletişim kutusu yok. Uygulama içi "ağ paylaşımı" anahtarı aynı şekilde çalışır.
- Etkileşimli tahtalar (Pardus ETAP) Chromium tabanlı tarayıcıyla bu sayfayı açabilir. Ancak tahtaların hangi VLAN'da olduğu bilinmiyor. ÇIKARIM.

---

### 9. Gözden kaçabilecek hususlar

1. **Türkçe arama SQLite'ta bozulur.** OYS PostgreSQL kullanıyor (`okulapp/backend/config/settings/base.py:227`) ve `icontains` ile arıyor (`kutuphane/selectors.py:47-55`). SQLite'ta `LIKE` yalnız ASCII için büyük/küçük harf duyarsız; "æ LIKE Æ" FALSE ([sqlite lang_expr](https://www.sqlite.org/lang_expr.html)). DOĞRULANDI. "çocuk/Çocuk", "ı/I/İ" eşleşmez. Çözüm: `search_key` sütununda Türkçe katlama (İ/I/ı→i, ş→s, ç→c, ğ→g, ö→o, ü→u) ve sorguya da aynı katlama uygulanır. Hem yönetim aramasını hem katalog aramasını etkiler.
2. **Geri yükleme ile katalog bağlantıları** (§2): Windows'ta açık bağlantı dosya değişimini bozar.
3. **Uygulama parolası ve kilit:** Kelebekte isteğe bağlı açılış parolası var (`settings.py:91-94`). Program kilitliyken katalog yayında kalsın mı? Kişisel veri yoksa kalabilir, ama bu bir karar.
4. **Okul ağının yapısı:** öğrenci Wi-Fi'sinde istemci yalıtımı ya da ayrı VLAN olabilir, tahtalar ayrı ağda olabilir. Bunlar `localsubnet` kuralını ve mDNS'i boşa çıkarabilir. Kurulum öncesi bilişim sorumlusuyla bir ağ keşfi yapılmalı. ÇIKARIM.
5. Öğrencilerin telefonla bağlanıp bağlanamayacağı okulun cep telefonu kurallarına bağlı. Mevzuat bu çalışmada doğrulanmadı; kullanıcıya sorulmalı.
6. **Yönetici gerektiren kurulum** kelebek/DD'deki "yönetici gerekmez" ilkesinden ayrılıyor (`.iss:7-9`). Ağ özelliği olmadan yönetici gerektirmeyen kurulum yine mümkün olmalı.
7. Ağ katmanı test edilmeli:
   - yönetim sunucusu 127.0.0.1 dışına bağlanamamalı;
   - bütün yönetim URL'leri katalog portunda 404 dönmeli;
   - katalog modülü `Loan` ve `Membership` modellerini import etmemeli, authorizer bu tablolara `DENY` vermeli.

---

### 10. Kullanıcıya sorulacak kararlar

1. Katalogla kimler bağlanacak: öğrenci telefonları, sınıf tahtaları, öğretmenler odası bilgisayarları? Bunlar kütüphane bilgisayarıyla aynı alt ağda mı?
2. Kurulumda bir kez yönetici (bilişim sorumlusu) desteği alınabilir mi? Güvenlik duvarı kuralı ve `Program Files` kurulumu buna bağlı.
3. Ağ profili Genel ise kural Genel profili de kapsasın mı (yalnız yerel alt ağla sınırlı), yoksa bilişim sorumlusu ağı Özel'e mi çevirsin?
4. "Ödünçte" yanında iade tarihi gösterilsin mi? Varsayılan: hayır.
5. Katalog canlı veritabanını görünüm + authorizer ile mi okusun, yoksa ayrı bir anlık katalog dosyasını mı? İkincisi fiziksel ayrım sağlar ama daha çok kod ister.
6. Faz 1'de "yalnız program açıkken" yeterli mi? Tepsi ve otomatik başlatma Faz 2'ye kalsın mı?
7. Öğrencinin kendi ödünçlerini görmesi ve ayırtma: ayrı faz olarak ertelensin mi? Önerilen: evet.
8. Varsayılan port 8765 uygun mu, ve DHCP rezervasyonu istenebilir mi?

**Kaynaklar:** [waitress arguments](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html) · [waitress design](https://docs.pylonsproject.org/projects/waitress/en/stable/design.html) · [waitress server.py](https://raw.githubusercontent.com/Pylons/waitress/main/src/waitress/server.py) · [waitress task.py](https://raw.githubusercontent.com/Pylons/waitress/main/src/waitress/task.py) · [waitress wasyncore.py](https://raw.githubusercontent.com/Pylons/waitress/main/src/waitress/wasyncore.py) · [SQLite WAL](https://www.sqlite.org/wal.html) · [SQLite LIKE](https://www.sqlite.org/lang_expr.html) · [Python sqlite3](https://docs.python.org/3/library/sqlite3.html) · [Django sqlite3 base.py](https://raw.githubusercontent.com/django/django/stable/5.2.x/django/db/backends/sqlite3/base.py) (`uri=True`, `check_same_thread=False` her zaman) · [MS Windows Firewall Rules](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/rules) · [MS netsh advfirewall KB947709](https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/netsh-advfirewall-firewall-control-firewall-behavior) · [MS SO_EXCLUSIVEADDRUSE](https://learn.microsoft.com/en-us/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse) · [Rebex: Cancel on firewall alert](https://blog.rebex.net/beware-pressing-cancel-on-windows-firewall-security-alert) · [comcomponent firewall](https://comcomponent.com/en/blog/windows-firewall-business-apps/) · [comcomponent name resolution](https://comcomponent.com/en/blog/windows-name-resolution-order-hosts-dns-cache-llmnr-mdns-doh/) · [cyclonedds #2090](https://github.com/eclipse-cyclonedds/cyclonedds/issues/2090) · [MS: Aligning on mDNS](https://techcommunity.microsoft.com/blog/networkingblog/aligning-on-mdns-ramping-down-netbios-name-resolution-and-llmnr/3290816) · [Esper: Android mDNS](https://www.esper.io/blog/android-dessert-bites-26-mdns-local-47912385) · [Google: HTTPS by default](https://blog.google/security/https-by-defau/) · [Inno PrivilegesRequiredOverridesAllowed](https://jrsoftware.org/ishelp/topic_setup_privilegesrequiredoverridesallowed.htm) · [Inno Run/UninstallRun](https://jrsoftware.org/ishelp/topic_runsection.htm) · [pywebview API](https://pywebview.flowrl.com/api/) · [ufw man](https://manpages.ubuntu.com/manpages/noble/en/man8/ufw.8.html) · [Pureinfotech: network profile](https://pureinfotech.com/change-network-profile-windows-11/) · [IANA port 8765](https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml?search=8765)

