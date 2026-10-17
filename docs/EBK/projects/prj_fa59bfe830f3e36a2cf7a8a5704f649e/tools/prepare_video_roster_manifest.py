#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

SUPPORTED_EXTENSIONS={'.png','.jpg','.jpeg','.webp'}
SLOT_PATTERN=re.compile(r'^slot([0-9]+)$',re.IGNORECASE)
POSTER_FOLDERS=[
 ('main','EventPoster'),('front','FrontPoster'),('side','SidePoster'),
 ('back','BackPoster'),('notice','Notice'),('menu','Menu'),('kanpe','Kanpe')
]

def discover(folder:Path):
    found={}
    if not folder.is_dir(): return []
    for path in folder.iterdir():
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS: continue
        m=SLOT_PATTERN.match(path.stem)
        if not m: continue
        slot=int(m.group(1))
        if slot in found: raise RuntimeError(f'duplicate slot{slot}: {found[slot]} / {path}')
        found[slot]=path
    return sorted(found)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',default='data/roster_manifest.json')
    ap.add_argument('--posters-root',default='images/posters')
    ap.add_argument('--output',default='data/roster_manifest.video.generated.json')
    ap.add_argument('--allow-gaps',action='store_true')
    a=ap.parse_args()

    src=json.loads(Path(a.manifest).read_text(encoding='utf-8'))
    known={c.lower() for _,c in POSTER_FOLDERS}
    posters=[]
    for item in src.get('posters',[]):
        if isinstance(item,dict) and str(item.get('category','')).lower() not in known:
            posters.append(dict(item))

    for folder,category in POSTER_FOLDERS:
        slots=discover(Path(a.posters_root)/folder)
        if slots and not a.allow_gaps:
            expected=list(range(max(slots)+1))
            if slots!=expected:
                raise RuntimeError(f'{category} slots must be contiguous from slot0: {slots}')
        for slot in slots:
            posters.append({'category':category,'enabled':True,'slot':slot})
        print(f'{category}: {len(slots)}')

    out=dict(src)
    out['posters']=posters
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('generated:',a.output)

if __name__=='__main__':
    main()
