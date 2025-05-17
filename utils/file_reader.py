import docx
import openpyxl
import re
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


def clean_domain(domain: str) -> Optional[str]:
    """
    Domen nomini tozalash va validatsiya qilish.

    Args:
        domain: Tozalash kerak bo'lgan domen nomi

    Returns:
        Tozalangan domen yoki None (agar noto'g'ri formatda bo'lsa)
    """
    if not domain or not isinstance(domain, str):
        return None

    # Domenni tozalash
    domain = domain.strip().lower()

    # Protokollarni olib tashlash
    domain = re.sub(r'^https?://', '', domain)

    # Trailing slash va qo'shimcha parametrlarni olib tashlash
    domain = re.sub(r'/.*$', '', domain)

    # IP-addresslarni tekshirish
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ip_pattern, domain):
        return domain

    # Domainni tekshirish
    domain_pattern = r'^[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,}$'
    if re.match(domain_pattern, domain):
        return domain

    # Subdomenlar uchun tekshirish
    subdomain_pattern = r'^[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,}$'
    if re.match(subdomain_pattern, domain):
        return domain

    return None


def read_file(file_path: str, max_domains: int = 5000) -> List[str]:
    """
    Fayldan domainlarni o'qish.

    Args:
        file_path: Fayl yo'li
        max_domains: Qayta ishlash uchun maksimal domenlar soni

    Returns:
        Domenlar ro'yxati
    """
    domains = []

    try:
        # Fayl mavjudligini tekshirish
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return []

        # Faylning turi bo'yicha o'qish
        if file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        domains.append(line)

        elif file_path.endswith('.docx'):
            try:
                doc = docx.Document(file_path)
                for para in doc.paragraphs:
                    text = para.text.strip()
                    if text:
                        # Har bir satrni alohida domen sifatida qabul qilish
                        for line in text.split('\n'):
                            line = line.strip()
                            if line:
                                domains.append(line)

                # Jadvallardan ham domenlarni olish
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            text = cell.text.strip()
                            if text:
                                for line in text.split('\n'):
                                    line = line.strip()
                                    if line:
                                        domains.append(line)
            except Exception as e:
                logger.error(f"Error reading docx file: {str(e)}")

        elif file_path.endswith('.xlsx'):
            try:
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                for sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    for row in sheet.rows:
                        for cell in row:
                            if cell.value and isinstance(cell.value, str):
                                text = cell.value.strip()
                                if text:
                                    # Vergul bilan ajratilgan domenlar ro'yxatini tekshirish
                                    if ',' in text:
                                        for part in text.split(','):
                                            part = part.strip()
                                            if part:
                                                domains.append(part)
                                    else:
                                        domains.append(text)
            except Exception as e:
                logger.error(f"Error reading xlsx file: {str(e)}")

        # Domenlarni tozalash va validatsiya qilish
        valid_domains = []
        for domain in domains:
            cleaned = clean_domain(domain)
            if cleaned:
                valid_domains.append(cleaned)

            # Maksimal domenlar sonini tekshirish
            if len(valid_domains) >= max_domains:
                logger.warning(f"Reached maximum number of domains ({max_domains}). Truncating list.")
                break

        # Duplikatlarni olib tashlash
        unique_domains = list(set(valid_domains))
        logger.info(f"Read {len(domains)} domains, {len(valid_domains)} valid, {len(unique_domains)} unique")

        return unique_domains

    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        return []