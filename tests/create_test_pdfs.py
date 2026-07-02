#!/usr/bin/env python3
"""Create synthetic test PDFs for OCR pipeline profile testing.

Each PDF is a single page designed to test profile-specific VLM rules.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

FIXTURES = Path(__file__).parent


class AcademicPDF(FPDF):
    def header(self):
        self.set_font("Times", "I", 8)
        self.cell(0, 5, "Journal of Applied Sciences, Vol. 42, No. 3, pp. 247-260", align="L")
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Times", size=8)
        self.cell(0, 10, "247", align="C")


class MathPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Times", size=8)
        self.cell(0, 10, "142", align="C")


class LegalPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Times", size=8)
        self.cell(0, 10, "12", align="C")


class TechnicalPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Times", size=8)
        self.cell(0, 10, "5", align="C")


class BooksPDF(FPDF):
    def header(self):
        self.set_font("Times", "I", 9)
        self.cell(0, 5, "The Nature of Light", align="C")
        self.ln(8)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ==============================================================================
# 1. ACADEMIC — Journal article page
# ==============================================================================

def create_academic_journal():
    pdf = AcademicPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Title
    pdf.set_font("Times", "B", 14)
    pdf.cell(0, 10, "Effects of Temperature on Polymer Degradation", align="C")
    pdf.ln(12)

    # Authors with superscript affiliation markers
    pdf.set_font("Times", size=11)
    pdf.cell(0, 6, "John A. Smith", align="C")
    pdf.set_font("Times", size=7)
    pdf.cell(0, 6, "1*", align="R")  # approximation — fpdf2 limited superscript support
    # Actually, let's add affiliations more cleanly
    pdf.set_font("Times", size=11)
    pdf.cell(0, 6, "Maria L. Chen", align="C")
    pdf.set_font("Times", size=7)
    pdf.cell(0, 6, "2", align="R")
    pdf.ln(6)
    pdf.set_font("Times", size=11)
    pdf.cell(0, 6, "Robert K. Park", align="C")
    pdf.set_font("Times", size=7)
    pdf.cell(0, 6, "1", align="R")
    pdf.ln(10)

    # Affiliations
    pdf.set_font("Times", "I", 9)
    pdf.cell(0, 5, "1 Department of Chemistry, Stanford University, Stanford, CA 94305", align="C")
    pdf.ln(5)
    pdf.cell(0, 5, "2 Institute of Materials Science, MIT, Cambridge, MA 02139", align="C")
    pdf.ln(10)

    # Abstract
    pdf.set_font("Times", "B", 10)
    pdf.cell(0, 6, "Abstract")
    pdf.ln(8)
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "The thermal degradation of polyethylene terephthalate (PET) was investigated "
        "under varying atmospheric conditions. We report activation energies in the range "
        "of 180-220 kJ/mol, consistent with prior studies (Smith et al., 2019; Chen & Park, 2020). "
        "A novel rate law incorporating humidity dependence is proposed."
    )
    pdf.ln(4)

    # Keywords
    pdf.set_font("Times", "B", 10)
    pdf.cell(0, 6, "Keywords: ")
    pdf.set_font("Times", size=10)
    pdf.cell(0, 6, "polymer degradation, thermal analysis, activation energy, PET")
    pdf.ln(12)

    # Body text with citation
    pdf.set_font("Times", "B", 11)
    pdf.cell(0, 7, "1. Introduction")
    pdf.ln(10)
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "Polymer degradation under thermal stress is a well-studied phenomenon with "
        "significant industrial implications. Early work by Arrhenius established the "
        "foundational kinetic framework (Arrhenius, 1889), which has been extended by "
        "numerous researchers to polymer systems."
    )
    pdf.ln(4)
    pdf.multi_cell(0, 5,
        "Recent advances in thermogravimetric analysis (TGA) have enabled high-precision "
        "measurements of mass loss as a function of temperature. The degradation mechanism "
        "proceeds via random chain scission, as demonstrated by the molecular weight "
        "distribution analysis.1"
    )
    pdf.ln(10)

    # Footnote
    pdf.set_font("Times", size=8)
    y_before = pdf.get_y()
    pdf.line(20, y_before, 60, y_before)
    pdf.ln(2)
    pdf.set_font("Times", size=8)
    pdf.cell(5, 4, "1")
    pdf.multi_cell(0, 4,
        "Corresponding author. Email: jsmith@stanford.edu. "
        "Presented in part at the 242nd ACS National Meeting, Denver, CO, August 2021."
    )

    outdir = ensure_dir(FIXTURES / "academic")
    pdf.output(str(outdir / "journal_article.pdf"))
    print("  Created: academic/journal_article.pdf")


# ==============================================================================
# 2. ACADEMIC — Table with table-specific footnotes (edge case)
# ==============================================================================

def create_academic_table_footnotes():
    pdf = AcademicPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 8, "Table 1. Mass Loss Under Various Treatments")
    pdf.ln(12)

    # Table
    pdf.set_font("Times", "B", 10)
    col_w = [40, 60, 50]
    headers = ["Sample", "Treatment", "Mass Loss (%)"]
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1)
    pdf.ln()

    pdf.set_font("Times", size=10)
    data = [
        ["PET-01", "Nitrogen, 300 C", "12.4 \u00b1 0.3"],
        ["PET-02", "Air, 300 C", "18.7 \u00b1 0.5"],
        ["PET-03", "Nitrogen, 350 C", "45.2 \u00b1 0.8"],
        ["PET-04a", "Air, 350 C", "62.1 \u00b1 1.2"],
    ]
    for row in data:
        for i, cell in enumerate(row):
            pdf.cell(col_w[i], 7, cell, border=1)
        pdf.ln()
    pdf.ln(4)

    # Table-specific footnote
    pdf.set_font("Times", "I", 8)
    pdf.cell(0, 4, "a Sample pre-treated with UV radiation for 24 h before thermal exposure.")
    pdf.ln(5)
    pdf.set_font("Times", size=8)
    pdf.cell(0, 4, "Values are mean \u00b1 SD (n = 3). Bold values indicate p < 0.01 vs. control.")
    pdf.ln(12)

    # Body text
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "The data clearly show that oxidative conditions accelerate degradation, "
        "as expected from the radical-mediated mechanism proposed by Zimmerman "
        "(Zimmerman et al., 2018). The UV pre-treatment effect is particularly "
        "notable, suggesting that photodegradation creates additional initiation sites.2"
    )
    pdf.ln(10)

    # Page-level footnote
    pdf.set_font("Times", size=8)
    pdf.line(20, pdf.get_y(), 60, pdf.get_y())
    pdf.ln(2)
    pdf.cell(5, 4, "2")
    pdf.multi_cell(0, 4,
        "Funding: This work was supported by NSF Grant No. DMR-2104598. "
        "The authors declare no competing financial interests."
    )

    outdir = ensure_dir(FIXTURES / "academic")
    pdf.output(str(outdir / "table_footnotes.pdf"))
    print("  Created: academic/table_footnotes.pdf")


# ==============================================================================
# 3. MATHEMATICAL — Theorem with blackboard bold and display equations
# ==============================================================================

def create_mathematical_theorem():
    pdf = MathPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Title
    pdf.set_font("Times", "B", 13)
    pdf.cell(0, 10, "2. Preliminaries on Normed Vector Spaces")
    pdf.ln(14)

    # Theorem block
    pdf.set_font("Times", "B", 11)
    pdf.cell(0, 7, "Theorem 2.1 (Mean Value Theorem for Vector-Valued Functions).")
    pdf.ln(10)
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "Let f : R -> R^n be a differentiable function on the open interval (a, b) "
        "and continuous on the closed interval [a, b]. Then there exists a point "
        "c in (a, b) such that the following inequality holds for the operator norm."
    )
    pdf.ln(4)

    # Display equation with blackboard bold
    pdf.set_font("Times", size=11)
    pdf.cell(0, 7, "||f(b) - f(a)|| <= (b - a) * sup ||f'(x)||", align="C")
    pdf.ln(3)
    pdf.cell(0, 7, "x in [a,b]", align="C")
    pdf.ln(2)
    pdf.cell(0, 7, "(2.1)", align="R")
    pdf.ln(8)

    # Proof
    pdf.set_font("Times", "B", 11)
    pdf.cell(0, 7, "Proof.")
    pdf.ln(9)
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "Define the function g : [a, b] -> R by g(t) = <f(t), f(b) - f(a)>. "
        "By the chain rule, g is differentiable on (a, b) and continuous on [a, b]. "
        "Applying the classical Mean Value Theorem to g yields the result. "
        "The inequality follows from the Cauchy-Schwarz inequality and the definition "
        "of the operator norm on R^n."
    )
    pdf.ln(4)

    # End marker
    pdf.set_font("Times", size=11)
    pdf.cell(0, 7, "[square symbol]", align="R")
    pdf.ln(10)

    # Body text with inline math
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "For functions taking values in R (the set of real numbers), the above "
        "theorem reduces to the standard Mean Value Theorem. The generalization to "
        "R^n is nontrivial because the intermediate value property does not hold "
        "in higher dimensions. For a thorough treatment of differentiation in Banach "
        "spaces, the reader is referred to Rudin (1976)."
    )
    pdf.ln(4)
    pdf.multi_cell(0, 5,
        "In the context of normed vector spaces over R (real numbers) or C (complex "
        "numbers), the operator norm ||.|| is defined on the space of bounded linear "
        "transformations L(V, W)."
    )

    outdir = ensure_dir(FIXTURES / "mathematical")
    pdf.output(str(outdir / "theorem.pdf"))
    print("  Created: mathematical/theorem.pdf")


# ==============================================================================
# 4. LEGAL — Contract page with paragraph hierarchy and citations
# ==============================================================================

def create_legal_contract():
    pdf = LegalPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Section with section symbol
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 8, "Section 4.2  Termination Rights")
    pdf.ln(12)

    # Numbered paragraphs
    pdf.set_font("Times", "B", 10)
    pdf.cell(0, 7, "4.2.1  Termination for Cause.")
    pdf.ln(9)
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "Either party may terminate this Agreement upon thirty (30) days' written "
        "notice to the other party in the event of a material breach of any provision "
        "of this Agreement by the other party, provided that the breaching party fails "
        "to cure such breach within such thirty (30) day period. For purposes of this "
        "Section, a material breach shall include, but not be limited to:"
    )
    pdf.ln(4)

    # Sub-paragraphs
    pdf.set_font("Times", size=10)
    items = [
        "(a) any unauthorized disclosure of Confidential Information, as defined in Section 2.1;",
        "(b) failure to meet the performance standards set forth in Exhibit A for a period "
        "exceeding sixty (60) consecutive days;",
        "(c) any violation of applicable law, including but not limited to 15 U.S.C. Section 1681 "
        "et seq. (the Fair Credit Reporting Act).",
    ]
    for item in items:
        pdf.cell(10, 5, "")  # indent
        pdf.multi_cell(0, 5, item)
        pdf.ln(1)
    pdf.ln(4)

    pdf.set_font("Times", "B", 10)
    pdf.cell(0, 7, "4.2.2  Termination for Convenience.")
    pdf.ln(9)
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "Notwithstanding Section 4.2.1, the Client may terminate this Agreement at any "
        "time, with or without cause, by providing not less than ninety (90) days' "
        "advance written notice to the Service Provider. This right is consistent with "
        "principles articulated in Brown v. Board of Education, 347 U.S. 483 (1954), "
        "which established that contractual provisions must be interpreted in light of "
        "their equitable underpinnings."
    )
    pdf.ln(10)

    # Signature block
    pdf.set_font("Times", size=10)
    pdf.cell(0, 6, "IN WITNESS WHEREOF, the parties have executed this Agreement.")
    pdf.ln(15)
    pdf.cell(90, 5, "___________________________", align="C")
    pdf.cell(90, 5, "___________________________", align="C")
    pdf.ln(5)
    pdf.set_font("Times", "B", 10)
    pdf.cell(90, 5, "Client", align="C")
    pdf.cell(90, 5, "Service Provider", align="C")
    pdf.ln(10)
    pdf.set_font("Times", size=10)
    pdf.cell(90, 5, "By: ______________________", align="C")
    pdf.cell(90, 5, "By: ______________________", align="C")
    pdf.ln(5)
    pdf.cell(90, 5, "Name: ____________________", align="C")
    pdf.cell(90, 5, "Name: ____________________", align="C")
    pdf.ln(5)
    pdf.cell(90, 5, "Date: ____________________", align="C")
    pdf.cell(90, 5, "Date: ____________________", align="C")

    outdir = ensure_dir(FIXTURES / "legal")
    pdf.output(str(outdir / "contract.pdf"))
    print("  Created: legal/contract.pdf")


# ==============================================================================
# 5. TECHNICAL — Datasheet with warning callout and specification table
# ==============================================================================

def create_technical_datasheet():
    pdf = TechnicalPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Title
    pdf.set_font("Times", "B", 13)
    pdf.cell(0, 10, "Specification Sheet: PN-42X7-A Pressure Sensor")
    pdf.ln(12)

    # Document info
    pdf.set_font("Times", size=9)
    pdf.cell(0, 5, "Revision: 3.2 | Date: 2024-01-15 | Author: Engineering Dept.")
    pdf.ln(12)

    # WARNING callout
    pdf.set_font("Times", "B", 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 7, "WARNING:", fill=True)
    pdf.ln(7)
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "Do not exceed the maximum rated voltage of 30 VDC. Operation above this "
        "threshold may result in permanent sensor damage and void the warranty. "
        "Always verify supply voltage before connecting the sensor."
    )
    pdf.ln(8)

    # Specification table
    pdf.set_font("Times", "B", 11)
    pdf.cell(0, 7, "Electrical Specifications")
    pdf.ln(10)

    pdf.set_font("Times", "B", 10)
    col_w = [65, 50, 50]
    for i, h in enumerate(["Parameter", "Value", "Unit"]):
        pdf.cell(col_w[i], 7, h, border=1)
    pdf.ln()

    pdf.set_font("Times", size=10)
    spec_data = [
        ["Supply Voltage", "5.0 \u00b1 0.25", "VDC"],
        ["Output Range", "0.5 to 4.5", "V"],
        ["Accuracy", "\u00b1 0.005", "mm"],
        ["Operating Temperature", "-40 to +125", "\u00b0C"],
        ["Response Time", "< 1.0", "ms"],
        ["Housing Material", "316L Stainless Steel", "-"],
    ]
    for row in spec_data:
        for i, cell in enumerate(row):
            pdf.cell(col_w[i], 7, cell, border=1)
        pdf.ln()
    pdf.ln(8)

    # NOTE callout
    pdf.set_font("Times", "B", 10)
    pdf.set_fill_color(255, 255, 200)
    pdf.cell(0, 7, "NOTE:", fill=True)
    pdf.ln(7)
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "For applications requiring accuracy better than \u00b1 0.001 mm, use model "
        "PN-42X7-B which includes temperature compensation. Contact Technical Support "
        "for calibration certificates traceable to NIST standards."
    )

    outdir = ensure_dir(FIXTURES / "technical")
    pdf.output(str(outdir / "datasheet.pdf"))
    print("  Created: technical/datasheet.pdf")


# ==============================================================================
# 6. TECHNICAL — Code block alongside specification table (edge case)
# ==============================================================================

def create_technical_codeblock():
    pdf = TechnicalPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Times", "B", 13)
    pdf.cell(0, 10, "API Configuration Reference v2.1")
    pdf.ln(12)

    # YAML code block (left column area)
    pdf.set_font("Times", "B", 10)
    pdf.cell(0, 7, "Configuration File (config.yaml):")
    pdf.ln(8)

    pdf.set_font("Courier", size=9)
    code_lines = [
        "server:",
        "  host: 0.0.0.0",
        "  port: 8080",
        "  timeout_ms: 5000",
        "",
        "database:",
        "  driver: postgresql",
        "  host: ${DB_HOST}",
        "  pool_size: 20",
        "",
        "logging:",
        "  level: INFO",
        "  format: json",
        "  output: /var/log/app.log",
    ]
    for line in code_lines:
        pdf.cell(10, 4.5, "")  # indent
        pdf.cell(0, 4.5, line)
        pdf.ln()
    pdf.ln(6)

    # Spec table on same page
    pdf.set_font("Times", "B", 10)
    pdf.cell(0, 7, "Environment Variable Reference:")
    pdf.ln(8)

    pdf.set_font("Times", "B", 9)
    col_w = [45, 50, 60]
    for i, h in enumerate(["Variable", "Required", "Description"]):
        pdf.cell(col_w[i], 7, h, border=1)
    pdf.ln()

    pdf.set_font("Times", size=9)
    env_data = [
        ["DB_HOST", "Yes", "Database hostname or IP"],
        ["DB_PORT", "No", "Database port (default: 5432)"],
        ["API_KEY", "Yes", "Authentication token"],
        ["LOG_LEVEL", "No", "Logging verbosity (default: info)"],
    ]
    for row in env_data:
        for i, cell in enumerate(row):
            pdf.cell(col_w[i], 7, cell, border=1)
        pdf.ln()
    pdf.ln(5)

    # IMPORTANT callout
    pdf.set_font("Times", "B", 10)
    pdf.set_fill_color(255, 230, 230)
    pdf.cell(0, 7, "IMPORTANT:", fill=True)
    pdf.ln(7)
    pdf.set_font("Times", size=9)
    pdf.multi_cell(0, 4.5,
        "All environment variables marked as Required must be set before starting "
        "the application. The server will fail to start with exit code 1 if any "
        "required variable is missing."
    )

    outdir = ensure_dir(FIXTURES / "technical")
    pdf.output(str(outdir / "codeblock.pdf"))
    print("  Created: technical/codeblock.pdf")


# ==============================================================================
# 7. BOOKS — Chapter page with block quote, scene break, running header
# ==============================================================================

def create_books_chapter():
    pdf = BooksPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Chapter title
    pdf.set_font("Times", "B", 16)
    pdf.cell(0, 14, "Chapter 3: The Nature of Light", align="C")
    pdf.ln(18)

    # Epigraph / block quote
    pdf.set_font("Times", "I", 11)
    pdf.cell(60, 5, "")  # indent
    pdf.multi_cell(0, 6,
        '"Light is the shadow of God."'
    )
    pdf.cell(60, 5, "")  # indent
    pdf.set_font("Times", size=10)
    pdf.cell(0, 6, "--- Plato")
    pdf.ln(12)

    # Body text
    pdf.set_font("Times", size=11)
    pdf.multi_cell(0, 5.5,
        "The nature of light has puzzled philosophers and scientists for millennia. "
        "Ancient Greek thinkers debated whether vision resulted from rays emanating "
        "from the eye or from objects themselves. It was not until the seventeenth "
        "century that a more rigorous understanding began to emerge, with the competing "
        "theories of Newton and Huygens framing a debate that would persist for over "
        "two hundred years."
    )
    pdf.ln(4)
    pdf.multi_cell(0, 5.5,
        "Newton's corpuscular theory, presented in his Opticks (1704), proposed that "
        "light consisted of tiny particles traveling in straight lines. This elegantly "
        "explained reflection and refraction, though it struggled to account for the "
        "phenomenon of diffraction, which Huygens' wave theory described with remarkable "
        "accuracy."
    )
    pdf.ln(12)

    # Scene break
    pdf.set_font("Times", size=11)
    pdf.cell(0, 8, "*  *  *", align="C")
    pdf.ln(14)

    # After scene break
    pdf.set_font("Times", size=11)
    pdf.multi_cell(0, 5.5,
        "By the mid-nineteenth century, the wave theory had gained near-universal "
        "acceptance. Thomas Young's double-slit experiment of 1801 provided the first "
        "direct evidence for the wave nature of light, demonstrating interference "
        "patterns that were impossible to explain with corpuscular theory alone. "
        "Augustin-Jean Fresnel subsequently developed a comprehensive mathematical "
        "framework that accounted for diffraction, polarization, and interference "
        "with stunning precision."
    )

    # Footer page number (already handled by header)

    outdir = ensure_dir(FIXTURES / "books")
    pdf.output(str(outdir / "chapter.pdf"))
    print("  Created: books/chapter.pdf")


# ==============================================================================
# 8. BOOKS — Front matter with Roman numerals and TOC (edge case)
# ==============================================================================

def create_books_frontmatter():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Roman numeral page number in footer
    pdf.set_font("Times", "I", 10)
    pdf.cell(0, 10, "Contents", align="C")
    pdf.ln(16)

    # TOC entries
    pdf.set_font("Times", size=11)

    toc_entries = [
        ("List of Illustrations", "vii"),
        ("Preface", "ix"),
        ("Acknowledgments", "xiii"),
        ("", ""),
        ("Introduction: The Puzzle of Light", "1"),
        ("", ""),
        ("1. Shadows and Reflections: Early Optics", "15"),
        ("2. The Newtonian Synthesis", "42"),
        ("3. Huygens and the Wave Theory", "68"),
        ("4. Young's Interference", "95"),
        ("5. Fresnel and Diffraction", "122"),
        ("6. Maxwell's Equations", "151"),
        ("7. The Michelson-Morley Experiment", "178"),
        ("", ""),
        ("Appendix A: Mathematical Derivations", "203"),
        ("Appendix B: Chronology of Discoveries", "215"),
        ("Bibliography", "221"),
        ("Index", "235"),
    ]

    for title, page_num in toc_entries:
        if not title:
            pdf.ln(5)
            continue
        # Dot leaders
        pdf.set_font("Times", size=11)
        title_width = pdf.get_string_width(title)
        page_width = pdf.get_string_width(page_num)
        dots_width = 190 - title_width - page_width - 5
        dots = "." * max(1, int(dots_width / pdf.get_string_width(".")))
        pdf.cell(title_width + 1, 6, title)
        pdf.set_font("Times", size=11)
        pdf.cell(dots_width, 6, dots)
        pdf.cell(page_width, 6, page_num)
        pdf.ln(7)

    # Roman numeral footer
    pdf.set_y(-15)
    pdf.set_font("Times", size=9)
    pdf.cell(0, 10, "iv", align="C")

    outdir = ensure_dir(FIXTURES / "books")
    pdf.output(str(outdir / "frontmatter.pdf"))
    print("  Created: books/frontmatter.pdf")


# ==============================================================================
# 9. GENERAL — Mixed page with lists, bold/italic, table, multi-column
# ==============================================================================

def create_general_mixed():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Page footer with page number
    pdf.set_font("Times", size=9)
    pdf.cell(0, 10, "18", align="C")
    pdf.set_y(20)

    # Title
    pdf.set_font("Times", "B", 14)
    pdf.cell(0, 10, "Quarterly Report: Q3 2024 Summary")
    pdf.ln(14)

    # Bold and italic content
    pdf.set_font("Times", "B", 11)
    pdf.cell(0, 7, "Executive Overview")
    pdf.ln(10)
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "This quarter saw significant growth across all product lines. The flagship "
        "product, as described in The Journal of Industrial Economics, continues to "
        "lead the market. We are pleased to report the following results."
    )
    pdf.ln(6)

    # Bullet list
    pdf.set_font("Times", "B", 11)
    pdf.cell(0, 7, "Key Achievements")
    pdf.ln(9)
    pdf.set_font("Times", size=10)
    bullets = [
        "Revenue increased 23% year-over-year, exceeding Q3 targets by 4.2 percentage points.",
        "Customer acquisition cost decreased to $42 per user, down from $58 in Q3 2023.",
        "Three new patents were filed in the area of machine learning optimization.",
        "Employee satisfaction scores reached an all-time high of 87/100.",
    ]
    for bullet in bullets:
        pdf.cell(5, 5, "")
        pdf.cell(4, 5, "-")
        pdf.multi_cell(0, 5, bullet)
        pdf.ln(1)
    pdf.ln(6)

    # Simple table
    pdf.set_font("Times", "B", 11)
    pdf.cell(0, 7, "Revenue by Region (USD millions)")
    pdf.ln(9)

    pdf.set_font("Times", "B", 10)
    col_w = [70, 50, 50]
    for i, h in enumerate(["Region", "Q3 2024", "Q3 2023"]):
        pdf.cell(col_w[i], 7, h, border=1)
    pdf.ln()

    pdf.set_font("Times", size=10)
    region_data = [
        ["North America", "$12.4", "$10.1"],
        ["Europe", "$8.7", "$7.3"],
        ["Asia-Pacific", "$5.2", "$4.0"],
        ["Rest of World", "$2.1", "$1.8"],
    ]
    for row in region_data:
        for i, cell in enumerate(row):
            pdf.cell(col_w[i], 7, cell, border=1)
        pdf.ln()
    pdf.ln(10)

    # Multi-column text (simulated by indenting)
    pdf.set_font("Times", "B", 11)
    pdf.cell(0, 7, "Market Outlook")
    pdf.ln(9)
    pdf.set_font("Times", size=10)
    pdf.multi_cell(0, 5,
        "Analysts project continued growth in the coming quarters, driven by "
        "increased adoption of cloud-based solutions and favorable regulatory "
        "developments in key markets. The company remains well-positioned to "
        "capitalize on these trends through its diversified product portfolio "
        "and strong balance sheet."
    )
    pdf.ln(4)
    pdf.multi_cell(0, 5,
        "Risks to the outlook include potential interest rate increases, supply "
        "chain disruptions in semiconductor manufacturing, and geopolitical "
        "uncertainty in eastern markets. Management continues to monitor these "
        "factors and has contingency plans in place."
    )

    outdir = ensure_dir(FIXTURES / "general")
    pdf.output(str(outdir / "mixed.pdf"))
    print("  Created: general/mixed.pdf")


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":
    print("Creating test PDF fixtures...\n")
    create_academic_journal()
    create_academic_table_footnotes()
    create_mathematical_theorem()
    create_legal_contract()
    create_technical_datasheet()
    create_technical_codeblock()
    create_books_chapter()
    create_books_frontmatter()
    create_general_mixed()
    print("\nAll test PDFs created.")
