"""
BioInfoNews — pobieranie realnych newsów badawczych/narzędziowych z bioinformatyki.

Źródła:
  - bioRxiv API       (preprinty, 6 kategorii)                      -> api.biorxiv.org
  - Europe PMC API    (opublikowane artykuły z 9 czasopism)         -> www.ebi.ac.uk
  - GitHub Releases   (nowe wersje 18 narzędzi)                     -> api.github.com
  - PyPI              (nowe wersje pakietów pythonowych)            -> pypi.org
  - Nauka w Polsce/PAP (kategoria "Życie", filtrowana słowami kluczowymi) -> naukawpolsce.pl

Uwaga o środowisku:
  bioRxiv, Europe PMC i Nauka w Polsce są blokowane w sandboxie Claude
  (egress allowlist), dlatego ten skrypt trzeba uruchomić w środowisku
  z pełnym dostępem do internetu — lokalnie albo (zalecane) w GitHub
  Actions, patrz .github/workflows/fetch-research-news.yml w tym samym
  folderze. Zapytania do GitHub API i PyPI zostały przetestowane i działają
  z tego sandboxa.

Wyjście: research-news.json — osobny plik, w formacie zgodnym ze
  strukturą Twojego istniejącego news.json (żeby łatwo było go scalić
  z istniejącymi wpisami albo renderować obok nich).
"""

import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER_AGENT = "BioInfoNews-fetcher/1.0 (+https://biokoderka.github.io/bioinfo-news/)"

# Opcjonalny token GitHub — bez niego limit to 60 zapytan/h (latwo go
# wyczerpac przy kilkunastu repo x kilka wywolan). W GitHub Actions ustaw
# sekret GITHUB_TOKEN (workflow ponizej robi to automatycznie) -> limit 5000/h.
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
                          "long-read", "nanopore", "pacbio", "sequence alignment",
                          "read alignment", "genome alignment", "partial order alignment",
                          "chromatin", "enhancer", "epigenom", "3d genome", "hi-c"],
    "single-cell":      ["single-cell", "single cell", "scrna", "spatial transcriptomics",
                          "scanpy", "cell atlas", "cell type annotation"],
    "transkryptomika":  ["rna-seq", "transcriptom", "differential expression", "splicing",
                          "gene expression", "mirna", "microrna", "non-coding rna", "ncrna",
                          "epitranscriptom", "rna modification", "m6a", "m1a"],
    "proteomika":       ["proteomic", "mass spectrometry", "protein-protein interaction",
                          "post-translational", "protein panel", "biomarker panel",
                          "diagnostic biomarker"],
    "mikrobiom":        ["microbiome", "metagenom", "16s rrna", "microbial community"],
    "immunoinformatyka":["antibody", "antibodies", "epitope", "mhc", "hla", "tcr", "bcr",
                          "immunogenicity", "vaccine design", "nanobody", "affinity maturation",
                          "cdr loop", "paratope", "t cell receptor", "cdr contacts",
                          "cdr region"],
    "sieci-systemy":    ["gene regulatory network", "regulatory network", "systems biology",
                          "pathway analysis", "interactome", "network biology", "network analysis",
                          "boolean model", "progression model", "dynamical model",
                          "uncertainty quantification"],
    "wielo-omika":      ["multi-omic", "multiomic", "multi-omics", "omics integration",
                          "cross-omic", "omic alignment", "spatial multiomic"],
    "tekst-i-nlp":      ["biomedical text", "text mining", "literature mining",
                          "named entity recognition", "natural language processing", "nlp",
                          "text corpus", "information extraction", "relation extraction",
                          "entity linking", "relationship grounding"],
    "ai-ml":            ["deep learning", "neural network", "machine learning", "transformer",
                          "large language model", "llm", "diffusion model", "foundation model",
                          "generative model", "embedding", "predictive model", "classifier",
                          "graph neural", "graph encoder", "gnn", "contrastive learning",
                          "encoder network", "attention mechanism", "representation learning",
                          "triplet network", "association prediction", "link prediction",
                          "self-supervised", "multi-agent", "llm agent", "agent-based",
                          "mixture of experts", "language model", "agentic"],
    "struktury":        ["protein structure", "alphafold", "esmfold", "folding", "docking",
                          "cryo-em", "molecular dynamics", "protein design", "crystal structure",
                          "nmr structure", "binding affinity", "structure prediction"],
    "leki":             ["drug discovery", "compound", "inhibitor", "virtual screening", "admet",
                          "drug target", "pharmacogenom", "drug repurposing", "molecule generation"],
    "epidemiologia":    ["epidemiolog", "outbreak", "surveillance", "phylodynamic", "pandemic"],
    "ewolucja":         ["phylogen", "evolution", "selection pressure", "comparative genomic"],
    "neuronauka":       ["neuron", "neural dynamics", "neural activity", "brain", "eeg", "fmri",
                          "cognitive", "cognition", "synaptic", "cortex", "cortical",
                          "working memory", "decision making", "decision polic", "neuroscience"],
    "modelowanie":      ["mathematical model", "compartmental model", "dynamical system",
                          "differential equation", "stochastic model", "agent-based model",
                          "pattern formation", "traveling wave", "travelling wave",
                          "population dynamics", "mechanistic model", "kinetic model",
                          "likelihood-ratio test", "bayesian inference"],
    "kliniczne":        ["clinical", "patient", "cohort", "hospital", "mortality", "prevalence",
                          "diagnosis", "diagnostic", "cancer", "tumor", "tumour", "oncolog",
                          "electronic health record", "ehr", "randomized controlled", "public health"],
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
    "Bioinformatics (OUP)":         'JOURNAL:"Bioinformatics" AND (FIRST_PDATE:[{start} TO {end}])',
    "Genome Biology":               'JOURNAL:"Genome Biology" AND (FIRST_PDATE:[{start} TO {end}])',
    "Genome Research":              'JOURNAL:"Genome Research" AND (FIRST_PDATE:[{start} TO {end}])',
    "Nucleic Acids Research":       'JOURNAL:"Nucleic Acids Research" AND (FIRST_PDATE:[{start} TO {end}])',
    "PLOS Computational Biology":   'JOURNAL:"PLoS computational biology" AND (FIRST_PDATE:[{start} TO {end}])',
    "Cell Systems":                 'JOURNAL:"Cell Systems" AND (FIRST_PDATE:[{start} TO {end}])',
    "GigaScience":                  'JOURNAL:"GigaScience" AND (FIRST_PDATE:[{start} TO {end}])',
    "BMC Bioinformatics":           'JOURNAL:"BMC Bioinformatics" AND (FIRST_PDATE:[{start} TO {end}])',
    "Briefings in Bioinformatics":  'JOURNAL:"Briefings in Bioinformatics" AND (FIRST_PDATE:[{start} TO {end}])',
}

