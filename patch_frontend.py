import re

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add global variable
if "let isProcessing = false;" not in html:
    html = html.replace("        let selectedFiles = [];", "        let isProcessing = false;\n        let selectedFiles = [];")

# 2. Add showErrorModal helper
if "function showErrorModal(" not in html:
    html = html.replace("        // Toggle Theme", """        function showErrorModal(message) {
            alert(message); // Fallback to alert for simplicity, or we can use custom modal
        }
        
        // Toggle Theme""")

# 3. Patch handleDrop
html = html.replace("        async function handleDrop(e) {", """        async function handleDrop(e) {
            if (isProcessing) {
                showErrorModal("Дождитесь завершения текущей операции!");
                return;
            }""")

# 4. Patch openFileDialog
html = html.replace("        async function handleOpenFiles() {", """        async function handleOpenFiles() {
            if (isProcessing) {
                showErrorModal("Дождитесь завершения текущей операции!");
                return;
            }""")

# 5. Patch startProcessing
html = html.replace("        async function startProcessing() {", """        async function startProcessing() {
            if (isProcessing) {
                showErrorModal("Система уже обрабатывает файлы!");
                return;
            }
            isProcessing = true;""")

# Add finally block to startProcessing to reset isProcessing
# Find the end of startProcessing
start_proc_end = """            } catch (error) {
                alert("Ошибка: " + error);
                btn.style.display = 'block';
                progressContainer.style.display = 'none';
            }
        }"""
new_start_proc_end = """            } catch (error) {
                alert("Ошибка: " + error);
                btn.style.display = 'block';
                progressContainer.style.display = 'none';
            } finally {
                isProcessing = false;
            }
        }"""
html = html.replace(start_proc_end, new_start_proc_end)

# 6. Patch saveDocuments
html = html.replace("        async function saveDocuments() {", """        async function saveDocuments() {
            if (isProcessing) {
                showErrorModal("Дождитесь завершения текущей операции!");
                return;
            }
            isProcessing = true;""")
save_doc_end = """            } catch (error) {
                alert("Ошибка при сохранении: " + error);
            }
        }"""
new_save_doc_end = """            } catch (error) {
                alert("Ошибка при сохранении: " + error);
            } finally {
                isProcessing = false;
            }
        }"""
html = html.replace(save_doc_end, new_save_doc_end)

# 7. Patch downloadModel and deleteModel
html = html.replace("        async function downloadModel() {", """        async function downloadModel() {
            if (isProcessing) return showErrorModal("Дождитесь завершения текущей операции!");
            isProcessing = true;""")
html = html.replace("                checkModelStatus();\n            } catch", "                checkModelStatus();\n            } finally { isProcessing = false; }\n            catch")

html = html.replace("        async function deleteModel() {", """        async function deleteModel() {
            if (isProcessing) return showErrorModal("Дождитесь завершения текущей операции!");
            isProcessing = true;""")
html = html.replace("                checkModelStatus();\n            }\n        }", "                checkModelStatus();\n            } finally { isProcessing = false; }\n        }")

# 8. Disable dropzone click
html = html.replace("onclick=\"handleOpenFiles()\"", "onclick=\"if(!isProcessing) handleOpenFiles()\"")

with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Frontend patched.")
