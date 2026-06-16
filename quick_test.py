import json
from backend.llm_handler import LLMHandler
llm = LLMHandler("/Users/alex/BerestaAI/fast.gguf")
text = "Справка об установлении инвалидности (копия справки МСЭ)\\n\\nСтороны: ИП Смирнов А.А. и Сидоров С.С.\\n\\n(Текст документа...)\\nПодписи сторон."
res = llm.analyze_text(text, 1)
print("---")
print("Type:", res['short_name'])
print("Date:", res['date'])
