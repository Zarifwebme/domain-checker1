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
app.config['PROCESSING_TIMEOUT'] = 300  # 5 daqiqalik timeout

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

    def add_task(self, task_id, timeout=300):
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


# Domainlar ro'yxatini tekshirish va Excel hisobotini yaratish
async def process_domains(domains, output_path, task_id, batch_size=8):
    try:
        # Domain tekshirishni boshlash
        logger.info(f"Starting domain processing for task {task_id} with {len(domains)} domains")
        results = await check_domains(domains, batch_size)

        # Excel hisobotini yaratish
        generate_excel(results, output_path)
        logger.info(f"Completed domain processing for task {task_id}")

        # Jarayonni tugallanganligi haqida belgi
        timeout_manager.remove_task(task_id)
        return True
    except Exception as e:
        logger.error(f"Error in process_domains for task {task_id}: {str(e)}")
        timeout_manager.remove_task(task_id)
        return False


# Fayl yuklash va domainlarni tekshirish
@app.route('/upload', methods=['POST'])
async def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Fayl yuklanmadi"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Fayl tanlanmadi"}), 400

        if file and allowed_file(file.filename):
            # Xavfsiz fayl nomini yaratish
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Domenlarni fayldan o'qish
            logger.info(f"Reading domains from {filename}")
            domains = read_file(file_path)

            if not domains:
                return jsonify({"error": "Faylda hech qanday domen topilmadi"}), 400

            if len(domains) > app.config['DOMAIN_LIMIT']:
                return jsonify(
                    {"error": f"Juda ko'p domenlar ({len(domains)}). Maksimal: {app.config['DOMAIN_LIMIT']}"}), 400

            # Task ID ni yaratish
            task_id = uuid.uuid4().hex
            output_filename = f"domain_report_{task_id}.xlsx"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

            # Jarayonni boshlatish
            timeout_manager.add_task(task_id, app.config['PROCESSING_TIMEOUT'])

            # Domain tekshirish va Excel yaratish
            batch_size = min(8, max(1, len(domains) // 50))  # Domenlar soniga qarab optimal batch size
            await process_domains(domains, output_path, task_id, batch_size)

            if os.path.exists(output_path):
                # Javob qaytarish
                return send_file(output_path, as_attachment=True, download_name="domain_report.xlsx")
            else:
                return jsonify({"error": "Hisobot yaratishda xatolik"}), 500

        return jsonify({"error": "Noto'g'ri fayl formati. .txt, .docx, yoki .xlsx fayllaridan foydalaning"}), 400

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({"error": "Faylni qayta ishlashda xatolik yuz berdi. Iltimos, qayta urinib ko'ring."}), 500


if __name__ == '__main__':
    # Asinxron xususiyatlarni qo'llab-quvvatlash uchun
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)