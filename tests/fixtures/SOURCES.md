# OCR Pipeline Test Fixtures — Sources

All documents are public domain or freely redistributable.

## 1. Academic

| Fixture | Source | Pages | License |
|---|---|---|---|
| `academic/title_abstract.pdf` | Llama 2 Technical Report (arXiv:2307.09288) | Page 0 | CC BY 4.0 |
| `academic/citations_body.pdf` | LLaMA Technical Report (arXiv:2302.13971) | Page 1 | CC BY 4.0 |

**Source URLs:**
- https://arxiv.org/abs/2307.09288 (Hugo Touvron et al., "Llama 2: Open Foundation and Fine-Tuned Chat Models", 2023)
- https://arxiv.org/abs/2302.13971 (Hugo Touvron et al., "LLaMA: Open and Efficient Foundation Language Models", 2023)

**What's on each page:**
- `title_abstract.pdf`: Title, author list with affiliation superscripts (∗ equal contribution, † second author, explained in page-bottom notes), abstract, no page number
- `citations_body.pdf`: Body text ("Approach" section) with dense parenthetical citations: (Brown et al., 2020; Chowdhery et al., 2022), (Hoffmann et al., 2022), numbered page header "2"

## 2. Mathematical

| Fixture | Source | Pages | License |
|---|---|---|---|
| `mathematical/theorem_proof.pdf` | arXiv:1906.01277 | Page 2 | CC BY 4.0 |
| `mathematical/lemma_proof.pdf` | arXiv:1906.01277 | Page 12 | CC BY 4.0 |

**Source URL:** https://arxiv.org/abs/1906.01277 (Togninalli et al., "Wasserstein Weisfeiler-Lehman Graph Kernels", NeurIPS 2019)

**What's on each page:**
- `theorem_proof.pdf`: Definition 1 (Wasserstein distance) with numbered equation (1) including integral notation, equation (2), equation (3); inline mathematical notation (∈, inf, ∫, ⟨·⟩)
- `lemma_proof.pdf`: Lemma 1 and its proof, transport matrices, structured mathematical argument, equation numbering

## 3. Legal

| Fixture | Source | Pages | License |
|---|---|---|---|
| `legal/court_opinion.pdf` | Supreme Court of the United States | Page 0 | Public Domain (US Gov) |
| `legal/section_hierarchy.pdf` | Supreme Court of the United States | Page 27 | Public Domain (US Gov) |

**Source URL:** https://www.supremecourt.gov/opinions/23pdf/23-939_2c83.pdf (Moyle v. United States, 603 U.S. ___ (2024))

**What's on each page:**
- `court_opinion.pdf`: Slip opinion header ("NOTICE: This opinion is subject to formal revision..."), case caption with party names in all caps, "v." format, Per Curiam opinion opening, numbered docket (Nos. 23-726 and 23-727), date
- `section_hierarchy.pdf`: 9 section symbol (§) occurrences, statutory citations (§1395dd(e)(1)(A)), ALITO dissenting opinion, numbered hierarchy structure, page number 5, legal running header "MOYLE v. UNITED STATES"

## 4. Technical

| Fixture | Source | Pages | License |
|---|---|---|---|
| `technical/datasheet_specs.pdf` | Espressif ESP32 Datasheet | Page 51 | Publicly available |
| `technical/pin_config.pdf` | Espressif ESP32 Datasheet | Page 22 | Publicly available |

**Source URL:** https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf

**What's on each page:**
- `datasheet_specs.pdf`: Section "5 Electrical Characteristics", Absolute Maximum Ratings table with Min/Max/Unit columns, CAUTION callout ("Stresses above those listed...may cause permanent damage"), tolerance values (e.g., –0.3 to 3.6 V), page header "5"
- `pin_config.pdf`: Boot Configurations section, Timing Parameters table for Strapping Pins (Parameter | Description | Min(ms) columns), Chip Boot Mode Control table (GPIO0, GPIO2 configuration), numbered footnote ("1 Bold marks the default value..."), page header "3"

## 5. Books

| Fixture | Source | Pages | License |
|---|---|---|---|
| `books/block_quotes.pdf` | Moby Dick (Herman Melville, 1851) | Page 5 | Public Domain |
| `books/chapter_opening.pdf` | Moby Dick (Herman Melville, 1851) | Page 20 | Public Domain |

**Source:** Planet eBook edition of Moby Dick (formatted from Project Gutenberg text)
**URL:** https://www.planetebook.com/moby-dick/ (via Project Gutenberg #2701 at https://www.gutenberg.org/ebooks/2701)

**What's on each page:**
- `block_quotes.pdf`: Multiple block quotes with em-dash attributions: "killed sixty in two days.' —OTHER OR OCTHER'S VERBAL NARRATIVE TAKEN DOWN...", running header "Moby Dick", page number 6
- `chapter_opening.pdf`: Chapter title "Chapter 1 / Loomings.", famous opening line "Call me Ishmael.", running footer "Free eBooks at Planet eBook.com", page number 21, body text with narrative prose

## 6. General

| Fixture | Source | Pages | License |
|---|---|---|---|
| `general/periodic_table.pdf` | Wikipedia: Periodic Table | Page 0 | CC BY-SA 4.0 |
| `general/mixed_format.pdf` | Wikipedia: Periodic Table | Page 3 | CC BY-SA 4.0 |

**Source URL:** https://en.wikipedia.org/wiki/Periodic_table (PDF export via Wikimedia REST API)

**What's on each page:**
- `periodic_table.pdf`: Full periodic table grid with 118 elements, multi-column layout, color-coding by element sets, infobox, section headers, intro paragraph
- `mixed_format.pdf`: Subshell filling rule section, numbered list/sequence (1s ≪ 2s < 2p ≪ 3s...), multi-column content with atomic orbital diagrams, section header, mathematical symbols (≪, <), body text with bold terms

---

## Fixture Summary

| Profile | File Count | Total Pages | Sources |
|---|---|---|---|
| academic | 2 | 2 | arXiv (CC BY 4.0) |
| mathematical | 2 | 2 | arXiv (CC BY 4.0) |
| legal | 2 | 2 | US Supreme Court (Public Domain) |
| technical | 2 | 2 | Espressif ESP32 Datasheet |
| books | 2 | 2 | Project Gutenberg (Public Domain) |
| general | 2 | 2 | Wikipedia (CC BY-SA 4.0) |
| **TOTAL** | **12** | **12** | |
