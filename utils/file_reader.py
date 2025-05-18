import docx
import openpyxl
import re
import logging
import os
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


def clean_domain(domain: str) -> Optional[str]:
    """
    Domen nomini tozalash va validatsiya qilish.
    Subdomainlarni ham to'g'ri aniqlaydi (masalan: 'sur.ewe.test.uz').

    Args:
        domain: Tozalash kerak bo'lgan domen nomi

    Returns:
        Tozalangan domen yoki None (agar noto'g'ri formatda bo'lsa)
    """
    if not domain or not isinstance(domain, str):
        return None

    # Domenni tozalash
    domain = domain.strip().lower()

    # Tekshirish natijalari: kabi yozuvlarni olib tashlash
    domain = re.sub(r'tekshirish natijalari:.*', '', domain, flags=re.IGNORECASE)

    # Protokollarni olib tashlash
    domain = re.sub(r'^https?://', '', domain)

    # Trailing slash va qo'shimcha parametrlarni olib tashlash
    domain = re.sub(r'/.*$', '', domain)

    # Bo'sh joylarni yana bir bor tekshirish
    domain = domain.strip()

    if not domain:
        return None

    # IP-addresslarni tekshirish
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ip_pattern, domain):
        return domain

    # Domainni tekshirish - yanada yaxshiroq pattern
    # Bu pattern ko'p darajali subdomainlarni ham qo'llab-quvvatlaydi
    domain_pattern = r'^([a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$'
    if re.match(domain_pattern, domain):
        return domain

    return None


def extract_domains_from_text(text: str) -> List[str]:
    """
    Matndan domenlarni ajratib olish.

    Args:
        text: Matn

    Returns:
        Domenlar ro'yxati
    """
    if not text:
        return []

    domains = []

    # Vergul, tab, yangi qator yoki bo'sh joy bilan ajratilgan domenlarni ajratib olish
    for line in re.split(r'[\n\r]+', text):
        line = line.strip()
        if not line:
            continue

        # Vergul bilan ajratilgan domenlar
        parts = re.split(r'[,\t ]+', line)
        for part in parts:
            part = part.strip()
            if part:
                domains.append(part)

    return domains


def read_file(file_path: str, max_domains: int = 5000) -> List[str]:
    """
    Fayldan domainlarni o'qish va formatini to'g'rilash.

    Ko'p darajali subdomainlarni to'g'ri aniqlaydi ('sur.ewe.test.uz' kabi).
    Fayl tarkibidagi barcha domainlarni topishi uchun yaxshilangan.

    Args:
        file_path: Fayl yo'li
        max_domains: Qayta ishlash uchun maksimal domenlar soni

    Returns:
        Domenlar ro'yxati
    """
    potential_domains: Set[str] = set()

    try:
        # Fayl mavjudligini tekshirish
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return []

        # Faylning turi bo'yicha o'qish
        if file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                domains_from_text = extract_domains_from_text(content)
                potential_domains.update(domains_from_text)

        elif file_path.endswith('.docx'):
            try:
                doc = docx.Document(file_path)
                # Paragraflardan domenlarni olish
                for para in doc.paragraphs:
                    text = para.text.strip()
                    domains_from_text = extract_domains_from_text(text)
                    potential_domains.update(domains_from_text)

                # Jadvallardan domenlarni olish
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            text = cell.text.strip()
                            domains_from_text = extract_domains_from_text(text)
                            potential_domains.update(domains_from_text)
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
                                domains_from_text = extract_domains_from_text(text)
                                potential_domains.update(domains_from_text)
            except Exception as e:
                logger.error(f"Error reading xlsx file: {str(e)}")

        # Domenlarni tozalash va validatsiya qilish
        valid_domains = []
        for domain in potential_domains:
            cleaned = clean_domain(domain)
            if cleaned:
                valid_domains.append(cleaned)

            # Maksimal domenlar sonini tekshirish
            if len(valid_domains) >= max_domains:
                logger.warning(f"Reached maximum number of domains ({max_domains}). Truncating list.")
                break

        # Duplikatlarni olib tashlash
        unique_domains = list(set(valid_domains))
        unique_domains.sort()  # Sortirovka qilish
        logger.info(
            f"Read {len(potential_domains)} potential domains, {len(valid_domains)} valid, {len(unique_domains)} unique")

        return unique_domains

    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        return []