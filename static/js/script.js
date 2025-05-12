async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const errorDiv = document.getElementById('error');
    const loadingDiv = document.getElementById('loading');

    errorDiv.style.display = 'none';
    loadingDiv.style.display = 'none';

    if (!fileInput.files.length) {
        errorDiv.textContent = 'Please select a file';
        errorDiv.style.display = 'block';
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        loadingDiv.style.display = 'block';

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        loadingDiv.style.display = 'none';

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'domain_report.xlsx';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } else {
            const data = await response.json();
            errorDiv.textContent = data.error || 'Error processing file';
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        loadingDiv.style.display = 'none';
        errorDiv.textContent = 'Server error. Please try again.';
        errorDiv.style.display = 'block';
    }
}