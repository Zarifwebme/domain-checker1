import docx
import openpyxl
import re


def read_file(file_path):
    domains = []
    try:
        if file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8') as f:
                domains = [line.strip() for line in f if line.strip()]

        elif file_path.endswith('.docx'):
            doc = docx.Document(file_path)
            domains = [para.text.strip() for para in doc.paragraphs if para.text.strip()]

        elif file_path.endswith('.xlsx'):
            wb = openpyxl.load_workbook(file_path)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                for cell in row:
                    if cell and isinstance(cell, str):
                        domains.append(cell.strip())

        # Clean and validate domains
        domains = [re.sub(r'^https?://', '', d).strip('/') for d in domains]
        domains = [d for d in domains if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', d)]
        return list(set(domains))  # Remove duplicates

    except Exception as e:
        print(f"Error reading file: {str(e)}")
        return []