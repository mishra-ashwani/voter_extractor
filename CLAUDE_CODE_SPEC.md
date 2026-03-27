# Voter List PDF Extractor - Claude Code Project Specification

## Project Overview

Build a Flask web application that extracts structured voter data from Indian electoral roll PDFs into downloadable CSV files. The app must handle two fundamentally different PDF formats using different extraction strategies, auto-detect which format is uploaded, and present results through a clean web interface.

## Problem Statement

Indian election commissions publish voter lists as PDFs in two formats:
1. **Panchayat Electoral Rolls** — Have embedded text but with broken Hindi font encoding (Nirmala UI font with mixed WinAnsi/Identity-H CID encoding). Standard text extraction tools (PyPDF, pdfplumber, Tesseract) produce garbled output like `æलı` instead of `अली`, `øुमार` instead of `कुमार`.
2. **Vidhan Sabha (Assembly) Electoral Rolls** — Pure image PDFs with zero embedded text or fonts. Each page is a single JPEG image containing voter cards in a 3-column grid layout. All text extraction tools return empty strings.

## Architecture

```
User uploads PDF
       │
       ▼
┌─────────────────────────┐
│   PDF Type Detector     │
│   (Check fonts/images   │
│    using PyMuPDF)       │
└───────────┬─────────────┘
            │
    ┌───────┴────────┐
    ▼                ▼
┌──────────┐   ┌──────────────┐
│ Type 1   │   │ Type 2       │
│ Panchayat│   │ Vidhan Sabha │
│ Extractor│   │ Extractor    │
└────┬─────┘   └──────┬───────┘
     │                │
     ▼                ▼
  PyMuPDF          pdf2image
  text extract     converts pages
     │             to JPEG @200dpi
     ▼                │
  3-Layer             ▼
  Character        Claude Vision
  Mapping          API reads each
  Engine           page image and
  (200+ rules)     returns JSON
     │                │
     ▼                ▼
     └───────┬────────┘
             ▼
      Structured records → CSV + Web UI
```

## Tech Stack

- **Backend:** Python 3.9+, Flask
- **PDF Processing:** PyMuPDF (fitz) for text extraction and PDF structure analysis
- **Image Conversion:** pdf2image + poppler-utils (system dep) for converting image PDFs to JPEG
- **AI/LLM:** Anthropic Claude API (claude-sonnet-4-20250514) with vision capability for reading image-based PDFs
- **Frontend:** Single-page HTML with vanilla CSS and JavaScript (no React/Vue/frameworks)
- **Output:** CSV with UTF-8 BOM encoding (`utf-8-sig`) for proper Hindi display in Excel

## System Prerequisites

```bash
# Ubuntu/Debian
sudo apt-get install poppler-utils

# macOS
brew install poppler
```

## Python Dependencies (requirements.txt)

```
flask>=3.0
PyMuPDF>=1.24
pdf2image>=1.17
Pillow>=10.0
```

## Project Structure

```
voter_extractor/
├── app.py                              # Flask application (routes, file handling, job tracking)
├── requirements.txt
├── CLAUDE_CODE_SPEC.md                 # This specification file
├── templates/
│   └── index.html                      # Single-page web UI (dark theme, 3-step wizard)
├── extractors/
│   ├── __init__.py                     # Empty package init
│   ├── detector.py                     # Auto-detect PDF type from internal structure
│   ├── panchayat_extractor.py          # Type 1: PyMuPDF + 3-layer CharMap engine
│   └── vidhansabha_extractor.py        # Type 2: Claude Vision API page-by-page extractor
├── uploads/                            # Temporary PDF uploads (auto-created by app)
└── outputs/                            # Generated CSV files (auto-created by app)
```

---

## Module Specifications

### Module 1: `extractors/detector.py`

**Purpose:** Determine which extraction pipeline to use.

**Exports:** `detect_pdf_type(filepath) -> tuple[str, dict]`

**Logic:**
```python
import fitz

def detect_pdf_type(filepath):
    doc = fitz.open(filepath)
    has_text = False
    has_fonts = False
    has_images = False

    for i, page in enumerate(doc):
        if i >= 3:
            break
        if page.get_text().strip():
            has_text = True
        if page.get_fonts():
            has_fonts = True
        if page.get_images():
            has_images = True

    page_count = len(doc)
    doc.close()

    if has_fonts and has_text:
        return 'panchayat_table', {
            'label': 'पंचायत निर्वाचक नामावली (Panchayat Electoral Roll)',
            'method': 'PyMuPDF + Character Mapping',
            'needs_api': False,
            'pages': page_count,
        }
    elif has_images and not has_text:
        return 'vidhan_sabha_card', {
            'label': 'विधानसभा निर्वाचक नामावली (Vidhan Sabha Electoral Roll)',
            'method': 'Claude Vision API',
            'needs_api': True,
            'pages': page_count,
        }
    else:
        return 'unknown', {
            'label': 'Unknown PDF format',
            'method': 'N/A',
            'needs_api': False,
            'pages': page_count,
        }
```