# Kategorie bioRxiv, ktore nas interesuja (dokladne nazwy z taksonomii
# bioRxiv, male litery). Wczesniej lapalismy tylko "bioinformatics" -
# duzo istotnych prac (np. AlphaFold-owe) wpada w genomics/genetics.
BIORXIV_CATEGORIES = {
    "bioinformatics", "genomics", "genetics",
    "evolutionary biology", "systems biology", "synthetic biology",
}

# Kategorie medRxiv (siostrzany serwer, klinika/zdrowie publiczne) - realne
# nazwy z taksonomii medRxiv, male litery. Wybrane pod katem bioinformatyki
# klinicznej/epidemiologii obliczeniowej, nie caly medRxiv (za szeroki).
MEDRXIV_CATEGORIES = {
    "epidemiology", "health informatics", "genetic and genomic medicine",
    "infectious diseases (except hiv/aids)",
}

GITHUB_REPOS = [
    "Bioconductor/BiocManager",
    "samtools/samtools",
    "samtools/bcftools",
    "broadinstitute/gatk",
    "broadinstitute/picard",
    "nextflow-io/nextflow",
    "snakemake/snakemake",
    "pysam-developers/pysam",
    "scverse/scanpy",
    "deepmind/alphafold",
    "facebookresearch/esm",
    "COMBINE-lab/salmon",
    "lh3/bwa",
    "BenLangmead/bowtie2",
    "deeptools/deepTools",
    "shenwei356/seqkit",
    "ewels/MultiQC",
    "OpenGene/fastp",
    "biopython/biopython",
    "pachterlab/kallisto",
]

# Pakiety PyPI do sledzenia nowych wersji (glownie python-owe narzedzia
# bioinformatyczne, ktore nie zawsze publikuja rownolegle release na GitHubie).
PYPI_PACKAGES = [
    "scanpy", "biopython", "pysam", "scikit-bio", "anndata", "pyfaidx",
]

