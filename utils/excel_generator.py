from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def generate_excel(results, output_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Domenlarni tekshirish hisoboti"

    headers = ["№", "Domen", "Holati", "Holat kodi", "Sahifa turi", "Sarlavha"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col)
        cell.value = header
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")

    # Yangilangan status kodlari - 400 va 403 'Tekshirish kerak' ga o'zgartirildi
    status_codes = {
        200: "OK",
        400: "Tekshirish kerak",  # Changed from "Bad Request"
        403: "Tekshirish kerak",  # Changed from "Taqiqlangan"
        404: "Topilmadi",
        500: "Server xatosi",
        429: "Tekshirish kerak",
        503: "Tekshirish kerak",
        None: "Mavjud emas"
    }

    page_types = {
        "Internal": "Ichki",
        "External": "Tashqi",
        "Error": "Xato",
        "Non-HTML": "HTML emas",
        "Unknown": "Noma'lum"
    }

    title_defaults = {
        "No Title": "Sarlavhasiz",
        "Error": "Xato",
        "Non-HTML": "HTML emas",
        "Timeout": "Tekshirish kerak"  # Added for timeout case
    }

    for row, result in enumerate(results, 2):
        ws.cell(row=row, column=1).value = row - 1
        ws.cell(row=row, column=2).value = result["domain"]

        # Holati ustuniga "Tekshirish kerak" qo'yish uchun qo'shimcha mantiq
        status_value = {
            "Working": "Ishlayapti",
            "Not Working": "Ishlamayapti",
            "Need to Check": "Tekshirish kerak"
        }.get(result["status"], "Noma'lum")

        # 400, 403 statuslari uchun "Tekshirish kerak" qo'yish
        if result["status_code"] in [400, 403]:
            status_value = "Tekshirish kerak"

        # Timeout holatida ham "Tekshirish kerak" qo'yish
        if result.get("title") == "Timeout":
            status_value = "Tekshirish kerak"

        ws.cell(row=row, column=3).value = status_value

        # Status kodi ustuni
        status_code = result["status_code"]
        status_code_str = status_codes.get(status_code, str(status_code) if status_code else "Mavjud emas")
        ws.cell(row=row, column=4).value = status_code_str

        ws.cell(row=row, column=5).value = page_types.get(result["page_type"], result["page_type"])
        ws.cell(row=row, column=6).value = title_defaults.get(result["title"], result["title"])

        # Status cell rangi - "Need to Check" holatlarni sariq rangda ko'rsatish
        status_cell = ws.cell(row=row, column=3)

        if status_value == "Tekshirish kerak":
            # Sariq rang
            color = "FFC107"
        elif status_value == "Ishlayapti":
            # Yashil rang
            color = "4CAF50"
        else:
            # Qizil rang (Ishlamayapti va boshqa holatlar uchun)
            color = "F44336"

        status_cell.fill = PatternFill(
            start_color=color,
            end_color=color,
            fill_type="solid"
        )

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    for row in ws.iter_rows(min_row=1, max_row=len(results) + 1, min_col=1, max_col=6):
        for cell in row:
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="left")

    for col in range(1, 7):
        ws.column_dimensions[get_column_letter(col)].width = 20

    wb.save(output_path)