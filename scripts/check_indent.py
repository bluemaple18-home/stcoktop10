with open('app/ui.py', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if i >= 950 and i < 970:
            print(f"{i+1}: {repr(line)}")