# Nauka w Polsce (PAP) - kategoria "Zycie" (biologia), filtrowana slowami
# kluczowymi zwiazanymi z bioinformatyka/genomika, bo sam kanal jest
# ogolnobiologiczny, nie tylko bioinformatyczny.
NAUKAWPOLSCE_RSS = "https://naukawpolsce.pl/zycie/rss.xml"
NAUKAWPOLSCE_KEYWORDS = [
    "bioinformatyk", "genom", "sekwencjonowani", "dna", "mutacj",
    "mikrobiom", "biotechnolog", "algorytm", "sztuczna inteligencj",
    "uczenie maszynowe", "baza danych genetyczn", "białk", "genetyczn",
]


def http_get_json(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _keyword_pattern(keywords):
    """Buduje jeden regex z granicami slow dla listy fraz kluczowych.
    Zapobiega falszywym trafieniom typu 'evolution' wewnatrz 'revolutionizes'.
    Doklejone opcjonalne 's' na koncu kazdej frazy, zeby liczba mnoga
    (np. 'progression models') dalej pasowala do liczby pojedynczej w slowniku."""
    # Krotkie skroty (wes, snp, mhc, llm...) musza pasowac dokladnie, inaczej
    # "wes" trafialoby w "western". Dluzsze frazy dzialaja jak rdzen:
    # "epidemiolog" -> "epidemiological", "phylogen" -> "phylogenetic",
    # "transcriptom" -> "transcriptomic". Wczesniej koncowe \b blokowalo
    # wszystkie takie rdzenie i duza czesc wpisow wpadala do "inne".
    parts = [re.escape(k.strip()) + (r"\w*" if len(k.strip()) >= 5 else "s?") for k in keywords]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b")


_CATEGORY_PATTERNS = {tag: _keyword_pattern(kws) for tag, kws in CATEGORY_KEYWORDS.items()}
_ARTICLE_TYPE_PATTERNS = [(t, _keyword_pattern(kws)) for t, kws in ARTICLE_TYPE_KEYWORDS]


def truncate_summary(text, max_len=220):
    """Krociutkie streszczenie: tnie po pelnym zdaniu jesli to mozliwe w
    limicie, w przeciwnym razie po ostatnim pelnym slowie - nigdy w polowie
    wyrazu ani w polowie zdania."""
    text = (text or "").strip()
    if len(text) <= max_len:
        return text

    clipped = text[:max_len]
    last_dot = clipped.rfind(". ")
    if last_dot >= 60:  # sensowna dlugosc pierwszego zdania, nie ucinamy po "np."
        return clipped[:last_dot + 1]

    last_space = clipped.rfind(" ")
    if last_space > 0:
        clipped = clipped[:last_space]
    return clipped.rstrip(",;: ") + "…"


def tag_entry(title, summary):
    text = f"{title} {summary}".lower()
    tags = [tag for tag, pattern in _CATEGORY_PATTERNS.items() if pattern.search(text)]
    return tags or [FALLBACK_TAG]


def add_tag(tags, extra):
    """Dodaje tag jesli go jeszcze nie ma - unika duplikatow pilli na karcie."""
    return tags if extra in tags else tags + [extra]


def classify_article_type(title, summary):
    text = f"{title} {summary}".lower()
    for art_type, pattern in _ARTICLE_TYPE_PATTERNS:
        if pattern.search(text):
            return art_type
    return "eksperymentalne"  # domyslny typ dla oryginalnych badan/preprintow


# ---------------------------------------------------------------------------
# 1) bioRxiv / medRxiv — preprinty z ostatnich N dni (to samo API, inny serwer)
# ---------------------------------------------------------------------------
def fetch_preprint_server(server, categories, source_label, days_back=7, max_pages=3):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days_back)
    entries = []
    cursor = 0
    for _ in range(max_pages):
        url = f"https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}"
        try:
            data = http_get_json(url)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            print(f"[{source_label}] blad pobierania: {e}", file=sys.stderr)
            break

        collection = data.get("collection", [])
        if not collection:
            break

        for item in collection:
            category = (item.get("category") or "").strip().lower()
            if category not in categories:
                continue
            title = item.get("title", "").strip()
            abstract = item.get("abstract", "").strip()
            doi = item.get("doi", "")
            entries.append({
                "type": "research",
                "source": source_label,
                "title": title,
                "description": truncate_summary(abstract),
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


def fetch_biorxiv(days_back=7, max_pages=3):
    return fetch_preprint_server("biorxiv", BIORXIV_CATEGORIES, "bioRxiv", days_back, max_pages)


def fetch_medrxiv(days_back=7, max_pages=3):
    return fetch_preprint_server("medrxiv", MEDRXIV_CATEGORIES, "medRxiv", days_back, max_pages)


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
            "&resultType=core"  # bez tego API nie zwraca abstractText - domyslny "lite" go pomija
        )
        try:
            data = http_get_json(url)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
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
                "description": truncate_summary(abstract),
                "url": f"https://doi.org/{doi}" if doi else item.get("fullTextUrlList", {}),
                "date": item.get("firstPublicationDate", ""),
                "tags": tag_entry(title, abstract),
                "article_type": classify_article_type(title, abstract),
            })
        time.sleep(0.5)

    return entries


