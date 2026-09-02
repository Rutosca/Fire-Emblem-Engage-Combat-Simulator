import xml.etree.ElementTree as ET
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Check Job.xml for MoveType values (fliers, cavalry, armored)
tree = ET.parse(r'FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\Job.xml')
root = tree.getroot()
jobs = root.findall('.//Data/Param')

print("=== JOB MOVETYPES (unique values) ===")
move_types = {}
for job in jobs:
    jid = job.get('Jid', '')
    mt = job.get('MoveType', '')
    if jid and mt:
        if mt not in move_types:
            move_types[mt] = []
        move_types[mt].append(jid)

for mt, jids in sorted(move_types.items()):
    print(f"  MoveType={mt}: {jids[:5]}")

print()
# Check Skill.xml for effectiveness SID definitions
tree2 = ET.parse(r'FE17-DOC-main\FE17-DOC-main\fe_assets_gamedata\Skill.xml')
root2 = tree2.getroot()
skills = root2.findall('.//Data/Param')

print("=== EFFECTIVENESS SKILL SIDs ===")
effectiveness_keywords = ['特効', 'EffectiveAgainst', '効果']
for skill in skills:
    sid = skill.get('Sid', '')
    if any(kw in sid for kw in effectiveness_keywords):
        name = skill.get('Name', '')
        help_txt = skill.get('Help', '')
        # Look for what attributes determine the target
        for k, v in skill.attrib.items():
            if v and v not in ('0', ''):
                print(f"  {k}: {v}", end="  ")
        print()
        print()
