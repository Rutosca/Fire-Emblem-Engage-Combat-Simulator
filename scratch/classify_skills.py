import xml.etree.ElementTree as ET
import json

god_tree = ET.parse(r'FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\God.xml')
sheet1 = god_tree.getroot().findall('Sheet')[1].find('Data').findall('Param')
skill_tree = ET.parse(r'FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\Skill.xml')
skill_sheet = skill_tree.getroot().findall('Sheet')[0].find('Data').findall('Param')

with open('traducciones_cache.json', 'r', encoding='utf-8') as f:
    trans = json.load(f)

skills_dict = {}
for s in skill_sheet:
    sid = s.attrib.get('Sid')
    if sid:
        skills_dict[sid] = s.attrib

current_ggid = None
all_sync_sids = set()
for r in sheet1:
    ggid = r.attrib.get('Ggid', '').strip()
    if ggid:
        current_ggid = ggid
    lvl = r.attrib.get('Level', '').strip()
    if lvl and current_ggid:
        for s in r.attrib.get('SynchroSkills', '').split(';'):
            s = s.strip()
            if s:
                all_sync_sids.add(s)

stat_sids = []
passive_sids = []
for sid in sorted(all_sync_sids):
    sk = skills_dict.get(sid, {})
    has_stat = any(sk.get(f'Enhance.{st}', '0') != '0' for st in ['Hp', 'Str', 'Magic', 'Skill', 'Quick', 'Def', 'Mdef', 'Luck', 'Special', 'Move'])
    nom = trans.get(sk.get('Name', ''), trans.get(sid, sid))
    if has_stat:
        stat_sids.append((sid, nom))
    else:
        passive_sids.append((sid, nom))

with open('scratch/synchro_skills_classified.txt', 'w', encoding='utf-8') as f:
    f.write(f'--- STAT BOOST SKILLS ({len(stat_sids)}) ---\n')
    for sid, nom in stat_sids:
        sk = skills_dict.get(sid, {})
        enh = [f"{st}:{sk.get('Enhance.' + st)}" for st in ['Hp', 'Str', 'Magic', 'Skill', 'Quick', 'Def', 'Mdef', 'Luck', 'Special', 'Move'] if sk.get('Enhance.' + st, '0') != '0']
        f.write(f'{sid} -> {nom} ({", ".join(enh)})\n')
    f.write(f'\n--- PASSIVE SYNCHRO SKILLS ({len(passive_sids)}) ---\n')
    for sid, nom in passive_sids:
        f.write(f'{sid} -> {nom}\n')

print(f'Classified {len(all_sync_sids)} SynchroSkills into scratch/synchro_skills_classified.txt')
