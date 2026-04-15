import csv

files = [
    r'e:\Programs\vps-deploy\cashPayment_FebruaryDB_2026.csv',
    r'e:\Programs\vps-deploy\cashPayment March April.csv',
    r'e:\Programs\vps-deploy\contacts.csv',
]

for fp in files:
    count = 0
    with open(fp, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if any(cell.strip() for cell in row):
                count += 1
    print(f'{fp.split(chr(92))[-1]}: {count} data rows, headers={header[:5]}')
