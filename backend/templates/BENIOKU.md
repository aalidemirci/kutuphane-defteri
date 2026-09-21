# Evrak şablonları

KS'den alındı (KS bunları OYS'den AYNEN taşımıştı):

- `print/_design.css` — "Kurumsal Sade" baskı tasarım dili (bayt-eş kopya).
  `base.html` içine Django `{% include %}` ile gömülür; `text-transform`
  YASAK, DejaVu Sans, `--pr-*` token'ları.
- `documents/base.html` — ortak resmî evrak tabanı (antet `shared.letterhead`
  üzerinden). Kütüphane evrakı (tasarım §10) bu tabanı `extends` eder.

PyInstaller spec bu ağacı pakete kaynak olarak kopyalar.
