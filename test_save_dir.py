import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.api import Api

api = Api()

# Создаем пустой PDF-файл для имитации
test_pdf_path = "/tmp/test_original.pdf"
from pypdf import PdfWriter
writer = PdfWriter()
writer.add_blank_page(width=200, height=200)
with open(test_pdf_path, "wb") as f:
    writer.write(f)

# Mock preview data
preview_data = [{
    'original_file': test_pdf_path,
    'start_page': 1,
    'end_page': 1,
    'new_name': "Тестовый документ"
}]

# 1. Тест с пустым output_dir (должно сохраниться в директорию исходного файла)
saved_files = api.save_documents(preview_data, "")

print("=== РЕЗУЛЬТАТ ТЕСТА ===")
if saved_files:
    print(f"Сохранено в: {saved_files[0]}")
    expected_dir = os.path.dirname(test_pdf_path)
    actual_dir = os.path.dirname(saved_files[0])
    print(f"Ожидаемая папка: {expected_dir}")
    print(f"Фактическая папка: {actual_dir}")
    
    if expected_dir == actual_dir:
        print("УСПЕХ: Файл сохранился в ту же папку.")
    else:
        print("ОШИБКА: Файл сохранился не в ту папку (вероятно, в корень проекта).")
else:
    print("Ошибка сохранения!")