---

### Module 2: `extractors/panchayat_extractor.py`

**Purpose:** Extract voter records from text-based PDFs with broken Hindi font encoding.

**Exports:** `extract(pdf_path) -> tuple[list[dict], dict]`

**3-Layer Text Cleanup Engine:**

**Layer 1 — TOKEN_MAP dict (100+ entries, applied first, longest match priority):**
Sort by key length descending before applying `str.replace()`.

Critical mappings (include ALL of these plus extend with similar patterns):
```python
TOKEN_MAP = {
    # Common surnames/words (high frequency, 50+ occurrences each)
    'æलı': 'अली', 'øुमार': 'कुमार', 'कुमĭर': 'कुमार',
    'अĞमद': 'अहमद', 'अĕı': 'अली', 'देिı': 'देवी',
    'गुɑा': 'गुप्ता', 'अƢर': 'अख्तर',
    
    # Religious/common names
    'मोĞʃद': 'मोहम्मद', 'मोहʃद': 'मोहम्मद',
    'Šसैन': 'हुसैन', 'Ůसाद': 'प्रसाद',
    'Ůøाश': 'प्रकाश', 'Ůमोद': 'प्रमोद',
    'Ůताप': 'प्रताप', 'ŵी': 'श्री', 'ʴाम': 'श्याम',
    
    # Suffixes/titles
    'शमाŊ': 'शर्मा', 'वमाŊ': 'वर्मा',
    'ˢŝप': 'स्वरूप', 'बĭनो': 'बानो',
    'ęेगम': 'बेगम', 'खĭतून': 'खातून',
    
    # Singh variations (CRITICAL - 6 different garbled forms)
    'äंäंसĞ': 'सिंह', 'äंäंĝह': 'सिंह', 'äŃäŃसह': 'सिंह',
    'äंäंसह': 'सिंह', 'Įसंह': 'सिंह', 'ĮसंĞ': 'सिंह',
    
    # Place names
    'सȽलपुर': 'सन्दलपुर',
    
    # ... include 80+ more mappings for common names
}
```

**Layer 2 — CHAR_MAP dict (80+ entries, applied character-by-character after token mapping):**
```python
CHAR_MAP = {
    'æ': 'अ', 'ÿ': 'ज', 'Ů': 'प्र', 'Ğ': 'ह', 'ę': 'व',
    'ı': 'ी', 'ŝ': 'रू', 'ø': 'क', 'ĝ': 'स', 'ĕ': 'ल',
    'ý': 'च', 'Ţ': 'क्र', 'Ť': 'ग्र', 'Š': 'हु',
    'ʃ': 'म्म', 'ˢ': 'स्व', 'ũ': 'त्री', 'Ŋ': 'र्',
    'ƕ': 'क्ष', 'Ƣ': 'ख्त', 'Ĳ': 'रि', 'Ń': 'ं',
    'ĭ': 'ा', 'Į': 'वि', 'Ě': 'श', 'ȶ': 'न्ति',
    # ... include all 80+ mappings
    # Also include cleanup for Unicode combining marks:
    '̏': '', '̢': '', '̪': '', '̫': '', '̵': '', '̺': '', '̻': '', '̾': '',
}
```

**Layer 3 — POST_FIXES dict (cleanup double-substitution artifacts):**
```python
POST_FIXES = {
    'सिंसिंसह': 'सिंह',
    'सिंसह': 'सिंह',
    'साविवत्रीी': 'सावित्री',
    'सन्दलसन्दलपुर': 'सन्दलपुर',
    'विवि': 'वि',
    'कुकुमार': 'कुमार',
}
```

**`clean_text(text)` function:** Apply Layer 1 → Layer 2 → Layer 3 in sequence.

**Record extraction from PyMuPDF text:**

Each page's `page.get_text()` returns lines. Voter records follow a 6-7 line pattern:
```
Line 1: Serial number (regex: ^\d{1,4}$)
Line 2: House number
Line 3: Name (Hindi)
Line 4: Father/husband name (Hindi)
Line 5: SVN code (starts with "SNP") OR gender ("म"/"पु")
Line 6: Gender (if Line 5 was SVN)
Line 7: Age (if Line 5 was SVN)
```

Parser state machine: iterate through lines, when a serial number is found, try to read the next 5-6 lines as a record. Check Line 5: if starts with "SNP" → 7-line record, if "म"/"पु" → 6-line record (no SVN). Skip header/footer lines matching `^(Page|1-|2-|...|8-|Ţ|č|Ĳ)`.

Apply `clean_text()` to name, father_name, and house_no fields.

**Output per record:**
```python
{'sr_no': int, 'house_no': str, 'name': str, 'father_name': str,
 'voter_id': str, 'gender': str, 'age': str, 'page': int}
```

---

