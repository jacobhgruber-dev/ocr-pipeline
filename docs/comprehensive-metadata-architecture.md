## Summary

Design a comprehensive file format strategy and scholarly metadata model for the OCR Pipeline. The current system is PDF-only with a flat ~25-field `MetadataResult`. This architecture extends it to handle 50+ file formats across three tiers, introduces a structured nested metadata model spanning citation, provenance, technical, rights, and archival domains, and defines a phased implementation plan that minimizes disruption to the existing codebase.

---

## Mode

Fresh first-principles design — designing the format and metadata universe from scratch, anchoring to the existing `MetadataResult`, `DocumentSource` ABC (from `docs/multi-format-architecture.md`), and `Pipeline` architecture.

---

## Part 1: Filetype Universe

### Tiering Philosophy

Formats are assigned to tiers based on three criteria:
1. **Frequency of encounter** — how often a scholar/archivist/researcher actually sees this format
2. **Implementation complexity** — how hard is text extraction and metadata extraction
3. **Strategic value** — does it unlock important use cases (scholarly publishing, digital libraries, archives)

### Tier 1: Must-have (implement in Phase 1)

These are formats that every universal document ingestion system must handle. They cover the vast majority of real-world document ingest scenarios.

| Format | Extensions | Text extraction library | Complexity | OCR needed? | Page model | Metadata source |
|--------|-----------|------------------------|------------|-------------|------------|-----------------|
| **PDF** | `.pdf` | PyMuPDF (existing) | Low | Sometimes | Native pages | PyMuPDF dict, GROBID |
| **EPUB** | `.epub` | `ebooklib` + `beautifulsoup4` | Medium | No | Spine items (chapters) | OPF XML |
| **DOCX** | `.docx` | `python-docx` | Low | No | 1 (whole document) | `core.xml` properties |
| **TXT** | `.txt` | Python `open()` + `chardet` | Low | No | 1 (whole file) | Filename heuristics, mtime |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.webp` | Pillow (EXIF only) | Low | Yes (always) | 1 per file | EXIF |
| **CSV** | `.csv` | `csv` stdlib / `pandas` | Low | No | 1 (tabular) | Column headers, row count |
| **Excel** | `.xlsx`, `.xls` | `openpyxl`, `xlrd` | Medium | No | 1 per sheet | Sheet names, cell count |
| **PPTX** | `.pptx` | `python-pptx` | Medium | No | 1 per slide | `core.xml` properties |

#### Additional Tier 1 formats to add:

| Format | Extensions | Text extraction library | Complexity | OCR needed? | Page model | Metadata source | Why it's critical |
|--------|-----------|------------------------|------------|-------------|------------|-----------------|-------------------|
| **LaTeX** | `.tex` | Plain text read + `pylatexenc` for macro resolution | Low | No | 1 (source file) | `\title{}`, `\author{}`, `\date{}`, `\bibliography{}` regex | arXiv, academic preprints, scientific computing. ~2M papers on arXiv alone. |
| **Markdown** | `.md`, `.markdown` | Plain text read | Low | No | 1 (source file) | YAML frontmatter, first H1 heading | Documentation, Jupyter exports, GitHub repos, SSG content. Pervasive. |
| **HTML** | `.html`, `.htm` | `beautifulsoup4` | Low | No | 1 (single page) | `<title>`, `<meta>` tags, Open Graph, schema.org JSON-LD, Dublin Core `<meta>` | Web pages, saved articles, email exports. Key for web archiving. |
| **RTF** | `.rtf` | `striprtf` or `pyth` | Low | No | 1 | `{\info {\title ...}}` block | Legacy word processing. Many government/law documents are RTF. Still in active use by courts. |
| **ODT** | `.odt`, `.ods`, `.odp` | `odfpy` or unzip + parse `content.xml` | Low | No | 1 (whole document) | `meta.xml` (Dublin Core, OpenDocument metadata) | LibreOffice/OpenOffice format. EU government standard. Required for public sector compliance in many jurisdictions. |
| **DJVU** | `.djvu` | `djvulibre` (`djvutxt` CLI) or `pydjvu` | Medium | Sometimes | Native pages | Bundled metadata, OCR text layer | Scanned books in digital libraries (Internet Archive, HathiTrust). Millions of books. Critical for digital humanities. |
| **Multi-page TIFF** | `.tiff`, `.tif` | Pillow (frame iteration) | Low | Yes (always) | 1 per frame | EXIF per frame | Scanned archival documents, fax archives, legal document production. Standard in library digitization. |
| **Email** | `.eml` | `email` stdlib | Low | No | 1 (single message) | Headers (From, To, Date, Subject, Message-ID) | Correspondence archives, FOIA releases, legal discovery. |
| **JSON** | `.json` | `json` stdlib | Low | No | 1 (structured) | Top-level keys, `$schema`, JSON-LD `@context` | API exports, structured data archives, configuration-as-data. |
| **TEI XML** | `.xml` (TEI namespace) | `lxml` (already a dependency) | Low | No | 1 (structured) | `<teiHeader>` with `<fileDesc>`, `<profileDesc>`, `<encodingDesc>` | Academic publishing standard. Already used by GROBID. Natural fit. |
| **JATS XML** | `.xml` (JATS namespace) | `lxml` (already a dependency) | Low | No | 1 (structured) | `<article-meta>` with `<title-group>`, `<contrib-group>`, `<abstract>` | NLM/PubMed Central standard for journal articles. Highly structured. |
| **SRT/VTT subtitles** | `.srt`, `.vtt` | Plain text parse | Low | No | 1 (transcript) | None native (derived from video filename) | Video transcripts, lecture recordings, meeting captions. Increasingly important for accessibility. |
| **Log files** | `.log` | Plain text read | Low | No | 1 (stream) | Filename, mtime, line count | System logs, build output, experiment logs. Not "documents" but ingested in research pipelines. |

### Tier 2: Nice-to-have (implement in Phase 2)

These formats are less common in daily ingest but unlock high-value specialized domains.

| Format | Extensions | Text extraction approach | Metadata source | Why it matters |
|--------|-----------|--------------------------|----------------|----------------|
| **Audio — interviews, lectures** | `.mp3`, `.wav`, `.flac`, `.m4a`, `.ogg` | Speech-to-text (Whisper, Google STT) → transcript | ID3 tags, Vorbis comments, duration, sample rate, channel count | Oral histories, ethnographic research, legal depositions, podcast archives |
| **Audio — music** | `.mp3`, `.flac`, `.wav` | N/A (metadata only) | ID3 (artist, album, track, year, genre, composer), ISRC | Musicology, ethnomusicology, performance studies |
| **Video** | `.mp4`, `.mkv`, `.webm`, `.avi`, `.mov` | Frame extraction → OCR + audio track → STT | Container metadata (codec, resolution, duration, creation date), subtitles | Archival footage, lecture recordings, documentary sources |
| **ZIP archives** | `.zip` | Recurse into contained files, process each with its own format handler | File listing, directory structure, compression metadata | Most digital collections arrive as archives. Recurse-and-process. |
| **TAR archives** | `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2` | Same as ZIP — extract + recurse | Same as ZIP | Common in academic data repositories, software distribution |
| **7z archives** | `.7z` | `py7zr` — extract + recurse | Same as ZIP | High-compression archives from data repositories |
| **GZ/BZ2/XZ** | `.gz`, `.bz2`, `.xz` | Single-file decompression (often wraps TXT/JSON/CSV) | Compression ratio, original filename | Compressed log files, database dumps, large text corpora |
| **Jupyter notebooks** | `.ipynb` | Parse JSON → extract markdown cells, code cells, outputs (images, tables) | Kernel metadata, execution count, cell structure, `nbformat` version | Data science, computational research, reproducible papers |
| **MBOX email archives** | `.mbox` | `mailbox` stdlib → iterate messages, each processed via `.eml` handler | Archive-level: message count, date range, participants | Corpus-level email analysis, FOIA releases, organizational archives |
| **PST email archives** | `.pst` | `libpff` / `pypff` → extract to .eml or .mbox | Same as MBOX | Microsoft Outlook archives, legal e-discovery |
| **SQLite databases** | `.sqlite`, `.db` | `sqlite3` stdlib → extract table schemas, sample rows, statistics | Table names, column types, row counts, SQL schema | Embedded datasets, application databases, research data |
| **BibTeX** | `.bib` | `bibtexparser` → parse entries | Author, title, journal, year, DOI — every field is metadata | Bibliography as input to enrich related document metadata |
| **Font files** | `.ttf`, `.otf`, `.woff`, `.woff2` | N/A (metadata only) | `fonttools` — family name, designer, version, copyright, embedding flags | Typography research, document forensics, design history |
| **GIS vector** | `.shp`, `.geojson`, `.kml`, `.gpx` | N/A (metadata only) | `fiona` / `geopandas` — CRS, feature count, extent, attribute schema | Spatial humanities, environmental research, historical geography |
| **CAD files** | `.dwg`, `.dxf` | N/A (metadata only) | `ezdxf` / header variables — author, creation date, units, layer names | Engineering history, architectural archives, industrial design |
| **RDF / Turtle** | `.ttl`, `.rdf`, `.nt`, `.n3` | Parse triples → extract predicates and objects | `@prefix` declarations, named graph URI, triple count | Linked data, semantic web, knowledge graph ingestion |
| **RIS** | `.ris` | `rispy` → parse reference entries | Same fields as BibTeX — reference manager export format | Reference manager exports, systematic reviews |

### Tier 3: Future (specialized domains)

These formats are domain-specific and should be designed for but not implemented until user demand materializes.

| Format | Description | When to implement |
|--------|-------------|-------------------|
| **MARC (.mrc)** | Library catalog records — already metadata, not content | When library catalog integration is needed |
| **MARCXML** | XML variant of MARC | Same as above |
| **ONIX (.xml)** | Book industry metadata standard | When publisher metadata ingestion is needed |
| **EAD (.xml)** | Encoded Archival Description — finding aids | Digital archives / special collections use case |
| **METS/ALTO** | Digital object structural metadata + OCR layout | When digitized book structure preservation matters |
| **Kindle (.azw, .azw3, .kfx)** | Amazon e-book formats — detect DRM, flag as unprocessable if locked | When e-book archive processing is needed |
| **Apple Books** | Proprietary — likely unprocessable without DRM removal | Same as Kindle |
| **Comics (.cbz, .cbr)** | ZIP/RAR of numbered images | Digital comics archives |
| **MusicXML (.musicxml, .mxl)** | Sheet music notation | Musicology, performance studies |
| **MEI (.mei)** | Music Encoding Initiative XML | Academic musicology |
| **HDF5 (.h5, .hdf5)** | Scientific data containers | Research data archives |
| **NetCDF (.nc)** | Climate/geoscience data | Environmental research |
| **FITS (.fits)** | Astronomy data | Astrophysics archives |
| **DICOM (.dcm)** | Medical imaging | Medical research pipelines |
| **PDF/A (archival PDF)** | Subtype of PDF — already handled, but flag conformance level | Long-term digital preservation |

### Format-specific design notes for each new Tier 1 addition

#### LaTeX (.tex)

- **Text extraction**: Read as plain text. Optionally resolve `\input{}` / `\include{}` directives to rebuild full document. `pylatexenc` for macro-to-Unicode conversion.
- **Metadata extraction**: Regex-based parsing of `\title{...}`, `\author{...}`, `\date{...}`, `\maketitle`, `\bibliography{...}`, `\bibliographystyle{...}`. Extract `\usepackage{}` declarations for dependency tracking.
- **OCR needed?**: No — the source IS the text.
- **Page model**: 1 conceptual page (the source file). For multi-file projects (.tex + .bib + figures), treat the `.tex` as the entry point and optionally recurse.
- **Scholarly value**: Can extract the raw bibliography entries, making it easier to build citation graphs.

#### Markdown (.md)

- **Text extraction**: Read as plain text. No parsing needed for text — the markdown source IS human-readable.
- **Metadata extraction**: Parse YAML frontmatter (between `---` delimiters) for title, author, date, tags, etc. If no frontmatter, use the first H1 heading (`# Title`) as the title. Check for Hugo/Jekyll/Gatsby frontmatter conventions.
- **OCR needed?**: No.
- **Page model**: 1 conceptual page.
- **Scholarly value**: Common in digital humanities, software documentation, and SSG-based academic websites. YAML frontmatter often contains structured metadata.

