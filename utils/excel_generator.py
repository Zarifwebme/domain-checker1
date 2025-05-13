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

    status_codes = {
        200: "OK",
        404: "Topilmadi",
        403: "Taqiqlangan",
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
        "Non-HTML": "HTML emas"
    }

    for row, result in enumerate(results, 2):
        ws.cell(row=row, column=1).value = row - 1
        ws.cell(row=row, column=2).value = result["domain"]
        ws.cell(row=row, column=3).value = {
            "Working": "Ishlayapti",
            "Not Working": "Ishlamayapti",
            "Need to Check": "Tekshirish kerak"
        }.get(result["status"], "Noma'lum")
        ws.cell(row=row, column=4).value = status_codes.get(result["status_code"], str(result["status_code"]))
        ws.cell(row=row, column=5).value = page_types.get(result["page_type"], result["page_type"])
        ws.cell(row=row, column=6).value = title_defaults.get(result["title"], result["title"])

        status_cell = ws.cell(row=row, column=3)
        status_cell.fill = PatternFill(
            start_color="4CAF50" if result["status"] == "Working" else "F44336" if result[
                                                                                       "status"] == "Not Working" else "FFC107",
            end_color="4CAF50" if result["status"] == "Working" else "F44336" if result[
                                                                                     "status"] == "Not Working" else "FFC107",
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