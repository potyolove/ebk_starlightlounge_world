#!/usr/bin/env python3
"""Discover all theme manifests under one parent folder; image originals are untouched."""
from pathlib import Path
import argparse,hashlib,json,re

def build(parent):
    parent=Path(parent)
    if parent.is_symlink() or not parent.is_dir():raise ValueError('Theme parent must be an existing regular directory')
    parent=parent.resolve();rows=[];ids=set();asset_ids=set()
    paths=sorted(parent.rglob('*.json'))
    if len(paths)>4096:raise ValueError('Too many JSON files under theme parent')
    for path in paths:
        if path.name=='theme_catalog.json':continue
        if path.is_symlink() or not path.resolve().is_relative_to(parent):raise ValueError('Symlink outside theme parent')
        if path.stat().st_size>262144:continue
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data,dict):continue
        if data.get('schemaVersion')==1 and isinstance(data.get('themeId'),str):
            ident=data['themeId'];label=data.get('displayName') or ident;kind='ebk-theme-v1'
        elif data.get('format')=='ebk-sample-videoroster-v1' and data.get('kind')=='theme':
            ident=data.get('groupId');label=data.get('label');kind='ebk-sample-videoroster-v1'
        else:continue
        if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',ident):raise ValueError('Invalid theme ID')
        asset=ident.replace('.','_').casefold()
        if ident.casefold() in ids or asset in asset_ids:raise ValueError('Duplicate theme ID or import path: '+ident)
        if not isinstance(label,str) or not label.strip() or len(label)>120:raise ValueError('Invalid display name')
        ids.add(ident.casefold());asset_ids.add(asset)
        relative=path.relative_to(parent).as_posix()
        if any(not re.fullmatch(r'[\w .-]+',part,flags=re.UNICODE) for part in relative.split('/')):raise ValueError('Unsupported theme path')
        explicit_generation=data.get('generation')
        generation=(explicit_generation if isinstance(explicit_generation,str) and re.fullmatch(r'[0-9a-f]{32}',explicit_generation)
                    else hashlib.sha256(path.read_bytes()).hexdigest()[:32])
        rows.append({'themeId':ident,'displayName':label,'manifestPath':relative,'format':kind,
                     'generation':generation})
    if len(rows)>64:raise ValueError('At most 64 themes per catalog')
    rows.sort(key=lambda row:row['themeId'])
    target=parent/'theme_catalog.json'
    if target.is_symlink():raise ValueError('Catalog must not be a symlink')
    generation=hashlib.sha256(json.dumps(
        {'format':'ebk-theme-catalog-v1','themes':[
            {'themeId':r['themeId'],'generation':r['generation']} for r in rows]},
        ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()[:32]
    content=json.dumps({'schemaVersion':1,'format':'ebk-theme-catalog-v1',
                        'generation':generation,'themes':rows},ensure_ascii=False,indent=2)+'\n'
    temporary=parent/'.theme_catalog.tmp';temporary.write_text(content,encoding='utf-8');temporary.replace(target)
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);a=p.parse_args();print('Themes:',len(build(a.folder)))