#### HTML (.html)

- **Text extraction**: `beautifulsoup4` `get_text()` with newline separation. Strip `<script>`, `<style>`, `<nav>`, `<footer>` before extraction.
- **Metadata extraction**: Multi-layer approach:
  1. **Open Graph** (`<meta property="og:title">`, `og:description`, `og:type`, `og:url`, `og:image`)
  2. **Twitter Cards** (`<meta name="twitter:title">`, etc.)
  3. **Schema.org JSON-LD** (`<script type="application/ld+json">`) — parsed with `json.loads()`. Supports `Article`, `ScholarlyArticle`, `Book`, `WebPage`, `Dataset`, `Person`, `Organization`, and 30+ other types with rich structured data.
  4. **Dublin Core** (`<meta name="DC.title">`, `DC.creator`, `DC.date`, `DC.identifier`, `DC.rights`)
  5. **Highwire Press tags** (`<meta name="citation_title">`, `citation_author`, `citation_doi`, `citation_journal_title` — used by academic publishers)
  6. **Standard HTML** (`<title>`, `<meta name="description">`, `<meta name="author">`, `<meta name="keywords">`)
  7. **PRISM** (`<meta name="prism.doi">`, `prism.publicationName` — publishing industry standard)
- **OCR needed?**: No.
- **Page model**: 1 conceptual page per HTML file.
- **Scholarly value**: Schema.org JSON-LD is extremely rich for scholarly articles. Highwire Press tags are used by nearly every major academic publisher (Elsevier, Springer, Wiley, Taylor & Francis). Combined, these can yield more structured metadata than a PDF.

#### RTF (.rtf)

- **Text extraction**: `striprtf` library for clean text, or `pyth` for more robust parsing. The RTF format encodes text alongside formatting commands.
- **Metadata extraction**: Parse the `{\info ...}` block for `{\title ...}`, `{\author ...}`, `{\creatim ...}` (creation time), `{\revtim ...}` (revision time), `{\doccomm ...}` (comments), `{\company ...}`, `{\manager ...}`.
- **OCR needed?**: No.
- **Page model**: 1 conceptual page.
- **Scholarly value**: Widely used in legal documents, government reports, and pre-2000s word processing. Many archival documents are RTF.

#### ODT (.odt)

- **Text extraction**: An ODT is a ZIP file containing `content.xml`. Unzip, parse `content.xml` with `lxml`, extract `<text:p>` elements. Or use `odfpy` for a higher-level API.
- **Metadata extraction**: Parse `meta.xml` from the ZIP — contains Dublin Core elements (`<dc:title>`, `<dc:creator>`, `<dc:date>`, `<dc:language>`, `<dc:subject>`, `<dc:description>`, `<dc:identifier>`), plus OpenDocument metadata (`<meta:document-statistic>`, `<meta:generator>`, `<meta:creation-date>`, `<meta:editing-cycles>`, `<meta:editing-duration>`).
- **OCR needed?**: No.
- **Page model**: 1 conceptual page.
- **Scholarly value**: ODF is an ISO standard (ISO/IEC 26300) and the mandated format for EU public sector documents. Rich Dublin Core metadata.

#### DJVU (.djvu)

- **Text extraction**: DJVU files often contain a hidden text layer (OCR output). Use `djvutxt` CLI (from `djvulibre`) or `pydjvu` to extract. If no text layer, the pages are purely scanned images and must go through the OCR path.
- **Metadata extraction**: DJVU bundles metadata in the file header (`djvused` CLI to extract). Can include title, author, year, and annotations.
- **OCR needed?**: Sometimes — if text layer exists, skip OCR. If not, render pages to PNG and OCR.
- **Page model**: Native pages (like PDF).
- **Implementation approach**: Use `djvulibre` tools via subprocess (like the Marker/Surya2 engines do). `djvutxt` for text, `ddjvu` for rendering. These are C libraries with Python wrappers available.
- **Scholarly value**: Critical for Internet Archive and HathiTrust collections. Millions of scanned books are in DJVU format. Without DJVU support, large swaths of digitized library content are inaccessible.

#### Multi-page TIFF

- **Text extraction**: Always returns `None` — TIFF frames are images.
- **Metadata extraction**: EXIF on a per-frame basis (DateTime, ImageDescription, Artist, Make/Model for scanner metadata). Document-level metadata from page 0 EXIF + file stats.
- **OCR needed?**: Yes, always.
- **Page model**: 1 per frame. Pillow's `Image.seek()` and `n_frames`/`tell()` for frame iteration.
- **Implementation approach**: Extend `ImageSource` to detect multi-frame TIFFs and return `page_count() > 1`. Each frame is rendered as a PNG for the OCR engines.
- **Scholarly value**: Standard format for scanned archival documents, legal document production, and library digitization programs. A single multi-page TIFF can contain an entire document.

#### Email (.eml)

- **Text extraction**: Use Python's `email` stdlib. Parse MIME structure, extract `text/plain` and `text/html` parts. For HTML parts, use `beautifulsoup4` to extract text.
- **Metadata extraction**: Headers provide rich structured metadata:
  - `From`, `To`, `Cc`, `Bcc` → author and recipients
  - `Date` → precise timestamp
  - `Subject` → title
  - `Message-ID` → unique identifier
  - `In-Reply-To`, `References` → threading (related works)
  - `Content-Type`, `Content-Transfer-Encoding`
  - `User-Agent` → creation software
  - `X-Mailer` → email client
  - `DKIM-Signature`, `SPF` → authentication metadata
