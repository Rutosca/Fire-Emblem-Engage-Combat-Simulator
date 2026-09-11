import sys, urllib.request, re
sys.stdout.reconfigure(encoding='utf-8')
from bs4 import BeautifulSoup

url = 'https://fireemblemwiki.org/wiki/Dark_Emblem'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')
soup = BeautifulSoup(html, 'html.parser')

tables = soup.find_all('table')
for idx, t in enumerate(tables):
    text = t.get_text(' ', strip=True)
    if 'Wing Tamer' in text and 'Hortensia' in text:
        # Find which tab this table belongs to
        parent_tab = t.find_parent('div', class_='tabbertab')
        tab_title = parent_tab.get('title') if parent_tab else 'Unknown'
        print(f'=== TABLE {idx} | TAB: {tab_title} ===')
        for r in t.find_all('tr'):
            cells = [c.get_text(' ', strip=True) for c in r.find_all(['td', 'th'])]
            if any(name in str(cells) for name in ['Hortensia', 'Rosado', 'Goldmary']) and len(cells) > 6:
                print(' | '.join(cells[:15]))
                print('    Skills/Items:', cells[-1] if cells else '')