# ---------------------------------------------------------------------------
# 3a) GitHub — dynamiczne odkrywanie repo po temacie, zamiast tylko sztywnej
#     listy GITHUB_REPOS. Lapie nowe/popularne projekty, ktorych nie znamy
#     z gory. Wyniki laczymy z GITHUB_REPOS przed sprawdzeniem release'ow.
# ---------------------------------------------------------------------------
GITHUB_TOPICS = ["bioinformatics", "computational-biology", "genomics"]


def discover_github_topic_repos(topics=None, per_topic=8, min_stars=50):
    topics = topics or GITHUB_TOPICS
    gh_headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        gh_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    discovered = []
    seen = set()
    for topic in topics:
        url = (
            "https://api.github.com/search/repositories"
            f"?q=topic:{topic}+stars:>={min_stars}&sort=updated&order=desc&per_page={per_topic}"
        )
        try:
            data = http_get_json(url, headers=gh_headers)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            print(f"[GitHub-topic] blad pobierania dla topic:{topic}: {e}", file=sys.stderr)
            continue
        for repo in data.get("items", []):
            full_name = repo.get("full_name", "")
            if full_name and full_name not in seen:
                seen.add(full_name)
                discovered.append(full_name)
        time.sleep(0.3)

    return discovered


# ---------------------------------------------------------------------------
# 3b) GitHub Releases — nowe wersje narzedzi (lista sztywna + odkryte po temacie)
# ---------------------------------------------------------------------------
def fetch_github_releases(days_back=14, repos=None):
    repos = repos if repos is not None else GITHUB_REPOS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    entries = []

    for repo in repos:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=3"
        gh_headers = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            gh_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        try:
            releases = http_get_json(url, headers=gh_headers)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
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
                "tags": add_tag(tag_entry(title, body), "narzedzia"),
            })
        time.sleep(0.3)

    return entries


# ---------------------------------------------------------------------------
# 4) PyPI — nowe wersje wybranych pakietow pythonowych
# ---------------------------------------------------------------------------
def fetch_pypi_releases(days_back=14):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    entries = []

    for pkg in PYPI_PACKAGES:
        url = f"https://pypi.org/pypi/{pkg}/json"
        try:
            data = http_get_json(url)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            print(f"[PyPI] blad pobierania dla {pkg}: {e}", file=sys.stderr)
            continue

        version = data.get("info", {}).get("version", "")
        releases = data.get("releases", {}).get(version, [])
        if not releases:
            continue
        upload_time = releases[0].get("upload_time_iso_8601", "")
        if not upload_time:
            continue
        pub_dt = datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
        if pub_dt < cutoff:
            continue

        summary = data.get("info", {}).get("summary", "") or ""
        title = f"{pkg} {version}"
        entries.append({
            "type": "narzedzie",
            "source": f"PyPI · {pkg}",
            "title": title,
            "description": summary,
            "url": data.get("info", {}).get("project_url") or f"https://pypi.org/project/{pkg}/",
            "date": pub_dt.date().isoformat(),
            "tags": add_tag(tag_entry(title, summary), "narzedzia"),
        })
        time.sleep(0.3)

    return entries