- **OCR needed?**: No.
- **Page model**: 1 per email file.
- **Scholarly value**: Critical for correspondence archives, FOIA releases, legal e-discovery, and historical research.

#### JSON (.json)

- **Text extraction**: If the JSON contains text fields, extract them. The approach is format-specific:
  - For generic JSON: serialize with `json.dumps(indent=2)` as "text"
  - For JSON-LD: parse `@context`, extract typed entities
  - For GeoJSON: extract feature properties as metadata, geometry as technical metadata
  - For API responses: extract relevant text fields
- **Metadata extraction**: Parse top-level keys. If `$schema` is present, record it. If `@context` is present (JSON-LD), parse linked data.
- **OCR needed?**: No.
- **Page model**: 1 per JSON file.
- **Scholarly value**: API exports, data archives, configuration-as-data. JSON-LD is the foundation of schema.org metadata.

#### TEI XML (.xml with TEI namespace)

- **Text extraction**: Parse with `lxml` (already a dependency). Extract `<text>` or `<body>` content. More structured than raw text — can preserve chapters, sections, paragraphs as structural elements.
- **Metadata extraction**: The `<teiHeader>` contains everything a scholar needs:
  - `<fileDesc>` — bibliographic description (title, author, editor, publisher, date, extent)
  - `<encodingDesc>` — how the text was encoded (editorial decisions, normalization, etc.)
  - `<profileDesc>` — classification, language, keywords, abstract
  - `<revisionDesc>` — version history with dates and authors
  - Already parsed by GROBID for PDF → TEI conversion
- **OCR needed?**: No.
- **Page model**: 1 structured document.
- **Scholarly value**: This is the gold standard for scholarly text encoding. GROBID already produces TEI. Can serve as an alternative input format and also as a richer output format.

#### JATS XML (.xml with JATS namespace)

- **Text extraction**: Parse with `lxml`. Extract `<body>` content with section structure.
- **Metadata extraction**: The `<article-meta>` element contains:
  - `<article-id pub-id-type="doi">`, `<article-id pub-id-type="pmid">`, `<article-id pub-id-type="pmc">`
  - `<title-group>` with `<article-title>`
  - `<contrib-group>` with `<contrib>` (authors, affiliations, ORCID)
  - `<abstract>`
  - `<pub-date>`
  - `<volume>`, `<issue>`, `<fpage>`, `<lpage>`
  - `<permissions>` (copyright, license)
  - `<funding-group>` with grant numbers
- **OCR needed?**: No.
- **Page model**: 1 structured document.
- **Scholarly value**: NLM/PubMed Central standard. Highly structured metadata from academic publishers.

#### SRT/VTT subtitles (.srt, .vtt)

- **Text extraction**: Parse the subtitle format directly. `.srt` has a simple `index → timestamp → text` structure. `.vtt` (WebVTT) is similar with a header.
- **Metadata extraction**: WebVTT has an optional header block with metadata. For SRT, derive metadata from the associated video filename. Can extract speaker labels if present.
- **OCR needed?**: No.
- **Page model**: 1 transcript per file.
- **Scholarly value**: Video transcripts, lecture recordings, accessibility research.

#### Log files (.log)

- **Text extraction**: Read as plain text with encoding detection.
- **Metadata extraction**: Filename, file size, line count, first/last timestamps (if parseable from log format), log format detection.
- **OCR needed?**: No.
- **Page model**: 1 stream per file.
- **Scholarly value**: System logs, experiment output, build logs. Common in reproducibility research.

---

## Part 2: Comprehensive Scholarly Metadata Model

### Design principle: structured nesting with backward-compatible flat fallback

The current `MetadataResult` has ~25 flat fields plus an `extra` dict. At 80+ fields, flat becomes unmanageable. The solution:

- **Keep existing flat fields** for backward compatibility (existing extraction code, serialization, checkpoints)
- **Add structured nested dataclasses** for domain-specific metadata groups
- **New extraction methods populate nested objects; old methods still populate flat fields**
- **Over time, consumers migrate to nested fields; flat fields become deprecated aliases**

### The nested metadata model

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Identifier enums
# ---------------------------------------------------------------------------

class IdentifierScheme(str, Enum):
    """Standard identifier schemes."""
    DOI = "doi"
    ISBN = "isbn"
    ISSN = "issn"
    EISSN = "eissn"
    PMID = "pmid"
    PMCID = "pmcid"
    ARXIV = "arxiv"
    HANDLE = "handle"
    URI = "uri"
    URN = "urn"
    LCCN = "lccn"
    OCLC = "oclc"
    ORCID = "orcid"
    ISNI = "isni"
    VIAF = "viaf"
    ROR = "ror"
    FUNDREF = "fundref"
    ISTC = "istc"
    ISRC = "isrc"
    ISMN = "ismn"
    PURL = "purl"
    SSRN = "ssrn"
    JSTORE = "jstor"
    OPENALEX = "openalex"
    WIKIDATA = "wikidata"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Citation metadata — everything needed for a complete citation
# ---------------------------------------------------------------------------

@dataclass
class CitationMetadata:
    """All fields needed for a complete scholarly citation of any document type."""

    # -- Core bibliographic --
    title: str = ""
    subtitle: str = ""
    translated_title: str = ""  # for works in non-English languages
    authors: list[Author] = field(default_factory=list)
    editors: list[str] = field(default_factory=list)
    translators: list[str] = field(default_factory=list)
    illustrators: list[str] = field(default_factory=list)

    # -- Publication --
    publisher_name: str = ""  # e.g., "Oxford University Press"
    publisher_place: str = ""  # e.g., "New York"
    publication_date: str = ""  # ISO 8601 or free text
    year: str = ""  # just the year, for backward compat

    # -- Container (journal, book, conference) --
    container_title: str = ""  # journal name, book title, conference name
    container_type: str = ""  # "journal", "book", "conference_proceedings", "website", "archive"
    volume: str = ""
    issue: str = ""
    edition: str = ""  # "2nd", "Revised", etc.
    series: str = ""  # book series name
    series_number: str = ""  # series volume number

    # -- Pages / extent --
    first_page: str = ""
    last_page: str = ""
    page_count: int = 0
    article_number: str = ""  # e-article number (e.g., "e0123456")

    # -- Document type specifics --
    document_type: str = ""  # "journal_article", "book", "book_chapter", "conference_paper",
                              # "dissertation", "patent", "report", "dataset", "software",
                              # "web_page", "legal_case", "standard", "map", "musical_score",
                              # "interview", "archival_document", "preprint", "blog_post",
                              # "presentation", "poster", "lecture", "personal_communication"

    # -- Dissertation specifics --
    dissertation_type: str = ""  # "phd", "masters", "bachelors"
    dissertation_institution: str = ""

    # -- Patent specifics --
    patent_number: str = ""
    patent_country: str = ""
    patent_status: str = ""  # "granted", "pending", "expired"
    patent_assignee: str = ""

    # -- Legal case specifics --
    docket_number: str = ""
    court: str = ""
    court_circuit: str = ""  # e.g., "9th Circuit"
    case_citation: str = ""  # e.g., "410 U.S. 113"
    parties: str = ""  # e.g., "Roe v. Wade"
    decision_date: str = ""

    # -- Standard / specification --
    standard_number: str = ""  # e.g., "ISO 9001:2015"
    standard_body: str = ""  # e.g., "ISO", "IEEE", "W3C"
    standard_status: str = ""  # "active", "superseded", "withdrawn"

    # -- Musical score --
    composer: str = ""
    arranger: str = ""
    opus_number: str = ""
    key: str = ""  # e.g., "C minor"
    instrumentation: list[str] = field(default_factory=list)

    # -- Map --
    scale: str = ""  # e.g., "1:50,000"
    projection: str = ""
    coordinates: str = ""  # bounding box as WKT or lat/lon
    map_publisher: str = ""

    # -- Web page --
    url: str = ""
    access_date: str = ""  # date the resource was accessed
    site_name: str = ""  # e.g., "Wikipedia", "GitHub"

    # -- Software --
    version: str = ""
    programming_language: str = ""
    repository_url: str = ""
    commit_hash: str = ""

    # -- Abstract / summary --
    abstract: str = ""
    abstract_language: str = ""  # ISO 639-1 of the abstract

    # -- Keywords / subjects --
    keywords: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)  # controlled vocabulary terms
    classification: list[str] = field(default_factory=list)  # e.g., "JEL D72", "MSC 65D18"

    # -- Language --
    language: str = ""  # ISO 639-3 code (three-letter, more precise than 639-1)
    language_name: str = ""  # human-readable, e.g., "English"

    # -- References --
    references: list[Reference] = field(default_factory=list)
    reference_count: int = 0
    cited_by_count: int = 0  # from CrossRef/Google Scholar


