#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, tempfile, shutil
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

EXTS=['.png','.jpg','.jpeg','.webp']
PORTRAIT_FOLDERS={
 'Owner':'owner','Manager':'manager','Operator':'operator','Assistant':'assistant',
 'StaffLeader':'staffleader','Staff':'staff','SwitchCast':'switchcast',
 'CastLeader':'castleader','UpperCast':'uppercast','DownerCast':'downercast',
 'ConditionalCast':'condisionalcast','CondisionalCast':'condisionalcast'
}
POSTER_FOLDERS={
 'EventPoster':'main','FrontPoster':'front','SidePoster':'side','BackPoster':'back',
 'Notice':'notice','Menu':'menu','Kanpe':'kanpe'
}

def find_image(base:Path,kind:str,category:str,slot:int):
    folder=(PORTRAIT_FOLDERS if kind=='member' else POSTER_FOLDERS).get(category,category.lower())
    root=base/('portraits' if kind=='member' else 'posters')/folder
    for ext in EXTS:
        p=root/f'slot{slot}{ext}'
        if p.is_file(): return p
    return None

def raw_url(repo:str,branch:str,path:Path):
    return f'https://raw.githubusercontent.com/{repo}/{branch}/{path.as_posix()}'

def make_frame(src:Path|None,dst:Path,w:int,h:int,stretch:bool,label:str):
    if src is None:
        im=Image.new('RGB',(w,h),(20,20,20))
        d=ImageDraw.Draw(im); d.text((40,40),'MISSING: '+label,fill=(255,80,80))
        im.save(dst); return 1, 0, 0
    with Image.open(src) as im:
        im=ImageOps.exif_transpose(im).convert('RGB')
        source_width, source_height = im.size
        if stretch:
            out=im.resize((w,h),Image.Resampling.LANCZOS)
        else:
            out=Image.new('RGB',(w,h),(0,0,0))
            cp=im.copy(); cp.thumbnail((w,h),Image.Resampling.LANCZOS)
            out.paste(cp,((w-cp.width)//2,(h-cp.height)//2))
        out.save(dst)
    return 0, source_width, source_height

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repository',required=True,help='owner/repository')
    ap.add_argument('--branch',default='main')
    ap.add_argument('--manifest',default='data/roster_manifest.video.generated.json')
    ap.add_argument('--output',default='videos/roster.mp4')
    ap.add_argument('--frame-map-output',default='data/roster_frame_map.txt')
    ap.add_argument('--save-url-list',default='data/roster_resolved_urls.txt')
    ap.add_argument('--fps',type=int,default=30)
    ap.add_argument('--frames-per-entry',type=int,default=3)
    ap.add_argument('--sample-frame',type=int,default=1)
    ap.add_argument('--width',type=int,default=1920)
    ap.add_argument('--height',type=int,default=1080)
    ap.add_argument('--resize-mode',choices=['stretch','contain'],default='stretch')
    a=ap.parse_args()

    manifest=json.loads(Path(a.manifest).read_text(encoding='utf-8'))
    entries=[]
    for item in manifest.get('members',[]):
        if not isinstance(item,dict) or not item.get('enabled',True): continue
        if not item.get('showPortrait',True): continue
        entries.append(('member',str(item.get('category','')),int(item.get('slot',0))))
    for item in manifest.get('posters',[]):
        if not isinstance(item,dict) or not item.get('enabled',True): continue
        entries.append(('poster',str(item.get('category','')),int(item.get('slot',0))))

    fps=max(1,a.fps); frames=max(1,a.frames_per_entry)
    sample=max(0,min(a.sample_frame,frames-1))
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.frame_map_output).parent.mkdir(parents=True,exist_ok=True)

    with tempfile.TemporaryDirectory(prefix='ebk-video-roster-') as td:
        frame_dir=Path(td)/'frames'; frame_dir.mkdir()
        lines=[]; urls=[]; frame_no=1; page=0

        if not entries:
            entries=[('poster','Notice',0)]

        for kind,category,slot in entries:
            src=find_image(Path('images'),kind,category,slot)
            label=f'{kind}|{category}|{slot}'
            first=frame_dir/f'frame_{frame_no:06d}.png'
            bad, source_width, source_height=make_frame(src,first,a.width,a.height,a.resize_mode=='stretch',label)
            rel=(src if src is not None else Path('images/missing.png'))
            url=raw_url(a.repository,a.branch,rel)
            urls.append(url)
            sample_index=(frame_no-1)+sample
            sample_time=(sample_index+0.5)/fps
            geometry = ''
            if source_width > 0 and source_height > 0:
                geometry = f'|aspect={source_width/source_height:.8f}|width={source_width}|height={source_height}|fit={a.resize_mode}'
            lines.append(
                f'{sample_index}|{kind}|{category}|{slot}|{url}|1.00000000|1.00000000|0.00000000|0.00000000|'
                f'page={page}|frames={frames}|sampleFrame={sample}|sample={sample_time:.6f}|bad={bad}{geometry}'
            )
            for r in range(1,frames):
                shutil.copyfile(first,frame_dir/f'frame_{frame_no+r:06d}.png')
            frame_no+=frames; page+=1

        Path(a.frame_map_output).write_text('\n'.join(lines)+'\n',encoding='utf-8')
        Path(a.save_url_list).write_text('\n'.join(urls)+'\n',encoding='utf-8')

        subprocess.run([
            'ffmpeg','-y','-framerate',str(fps),'-start_number','1',
            '-i',str(frame_dir/'frame_%06d.png'),
            '-r',str(fps),'-c:v','libx264','-pix_fmt','yuv420p',
            '-crf','16','-g','1','-bf','0','-sc_threshold','0',
            '-tune','stillimage','-an','-movflags','+faststart',a.output
        ],check=True)
    print('built',a.output,'entries',len(entries))

if __name__=='__main__':
    main()
