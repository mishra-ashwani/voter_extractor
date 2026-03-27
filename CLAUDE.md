# Project Context

This is a voter list PDF extraction app. The full specification 
is in CLAUDE_CODE_SPEC.md — read it before making any changes.

## Key Decisions
- Type 1 PDFs (Panchayat): Use PyMuPDF + 200+ character mapping rules. NO API needed.
- Type 2 PDFs (Vidhan Sabha): Pure image PDFs. Use Claude Vision API.
- Auto-detection: Check fonts/text/images in first 3 pages via PyMuPDF.
- The broken font encoding uses Latin Extended chars (æ,ø,ĝ,Ğ) for Hindi chars.
- Token mapping must be applied BEFORE character mapping (longest match first).
- CSV encoding must be utf-8-sig (BOM) for Excel Hindi compatibility.
- Use urllib.request (stdlib) for API calls, NOT the requests library.
- Frontend: Vanilla HTML/CSS/JS, dark theme, no frameworks.