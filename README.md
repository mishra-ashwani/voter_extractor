# 🗳️ Voter List PDF Extractor

A Flask web application that extracts structured voter data from Indian electoral roll PDFs into CSV format.

## Supported PDF Types

| Type | Source | Format | Extraction Method |
|------|--------|--------|-------------------|
| **Panchayat Electoral Roll** | State Election Commission | Text-based tabular (broken Hindi fonts) | PyMuPDF + Character Mapping (200+ rules) |
| **Vidhan Sabha Electoral Roll** | Election Commission of India | Image-based card layout | Claude Vision API |

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   PDF Upload │────▶│  Auto-Detector   │────▶│  Type Router    │
└──────────────┘     │  (PyMuPDF check) │     └────────┬────────┘
                     └──────────────────┘              │
                            ┌───────────────────────────┤
                            ▼                           ▼
                  ┌──────────────────┐       ┌──────────────────┐
                  │  Type 1:         │       │  Type 2:         │
                  │  PyMuPDF +       │       │  PDF → Images →  │
                  │  CharMap Engine  │       │  Claude Vision   │
                  │  (No API needed) │       │  (API required)  │
                  └────────┬─────────┘       └────────┬─────────┘
                           │                          │
                           ▼                          ▼
                     ┌──────────────────────────────────┐
                     │  Structured CSV Output            │
                     │  (sr_no, voter_id, name,          │
                     │   father_name, house_no,          │
                     │   gender, age, page)              │
                     └──────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.9+
- `poppler-utils` (for pdf2image):
  ```bash
  # Ubuntu/Debian
  sudo apt-get install poppler-utils
  
  # macOS
  brew install poppler
  ```

### Installation
```bash
git clone <repo>
cd voter-extractor
pip install -r requirements.txt
```

### Run
```bash
python app.py
```
Open http://localhost:5000 in your browser.

### For Image-based PDFs (Vidhan Sabha)
Set your Anthropic API key in the web UI when prompted.
You can get one from https://console.anthropic.com/

## How It Works

### Type 1: Panchayat PDF (Broken Font Encoding)
1. **PyMuPDF** extracts raw text — gets structure but ~50% garbled Hindi
2. **Token Mapping** (200+ rules) fixes common words: `æलı` → `अली`, `øुमार` → `कुमार`
3. **Character Mapping** fixes remaining individual chars: `æ` → `अ`, `ę` → `व`
4. **Post-processing** cleans double-substitution artifacts
5. Result: **~99% accuracy** without any API calls

### Type 2: Vidhan Sabha PDF (Image-only)
1. **pdf2image** converts each page to JPEG at 200 DPI
2. **Claude Vision API** reads each page image, extracting structured voter data
3. Returns JSON with all fields per voter card
4. Result: **~98% accuracy** (depends on image quality)

## Project Structure
```
voter_extractor/
├── app.py                          # Flask application
├── requirements.txt
├── templates/
│   └── index.html                  # Web UI
├── extractors/
│   ├── __init__.py
│   ├── detector.py                 # Auto-detect PDF type
│   ├── panchayat_extractor.py      # Type 1: PyMuPDF + CharMap
│   └── vidhansabha_extractor.py    # Type 2: Claude Vision API
├── uploads/                        # Temporary upload storage
└── outputs/                        # Generated CSV files
```

## API Usage (Programmatic)

```python
from extractors.detector import detect_pdf_type
from extractors.panchayat_extractor import extract as extract_panchayat
from extractors.vidhansabha_extractor import extract as extract_vidhansabha

# Auto-detect
pdf_type, info = detect_pdf_type("voter_list.pdf")

# Extract based on type
if pdf_type == 'panchayat_table':
    records, meta = extract_panchayat("voter_list.pdf")
elif pdf_type == 'vidhan_sabha_card':
    records, meta = extract_vidhansabha("voter_list.pdf", api_key="sk-ant-...")
```

## Tech Stack
- **Backend:** Flask, PyMuPDF (fitz), pdf2image, Claude API
- **Frontend:** Vanilla HTML/CSS/JS
- **AI:** Claude Vision API (for image PDFs), CharMap engine (for text PDFs)
