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

- **Automatyczna** — ustaw `date_end` i po tej dacie wpis znika z głównej listy i trafia do archiwum (dostępnego przez przycisk na podstronie)
- **Ręczna** — ustaw `"archived": true`

---

## Formspree

Formularz zgłoszeń jest podpięty pod endpoint `xnjrzdnz`.  
Zgłoszenia przychodzą na e-mail — po weryfikacji edytujesz `news.json` ręcznie i pushujesz.

---

## Deploy na GitHub Pages

```bash
git add .
git commit -m "update news.json"
git push origin main
```

Strona odświeża się automatycznie po ~1 minucie.

---

## Ekosystem biokoderka

| Strona | Link |
|--------|------|
| 🧬 BioInfoNews | [biokoderka.github.io/bioinfo-news](https://biokoderka.github.io/bioinfo-news) |
| 💼 BioInfoJobs | [biokoderka.github.io/bioinfo-jobs](https://biokoderka.github.io/bioinfo-jobs) |
| 🎓 BioInfoUni | [biokoderka.github.io/bioinfo-uni](https://biokoderka.github.io/bioinfo-uni) |
