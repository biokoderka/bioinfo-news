# 🧬 bioinfo-news

Tablica ogłoszeń dla społeczności bioinformatycznej w Polsce.    

🔗 **Live:** [biokoderka.github.io/bioinfo-news](https://biokoderka.github.io/bioinfo-news)

---

## Struktura strony

Strona główna pokazuje top 3 najbliższe wpisy z każdej sekcji.  
Każda sekcja ma własną podstronę z pełną listą, wyszukiwarką i archiwum.

| Plik | Sekcja |
|------|--------|
| `index.html` | Strona główna (hub) |
| `meetups.html` | 🤝 Meetupy i wydarzenia |
| `courses-dated.html` | 🗓 Kursy z terminem |
| `courses-free.html` | 📚 Kursy stałe i zasoby |
| `projects.html` | 🌿 Projekty do współpracy |
| `other.html` | ✦ Inne inicjatywy |
| `submit.html` | Formularz zgłoszeń (Formspree) |
| `research.html` | 📄 Newsy badawcze + archiwum miesięczne |
| `news.json` | Dane — tu edytujesz wpisy |

---

## Jak dodać wpis

Otwórz `news.json` i dodaj obiekt do tablicy `entries`:

```json
{
  "id": "2026-010",
  "type": "meetup",
  "title": "BioInfo Wrocław Meetup #1",
  "org": "Społeczność lokalna",
  "description": "Pierwsze spotkanie bioinformatyków we Wrocławiu. Dwie prezentacje i networking.",
  "url": "https://example.com",
  "free": true,
  "lang": "🇵🇱 PL",
  "location": "Wrocław",
  "date_start": "2026-09-20",
  "date_end": "2026-09-20",
  "archived": false,
  "added": "2026-05-23"
}
```

### Typy wpisów (`type`)

| Wartość | Sekcja |
|---------|--------|
| `meetup` | Meetupy i wydarzenia |
| `course-dated` | Kursy z konkretnym terminem |
| `course-free` | Kursy stałe / platformy bez terminu |
| `project` | Projekty do współpracy |
| `other` | Hackathony, konkursy, inne |

### Wszystkie pola

| Pole | Opis | Wymagane |
|------|------|----------|
| `id` | Unikalny string, np. `2026-010` | ✅ |
| `type` | Jedna z wartości powyżej | ✅ |
| `title` | Tytuł wpisu | ✅ |
| `description` | Opis 2–4 zdania | ✅ |
| `added` | Data dodania `YYYY-MM-DD` | ✅ |
| `archived` | `false` domyślnie | ✅ |
| `org` | Organizacja / prowadzący | — |
| `url` | Link do strony | — |
| `free` | `true` jeśli bezpłatne | — |
| `lang` | np. `🇵🇱 PL` lub `🇬🇧 EN` | — |
| `location` | Miasto lub `Online` | — |
| `date_start` | Data rozpoczęcia `YYYY-MM-DD` | — |
| `date_end` | **Po tej dacie wpis trafia do archiwum automatycznie** | — |
| `deadline` | Deadline zgłoszeń `YYYY-MM-DD` | — |

### Archiwizacja

- **Automatyczna** — ustaw `date_end`; wpis jest aktywny do końca tego dnia, potem trafia do archiwum (przycisk na podstronie)
- **Ręczna** — ustaw `"archived": true` albo użyj akcji **Add entry → archive_id**
- Wydarzenie (`meetup`, `course-dated`) bez żadnej daty nigdy nie zniknie samo — walidacja to zgłasza

---

## Dodawanie wpisów

Zgłoszenia z `submit.html` przychodzą mailem przez Formspree (endpoint `xnjrzdnz`). Na końcu maila jest pole **`admin_json`**.

1. Sprawdź zgłoszenie; popraw opis albo daty bezpośrednio w `admin_json`.
2. GitHub → **Actions → Add entry → Run workflow** → wklej `admin_json` w pole **entry_json**.
3. id (`ROK-NNN`) i data dodania nadają się same. Po ok. minucie wpis jest na stronie.

Ręczna edycja `news.json` dalej działa — po każdym pushu workflow sprawdza plik (zdublowane id, format dat, linki). Lokalnie: `python3 scripts/add_entry.py --check`.

---

## Newsy badawcze (automatyczne)

`fetch_news.py` uruchamia się codziennie o 6:00 UTC (GitHub Actions) i pobiera: bioRxiv, medRxiv, Europe PMC (wybrane czasopisma), arXiv q-bio, GitHub Releases, PyPI, Nauka w Polsce, NIH RePORTER (granty) i Zenodo.

| Plik | Zawartość |
|------|-----------|
| `research-news.json` | ostatnie 30 dni — to ładują strony |
| `archive/research-RRRR-MM.json` | **wszystkie** pobrane wpisy z danego miesiąca, na zawsze |
| `archive/index.json` | lista miesięcy dla przełącznika archiwum na `research.html` |

Wpisy dostają tagi tematyczne słownikowo (`CATEGORY_KEYWORDS` w `fetch_news.py`) i typ artykułu (przeglądowy, benchmark…). Wpisy bez linku są pomijane. Jeśli wszystkie źródła danego dnia zawiodą, pliki zostają bez zmian.

---

## Pliki front-endu

| Plik | Rola |
|------|------|
| `assets/common.js` | wspólne funkcje: karty, daty, tagi, escapowanie danych |
| `assets/section.js` | logika pięciu podstron sekcji (typ z `data-type` w tagu `<script>`) |
| `index.html`, `research.html` | strona główna i newsy |

---

## Ekosystem biokoderka

| Strona | Link |
|--------|------|
| 🧬 BioinfoSites | [biokoderka.github.io/bioinfosites](https://biokoderka.github.io/bioinfosites/) |
| 🧬 BioInfoNews | [biokoderka.github.io/bioinfo-news](https://biokoderka.github.io/bioinfo-news) |
| 💼 BioInfoJobs | [biokoderka.github.io/bioinfo-jobs](https://biokoderka.github.io/bioinfo-jobs) |
| 🎓 BioInfoUni | [biokoderka.github.io/bioinfo-uni](https://biokoderka.github.io/bioinfo-uni) |
