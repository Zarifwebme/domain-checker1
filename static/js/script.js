// Global variables
let processingTimer = null;
let currentStage = 0;
const processingStages = [
    "Faylni yuklash...",
    "Domenlarni o'qish...",
    "Domenlarni tekshirish...",
    "Excel hisobotini yaratish..."
];

// File input handling
document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('fileInput');
    const fileContainer = document.getElementById('fileContainer');
    const fileName = document.getElementById('fileName');
    const uploadBtn = document.getElementById('uploadBtn');

    if (!fileInput || !fileContainer || !fileName || !uploadBtn) {
        console.error('Required elements not found');
        return;
    }

    // File selection handler
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            const file = fileInput.files[0];
            fileContainer.classList.add('has-file');
            fileName.textContent = file.name;
            fileName.style.display = 'block';
            uploadBtn.removeAttribute('disabled');
        } else {
            resetFileInput();
        }
    });
});

// Reset file input to initial state
function resetFileInput() {
    const fileInput = document.getElementById('fileInput');
    const fileContainer = document.getElementById('fileContainer');
    const fileName = document.getElementById('fileName');
    const uploadBtn = document.getElementById('uploadBtn');

    if (!fileInput || !fileContainer || !fileName || !uploadBtn) {
        console.error('Required elements not found');
        return;
    }

    fileInput.value = '';
    fileContainer.classList.remove('has-file');
    fileName.textContent = '';
    fileName.style.display = 'none';
    uploadBtn.setAttribute('disabled', true);
}

// Display toast notification
function showToast(message, type = 'info') {
    // Remove any existing toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        document.body.removeChild(existingToast);
    }

    // Create new toast
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Show the toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    // Auto hide after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// Show download button
function showDownloadButton(url, filename) {
    const downloadContainer = document.getElementById('downloadContainer');
    const downloadBtn = document.getElementById('downloadBtn');
    const processingContainer = document.getElementById('processingContainer');
    
    if (!downloadContainer || !downloadBtn) {
        console.error('Download elements not found');
        return;
    }
    
    downloadBtn.href = url;
    downloadBtn.download = filename;
    downloadContainer.style.display = 'block';
    processingContainer.style.display = 'none';
}

// Main upload function
async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const errorDiv = document.getElementById('error');
    const processingContainer = document.getElementById('processingContainer');
    const downloadContainer = document.getElementById('downloadContainer');
    const statusText = document.getElementById('statusText');

    // Check if all required elements exist
    if (!fileInput || !errorDiv || !processingContainer || !downloadContainer || !statusText) {
        console.error('Required elements not found');
        showToast('Saytda xatolik yuz berdi. Iltimos, sahifani yangilang.', 'error');
        return;
    }

    // Reset previous states
    errorDiv.style.display = 'none';
    downloadContainer.style.display = 'none';
    processingContainer.style.display = 'none';

    if (!fileInput.files.length) {
        errorDiv.textContent = 'Iltimos, faylni tanlang';
        errorDiv.style.display = 'block';
        return;
    }

    try {
        // Show processing indicator
        processingContainer.style.display = 'block';
        statusText.textContent = 'Faylni yuklash...';

        // Prepare form data
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        // Send request to server
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        // Check if response is OK
        if (!response.ok) {
            // Try to get error message from response
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Server xatosi yuz berdi');
            } else {
                throw new Error('Server xatosi yuz berdi');
            }
        }

        // Get statistics from headers
        const total = response.headers.get('X-Total-Domains');
        const working = response.headers.get('X-Working-Domains');
        const notWorking = response.headers.get('X-Not-Working-Domains');
        const needCheck = response.headers.get('X-Need-Check-Domains');

        statusText.textContent = 'Yakunlandi!';

        // Get the file blob
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);

        // Show download button
        showDownloadButton(url, 'domain_report.xlsx');

        // Show success message
        showToast('Hisobot muvaffaqiyatli yaratildi!', 'success');

    } catch (error) {
        console.error('Upload error:', error);
        // Show error message
        errorDiv.textContent = error.message || 'Server xatosi. Iltimos, qayta urinib ko\'ring.';
        errorDiv.style.display = 'block';
        processingContainer.style.display = 'none';
        showToast(error.message || 'Xatolik yuz berdi!', 'error');
    }
}