# ---------------------------------------------------------------------------
# 5) Nauka w Polsce (PAP) — kategoria "Zycie", filtrowana slowami kluczowymi
#    zwiazanymi z bioinformatyka/genomika (kanal jest ogolnobiologiczny).
#    RSS, nie JSON API - parsujemy przez stdlib xml.etree.
# ---------------------------------------------------------------------------
def fetch_naukawpolsce(days_back=7):
    entries = []
    req = urllib.request.Request(NAUKAWPOLSCE_RSS, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_bytes = resp.read()
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        print(f"[NaukaWPolsce] blad pobierania RSS: {e}", file=sys.stderr)
        return entries

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"[NaukaWPolsce] blad parsowania XML: {e}", file=sys.stderr)
        return entries

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    for item in root.iterfind(".//item"):
        title = (item.findtext("title") or "").strip()
        description = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()

        text = f"{title} {description}".lower()
        if not any(k in text for k in NAUKAWPOLSCE_KEYWORDS):
            continue  # poza tematyka bioinformatyczna/genomiczna

        pub_dt = None
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
            try:
                pub_dt = datetime.strptime(pub_date_raw, fmt)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        if pub_dt is None or pub_dt < cutoff:
            continue

        clean_desc = re.sub(r"<[^>]+>", "", description).strip()
        entries.append({
            "type": "research",
            "source": "Nauka w Polsce (PAP)",
            "title": title,
            "description": truncate_summary(clean_desc),
            "url": link,
            "date": pub_dt.date().isoformat(),
            "tags": add_tag(tag_entry(title, clean_desc), "polska"),
            "article_type": classify_article_type(title, clean_desc),
        })

    return entries


