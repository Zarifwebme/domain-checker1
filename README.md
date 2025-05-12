Domain Checker Web App
A Flask-based web application to check domains from uploaded files (.txt, .docx, .xlsx) and generate an Excel report with domain status, status code, page type, and title.
Features

Upload .txt, .docx, or .xlsx files containing domains.
Check domain status (Working/Not Working), HTTP status code, page type (Login/Functional), and page title.
Generate a formatted Excel report with conditional formatting.
Deployable on Railway with gunicorn for stability.

Setup

Clone the repository:git clone <repository-url>
cd domain_checker


Create a virtual environment and install dependencies:python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt


Run the app locally:python app.py


Deploy to Railway:
Push the code to a GitHub repository.
Connect the repository to Railway.
Set the PORT environment variable (Railway handles this automatically).
Deploy using the Procfile.



Usage

Open the app in a browser.
Upload a file containing domains (one per line or cell).
Wait for the app to process and download the Excel report.

File Structure

app.py: Flask backend.
utils/: File reading, domain checking, and Excel generation logic.
static/: CSS and JS for the frontend.
templates/: HTML for the single-page frontend.
requirements.txt: Python dependencies.
Procfile: Railway process configuration.

