"""
BioInfoNews — pobieranie realnych newsów badawczych/narzędziowych z bioinformatyki.

Źródła:
  - bioRxiv API      (preprinty, kategoria bioinformatics)         -> api.biorxiv.org
  - Europe PMC API   (opublikowane artykuły z wybranych czasopism) -> www.ebi.ac.uk
  - GitHub Releases  (nowe wersje kluczowych narzędzi)             -> api.github.com

Uwaga o środowisku:
  bioRxiv i Europe PMC są blokowane w sandboxie Claude (egress allowlist),
  dlatego ten skrypt trzeba uruchomić w środowisku z pełnym dostępem do
  internetu — lokalnie albo (zalecane) w GitHub Actions, patrz
  .github/workflows/fetch-research-news.yml w tym samym folderze.
  Zapytania do GitHub API i PyPI zostały już przetestowane i działają.

Wyjście: research-news.json — osobny plik, w formacie zgodnym ze
  strukturą Twojego istniejącego news.json (żeby łatwo było go scalić
  z istniejącymi wpisami albo renderować obok nich).
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

USER_AGENT = "BioInfoNews-fetcher/1.0 (+https://biokoderka.github.io/bioinfo-news/)"

# Opcjonalny token GitHub — bez niego limit to 60 zapytan/h (latwo go
# wyczerpac przy 10 repo x kilka wywolan). W GitHub Actions ustaw sekret
# GITHUB_TOKEN (workflow ponizej robi to automatycznie) -> limit 5000/h.
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ---------------------------------------------------------------------------
# Kategorie tematyczne i słowa kluczowe do prostego tagowania (bez LLM).
# Wpis może dostać kilka tagów. Rozszerzone słowniki, żeby "inne" trafiało
# się rzadko — nowe kategorie: transkryptomika, mikrobiom, epidemiologia,
# ewolucja/filogenetyka.
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "genomika":         ["genome", "genomic", "variant", "sequencing", "wgs", "wes", "snp",
                          "structural variant", "copy number", "assembly", "pangenome",
                          "long-read", "nanopore", "pacbio"],
    "single-cell":      ["single-cell", "single cell", "scrna", "spatial transcriptomics",
                          "scanpy", "cell atlas", "cell type annotation"],
    "transkryptomika":  ["rna-seq", "transcriptom", "differential expression", "splicing",
                          "gene expression"],
    "proteomika":       ["proteomic", "mass spectrometry", "protein-protein interaction",
                          "post-translational"],
    "mikrobiom":        ["microbiome", "metagenom", "16s rrna", "microbial community"],
    "ai-ml":            ["deep learning", "neural network", "machine learning", "transformer",
                          "large language model", " llm ", "diffusion model", "foundation model",
                          "generative model", "embedding"],
    "struktury":        ["protein structure", "alphafold", "esmfold", "folding", "docking",
                          "cryo-em", "molecular dynamics", "protein design"],
    "leki":             ["drug discovery", "compound", "inhibitor", "virtual screening", "admet",
                          "drug target", "pharmacogenom"],
    "epidemiologia":    ["epidemiolog", "outbreak", "surveillance", "phylodynamic", "pandemic"],
    "ewolucja":         ["phylogen", "evolution", "selection pressure", "comparative genomic"],
    "narzedzia":        ["tool", "package", "software", "pipeline", "workflow", "webserver",
                          "release"],
    "bazy-danych":      ["database", "repository", "api release", "data standard", "resource"],
}
FALLBACK_TAG = "inne"

# ---------------------------------------------------------------------------
# Typ artykułu — osobny wymiar od tematu: co ten tekst *jest*, nie o czym jest.
# Klasyfikacja heurystyczna po tytule/abstrakcie; sprawdzana w tej kolejności,
# pierwsze trafienie wygrywa (przeglądowy i benchmark są bardziej specyficzne
# niż domyślne "eksperymentalne", więc sprawdzamy je najpierw).
# ---------------------------------------------------------------------------
ARTICLE_TYPE_KEYWORDS = [
    ("przeglad",       ["review", "systematic review", "survey of", "meta-analysis", "we review"]),
    ("benchmark",      ["benchmark", "comparison of", "comparative evaluation", "we compare",
                         "performance evaluation"]),
    ("protokol",       ["protocol", "step-by-step", "methodology for", "best practices for"]),
    ("narzedzie-art",  ["we present", "we introduce", "new tool", "novel software", "new package",
                         "new method for", "open-source tool", "we developed"]),
]
ARTICLE_TYPE_LABELS = {
    "przeglad":      "📖 przeglądowy",
    "benchmark":     "📊 benchmark",
    "protokol":      "🧾 protokół",
    "narzedzie-art": "🔧 opis narzędzia",
    "eksperymentalne": "🧪 eksperymentalny",
}

JOURNAL_QUERIES = {
    "Bioinformatics (OUP)": 'JOURNAL:"Bioinformatics" AND (FIRST_PDATE:[{start} TO {end}])',
    "Genome Biology": 'JOURNAL:"Genome Biology" AND (FIRST_PDATE:[{start} TO {end}])',
    "Nucleic Acids Research": 'JOURNAL:"Nucleic Acids Research" AND (FIRST_PDATE:[{start} TO {end}])',
    "PLOS Computational Biology": 'JOURNAL:"PLoS computational biology" AND (FIRST_PDATE:[{start} TO {end}])',
}

GITHUB_REPOS = [
    "Bioconductor/BiocManager",
    "samtools/samtools",
    "broadinstitute/gatk",
    "nextflow-io/nextflow",
    "snakemake/snakemake",
    "pysam-developers/pysam",
    "scverse/scanpy",
    "deepmind/alphafold",
    "facebookresearch/esm",
    "COMBINE-lab/salmon",
]


def http_get_json(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tag_entry(title, summary):
    text = f"{title} {summary}".lower()
    tags = []
    for tag, keywords in CATEGORY_KEYWORDS.items():
        if any(k in text for k in keywords):
            tags.append(tag)
    return tags or [FALLBACK_TAG]


def classify_article_type(title, summary):
    text = f"{title} {summary}".lower()
    for art_type, keywords in ARTICLE_TYPE_KEYWORDS:
        if any(k in text for k in keywords):
            return art_type
    return "eksperymentalne"  # domyslny typ dla oryginalnych badan/preprintow


# ---------------------------------------------------------------------------
# 1) bioRxiv — preprinty z ostatnich N dni
# ---------------------------------------------------------------------------
def fetch_biorxiv(days_back=7, max_pages=3):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days_back)
    entries = []
    cursor = 0
    for _ in range(max_pages):
        url = f"https://api.biorxiv.org/details/biorxiv/{start}/{end}/{cursor}"
        try:
            data = http_get_json(url)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"[bioRxiv] blad pobierania: {e}", file=sys.stderr)
            break

        collection = data.get("collection", [])
        if not collection:
            break

        for item in collection:
            category = (item.get("category") or "").lower()
            if "bioinformatic" not in category:
                continue  # interesuje nas tylko kategoria bioinformatics
            title = item.get("title", "").strip()
            abstract = item.get("abstract", "").strip()
            doi = item.get("doi", "")
            entries.append({
                "type": "research",
                "source": "bioRxiv",
                "title": title,
                "description": (abstract[:280] + "…") if len(abstract) > 280 else abstract,
                "url": f"https://doi.org/{doi}" if doi else "",
                "date": item.get("date", ""),
                "tags": tag_entry(title, abstract),
                "article_type": classify_article_type(title, abstract),
            })

        messages = data.get("messages", [{}])
        total = int(messages[0].get("total", 0)) if messages else 0
        cursor += len(collection)
        if cursor >= total:
            break
        time.sleep(1)  # uprzejmość wobec API

    return entries


# ---------------------------------------------------------------------------
# 2) Europe PMC — opublikowane artykuły z wybranych czasopism
# ---------------------------------------------------------------------------
def fetch_europepmc(days_back=7, page_size=15):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days_back)
    entries = []

    for journal_name, query_template in JOURNAL_QUERIES.items():
        query = query_template.format(start=start.isoformat(), end=end.isoformat())
        url = (
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            f"?query={urllib.parse.quote(query)}"
            f"&format=json&pageSize={page_size}&sort=P_PDATE_D+desc"
        )
        try:
            data = http_get_json(url)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"[EuropePMC] blad pobierania dla {journal_name}: {e}", file=sys.stderr)
            continue

        for item in data.get("resultList", {}).get("result", []):
            title = item.get("title", "").strip()
            abstract = item.get("abstractText", "").strip()
            doi = item.get("doi", "")
            entries.append({
                "type": "research",
                "source": journal_name,
                "title": title,
                "description": (abstract[:280] + "…") if len(abstract) > 280 else abstract,
                "url": f"https://doi.org/{doi}" if doi else item.get("fullTextUrlList", {}),
                "date": item.get("firstPublicationDate", ""),
                "tags": tag_entry(title, abstract),
                "article_type": classify_article_type(title, abstract),
            })
        time.sleep(0.5)

    return entries


# ---------------------------------------------------------------------------
# 3) GitHub Releases — nowe wersje kluczowych narzędzi bioinformatycznych
# ---------------------------------------------------------------------------
def fetch_github_releases(days_back=14):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    entries = []

    for repo in GITHUB_REPOS:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=3"
        gh_headers = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            gh_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        try:
            releases = http_get_json(url, headers=gh_headers)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"[GitHub] blad pobierania dla {repo}: {e}", file=sys.stderr)
            continue

        if not isinstance(releases, list):
            continue

        for rel in releases:
            published = rel.get("published_at")
            if not published:
                continue
            pub_dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if pub_dt < cutoff:
                continue
            title = f"{repo.split('/')[-1]} {rel.get('tag_name', '')}"
            body = (rel.get("body") or "").strip()
            body_short = re.sub(r"\s+", " ", body)[:280]
            entries.append({
                "type": "narzedzie",
                "source": f"GitHub · {repo}",
                "title": title,
                "description": body_short,
                "url": rel.get("html_url", ""),
                "date": pub_dt.date().isoformat(),
                "tags": tag_entry(title, body) + ["narzedzia"],
            })
        time.sleep(0.3)

    return entries


def dedupe(entries):
    seen = set()
    unique = []
    for e in entries:
        key = e["title"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    return unique


def main():
    all_entries = []
    print("Pobieram z bioRxiv...", file=sys.stderr)
    all_entries += fetch_biorxiv()
    print("Pobieram z Europe PMC...", file=sys.stderr)
    all_entries += fetch_europepmc()
    print("Pobieram release'y z GitHub...", file=sys.stderr)
    all_entries += fetch_github_releases()

    all_entries = dedupe(all_entries)
    all_entries.sort(key=lambda e: e.get("date", ""), reverse=True)

    for i, e in enumerate(all_entries, start=1):
        e["id"] = f"research-{datetime.now(timezone.utc).year}-{i:03d}"

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entries": all_entries,
    }

    with open("research-news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Zapisano {len(all_entries)} wpisow do research-news.json", file=sys.stderr)


if __name__ == "__main__":
    main()
