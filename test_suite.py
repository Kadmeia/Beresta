import os
import json
import re
from backend.llm_handler import LLMHandler

model_path = os.path.expanduser('~') + "/BerestaAI/fast.gguf"
llm = LLMHandler(model_path)
llm.load_model()

with open('test_data_criminal.json', 'r', encoding='utf-8') as f:
    scenarios = json.load(f)

print(f"=== STARTING MASS TESTS ({len(scenarios)} documents) ===")

results = []

for i, sc in enumerate(scenarios):
    print(f"[{i+1}/{len(scenarios)}] Testing: {sc['name']} (Layout: {sc['layout']})")
    
    # Analyze text
    analysis = llm.analyze_text(sc['text'], 1, 0)
    
    # Демонстрация паттерна самопроверки (Двухпроходный анализ для сложных документов)
    # Если мы не нашли дату или полное имя, делаем retry
    if not analysis['date'] or not analysis['full_name'] or len(analysis['full_name']) < 10:
        analysis = llm.analyze_text(sc['text'], 1, retry=1)
        
    results.append({
        "Document": sc['name'],
        "Layout": sc['layout'],
        "Expected Date/Num": sc['expected_date_num'],
        "Extracted Type": analysis['short_name'],
        "Extracted Date": analysis['date']
    })

print("\\n=== TESTS FINISHED ===")

# Generate Markdown Report
with open('mass_test_report_criminal.md', 'w', encoding='utf-8') as f:
    f.write("# Массовое тестирование распознавания уголовно-правовых документов (30+ файлов)\\n\\n")
    f.write("Модель: `Vikhr-Qwen-2.5-1.5B` (локальная)\\n\\n")
    f.write("| Документ | Layout | Ожидаемые реквизиты | Извлеченный Тип | Извлеченная Дата |\\n")
    f.write("|---|---|---|---|---|\\n")
    for r in results:
        doc = r['Document']
        if len(doc) > 40: doc = doc[:37] + "..."
        layout = r['Layout']
        expected = r['Expected Date/Num']
        extr_type = r['Extracted Type']
        extr_date = r['Extracted Date']
        f.write(f"| {doc} | {layout} | {expected} | {extr_type} | {extr_date} |\\n")

print("Report saved to mass_test_report_criminal.md")