### Module 3: `extractors/vidhansabha_extractor.py`

**Purpose:** Extract voter records from image-only PDFs using Claude Vision API.

**Exports:** `extract(pdf_path, api_key=None, progress_callback=None) -> tuple[list[dict], dict]`

**Process:**

1. Raise `ValueError` if api_key is None/empty
2. `convert_from_path(pdf_path, dpi=200)` → list of PIL Images
3. Skip pages 1, 2, and last page (non-data pages)
4. For each remaining page:
   a. Convert PIL Image to base64 JPEG (quality=85)
   b. POST to `https://api.anthropic.com/v1/messages`:
      - Model: `claude-sonnet-4-20250514`
      - Headers: `x-api-key`, `anthropic-version: 2023-06-01`
      - Content: image (base64) + extraction prompt
      - max_tokens: 4096
   c. Parse response: extract text blocks, strip markdown fences, JSON.loads
   d. Add `page` number to each record
   e. `time.sleep(0.5)` for rate limiting
5. Normalize gender: "पुरुष"/"पु" → "पुरुष", "महिला"/"म" → "महिला"
6. Return (records, metadata_with_errors)

**Use `urllib.request` (stdlib) for HTTP calls.** Do NOT use `requests` library.

**Error handling per page:** try/except wrapping each API call. On failure, append error message to errors list, continue processing remaining pages.

---

### Module 4: `app.py`

**Flask routes:**

`GET /` → `render_template('index.html')`

`POST /upload`:
- Get file from `request.files['pdf']`
- Validate: exists, .pdf extension
- job_id = uuid4()[:8]
- Save to `uploads/{job_id}_{secure_filename}`
- Call `detect_pdf_type()`
- Store in `jobs` dict
- Return JSON: `{job_id, filename, pdf_type, info}`

`POST /extract`:
- Read JSON body: `{job_id, api_key}`
- Lookup job, route to correct extractor
- Type 2 without api_key → 400 error
- Write CSV to `outputs/{job_id}_voters.csv`
- fieldnames: `['sr_no', 'voter_id', 'name', 'father_name', 'house_no', 'gender', 'age', 'page']`
- Encoding: `utf-8-sig`
- Use `csv.DictWriter` with `extrasaction='ignore'`
- Calculate male/female stats
- Return JSON: `{success, job_id, total, male, female, method, errors, preview, csv_filename}`

`GET /download/<job_id>`:
- Lookup job, return CSV via `send_file()` with `as_attachment=True`

**Config:** MAX_CONTENT_LENGTH=50MB, auto-create upload/output dirs, random secret_key.

---

### Module 5: `templates/index.html`

**3-step progressive wizard in a single page:**

Step 1: Upload zone (drag-drop + click) → POST FormData to /upload → show detected type
Step 2: API key input (only for Type 2) + extract button → POST JSON to /extract → progress bar
Step 3: Stats grid + download button + preview table

**UI:** Dark theme (#0a0e17 bg), blue accent (#3b82f6), Google Fonts (Outfit + Noto Sans Devanagari), no frameworks, responsive, gender color coding in table (blue=male, pink=female).

---

## CSV Output Schema

| Column | Type | Description | Examples |
|--------|------|-------------|---------|
| sr_no | int | Serial number | 1, 100, 1031 |
| voter_id | str | Voter ID code | ZTU3824547, SNPFAA002, empty |
| name | str | Voter name (Hindi) | अर्जुन सिंह, सलमा |
| father_name | str | Father/husband/mother (Hindi) | हज़रत सिंह, अज्ञान प्रसाद |
| house_no | str | House number | 00, 1, 3/16, 20ब/2 |
| gender | str | Gender | पुरुष, महिला, पु, म |
| age | str | Age | 74, 25 |
| page | int | Source page | 3, 15 |

Encoding: `utf-8-sig` (BOM for Excel compatibility).

## Error Handling

| Scenario | Response |
|----------|----------|
| No file / not .pdf / too large | HTTP 400 + JSON error |
| PDF can't be opened | HTTP 500 + JSON error |
| Type 1 parse error on a record | Skip record, continue |
| Type 2 no API key | HTTP 400 + "API key required" |
| Type 2 API auth failure (401) | Return error to user |
| Type 2 API rate limit (429) | Retry 3x with backoff |
| Type 2 API timeout | Skip page, log error, continue |
| Type 2 JSON parse error | Skip page, log error, continue |
| Download invalid job_id | HTTP 404 |

## Testing

After building, test these scenarios:
1. Upload Panchayat PDF → auto-detects, extracts ~2600 records without API key
2. Upload Vidhan Sabha PDF → auto-detects, requires API key
3. Extract Vidhan Sabha with valid key → extracts ~1000 records
4. Upload non-PDF → error message
5. Extract Type 2 without key → error message
6. CSV download → Hindi text displays correctly in Excel
7. Mobile responsive → UI works on phone screens
