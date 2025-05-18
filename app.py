import os
import asyncio
from flask import Flask, request, render_template, send_file, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from utils.file_reader import read_file
from utils.domain_checker import check_domains
from utils.excel_generator import generate_excel
import logging
import uuid
import time
from concurrent.futures import ThreadPoolExecutor
import threading

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max file size
app.config['DOMAIN_LIMIT'] = 1000  # Bir tekshirishda maksimal domenlar soni
app.config['PROCESSING_TIMEOUT'] = 180  # Reduced timeout to 3 minutes (from 5)

# Upload papkasini yaratish
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Yaxshiroq logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Fayl turlari
ALLOWED_EXTENSIONS = {'txt', 'docx', 'xlsx'}


# Fayl turini tekshirish
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Xatoliklarni boshqarish
@app.errorhandler(404)
def handle_404(error):
    logger.warning(f"404 Not Found: {request.url}")
    return jsonify({"error": "Resurs topilmadi"}), 404


@app.errorhandler(413)
def request_entity_too_large(error):
    logger.warning(f"413 Request Entity Too Large: {request.url}")
    return jsonify({"error": "Fayl hajmi juda katta (max 32MB)"}), 413


@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Error occurred: {str(error)}")
    return jsonify({"error": "Server xatosi yuz berdi. Iltimos, qayta urinib ko'ring."}), 500


# Favicon uchun
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico')


# Asosiy sahifa
@app.route('/')
def index():
    return render_template('index.html')


# TimeoutManager - uzoq davom etadigan jarayonlarni boshqarish
class TimeoutManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.active_tasks = {}

    def add_task(self, task_id, timeout=180):
        with self.lock:
            self.active_tasks[task_id] = {
                'start_time': time.time(),
                'timeout': timeout
            }

    def remove_task(self, task_id):
        with self.lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]

    def is_timed_out(self, task_id):
        with self.lock:
            if task_id in self.active_tasks:
                task_info = self.active_tasks[task_id]
                elapsed = time.time() - task_info['start_time']
                return elapsed > task_info['timeout']
            return False


# TimeoutManager yaratish
timeout_manager = TimeoutManager()


# Domain processing function with improved error handling
async def process_domains(domains, output_path, task_id, batch_size=5):
    try:
        # Limit number of domains to process to avoid timeouts
        max_domains = min(len(domains), app.config['DOMAIN_LIMIT'])
        domains_to_process = domains[:max_domains]

        logger.info(f"Starting domain processing for task {task_id} with {len(domains_to_process)} domains")

        # Set timeout for the entire check_domains operation
        try:
            # Create a task with timeout
            check_task = asyncio.create_task(check_domains(domains_to_process, batch_size))
            results = await asyncio.wait_for(check_task, timeout=app.config['PROCESSING_TIMEOUT'])
        except asyncio.TimeoutError:
            logger.error(f"Domain checking timed out for task {task_id}")
            # Process domains that we've already checked
            if hasattr(check_task, "_domains_processed") and check_task._domains_processed:
                results = check_task._domains_processed
                logger.info(f"Partial results available: {len(results)} domains processed")
            else:
                # Generate basic "Need to Check" responses if no results
                results = [
                    {
                        "domain": domain,
                        "status": "Need to Check",
                        "status_code": None,
                        "page_type": "Unknown",
                        "title": "Timeout during processing"
                    } for domain in domains_to_process
                ]

        # Excel hisobotini yaratish
        generate_excel(results, output_path)
        logger.info(f"Completed domain processing for task {task_id}")

        # Jarayonni tugallanganligi haqida belgi
        timeout_manager.remove_task(task_id)
        return True, results
    except Exception as e:
        logger.error(f"Error in process_domains for task {task_id}: {str(e)}")
        timeout_manager.remove_task(task_id)

        # Generate basic error report to avoid completely failing
        try:
            error_results = [
                {
                    "domain": domain,
                    "status": "Need to Check",
                    "status_code": None,
                    "page_type": "Error",
                    "title": f"Error: {str(e)[:50]}"
                } for domain in domains[:max_domains]
            ]
            generate_excel(error_results, output_path)
            logger.info(f"Generated error report for {len(error_results)} domains")
            return False, error_results
        except Exception as excel_error:
            logger.error(f"Failed to generate error report: {str(excel_error)}")
            return False, []


# Fayl yuklash va domainlarni tekshirish - switched to sync version for better Flask integration
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Fayl topilmadi'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Fayl tanlanmagan'}), 400
        
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Noto\'g\'ri fayl formati'}), 400

    try:
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join(app.root_path, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save the uploaded file temporarily
        temp_filename = secure_filename(file.filename)
        temp_filepath = os.path.join(upload_dir, temp_filename)
        file.save(temp_filepath)
        
        try:
            # Read domains from the saved file
            domains = read_file(temp_filepath)
            if not domains:
                return jsonify({'error': 'Faylda domenlar topilmadi'}), 400

            # Create unique task ID
            task_id = str(uuid.uuid4())
            
            # Create output directory if it doesn't exist
            output_dir = os.path.join(app.root_path, 'reports')
            os.makedirs(output_dir, exist_ok=True)
            
            # Set output path
            output_path = os.path.join(output_dir, f'report_{task_id}.xlsx')
            
            # Process domains synchronously to ensure we have results
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            batch_size = min(5, max(1, len(domains) // 20))  # Smaller batch size
            try:
                result, check_results = loop.run_until_complete(process_domains(domains, output_path, task_id, batch_size))
                loop.close()

                if result and os.path.exists(output_path):
                    # Calculate statistics from actual results
                    stats = {
                        "total": len(domains),
                        "working": sum(1 for d in check_results if d.get("status") == "Working"),
                        "notWorking": sum(1 for d in check_results if d.get("status") == "Not Working"),
                        "needCheck": sum(1 for d in check_results if d.get("status") == "Need to Check")
                    }
                    
                    # Add statistics to response headers
                    response = send_file(output_path, as_attachment=True, download_name="domain_report.xlsx")
                    response.headers['X-Total-Domains'] = str(stats["total"])
                    response.headers['X-Working-Domains'] = str(stats["working"])
                    response.headers['X-Not-Working-Domains'] = str(stats["notWorking"])
                    response.headers['X-Need-Check-Domains'] = str(stats["needCheck"])
                    return response
                else:
                    return jsonify({'error': 'Hisobot yaratishda xatolik yuz berdi'}), 500
            except Exception as e:
                logger.error(f"Error processing domains: {str(e)}")
                return jsonify({'error': 'Domenlarni tekshirishda xatolik yuz berdi'}), 500
            finally:
                loop.close()
        finally:
            # Clean up the temporary file
            try:
                os.remove(temp_filepath)
            except Exception as e:
                logger.error(f"Error removing temporary file: {str(e)}")
            
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': 'Faylni qayta ishlashda xatolik yuz berdi'}), 500


if __name__ == '__main__':
    # Set appropriate server timeout
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)