@dataclass
class Author:
    """A single author with identifiers."""
    name: str = ""  # full name as it appears on the document
    given_name: str = ""
    family_name: str = ""
    suffix: str = ""  # "Jr.", "III", "MD"
    orcid: str = ""
    isni: str = ""
    email: str = ""
    affiliation: list[str] = field(default_factory=list)
    role: str = ""  # "author", "editor", "translator", "corresponding"
    corresponding: bool = False


@dataclass
class Reference:
    """A single bibliographic reference (cited work)."""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    journal: str = ""
    volume: str = ""
    pages: str = ""
    doi: str = ""
    url: str = ""
    raw_text: str = ""  # the original reference string
    type: str = ""  # "journal-article", "book", "webpage", etc.


# ---------------------------------------------------------------------------
# Research context — provenance, funding, review, related works
# ---------------------------------------------------------------------------

@dataclass
class ResearchContext:
    """Provenance, funding, peer review, data availability, and related works."""

    # -- Provenance --
    source: str = ""  # where did this document come from?
    source_url: str = ""
    source_accession_date: str = ""
    source_method: str = ""  # "web_download", "api", "library_digitization", "user_upload", "email"
    collector: str = ""  # who collected/ingested this?
    collection_date: str = ""

    # -- Version history --
    version: str = ""  # e.g., "v1", "v2", "revised"
    version_stage: str = ""  # "preprint", "submitted", "accepted", "published",
                              # "revised", "corrected", "retracted", "expression_of_concern"
    preprint_server: str = ""  # "arXiv", "SSRN", "bioRxiv", "PsyArXiv"
    preprint_identifier: str = ""
    previous_versions: list[str] = field(default_factory=list)  # DOIs/URLs of prior versions
    revision_number: str = ""
    revision_date: str = ""

    # -- Peer review --
    peer_reviewed: bool | None = None  # None = unknown
    peer_review_type: str = ""  # "single-blind", "double-blind", "open", "post-publication"
    review_url: str = ""  # URL to published peer review (e.g., Publons, PeerJ)
    reviewer_identities: list[str] = field(default_factory=list)

    # -- Funding --
    funding: list[FundingAward] = field(default_factory=list)
    conflict_of_interest: str = ""  # free-text COI statement
    conflict_of_interest_flag: bool | None = None

    # -- Data / code availability --
    data_availability: str = ""  # free-text data availability statement
    data_availability_url: str = ""
    code_availability: str = ""
    code_availability_url: str = ""
    materials_availability: str = ""
    preregistration: str = ""  # e.g., OSF preregistration DOI/URL

    # -- Related works --
    related_datasets: list[str] = field(default_factory=list)  # DOIs
    related_software: list[str] = field(default_factory=list)  # DOIs/URLs
    related_publications: list[str] = field(default_factory=list)  # DOIs
    supplements: list[str] = field(default_factory=list)  # URLs


@dataclass
class FundingAward:
    """A single funding award."""
    funder_name: str = ""
    funder_identifier: str = ""  # ROR or FundRef ID
    award_number: str = ""
    award_title: str = ""
    award_url: str = ""


# ---------------------------------------------------------------------------
# Rights & licensing metadata
# ---------------------------------------------------------------------------

@dataclass
class RightsMetadata:
    """Copyright, licensing, and access rights."""

    # -- License --
    license_type: str = ""  # "CC-BY", "CC-BY-SA", "CC-BY-NC", "CC0", "MIT", "GPL", "proprietary"
    license_url: str = ""
    license_version: str = ""  # "4.0", "3.0"

    # -- Copyright --
    copyright_holder: str = ""
    copyright_year: str = ""
    copyright_statement: str = ""

    # -- Open access --
    open_access: bool | None = None
    oa_status: str = ""  # "gold", "green", "hybrid", "bronze", "closed"
    embargo_date: str = ""  # date when OA embargo ends
    oa_repository: str = ""  # arXiv, university repository, PubMed Central

    # -- Permissions --
    permissions: str = ""  # free-text permissions statement
    reuse_allowed: bool | None = None
    commercial_use_allowed: bool | None = None
    modifications_allowed: bool | None = None

    # -- Publisher agreements --
    sherpa_romeo_colour: str = ""  # "green", "blue", "yellow", "white"


# ---------------------------------------------------------------------------
# Technical metadata — file-level details
# ---------------------------------------------------------------------------

@dataclass
class TechnicalMetadata:
    """File format, encoding, image resolution, OCR details."""

    # -- File identity --
    file_format: str = ""  # "PDF", "EPUB", "DOCX", etc.
    file_format_version: str = ""  # "1.7", "A-3a", etc.
    file_extension: str = ""
    mime_type: str = ""
    magic_bytes: str = ""  # hex signature

    # -- File stats --
    file_size_bytes: int = 0
    file_size_human: str = ""  # "1.2 MB"
    checksum_sha256: str = ""
    checksum_md5: str = ""

    # -- Encoding / text properties --
    encoding: str = ""  # "UTF-8", "ISO-8859-1", etc.
    encoding_confidence: float = 0.0
    line_count: int = 0
    word_count: int = 0
    character_count: int = 0
    paragraph_count: int = 0
    has_math: bool | None = None  # detected math content
    has_tables: bool | None = None
    has_figures: bool | None = None
    detected_languages: list[LanguageDetection] = field(default_factory=list)

    # -- Creation software --
    creator_software: str = ""  # "Microsoft Word", "LaTeX", "Adobe InDesign", "LibreOffice"
    creator_software_version: str = ""
    producer_software: str = ""  # PDF producer, EPUB generator
    creation_date: str = ""  # file creation timestamp
    modification_date: str = ""  # file modification timestamp

    # -- Image-specific (for rendered/scanned docs) --
    page_width_px: int = 0
    page_height_px: int = 0
    resolution_dpi: int = 0
    color_space: str = ""  # "RGB", "CMYK", "grayscale", "bitonal"
    color_depth: int = 0  # bits per pixel
    compression: str = ""  # "JPEG", "LZW", "CCITT Group 4", etc.
    image_format: str = ""  # "PNG", "JPEG", "TIFF", etc.

    # -- Audio-specific --
    duration_seconds: float = 0.0
    sample_rate_hz: int = 0
    channels: int = 0  # 1 = mono, 2 = stereo
    audio_codec: str = ""
    bitrate_kbps: int = 0

    # -- Video-specific --
    video_codec: str = ""
    frame_rate: float = 0.0
    video_width: int = 0
    video_height: int = 0

    # -- OCR / processing --
    ocr_engine: str = ""  # which engine produced the text
    ocr_confidence: float = 0.0  # overall confidence (0.0-1.0)
    ocr_languages: list[str] = field(default_factory=list)


@dataclass
class LanguageDetection:
    """Language detection result."""
    language_code: str = ""  # ISO 639-3
    language_name: str = ""
    confidence: float = 0.0
    script: str = ""  # "Latin", "Cyrillic", "Arabic", etc.


# ---------------------------------------------------------------------------
# Archival / library metadata
# ---------------------------------------------------------------------------

@dataclass
class ArchivalMetadata:
    """Library and archive-specific metadata for physical and digitized documents."""

    # -- Collection --
    collection_name: str = ""  # e.g., "Ronald Reagan Presidential Papers"
    collection_id: str = ""  # collection-level identifier
    repository: str = ""  # e.g., "Library of Congress", "National Archives"
    repository_id: str = ""  # ROR or ISIL

    # -- Physical location --
    shelf_mark: str = ""  # library call number
    call_number: str = ""
    call_number_scheme: str = ""  # "LC", "Dewey", "UDC"
    box_number: str = ""
    folder_number: str = ""
    container_number: str = ""
    series_name: str = ""  # archival series
    subseries_name: str = ""
    accession_number: str = ""
    barcode: str = ""

    # -- Finding aid --
    finding_aid_url: str = ""
    finding_aid_title: str = ""
    ead_identifier: str = ""

    # -- Physical description --
    physical_extent: str = ""  # e.g., "5 pages", "1 volume (250 pages)", "3 audio cassettes"
    physical_medium: str = ""  # "paper", "microfilm", "vellum", "photograph", "audio cassette"
    dimensions: str = ""  # e.g., "21 x 30 cm"
    condition: str = ""  # e.g., "good", "fragile", "water damage on pp. 12-15"
    conservation_notes: str = ""
    binding: str = ""  # "hardcover", "paperback", "spiral", "loose leaf"

    # -- Digitization --
    digitization_date: str = ""
    digitization_institution: str = ""
    digitization_equipment: str = ""  # e.g., "Epson Expression 12000XL"
    digitization_notes: str = ""
    master_file_location: str = ""  # URL or path to archival master


# ---------------------------------------------------------------------------
# Identifier set — all standard identifiers in one place
# ---------------------------------------------------------------------------

