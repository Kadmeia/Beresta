with open('requirements.txt', 'r') as f:
    lines = f.readlines()
with open('requirements.txt', 'w') as f:
    for line in lines:
        if 'pytesseract' not in line.lower():
            f.write(line)
