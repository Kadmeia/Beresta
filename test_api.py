import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.api import Api
from backend.llm_handler import LLMHandler

api = Api()

# Test the regex parsing directly
print("Testing format_parties...")
# mock the model manager for a quick test
api.llm_handler = LLMHandler("dummy_path")

text_test_1 = "Общество с ограниченной ответственностью 'Ромашка' и Индивидуальный предприниматель Иванов Иван Иванович"
# We can't easily test the private `format_parties` since it's nested inside `analyze_text`.
# Let's extract it or copy it for testing.

import re
def format_parties(text):
    if not text: return ""
    text = re.sub(r'(?i)общество\s+с\s+ограниченной\s+ответственностью', 'ООО', text)
    text = re.sub(r'(?i)публичное\s+акционерное\s+общество', 'ПАО', text)
    text = re.sub(r'(?i)закрытое\s+акционерное\s+общество', 'ЗАО', text)
    text = re.sub(r'(?i)акционерное\s+общество', 'АО', text)
    text = re.sub(r'(?i)индивидуальный\s+предприниматель', 'ИП', text)
    
    def replace_fio(match):
        return f"{match.group(1)} {match.group(2)[0]}.{match.group(3)[0]}."
    text = re.sub(r'([А-ЯЁ][а-яё\-]+)\s+([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+вич|[А-ЯЁ][а-яё]+вна)', replace_fio, text)
    return re.sub(r'\s+', ' ', text).strip()

print("Original:", text_test_1)
print("Formatted:", format_parties(text_test_1))