@dataclass
class IdentifierSet:
    """All standard identifiers for a document.

    Each field maps to a known identifier scheme. Fields are strings
    (with empty string = absent) rather than Optional[str] to simplify
    serialization and avoid None-checking everywhere.
    """

    doi: str = ""
    isbn: str = ""  # ISBN-13 preferred; ISBN-10 accepted
    isbn_set: list[str] = field(default_factory=list)  # multiple ISBNs (hardcover, paperback, ebook)
    issn: str = ""
    eissn: str = ""
    pmid: str = ""
    pmcid: str = ""
    arxiv: str = ""  # e.g., "2301.12345" or "arXiv:2301.12345"
    arxiv_version: str = ""  # "v1", "v2"
    handle: str = ""  # Handle System identifier (e.g., "20.1000/100")
    uri: str = ""  # any URI identifier
    lccn: str = ""  # Library of Congress Control Number
    oclc: str = ""  # OCLC / WorldCat number
    ssrn: str = ""  # Social Science Research Network
    jstor: str = ""
    openalex: str = ""  # OpenAlex ID (e.g., "W3123456789")
    wikidata: str = ""
    purl: str = ""  # Persistent URL

    # -- Author identifiers (can be lists) --
    orcids: list[str] = field(default_factory=list)
    isni: list[str] = field(default_factory=list)  # ISNI for contributors

    # -- Institutional identifiers --
    ror_ids: list[str] = field(default_factory=list)  # ROR IDs for affiliations

    # -- Work-level identifiers --
    istc: str = ""  # International Standard Text Code
    ismn: str = ""  # International Standard Music Number
    isrc: str = ""  # International Standard Recording Code

    # -- Catch-all for unknown schemes --
    custom: dict[str, str] = field(default_factory=dict)

    def as_flat_dict(self) -> dict[str, str]:
        """Return all non-empty identifiers as a flat {scheme: value} dict."""
        result: dict[str, str] = {}
        for field_name in self.__dataclass_fields__:
            if field_name == "custom":
                continue
            value = getattr(self, field_name)
            if isinstance(value, str) and value:
                result[field_name] = value
            elif isinstance(value, list) and value:
                result[field_name] = ",".join(value)
        result.update(self.custom)
        return {k: v for k, v in result.items() if v}  # strip empties

    @classmethod
    def from_flat_dict(cls, current_identifiers: dict[str, str]) -> IdentifierSet:
        """Initialize from the current model's identifiers dict."""
        known = {f.name: f.type for f in cls.__dataclass_fields__ if f.name != "custom"}
        result = cls()
        for key, value in current_identifiers.items():
            if key in known:
                setattr(result, key, value)
            else:
                result.custom[key] = value
        return result


# ---------------------------------------------------------------------------
# Provenance event — processing history
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceEvent:
    """One step in the document's processing history."""

    step: str = ""  # e.g., "text_extraction", "ocr", "vlm_merge", "metadata_extraction",
                     # "identifier_resolution", "language_detection", "format_conversion"
    engine: str = ""  # e.g., "pymupdf", "tesseract", "marker", "gemini-2.5-flash", "grobid"
    engine_version: str = ""  # e.g., "1.24.0", "0.4.0"
    timestamp: str = ""  # ISO 8601
    success: bool = True
    error: str = ""  # error message if failed
    duration_sec: float = 0.0
    parameters: dict[str, Any] = field(default_factory=dict)  # e.g., {"dpi": 300, "language": "en"}
    input_checksum: str = ""  # checksum of input data
    output_checksum: str = ""  # checksum of output data
    notes: str = ""  # free-text annotations


# ---------------------------------------------------------------------------
# Top-level metadata result (evolved from current MetadataResult)
# ---------------------------------------------------------------------------

