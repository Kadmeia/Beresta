from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

pages = [
    """ДОГОВОР № 15/2026
г. Москва                                       15 ноября 2026 г.

ООО "Ромашка" в лице Директора, с одной стороны, и ИП Иванов А.И., 
с другой стороны, заключили настоящий договор о нижеследующем:

1. Предмет договора.
""",
    """Продолжение договора со страницы 1...
Пункт 2. Обязанности сторон.
Подписи:
Директор ООО "Ромашка"
ИП Иванов А.И.
""",
    """АКТ ПРИЕМА-ПЕРЕДАЧИ
г. Москва, 16 ноября 2026 г.

ООО "Ромашка" передает, а ИП Иванов А.И. принимает результаты работ.
""",
    """ПРИЛОЖЕНИЕ № 1
Спецификация к договору № 15/2026

Наименование: Разработка ПО.
Стоимость: 100 рублей.
"""
]

# We need a font that supports Cyrillic. Helvetica standard font does not.
# Use standard Times-Roman or register Arial if possible.
# Actually, ReportLab's standard Helvetica does not support Russian well.
# We will use simple english for headers if cyrillic fails, or load a system font.
# macOS has Arial.ttf or Helvetica.ttf.
import os
font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"

def create_pdf():
    c = canvas.Canvas("test_document.pdf", pagesize=letter)
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('Arial', font_path))
        c.setFont("Arial", 14)
    else:
        c.setFont("Helvetica", 14)

    for p in pages:
        textobject = c.beginText()
        textobject.setTextOrigin(50, 750)
        for line in p.split('\\n'):
            textobject.textLine(line)
        c.drawText(textobject)
        c.showPage()
    c.save()

create_pdf()
print("Created test_document.pdf with 4 pages!")
