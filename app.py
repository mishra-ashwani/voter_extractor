"""
Voter List PDF Extractor - Flask Application
=============================================
Extracts structured voter data from Indian electoral roll PDFs.

Supports:
  Type 1: Panchayat Electoral Roll (text-based, broken fonts) → PyMuPDF + CharMap
  Type 2: Vidhan Sabha Electoral Roll (image-based) → Claude Vision API

Usage:
  pip install flask PyMuPDF pdf2image
  python app.py
"""

import os
import csv
import io
import uuid
import json
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename

from extractors.detector import detect_pdf_type
from extractors.panchayat_extractor import extract as extract_panchayat
from extractors.vidhansabha_extractor import extract as extract_vidhansabha

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(__file__), 'outputs')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limit

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# In-memory job tracker
jobs = {}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    """Upload PDF and detect type"""
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['pdf']
    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Please upload a valid PDF file'}), 400

    filename = secure_filename(file.filename)
    job_id = str(uuid.uuid4())[:8]
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
    file.save(filepath)

    try:
        pdf_type, info = detect_pdf_type(filepath)
        jobs[job_id] = {
            'filepath': filepath,
            'filename': filename,
            'type': pdf_type,
            'info': info,
            'status': 'detected',
            'records': None,
        }
        return jsonify({
            'job_id': job_id,
            'filename': filename,
            'pdf_type': pdf_type,
            'info': info,
        })
    except Exception as e:
        return jsonify({'error': f'Error analyzing PDF: {str(e)}'}), 500


@app.route('/extract', methods=['POST'])
def extract():
    """Extract voter data from uploaded PDF"""
    data = request.get_json()
    job_id = data.get('job_id')
    api_key = data.get('api_key', '').strip()

    if job_id not in jobs:
        return jsonify({'error': 'Invalid job ID. Please upload again.'}), 400

    job = jobs[job_id]
    job['status'] = 'extracting'

    try:
        if job['type'] == 'panchayat_table':
            records, meta = extract_panchayat(job['filepath'])
        elif job['type'] == 'vidhan_sabha_card':
            if not api_key:
                return jsonify({'error': 'API key required for image-based PDFs'}), 400
            records, meta = extract_vidhansabha(job['filepath'], api_key=api_key)
        else:
            return jsonify({'error': 'Unsupported PDF format'}), 400

        # Save CSV
        csv_filename = f"{job_id}_voters.csv"
        csv_path = os.path.join(app.config['OUTPUT_FOLDER'], csv_filename)

        fieldnames = ['sr_no', 'voter_id', 'name', 'father_name', 'house_no', 'gender', 'age', 'page']
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(records)

        # Stats
        male = sum(1 for r in records if r.get('gender') in ['पु', 'पुरुष'])
        female = sum(1 for r in records if r.get('gender') in ['म', 'महिला'])

        job['status'] = 'complete'
        job['records'] = records
        job['csv_path'] = csv_path
        job['csv_filename'] = csv_filename
        job['meta'] = meta

        return jsonify({
            'success': True,
            'job_id': job_id,
            'total': len(records),
            'male': male,
            'female': female,
            'method': meta.get('method', 'N/A'),
            'errors': meta.get('errors', []),
            'preview': records[:10],
            'csv_filename': csv_filename,
        })

    except Exception as e:
        job['status'] = 'error'
        return jsonify({'error': str(e)}), 500


@app.route('/download/<job_id>')
def download(job_id):
    """Download extracted CSV"""
    if job_id not in jobs or not jobs[job_id].get('csv_path'):
        return jsonify({'error': 'File not found'}), 404

    job = jobs[job_id]
    return send_file(
        job['csv_path'],
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"voter_list_{job['filename'].replace('.pdf', '')}.csv"
    )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
