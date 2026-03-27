"""
Auto-detect voter list PDF type based on internal structure
"""

import fitz


def detect_pdf_type(filepath):
    """
    Detect voter list PDF type.
    Returns: 'panchayat_table' | 'vidhan_sabha_card' | 'unknown'
    """
    doc = fitz.open(filepath)

    has_text = False
    has_fonts = False
    has_images = False

    for i, page in enumerate(doc):
        if i >= 3:
            break

        text = page.get_text().strip()
        if text:
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
