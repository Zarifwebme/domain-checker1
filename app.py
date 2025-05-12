import os
import asyncio
from flask import Flask, request, render_template, send_file, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from utils.file_reader import read_file
from utils.domain_checker import check_domains
from utils.excel_generator import generate_excel
import logging
import uuid

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Logging setup for Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'txt', 'docx', 'xlsx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.errorhandler(404)
def handle_404(error):
    logger.warning(f"404 Not Found: {request.url}")
    return jsonify({"error": "Resource not found"}), 404


@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Error occurred: {str(error)}")
    return jsonify({"error": "Server error occurred. Please try again."}), 500


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
async def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Read domains from file
            domains = read_file(file_path)
            if not domains:
                return jsonify({"error": "No valid domains found in the file"}), 400

            # Check domains
            results = await check_domains(domains)

            # Generate Excel report
            output_filename = f"domain_report_{uuid.uuid4().hex}.xlsx"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            generate_excel(results, output_path)

            return send_file(output_path, as_attachment=True)

        return jsonify({"error": "Invalid file format. Use .txt, .docx, or .xlsx"}), 400

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({"error": "Error processing file. Please try again."}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))