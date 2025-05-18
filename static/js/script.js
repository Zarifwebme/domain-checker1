// Global variables
let processingTimer = null;
let progressInterval = null;
let currentProgress = 0;
const processingStages = [
    "Faylni yuklash...",
    "Domenlarni o'qish...",
    "Domenlarni tekshirish...",
    "Excel hisobotini yaratish..."
];
let currentStage = 0;

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

// Progress bar animation
function updateProgressBar(progress) {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    if (!progressBar || !progressText) {
        console.error('Progress bar elements not found');
        return;
    }
    
    // Update progress bar width
    progressBar.style.width = `${progress}%`;
    
    // Update progress text
    progressText.textContent = `${progress}%`;
    
    // Add continuous scrolling animation
    if (progress < 100) {
        progressBar.style.animation = 'progressScroll 1s linear infinite';
    } else {
        progressBar.style.animation = 'none';
    }
}

// Show download button
function showDownloadButton(url, filename) {
    const downloadContainer = document.getElementById('downloadContainer');
    const downloadBtn = document.getElementById('downloadBtn');
    
    if (!downloadContainer || !downloadBtn) {
        console.error('Download elements not found');
        return;
    }
    
    downloadBtn.href = url;
    downloadBtn.download = filename;
    downloadContainer.style.display = 'block';
}

// Add CSS animation for continuous scrolling
const style = document.createElement('style');
style.textContent = `
    @keyframes progressScroll {
        0% {
            background-position: 0% 50%;
        }
        100% {
            background-position: 200% 50%;
        }
    }
    
    #progressBar {
        background: linear-gradient(90deg, 
            #4CAF50 0%, 
            #45a049 25%, 
            #4CAF50 50%, 
            #45a049 75%, 
            #4CAF50 100%
        );
        background-size: 200% 100%;
        transition: width 0.3s ease-in-out;
    }
`;
document.head.appendChild(style);

// Main upload function
async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const errorDiv = document.getElementById('error');
    const processingContainer = document.getElementById('processingContainer');
    const downloadContainer = document.getElementById('downloadContainer');
    const progressBar = document.getElementById('progressBar');
    const statusText = document.getElementById('statusText');

    // Check if all required elements exist
    if (!fileInput || !errorDiv || !processingContainer || !downloadContainer || !progressBar || !statusText) {
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
        
        // Start with 0% progress and continuous animation
        updateProgressBar(0);

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

        // Update progress to 100% and stop animation
        updateProgressBar(100);
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
        if (progressBar) {
            progressBar.style.animation = 'none';
        }
        showToast(error.message || 'Xatolik yuz berdi!', 'error');
    }
}