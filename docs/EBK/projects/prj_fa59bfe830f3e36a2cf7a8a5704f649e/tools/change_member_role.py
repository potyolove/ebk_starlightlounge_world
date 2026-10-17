"""Change only a roster member's roleType/accessLevel; preserve image addresses."""
import json
import os
from pathlib import Path


def update_member_role(manifest, display_name, role_id):
    roles = manifest.get('roleTypes', [])
    matches = [r for r in roles if r.get('id') == role_id]
    if len(matches) != 1:
        raise ValueError('役職IDを登録役職一覧から一つ選んでください')
    role = matches[0]
    level = role.get('accessLevel')
    if type(level) is not int or not 0 <= level <= 4:
        raise ValueError('役職の権限は0から4で登録してください')
    members = [m for m in manifest.get('members', []) if (m.get('vrcName') or m.get('name')) == display_name]
    if len(members) != 1:
        raise ValueError('VRChat表示名が一意に見つかりません。名簿と完全に一致させてください')
    members[0]['roleType'] = role_id
    members[0]['accessLevel'] = level
    return manifest


if __name__ == '__main__':
    path = Path('data/roster_manifest.json')
    manifest = json.loads(path.read_text(encoding='utf-8-sig'))
    update_member_role(manifest, os.environ['EBK_MEMBER_NAME'], os.environ['EBK_ROLE_ID'])
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