@dataclass
class MetadataResult:
    """Structured metadata extracted from a document.

    This is an evolution of the existing flat MetadataResult. All existing
    flat fields are preserved for backward compatibility. New domain-specific
    metadata is organized into nested dataclasses.

    Consumers should prefer the nested fields (citation, research_context,
    technical, rights, archival, identifiers) for new code. The flat fields
    will be kept populated for backward compatibility.

    Populated by format-native extractors, VLM analysis, GROBID, and
    identifier resolution services.
    """

    # === Flat fields (backward compatible with existing MetadataResult) ===

    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    doi: str = ""
    journal: str = ""
    volume: str = ""
    issue: str = ""
    year: str = ""
    pages: str = ""
    references: list[dict] = field(default_factory=list)
    raw_tei: str = ""  # raw GROBID TEI XML (kept for debugging)

    document_type: str = ""
    language: str = ""  # ISO 639-1 (backward compat; prefer citation.language)
    publisher: str = ""
    date: str = ""

    isbn: str = ""
    docket_number: str = ""
    court: str = ""
    edition: str = ""
    series: str = ""
    part_number: str = ""
    revision: str = ""

    extraction_method: str = ""  # "vlm", "grobid", "epub", "docx", "pdf", "none", etc.
    identifiers: dict[str, str] = field(default_factory=dict)  # backward compat
    extra: dict[str, Any] = field(default_factory=dict)

    # === NEW: Structured nested metadata ===

    citation: CitationMetadata = field(default_factory=CitationMetadata)
    research_context: ResearchContext = field(default_factory=ResearchContext)
    technical: TechnicalMetadata = field(default_factory=TechnicalMetadata)
    rights: RightsMetadata = field(default_factory=RightsMetadata)
    archival: ArchivalMetadata = field(default_factory=ArchivalMetadata)

    # === NEW: Provenance chain ===

    provenance_chain: list[ProvenanceEvent] = field(default_factory=list)

    # === NEW: Extraction metadata ===

    extraction_confidence: float = 0.0  # 0.0-1.0 overall confidence in metadata
    extraction_warnings: list[str] = field(default_factory=list)  # non-fatal issues

    def to_dict(self) -> dict[str, Any]:
        """Serialize all fields including nested objects.

        Backward compatible: existing flat fields serialize the same way.
        Nested objects are serialized under their own keys.
        """
        return {
            # Flat fields (backward compatible)
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "doi": self.doi,
            "journal": self.journal,
            "volume": self.volume,
            "issue": self.issue,
            "year": self.year,
            "pages": self.pages,
            "references": self.references,
            "raw_tei": self.raw_tei,
            "document_type": self.document_type,
            "language": self.language,
            "publisher": self.publisher,
            "date": self.date,
            "isbn": self.isbn,
            "docket_number": self.docket_number,
            "court": self.court,
            "edition": self.edition,
            "series": self.series,
            "part_number": self.part_number,
            "revision": self.revision,
            "extraction_method": self.extraction_method,
            "identifiers": self.identifiers,
            "extra": self.extra,
            # Nested objects (NEW)
            "citation": self._serialize_dataclass(self.citation),
            "research_context": self._serialize_dataclass(self.research_context),
            "technical": self._serialize_dataclass(self.technical),
            "rights": self._serialize_dataclass(self.rights),
            "archival": self._serialize_dataclass(self.archival),
            "provenance_chain": [self._serialize_dataclass(e) for e in self.provenance_chain],
            # Extraction metadata
            "extraction_confidence": self.extraction_confidence,
            "extraction_warnings": self.extraction_warnings,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MetadataResult:
        """Deserialize from a dict. Backward compatible with old checkpoint files."""
        result = cls(
            # Flat fields
            title=str(d.get("title", "")),
            authors=[str(a) for a in d.get("authors", [])],
            abstract=str(d.get("abstract", "")),
            keywords=[str(k) for k in d.get("keywords", [])],
            doi=str(d.get("doi", "")),
            journal=str(d.get("journal", "")),
            volume=str(d.get("volume", "")),
            issue=str(d.get("issue", "")),
            year=str(d.get("year", "")),
            pages=str(d.get("pages", "")),
            references=[dict(r) for r in d.get("references", [])] if d.get("references") else [],
            raw_tei=str(d.get("raw_tei", "")),
            document_type=str(d.get("document_type", "")),
            language=str(d.get("language", "")),
            publisher=str(d.get("publisher", "")),
            date=str(d.get("date", "")),
            isbn=str(d.get("isbn", "")),
            docket_number=str(d.get("docket_number", "")),
            court=str(d.get("court", "")),
            edition=str(d.get("edition", "")),
            series=str(d.get("series", "")),
            part_number=str(d.get("part_number", "")),
            revision=str(d.get("revision", "")),
            extraction_method=str(d.get("extraction_method", "")),
            identifiers=d.get("identifiers", {}) or {},
            extra=d.get("extra", {}) or {},
            extraction_confidence=float(d.get("extraction_confidence", 0.0)),
            extraction_warnings=[str(w) for w in d.get("extraction_warnings", [])],
        )
        # Deserialize nested objects if present (None from old checkpoint files)
        if d.get("citation"):
            result.citation = cls._deserialize_dataclass(CitationMetadata, d["citation"])
        if d.get("research_context"):
            result.research_context = cls._deserialize_dataclass(ResearchContext, d["research_context"])
        if d.get("technical"):
            result.technical = cls._deserialize_dataclass(TechnicalMetadata, d["technical"])
        if d.get("rights"):
            result.rights = cls._deserialize_dataclass(RightsMetadata, d["rights"])
        if d.get("archival"):
            result.archival = cls._deserialize_dataclass(ArchivalMetadata, d["archival"])
        if d.get("provenance_chain"):
            result.provenance_chain = [
                cls._deserialize_dataclass(ProvenanceEvent, e)  # type: ignore[arg-type]
                for e in d["provenance_chain"]
            ]
        return result

    @staticmethod
    def _serialize_dataclass(obj: Any) -> dict[str, Any]:
        """Recursively serialize a dataclass to a dict."""
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dataclass_fields__"):
            result: dict[str, Any] = {}
            for f_name in obj.__dataclass_fields__:
                value = getattr(obj, f_name)
                if isinstance(value, list):
                    result[f_name] = [
                        MetadataResult._serialize_dataclass(item)
                        if hasattr(item, "__dataclass_fields__") else item
                        for item in value
                    ]
                elif hasattr(value, "__dataclass_fields__"):
                    result[f_name] = MetadataResult._serialize_dataclass(value)
                elif value is not None:
                    result[f_name] = value
            return result
        return str(obj)

    @staticmethod
    def _deserialize_dataclass(cls: type, d: dict[str, Any]) -> Any:
        """Recursively deserialize a dict to a dataclass instance."""
        if hasattr(cls, "from_dict"):
            return cls.from_dict(d)
        kwargs: dict[str, Any] = {}
        for field_info in cls.__dataclass_fields__.values():
            f_name = field_info.name
            if f_name in d:
                value = d[f_name]
                # Handle nested lists of dataclasses
                field_type = field_info.type
                if hasattr(field_type, "__origin__") and field_type.__origin__ is list:
                    args = field_type.__args__
                    if args and hasattr(args[0], "__dataclass_fields__"):
                        kwargs[f_name] = [
                            MetadataResult._deserialize_dataclass(args[0], item)  # type: ignore[arg-type]
                            for item in (value if isinstance(value, list) else [])
                        ]
                    else:
                        kwargs[f_name] = value if isinstance(value, list) else []
                elif hasattr(field_info.type, "__dataclass_fields__"):
                    kwargs[f_name] = MetadataResult._deserialize_dataclass(field_info.type, value)
                else:
                    kwargs[f_name] = value
        return cls(**kwargs)

    # ------------------------------------------------------------------
    # Convenience: sync flat fields from nested objects
    # ------------------------------------------------------------------

    def sync_nested_to_flat(self) -> None:
        """Copy values from nested objects into flat fields for backward compat.

        Call this before serialization to ensure flat fields are populated.
        Nested fields are the source of truth; flat fields are derived aliases.
        """
        c = self.citation
        if c.title:
            self.title = c.title
        if c.authors:
            self.authors = [a.name for a in c.authors]
        if c.abstract:
            self.abstract = c.abstract
        if c.keywords:
            self.keywords = c.keywords
        if c.year:
            self.year = c.year
        if c.container_title:
            self.journal = c.container_title
        if c.volume:
            self.volume = c.volume
        if c.issue:
            self.issue = c.issue
        if c.document_type:
            self.document_type = c.document_type
        if c.language:
            self.language = c.language
        if c.publisher_name:
            self.publisher = c.publisher_name
        if c.publication_date:
            self.date = c.publication_date
        if c.edition:
            self.edition = c.edition
        if c.series:
            self.series = c.series
        if c.docket_number:
            self.docket_number = c.docket_number
        if c.court:
            self.court = c.court
        if c.patent_number:
            self.part_number = c.patent_number
        if c.version:
            self.revision = c.version

        # Sync identifiers
        ids = self.identifiers  # backward-compat dict
        id_set = IdentifierSet.from_flat_dict(ids)
        if id_set.doi:
            self.doi = id_set.doi
        if id_set.isbn:
            self.isbn = id_set.isbn
```

### Metadata extraction priority chain

The pipeline should extract metadata in this order, with each later stage enriching (not replacing) earlier results:

```
1. FORMAT-NATIVE EXTRACTION (always runs, always first)
   ├── PDF: PyMuPDF metadata dict → flat fields
   ├── EPUB: OPF Dublin Core → citation fields
   ├── DOCX: core.xml properties → flat fields
   ├── TXT: filename heuristics → title, date
   ├── Image: EXIF → date, creator, dimensions
   ├── HTML: meta tags, schema.org JSON-LD, OG → citation + technical
   ├── LaTeX: regex patterns → title, authors, date
   ├── Markdown: YAML frontmatter → citation fields
   ├── RTF: \info block → title, author, dates
   ├── ODT: meta.xml Dublin Core → citation fields
   ├── DJVU: bundled metadata / OCR text layer → citation
   ├── Email (.eml): headers → title (subject), authors (from), date
   ├── JSON: JSON-LD @context, $schema → identifiers
   ├── TEI XML: teiHeader → citation + archival
   ├── JATS XML: article-meta → citation + funding + rights
   ├── SRT/VTT: filename → title
   └── CSV/Excel/PPTX: file properties → technical

2. VLM ANALYSIS (if enabled and confidence < threshold after step 1)
   └── Gemini/Claude analyzes rendered pages → broad metadata extraction
       Populates: citation, research_context, rights, identifiers

3. GROBID (academic PDFs only)
   └── TEI XML parsing → citation fields (authoritative for academic articles)
       Populates: citation.authors (with affiliations), citation.references

4. IDENTIFIER RESOLUTION (if enabled — see Part 3, Question 4)
   ├── DOI → CrossRef API → full citation metadata (REST JSON)
   ├── ISBN → OpenLibrary / Google Books API → citation metadata
   ├── PMID → PubMed API → citation + MeSH terms
   ├── arXiv ID → arXiv API → version history, categories
   └── ORCID → ORCID API → author names, affiliations

5. LANGUAGE DETECTION (if language not already known)
   └── lingua-py / langdetect / fasttext on extracted text → technical.detected_languages

6. REFERENCE PARSING (if references not already structured)
   └── anystyle.io / GROBID references / regex patterns → citation.references
```

### Mapping format-native metadata to the model

Each `DocumentSource.extract_metadata()` should populate BOTH flat fields (for backward compat) AND nested fields (for new consumers):

| Source | Flat fields populated | Nested fields populated |
|--------|----------------------|------------------------|
| PDF (PyMuPDF) | title, authors (from meta dict) | citation.title, citation.authors (shallow), technical.file_format, technical.creator_software |
| PDF (GROBID) | title, authors, abstract, keywords, doi, journal, volume, issue, year, pages, references, raw_tei | citation.* (full), citation.references (structured) |
| EPUB (OPF) | title, authors, publisher, date, language, isbn, document_type="book" | citation.title, citation.authors, citation.publisher_name, citation.publication_date, citation.language, identifiers.isbn, citation.document_type="book" |
| DOCX (core.xml) | title, authors, date, language, document_type="document" | citation.title, citation.authors, citation.publication_date, citation.language, technical.creator_software |
| TXT | title (filename), date (mtime), document_type="text" | citation.title, technical.file_size_bytes, technical.encoding |
| Image (EXIF) | title, authors, date, document_type="image" | citation.title, citation.authors, citation.publication_date, technical.* (width, height, color_space, etc.) |
| HTML | title (og:title, meta), authors (meta author), abstract (meta description), doi (Highwire Press), date | citation.* (rich from schema.org JSON-LD), identifiers.*, rights.license_type |
| LaTeX | title (\title{}), authors (\author{}), date (\date{}) | citation.title, citation.authors, citation.publication_date, research_context.version (from \bibliography{}) |
| Markdown | title (frontmatter or H1), authors (frontmatter), date (frontmatter) | citation.title, citation.authors, citation.publication_date, citation.keywords (tags in frontmatter) |
| RTF | title (\info title), authors (\info author), date (\info creatim) | citation.title, citation.authors, citation.publication_date, technical.creator_software |
| ODT | title (dc:title), authors (dc:creator), date (dc:date), language (dc:language) | citation.* (from Dublin Core), technical.* (from meta:document-statistic, meta:generator) |
| DJVU | title, authors, date (from file bundle) | citation.*, technical.page_count, technical.file_format="DJVU" |
| Email (.eml) | title (Subject), authors (From), date (Date header) | citation.title, citation.authors, citation.publication_date, technical.*, identifiers (Message-ID) |
| JSON-LD | title, authors, date, doi (from @context parsing) | citation.*, identifiers.*, research_context.funding (if present in JSON-LD) |
| TEI XML | title (teiHeader/fileDesc/titleStmt/title), authors (author), date, publisher | citation.* (full), archival.* (from msDesc if present), technical.* (from encodingDesc) |
| JATS XML | title, authors (with affiliations), abstract, doi, pmid, journal, volume, issue, year, pages | citation.* (full), research_context.funding (from funding-group), rights.* (from permissions) |
| VLM (Gemini/Claude) | ALL flat fields (based on VLM prompt) | citation.*, research_context.*, rights.*, identifiers.* |
| CrossRef API | title, authors, abstract, journal, volume, issue, year, pages, doi | citation.* (full), research_context.funding, research_context.cited_by_count, identifiers.* |
| OpenLibrary API | title, authors, publisher, date, isbn, subjects | citation.*, identifiers.isbn_set, citation.subjects |

---

## Part 3: Architecture Recommendations

### 1. Metadata model structure

**Recommendation: Keep flat fields + add nested typed objects. Do NOT remove flat fields.**

Rationale:
- The current `MetadataResult` with flat fields is used throughout the codebase (formatter, CLI, checkpoint, engines). Removing flat fields would require changes to every consumer.
- Adding nested objects is additive — new code can use the nested fields, old code continues to work with flat fields.
- The `sync_nested_to_flat()` bridge method ensures consistency when both are populated.
- In a future v2.0, flat fields can be deprecated in favor of nested accessors.

**The `extra: dict` field should remain as the escape hatch** for truly ad-hoc metadata that doesn't fit any category. It should NOT be the primary place to stuff structured metadata.

### 2. Filetype prioritization

**Phase 1 (now):** Implement the `DocumentSource` ABC pattern (already designed in `docs/multi-format-architecture.md`) for these formats:

1. **PDF** (existing code, wrap in `PdfSource`)
2. **EPUB** (libraries: `ebooklib`, `beautifulsoup4`)
3. **DOCX** (library: `python-docx`)
4. **TXT** (stdlib + `chardet`)
5. **Images** (Pillow, already in deps)
6. **CSV** (stdlib `csv`)
7. **Excel (.xlsx)** (`openpyxl` — already specified)
8. **PPTX** (`python-pptx` — already specified)

**Phase 1.5 (highest priority additions beyond the already-researched formats):**

9. **HTML** — highest-value Tier 1 addition. Schema.org JSON-LD + Highwire Press tags yield richer metadata than any other format. Every academic publisher's website has them. Low implementation complexity (just `beautifulsoup4` + `json`).
10. **LaTeX** — critical for arXiv pipeline, academic preprints. Trivial implementation (plain text + regex).
11. **Markdown** — trivial implementation. YAML frontmatter yields structured metadata. Pervasive.
12. **TEI XML + JATS XML** — GROBID already produces TEI. JATS is the NLM standard. Both have rich structured metadata. Use `lxml` which is already a dependency.
13. **DJVU** — critical for digital library collections. Requires `djvulibre` tools (subprocess or `pydjvu`).
14. **Multi-page TIFF** — small extension to `ImageSource`. Critical for archival documents.
15. **Email (.eml)** — stdlib `email` module. Very low implementation cost. Critical for correspondence archives.
16. **RTF** — low complexity. Important for legal documents and legacy word processing.

**Phase 2 (later):** Archive recursion (ZIP, TAR, 7z), Jupyter notebooks, MBOX, audio/video (STT), GIS, CAD.

**Phase 3 (future):** MARC, ONIX, EAD, METS/ALTO, DRM-protected e-books, sheet music, scientific data formats.

### 3. Metadata extraction strategy per format

Every format should extract metadata from these layers, in priority order:

**Layer 1: File-internal metadata** (always available, zero network cost)
- Document properties (PDF dict, EPUB OPF, DOCX core.xml, EXIF, ID3 tags)
- Structured markup (schema.org JSON-LD in HTML, teiHeader in TEI, article-meta in JATS)
- Convention-based parsing (YAML frontmatter in Markdown, `\title{}` in LaTeX, email headers)

**Layer 2: VLM analysis** (available for any format that can be rendered)
- 3-page visual analysis by Gemini/Claude
- Works on any document type, not just academic papers
- Broad but less precise than structured extraction

**Layer 3: Identifier resolution** (network-dependent, high precision)
- DOI → CrossRef, ISBN → OpenLibrary, PMID → PubMed, arXiv ID → arXiv API
- Optional, configurable, rate-limited, cached

**Layer 4: User-provided sidecar metadata** (highest authority, overrides all)
- `.meta.yaml` or `.meta.json` adjacent to the source file
- Same naming convention: `document.pdf.meta.yaml`
- Provides manual overrides for anything the automated extraction got wrong

### 4. Identifier resolution

**Recommendation: YES, add identifier resolution as an optional pipeline stage.**

Implementation plan:

```python
# New module: src/ocr_pipeline/enricher.py

class IdentifierResolver:
    """Resolve identifiers to enrich metadata.

    Resolution chain:
    1. DOI → CrossRef REST API (public, no auth required for basic queries)
       → Returns: full citation, authors with affiliations, references, funding
    2. ISBN → OpenLibrary API (public, no auth) + Google Books API (optional API key)
       → Returns: full citation, subjects, cover URLs
    3. PMID → PubMed E-utilities API (public, no auth)
       → Returns: full citation, MeSH terms, abstract
    4. arXiv ID → arXiv API (public, OAI-PMH)
       → Returns: version history, categories, license
    5. ORCID → ORCID Public API (public, no auth for public data)
       → Returns: author name, affiliations, other works
    """

    def __init__(self, cache_dir: Path | None = None, timeout_sec: float = 30):
        self._cache_dir = cache_dir
        self._timeout = timeout_sec
        self._rate_limiter = RateLimiter(calls_per_second=1.0)  # be polite

    def resolve_doi(self, doi: str) -> dict[str, Any]:
        """Query CrossRef API for DOI metadata."""
        ...

    def resolve_isbn(self, isbn: str) -> dict[str, Any]:
        """Query OpenLibrary API for ISBN metadata."""
        ...

    def resolve_pmid(self, pmid: str) -> dict[str, Any]:
        """Query PubMed API for PMID metadata."""
        ...

    def resolve_all(self, metadata: MetadataResult) -> MetadataResult:
        """Attempt to resolve any identifiers found in the metadata."""
        ...
```

Configuration flags:

```python
@dataclass
class PipelineConfig:
    # ... existing fields ...

    # -- Metadata enrichment --
    enrich_metadata: bool = False  # enable identifier resolution
    enrich_doi: bool = True  # resolve DOIs via CrossRef
    enrich_isbn: bool = True  # resolve ISBNs via OpenLibrary
    enrich_pmid: bool = True  # resolve PMIDs via PubMed
    enrich_arxiv: bool = True  # resolve arXiv IDs via arXiv API
    enrich_orcid: bool = True  # resolve ORCIDs via ORCID API
    enrich_cache_dir: Path | None = None  # cache directory for API responses
    enrich_timeout_sec: float = 30.0
    enrich_rate_limit: float = 1.0  # calls per second (be polite to APIs)
```

Key design decisions:
- **Always optional** — network calls should never block processing
- **Fail-safe** — API timeouts/errors degrade gracefully (metadata just stays as-is)
- **Cached** — don't re-query the same DOI twice (filesystem cache)
- **Rate-limited** — be respectful of public APIs
- **Non-destructive** — enrichment adds to metadata, never removes what was already extracted

### 5. Provenance tracking

**Recommendation: YES, record every processing step as a ProvenanceEvent.**

This is essential for scholarly use — a researcher needs to know:
- Was this text directly extracted from a Word document, or OCR'd from a scanned image?
- Which OCR engine produced it, and with what confidence?
- Was the text merged by a VLM? Which model?
- What was the chain of processing?

Implementation:

```python
# In Pipeline._process_single_page() or PageProcessor.process():
ctx.page.metadata["provenance"] = [e.to_dict() for e in provenance_chain]

# Example chain for a scanned PDF page:
provenance_chain = [
    ProvenanceEvent(
        step="rendering", engine="pymupdf", engine_version="1.24.0",
        timestamp="2026-07-03T10:00:00Z", success=True, duration_sec=0.1,
        parameters={"dpi": 300, "page_index": 5},
    ),
    ProvenanceEvent(
        step="ocr", engine="tesseract", engine_version="5.3.3",
        timestamp="2026-07-03T10:00:02Z", success=True, duration_sec=1.2,
        parameters={"languages": ["eng"], "oem": 3, "psm": 6},
        output_checksum="sha256:abc123...",
    ),
    ProvenanceEvent(
        step="vlm_merge", engine="gemini-2.5-flash", engine_version="gemini-2.5-flash-001",
        timestamp="2026-07-03T10:00:05Z", success=True, duration_sec=2.3,
        parameters={"max_tokens": 8192, "agreement_threshold": 0.97},
    ),
    ProvenanceEvent(
        step="text_extraction", engine="pymupdf", engine_version="1.24.0",
        timestamp="2026-07-03T10:00:01Z", success=False,
        error="No extractable text on image-only page",
    ),
]
```

### Files to create

```
src/ocr_pipeline/
├── sources/
│   ├── __init__.py           # DocumentSource ABC + FormatRegistry + detect() factory
│   ├── pdf.py                # PdfSource (wraps existing extractor.py / renderer.py)
│   ├── epub.py               # EpubSource (ebooklib + bs4)
│   ├── docx.py               # DocxSource (python-docx)
│   ├── txt.py                # TxtSource (stdlib + chardet)
│   ├── image.py              # ImageSource (Pillow, multi-page TIFF)
│   ├── html.py               # HtmlSource (bs4 + json for schema.org JSON-LD)
│   ├── latex.py              # LatexSource (plain text + regex)
│   ├── markdown.py           # MarkdownSource (plain text + YAML frontmatter)
│   ├── rtf.py                # RtfSource (striprtf)
│   ├── odt.py                # OdtSource (unzip + lxml)
│   ├── djvu.py               # DjvuSource (djvulibre subprocess)
│   ├── email_source.py       # EmailSource (email stdlib)
│   ├── csv_source.py         # CsvSource (csv stdlib)
│   ├── excel_source.py       # ExcelSource (openpyxl)
│   ├── pptx_source.py        # PptxSource (python-pptx)
│   ├── tei_xml.py            # TeiXmlSource (lxml)
│   ├── jats_xml.py           # JatsXmlSource (lxml)
│   ├── json_source.py        # JsonSource (json stdlib + json-ld detection)
│   └── subtitle.py           # SubtitleSource (SRT/VTT parse)
├── enricher.py               # IdentifierResolver (CrossRef, OpenLibrary, PubMed, arXiv, ORCID)
├── provenance.py             # ProvenanceTracker (records processing events)
```

### Existing files to modify

| File | Changes |
|------|---------|
| `models.py` | Add nested dataclasses: `CitationMetadata`, `ResearchContext`, `TechnicalMetadata`, `RightsMetadata`, `ArchivalMetadata`, `IdentifierSet`, `ProvenanceEvent`, `Author`, `Reference`, `FundingAward`, `LanguageDetection`. Extend `MetadataResult` with nested fields + `sync_nested_to_flat()`. Add `file_type` to `PdfProgress` and `FileIdentity`. |
| `config.py` | Add `input_extensions: list[str] \| None`, `input_file_concurrency: int`, `enrich_metadata: bool`, `enrich_doi: bool`, `enrich_isbn: bool`, `enrich_pmid: bool`, `enrich_arxiv: bool`, `enrich_orcid: bool`, `enrich_cache_dir: Path \| None`, `enrich_timeout_sec: float`, `enrich_rate_limit: float`, `sidecar_metadata: bool`. Add `pdf_concurrency` backward-compat alias. Update `_ENV_MAP`, `_from_dict`, `_flatten_dict`. |
| `pipeline.py` | `run()`: glob multiple extensions via `DocumentSource.supported_extensions()`. `process_one()`: accept `DocumentSource`. `_extract_metadata()`: add format-native step before VLM, add enricher step after. `_process_single_page()`: use `source` instead of `pdf_path`. Add provenance recording at each step. |
| `page_processor.py` | `PageContext.pdf_path` → `PageContext.source`. Add `source_image: Path \| None` for image inputs. `_try_text_extraction()`: delegate to `source.extract_text()`. `_render_page()`: delegate to `source.render_page()`. Handle image format (bypass rendering). |
| `formatter.py` | Update YAML frontmatter writer in `_produce_document_output()` to include nested metadata fields. Add a `JsonLinesFormatter` for streaming output. |
| `checkpoint.py` | Handle `file_type` in checkpoint serialization. |
| `__init__.py` | Export new public API: `DocumentSource`, `FormatRegistry`, `IdentifierResolver`, all new metadata dataclasses. |
| `pyproject.toml` | Add optional dependencies: `epub`, `docx`, `csv`, `excel`, `pptx`, `html`, `latex`, `rtf`, `odt`, `djvu`, `enrich`. |

### Untouched files

`renderer.py`, `extractor.py`, `merger.py`, `costing.py`, `errors.py`, `postprocess.py`, `progress.py`, `languages.py`, `profiles.py`, all engine files. These continue to work unchanged — the abstraction layer wraps them.

---

## Risks & Mitigations

### 1. Metadata model bloat
**Risk**: The nested metadata model has 80+ fields, many of which will be empty for most documents.
**Mitigation**: Default values are all empty strings/empty lists. Serialization omits empty fields via the `_serialize_dataclass` logic (which skips falsy values). JSON output is sparse. Storage overhead is minimal.

### 2. Backward compatibility break
**Risk**: Old checkpoint files lack `file_type`, nested metadata objects, and provenance chains.
**Mitigation**: All new fields have defaults. `from_dict()` handles missing keys gracefully. `PdfProgress.from_dict()` defaults `file_type="pdf"` for old checkpoints. The pipeline never fails on old data.

### 3. Dependency explosion
**Risk**: Adding 15+ new format handlers means 15+ new optional dependencies.
**Mitigation**: All format handlers use lazy imports (`try: import ... except ImportError: raise ImportError("...")`). Dependencies are organized as `[project.optional-dependencies]` groups. Core pipeline requires zero new dependencies for PDF-only use.

### 4. Network dependency for enrichment
**Risk**: Identifier resolution adds network calls that can fail or time out.
**Mitigation**: Enrichment is disabled by default (`enrich_metadata: false`). When enabled, it uses a filesystem cache, rate limiting, timeouts, and graceful degradation.

### 5. DJVU dependency availability
**Risk**: `djvulibre` is a C library that may not be available on all platforms.
**Mitigation**: Lazily detect availability at runtime. If `djvutxt` is not on PATH, `DjvuSource` raises a clear error message with installation instructions. Mark `djvu` as an optional extra.

### 6. DRM-protected files
**Risk**: EPUB/PDF with DRM will fail to open.
**Mitigation**: Catch DRM errors, log a clear message, and record a `ProvenanceEvent` with `success=False`. Add a `file_type="drm_protected"` status and skip further processing.

### 7. Performance with multi-thousand-page TIFFs
**Risk**: A 10,000-frame TIFF could OOM or take hours.
**Mitigation**: Add a `max_pages_per_file` config (default `None` = no limit). If exceeded, warn and truncate. `ImageSource.page_count()` reads frame count without loading all frames into memory.

### 8. Metadata extraction conflicts
**Risk**: When multiple sources provide different values for the same field (e.g., title from format-native vs. VLM vs. CrossRef), which one wins?
**Mitigation**: Priority: user-provided sidecar > CrossRef/API enrichment > VLM > GROBID > format-native. The enrichment chain is additive — later stages only fill gaps, never overwrite existing values unless configured to do so. Each stage records its provenance.

---

## Implementation Roadmap

### Phase 1: Foundation (2-3 weeks)
1. Extend `MetadataResult` with nested dataclasses (+ `sync_nested_to_flat()`)
2. Add `DocumentSource` ABC + `FormatRegistry` + `detect()` factory
3. Implement `PdfSource` (wrap existing code)
4. Implement `EpubSource`, `DocxSource`, `TxtSource`, `ImageSource`, `CsvSource`, `ExcelSource`, `PptxSource`
5. Add multi-page TIFF support to `ImageSource`
6. Refactor `Pipeline`, `PageProcessor`, `PdfProgress`/`FileIdentity` for format-agnostic operation
7. Update `ConfigLoader` for new fields
8. All existing tests must still pass

### Phase 1.5: High-value formats (1-2 weeks)
9. `HtmlSource` (schema.org JSON-LD + Highwire Press)
10. `LatexSource`
11. `MarkdownSource`
12. `TeiXmlSource` + `JatsXmlSource`
13. `DjvuSource`
14. `EmailSource`

### Phase 2: Enrichment + Provenance (1 week)
15. `IdentifierResolver` (CrossRef, OpenLibrary, PubMed, arXiv, ORCID)
16. `ProvenanceTracker` integration into Pipeline and PageProcessor
17. Sidecar metadata support (`.meta.yaml` / `.meta.json`)
18. Language detection integration (if language not already known)

### Phase 2.5: Additional Tier 1 formats (1 week)
19. `RtfSource`
20. `OdtSource`
21. `JsonSource` (with JSON-LD detection)
22. `SubtitleSource`
23. `LogSource`

### Phase 3: Archives + Tier 2 (future)
24. Archive recursion (ZIP, TAR, 7z, GZ)
25. Jupyter notebook (`IpynbSource`)
26. MBOX email archive
27. Audio/video (STT + metadata)
28. GIS, CAD, RDF

### Phase 4: Specialized (future)
29. MARC, ONIX, EAD, METS/ALTO
30. DRM detection and handling
31. Sheet music (MusicXML, MEI)
32. Scientific data formats (HDF5, NetCDF, FITS, DICOM)
```

