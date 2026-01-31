
try:
    with open(r"C:\Users\dados\Downloads\5opz1VEFCZ7X7Vitc2hQbQ-erro_execucao.html", "r", encoding="utf-8") as f:
        content = f.read()
        
    search_term = "tentar de outro jeito"
    index = content.lower().find(search_term.lower())
    
    if index != -1:
        start = max(0, index - 500)
        end = min(len(content), index + 500)
        print(f"Found match at index {index}")
        print("Context:")
        print(content[start:end])
    else:
        print("Not found")

except Exception as e:
    print(f"Error: {e}")