# ---------------------------------------------------------------------------
# 6) arXiv — kategoria q-bio (quantitative biology), Atom/XML API
# ---------------------------------------------------------------------------
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def fetch_arxiv(days_back=7, max_results=40):
    entries = []
    url = (
        "https://export.arxiv.org/api/query"
        "?search_query=cat:q-bio.*"
        "&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={max_results}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_bytes = resp.read()
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"[arXiv] blad pobierania: {e}", file=sys.stderr)
        return entries

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"[arXiv] blad parsowania XML: {e}", file=sys.stderr)
        return entries

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    for item in root.iterfind("atom:entry", ARXIV_NS):
        title = re.sub(r"\s+", " ", (item.findtext("atom:title", default="", namespaces=ARXIV_NS) or "")).strip()
        summary = re.sub(r"\s+", " ", (item.findtext("atom:summary", default="", namespaces=ARXIV_NS) or "")).strip()
        link = item.findtext("atom:id", default="", namespaces=ARXIV_NS).strip()
        published_raw = item.findtext("atom:published", default="", namespaces=ARXIV_NS).strip()

        try:
            pub_dt = datetime.strptime(published_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if pub_dt < cutoff:
            continue

        entries.append({
            "type": "research",
            "source": "arXiv (q-bio)",
            "title": title,
            "description": truncate_summary(summary),
            "url": link,
            "date": pub_dt.date().isoformat(),
            "tags": tag_entry(title, summary),
            "article_type": classify_article_type(title, summary),
        })

    return entries


# ---------------------------------------------------------------------------
# 7) NIH RePORTER — sfinansowane projekty (granty), inny typ newsa niz artykul
# ---------------------------------------------------------------------------
def fetch_nih_reporter(days_back=30, limit=15):
    entries = []
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days_back)

    body = {
        "criteria": {
            "advanced_text_search": {
                "operator": "and",
                "search_field": "projecttitle,terms",
                "search_text": "bioinformatics",
            },
            "award_notice_date": {
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
            },
        },
        "include_fields": [
            "ProjectTitle", "AbstractText", "Organization", "AwardAmount",
            "AwardNoticeDate", "ProjectStartDate", "ContactPiName", "ProjectNum",
        ],
        "offset": 0,
        "limit": limit,
        "sort_field": "award_notice_date",
        "sort_order": "desc",
    }
    req = urllib.request.Request(
        "https://api.reporter.nih.gov/v2/projects/search",
        data=json.dumps(body).encode("utf-8"),
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        print(f"[NIH RePORTER] blad pobierania: {e}", file=sys.stderr)
        return entries

    for item in data.get("results", []):
        title = (item.get("project_title") or "").strip()
        abstract = (item.get("abstract_text") or "").strip()
        # API v2 zwraca instytucje jako obiekt {"org_name": ...}, nie plaskie pole
        # - stad wczesniej puste "NIH RePORTER ·  · $...".
        org = ((item.get("organization") or {}).get("org_name") or item.get("org_name") or "").strip().title()
        amount = item.get("award_amount")
        amount_str = f" · ${amount:,.0f}" if isinstance(amount, (int, float)) else ""
        proj_num = item.get("project_num") or ""
        # Data przyznania tej transzy, NIE start projektu (projekty ciagnace sie
        # od 1997 r. pokazywaly sie jako "newsy" sprzed 29 lat).
        notice_date = (item.get("award_notice_date") or "")[:10]
        if not title or not notice_date or notice_date < start.isoformat():
            continue

        entries.append({
            "type": "grant",
            "source": "NIH RePORTER" + (f" · {org}" if org else "") + amount_str,
            "title": title,
            "description": truncate_summary(abstract),
            "url": f"https://reporter.nih.gov/project-details/{proj_num}" if proj_num else "https://reporter.nih.gov/",
            "date": notice_date,
            "tags": add_tag(tag_entry(title, abstract), "granty"),
            "article_type": None,
        })

    return entries


# ---------------------------------------------------------------------------
# 8) Zenodo — datasety i software release'y (uzupelnienie GitHuba)
# ---------------------------------------------------------------------------
def fetch_zenodo(days_back=14, max_results=20):
    entries = []
    url = (
        "https://zenodo.org/api/records"
        "?q=bioinformatics&sort=mostrecent&size={}".format(max_results)
    )
    try:
        data = http_get_json(url)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        print(f"[Zenodo] blad pobierania: {e}", file=sys.stderr)
        return entries

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    for hit in data.get("hits", {}).get("hits", []):
        meta = hit.get("metadata", {})
        resource_type = (meta.get("resource_type", {}) or {}).get("type", "")
        if resource_type not in ("software", "dataset"):
            continue  # publikacje/inne juz mamy z bioRxiv/EuropePMC

        pub_date_raw = meta.get("publication_date", "")
        try:
            pub_dt = datetime.strptime(pub_date_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if pub_dt < cutoff:
            continue

        title = (meta.get("title") or "").strip()
        description = re.sub(r"<[^>]+>", "", meta.get("description") or "").strip()
        entry_type = "narzedzie" if resource_type == "software" else "research"
        # wyszukiwarka Zenodo dla "bioinformatics" zwraca tez rzeczy zupelnie
        # obok tematu (np. dowody w Lean) - bez zadnego tematu = pomijamy
        if tag_entry(title, description) == [FALLBACK_TAG]:
            continue

        entries.append({
            "type": entry_type,
            "source": f"Zenodo · {resource_type}",
            "title": title,
            "description": truncate_summary(description),
            # nowe API Zenodo nie zawsze ma links.html - wtedy budujemy link z id rekordu
            "url": ((hit.get("links", {}) or {}).get("self_html")
                    or (hit.get("links", {}) or {}).get("html")
                    or (f"https://zenodo.org/records/{hit['id']}" if hit.get("id") else "")),
            "date": pub_dt.date().isoformat(),
            "tags": add_tag(tag_entry(title, description), "narzedzia" if resource_type == "software" else "bazy-danych"),
            "article_type": classify_article_type(title, description) if entry_type == "research" else None,
        })

    return entries


def norm_key(e):
    """Klucz deduplikacji: URL (bez parametrow i koncowego /), a gdy go brak - tytul."""
    url = (e.get("url") or "").split("?")[0].split("#")[0].rstrip("/").lower()
    return url or e["title"].strip().lower()


def dedupe(entries):
    seen_keys, seen_titles, unique = set(), set(), []
    for e in entries:
        k, t = norm_key(e), e["title"].strip().lower()
        if k in seen_keys or t in seen_titles:
            continue
        seen_keys.add(k)
        seen_titles.add(t)
        unique.append(e)
    return unique


def clean_text(t):
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or ""))
    t = t.replace("<", "‹").replace(">", "›")
    return re.sub(r"\s+", " ", t).strip()


