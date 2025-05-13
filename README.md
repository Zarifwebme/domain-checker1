Domenlarni tekshirish veb-ilovasi
Flask asosidagi veb-ilova .txt, .docx yoki .xlsx fayllaridagi domenlarni tekshiradi va o‘zbek tilida Excel hisobotini yaratadi.
Xususiyatlar

.txt, .docx yoki .xlsx fayllarini yuklash.
Domen holati (Ishlayapti/Ishlamayapti), HTTP holat kodi, sahifa turi (Ichki/Tashqi) va sarlavhani tekshirish.
O‘zbek tilida shartli formatlash bilan Excel hisoboti.
Bootstrap v5.3.3 va Word, Excel, tekst fayl logotiplari bilan frontend.
Railway’da gunicorn bilan joylashtiriladi.

Sozlash

Repozitoriyani klonlash:git clone <repository-url>
cd domain_checker


Virtual muhit yaratish va bog‘liqliklarni o‘rnatish:python -m venv venv
source venv/bin/activate  # Windows’da: venv\Scripts\activate
pip install -r requirements.txt


static/images/ ga logo rasmlarini qo‘shish:
word1.png, word2.png (Word ikonkalari)
excel1.png, excel2.png (Excel ikonkalari)
text1.png, text2.png (Tekst ikonkalari)


Ilovani lokalda ishga tushirish:python app.py


Railway’ga joylashtirish:
Kodni GitHub repozitoriyasiga yuboring.
Repozitoriyani Railway’ga ulang.
PIP_NO_CACHE_DIR=1 muhit o‘zgaruvchisini o‘rnating (ixtiyoriy).
Procfile yordamida joylashtiring.



Foydalanish

Ilovani brauzerda oching.
Domenlar ro‘yxati bo‘lgan faylni yuklang.
Natijalarni o‘zbek tilida Excel hisobotida yuklab oling.

Fayl tuzilishi

app.py: Flask backend.
utils/: Fayl o‘qish, domen tekshirish va Excel hisoboti logikasi.
static/: CSS, JS, rasmlar va favicon.
templates/: Yagona sahifa uchun HTML.
requirements.txt: Python bog‘liqliklari.
Procfile: Railway jarayon sozlamalari.

Eslatmalar

static/images/ dagi o‘rinbosar rasmlarni haqiqiy Word, Excel, tekst ikonkalari bilan almashtiring (100x100px PNG).
example.com, login.microsoftonline.com kabi domenlar bilan test.txt faylida sinovdan o‘tkazing.

