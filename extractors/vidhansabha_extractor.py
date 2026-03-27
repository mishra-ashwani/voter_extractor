"""
Vidhan Sabha Voter List Extractor (Type 2)
Handles: Image-based card-layout PDFs (no embedded text)
Method: Convert pages to images → Claude Vision API → Structured JSON
"""

import json
import re
import base64
import urllib.request
import urllib.error
import time
from pdf2image import convert_from_path


def extract_page_with_vision(image, page_num, api_key):
    """Send a single page image to Claude Vision API for extraction"""
    import io
    buf = io.BytesIO()
    image.save(buf, format='JPEG', quality=85)
    b64_image = base64.b64encode(buf.getvalue()).decode('utf-8')

    prompt = """Extract ALL voter records from this Indian electoral roll page image.

Each voter card has: serial number, voter ID (like ZTU/DCT/UP format), name (नाम), father/husband/mother name (पिता/पति का नाम), house number (मकान संख्या), age (आयु), gender (लिंग: पुरुष/महिला).

Return ONLY a JSON array. No explanation, no markdown backticks.
Format: [{"sr_no": 1, "voter_id": "ZTU3824547", "name": "अर्जुन सिंह", "father_name": "हज़रत सिंह यादव", "house_no": "00", "age": "74", "gender": "पुरुष"}]

If the page has no voter cards (cover page, summary etc), return empty array: []"""

    body = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_image}
                },
                {"type": "text", "text": prompt}
            ]
        }]
    }).encode('utf-8')

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            text = ''.join(b['text'] for b in result.get('content', []) if b.get('type') == 'text')
            text = re.sub(r'^```json\s*', '', text.strip())
            text = re.sub(r'\s*```$', '', text)
            records = json.loads(text)
            for r in records:
                r['page'] = page_num
            return records
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        raise Exception(f"API Error {e.code}: {error_body[:200]}")
    except json.JSONDecodeError as e:
        raise Exception(f"JSON parse error on page {page_num}: {e}")


def extract(pdf_path, api_key=None, progress_callback=None):
    """Extract voter data from image-based PDF using Claude Vision API"""
    if not api_key:
        raise ValueError("Claude API key is required for image-based PDFs. Please provide your Anthropic API key.")

    # Convert all pages to images
    if progress_callback:
        progress_callback("Converting PDF pages to images...")
    images = convert_from_path(pdf_path, dpi=200)

    all_records = []
    total_pages = len(images)
    errors = []

    for i, img in enumerate(images):
        page_num = i + 1
        # Skip first 2 pages (cover + maps) and last page (summary)
        if page_num <= 2 or page_num == total_pages:
            if progress_callback:
                progress_callback(f"Skipping page {page_num}/{total_pages} (non-data page)")
            continue

        if progress_callback:
            progress_callback(f"Processing page {page_num}/{total_pages} via Claude Vision...")

        try:
            records = extract_page_with_vision(img, page_num, api_key)
            all_records.extend(records)
            time.sleep(0.5)  # Rate limiting
        except Exception as e:
            errors.append(f"Page {page_num}: {str(e)}")
            if progress_callback:
                progress_callback(f"Error on page {page_num}: {str(e)[:100]}")

    # Normalize gender field
    for r in all_records:
        gender = r.get('gender', '')
        if 'पुरुष' in gender or gender == 'पु':
            r['gender'] = 'पुरुष'
        elif 'महिला' in gender or gender == 'म':
            r['gender'] = 'महिला'

    return all_records, {
        'type': 'Vidhan Sabha Electoral Roll (Image PDF)',
        'method': 'Claude Vision API',
        'total': len(all_records),
        'pages': total_pages,
        'errors': errors,
    }