def sanitize(e):
    """Strony wstawiaja te pola przez innerHTML - czyscimy je tutaj, u zrodla."""
    for k in ("title", "description", "source"):
        e[k] = clean_text(e.get(k))
    url = (e.get("url") or "").strip()
    e["url"] = url if re.match(r"^https?://", url, re.I) and not re.search(r"[\"'<>\s]", url) else ""
    e["id"] = "r-" + hashlib.md5(norm_key(e).encode("utf-8")).hexdigest()[:12]
    return e


def run_source(label, fn):
    """Uruchamia jedno zrodlo w try/except obejmujacym WSZYSTKIE wyjatki -
    zeby blad (nawet nieprzewidziany, np. zmiana struktury odpowiedzi API)
    w jednym zrodle nigdy nie ubijal calego skryptu i nie blokowal zapisu
    danych z pozostalych, juz pobranych zrodel."""
    print(f"Pobieram z {label}...", file=sys.stderr)
    try:
        return fn()
    except Exception as e:
        print(f"[{label}] NIEOCZEKIWANY BLAD, pomijam to zrodlo: {e!r}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return []


FEED_PATH = Path("research-news.json")
ARCHIVE_DIR = Path("archive")
FEED_DAYS = 30   # research-news.json = ostatnie 30 dni (to laduja strony)


def load_entries(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    except (FileNotFoundError, ValueError):
        return []


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def update_archive(entries):
    """Kazdy wpis trafia na zawsze do archive/research-YYYY-MM.json (wg daty),
    archive/index.json trzyma liste miesiecy dla strony."""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    by_month = {}
    for e in entries:
        if e.get("date"):
            by_month.setdefault(e["date"][:7], []).append(e)
    for month, items in by_month.items():
        path = ARCHIVE_DIR / f"research-{month}.json"
        merged = dedupe(items + load_entries(path))   # nowe wersje wygrywaja
        merged.sort(key=lambda x: x.get("date", ""), reverse=True)
        write_json(path, {"month": month, "count": len(merged), "entries": merged})
    months = []
    for path in sorted(ARCHIVE_DIR.glob("research-*.json"), reverse=True):
        months.append({"month": path.stem.replace("research-", ""), "count": len(load_entries(path))})
    write_json(ARCHIVE_DIR / "index.json", {"months": months})


def main():
    fresh = []
    fresh += run_source("bioRxiv", fetch_biorxiv)
    fresh += run_source("medRxiv", fetch_medrxiv)
    fresh += run_source("Europe PMC", fetch_europepmc)

    # GitHub: sztywna lista + dynamicznie odkryte repo po temacie, w jednym
    # przebiegu sprawdzania release'ow (mniej wywolan do API niz osobno)
    topic_repos = run_source("GitHub-topic-discovery", discover_github_topic_repos)
    combined_repos = list(dict.fromkeys(GITHUB_REPOS + topic_repos))  # dedupe, zachowaj kolejnosc
    fresh += run_source("GitHub Releases", lambda: fetch_github_releases(repos=combined_repos))

    fresh += run_source("PyPI", fetch_pypi_releases)
    fresh += run_source("Nauka w Polsce", fetch_naukawpolsce)
    fresh += run_source("arXiv", fetch_arxiv)
    fresh += run_source("NIH RePORTER", fetch_nih_reporter)
    fresh += run_source("Zenodo", fetch_zenodo)

    # bez tytułu albo bez działającego linku karta jest bezużyteczna
    fresh = [e for e in (sanitize(e) for e in fresh if (e.get("title") or "").strip()) if e["url"]]
    if not fresh:
        print("Zadne zrodlo nic nie zwrocilo - zostawiam pliki bez zmian", file=sys.stderr)
        return

    # Nowe wpisy + to, co juz bylo w feedzie: jesli jakies zrodlo padnie na
    # jeden dzien, jego wpisy nie znikaja ze strony.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=FEED_DAYS)).date().isoformat()
    previous = [e for e in (sanitize(e) for e in load_entries(FEED_PATH)) if e["url"]]
    feed = dedupe(fresh + previous)
    feed = [e for e in feed if e.get("date", "") >= cutoff]
    feed.sort(key=lambda e: e.get("date", ""), reverse=True)

    write_json(FEED_PATH, {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "days": FEED_DAYS,
        "entries": feed,
    })
    update_archive(fresh + previous)
    print(f"Zapisano {len(feed)} wpisow do {FEED_PATH} (+ archiwum miesieczne)", file=sys.stderr)


if __name__ == "__main__":
    main()
