import fitz
import os
from backend.llm_handler import LLMHandler

model_path = os.path.expanduser('~') + "/BerestaAI/fast.gguf"
llm = LLMHandler(model_path)
llm.load_model()

text = """
г. Москва
01.10.2025 г.

Приложение № 29
к Договору разработки № Р-01-06/2023 от 01.06.2023 г.
(далее - Приложение и Договор)

Заказчик: Общество с ограниченной ответственностью "ЛАНГЕЙМ ПРОГРАММНЫЕ РЕШЕНИЯ"
в лице Генерального директора Лукина Дмитрия Сергеевича, действующего на основании Устава

Исполнитель: ИП Синицын Андрей Дмитриевич
"""

print(llm.analyze_text(text, 1, 0))
