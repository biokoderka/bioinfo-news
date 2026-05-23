# 🧬 bioinfo-news

Tablica ogłoszeń dla społeczności bioinformatycznej w Polsce.  
Prowadzona przez [@biokoderka](https://instagram.com/biokoderka).

## Kategorie wpisów

| Typ | Opis |
|-----|------|
| `project` | Otwarte projekty do współpracy / collaboracje |
| `course-free` | Darmowe kursy stałe (platformy, zasoby bez terminu) |
| `course-dated` | Kursy z konkretnym terminem / edycją |
| `meetup` | Meetupy, konferencje, warsztaty |
| `other` | Inne — hackathony, inicjatywy, itp. |

## Struktura plików

```
bioinfo-news/
├── index.html      — strona główna
├── submit.html     — formularz zgłoszeń (Formspree)
├── news.json       — dane (edytujesz ręcznie)
└── README.md
```

## Jak dodać wpis (ręcznie)

Otwórz `news.json` i dodaj obiekt do tablicy `entries`:

```json
{
  "id": "2025-007",
  "type": "meetup",
  "title": "BioInfo Wrocław Meetup #1",
  "org": "Społeczność lokalna",
  "description": "Pierwsze spotkanie bioinformatyków we Wrocławiu. Dwie prezentacje + networking.",
  "url": "https://example.com",
  "free": true,
  "lang": "🇵🇱 PL",
  "location": "Wrocław",
  "date_start": "2025-09-20",
  "date_end": "2025-09-20",
  "archived": false,
  "added": "2025-08-01"
}
```

### Archiwizacja wpisu

- **Automatyczna** — jeśli wpis ma `date_end` i ta data minęła, wpis trafia do archiwum bez edycji
- **Ręczna** — ustaw `"archived": true`

## Formspree — konfiguracja

1. Wejdź na [formspree.io](https://formspree.io) i utwórz formularz
2. Skopiuj swój endpoint, np. `https://formspree.io/f/xpwzqabc`
3. W `submit.html` zamień:
   ```html
   action="https://formspree.io/f/TWÓJ_FORMSPREE_ID"
   ```
   na swój endpoint

Zgłoszenia będą przychodzić na Twój e-mail. Następnie ręcznie edytujesz `news.json` i pushujesz.

## Deploy na GitHub Pages

```bash
# Utwórz repo bioinfo-news na GitHub
git init
git add .
git commit -m "init bioinfo-news"
git branch -M main
git remote add origin https://github.com/biokoderka/bioinfo-news.git
git push -u origin main
```

W ustawieniach repo: **Settings → Pages → Source: main branch / root**.

Strona będzie dostępna pod: `https://biokoderka.github.io/bioinfo-news/`
