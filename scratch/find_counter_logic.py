import sys, os
sys.stdout.reconfigure(encoding='utf-8')

with open('motor_calculo.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines, 1):
    l = line.lower()
    if 'puede_contra' in l or 'contraataque' in l or 'distancia' in l and 'rango' in l:
        print(f"L{idx:4}: {line.strip()}")
