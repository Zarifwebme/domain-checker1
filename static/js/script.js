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

// Start the visual progress simulation
function startProgressSimulation() {
    currentProgress = 0;
    const progressBar = document.getElementById('progressBar');
    const statusText = document.getElementById('statusText');

    // Clear any existing intervals
    if (progressInterval) {
        clearInterval(progressInterval);
    }

    // Set first stage
    statusText.textContent = processingStages[currentStage];

    // Update progress every 100ms
    progressInterval = setInterval(() => {
        // Determine how far to progress based on current stage
        let targetProgress;

        switch(currentStage) {
            case 0: // Uploading
                targetProgress = 25;
                break;
            case 1: // Reading domains
                targetProgress = 40;
                break;
            case 2: // Checking domains
                targetProgress = 90;
                break;
            case 3: // Creating Excel
                targetProgress = 100;
                break;
            default:
                targetProgress = 100;
        }

        // Increment progress toward target
        if (currentProgress < targetProgress) {
            currentProgress += 0.5;
            progressBar.style.width = `${currentProgress}%`;
        }
    }, 100);

    // Simulate stage transitions
    processingTimer = setTimeout(() => {
        advanceStage();
    }, 2000);
}

// Advance to next processing stage
function advanceStage() {
    currentStage++;
    if (currentStage < processingStages.length) {
        document.getElementById('statusText').textContent = processingStages[currentStage];

        // Schedule next stage advancement
        const waitTime = currentStage === 2 ? 5000 : 2000; // Domain checking takes longer
        processingTimer = setTimeout(() => {
            advanceStage();
        }, waitTime);
    }
}

// Stop progress simulation
function stopProgressSimulation() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }

    if (processingTimer) {
        clearTimeout(processingTimer);
        processingTimer = null;
    }

    currentStage = 0;
}

// Update domain counter during processing
function updateDomainCounter(processed, total) {
    const counter = document.getElementById('domainCounter');
    counter.textContent = `${processed} / ${total} domenlar tekshirildi`;
}

// Display the result summary
function showResultSummary(stats) {
    const summary = document.getElementById('resultSummary');
    const totalElem = document.getElementById('totalDomains');
    const workingElem = document.getElementById('workingDomains');
    const notWorkingElem = document.getElementById('notWorkingDomains');
    const checkElem = document.getElementById('checkDomains');

    totalElem.textContent = stats.total;
    workingElem.textContent = stats.working;
    notWorkingElem.textContent = stats.notWorking;
    checkElem.textContent = stats.needCheck;

    summary.style.display = 'block';
}

// Show download button
function showDownloadButton(url, filename) {
    const downloadContainer = document.getElementById('downloadContainer');
    const downloadLink = document.getElementById('downloadLink');

    downloadLink.setAttribute('href', url);
    downloadLink.setAttribute('download', filename);
    downloadContainer.style.display = 'block';
}

// Main upload function
async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const errorDiv = document.getElementById('error');
    const processingContainer = document.getElementById('processingContainer');
    const resultSummary = document.getElementById('resultSummary');
    const downloadContainer = document.getElementById('downloadContainer');

    // Reset previous states
    errorDiv.style.display = 'none';
    resultSummary.style.display = 'none';
    downloadContainer.style.display = 'none';

    if (!fileInput.files.length) {
        errorDiv.textContent = 'Iltimos, faylni tanlang';
        errorDiv.style.display = 'block';
        return;
    }

    try {
        // Show processing indicator
        processingContainer.style.display = 'block';
        startProgressSimulation();

        // Prepare form data
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        // Send request to server
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        // Stop progress simulation
        stopProgressSimulation();

        // Update progress to 100%
        document.getElementById('progressBar').style.width = '100%';
        document.getElementById('statusText').textContent = 'Yakunlandi!';

        if (response.ok) {
            // Successful response
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);

            // Get domain statistics from response headers if available
            const stats = {
                total: parseInt(response.headers.get('X-Total-Domains') || '0'),
                working: parseInt(response.headers.get('X-Working-Domains') || '0'),
                notWorking: parseInt(response.headers.get('X-Not-Working-Domains') || '0'),
                needCheck: parseInt(response.headers.get('X-Need-Check-Domains') || '0')
            };

            // If no stats from headers, use default values
            if (stats.total === 0) {
                stats.total = "Mavjud emas";
                stats.working = "Mavjud emas";
                stats.notWorking = "Mavjud emas";
                stats.needCheck = "Mavjud emas";
            }

            // Show the summary
            showResultSummary(stats);

            // Show download button
            showDownloadButton(url, 'domain_report.xlsx');

            // Show success message
            showToast('Hisobot muvaffaqiyatli yaratildi!', 'success');
        } else {
            // Error response
            const data = await response.json();
            errorDiv.textContent = data.error || 'Faylni qayta ishlashda xatolik';
            errorDiv.style.display = 'block';
            processingContainer.style.display = 'none';
            showToast('Xatolik yuz berdi!', 'error');
        }
    } catch (error) {
        // Exception handling
        stopProgressSimulation();
        processingContainer.style.display = 'none';
        errorDiv.textContent = 'Server xatosi. Iltimos, qayta urinib ko\'ring.';
        errorDiv.style.display = 'block';
        showToast('Server xatosi!', 'error');
        console.error('Error:', error);
    }
}