#!/usr/bin/env python3
"""Build an isolated EBK media root. No writes outside the selected folder.

Inputs are copied to a temporary build directory. Only validated generated
outputs are published; the caller commits them together. Legacy inputs, scripts
and videos at the repository root are not read or changed.
"""
from pathlib import Path
from urllib.parse import urlsplit, unquote, quote
import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageOps
import build_room_media_slides as slides
import build_clubcard_video as cards
import build_theme_catalog as themes


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def source_image(root, row, kind, base):
    # Portrait authority is the roster's category + slot, never an unverified URL.
    # A stale portraitUrl must not redirect one member to another member's slot.
    from github_manifest_to_video import find_image
    if kind == 'member':
        return find_image(root / 'images', kind, str(row['category']), int(row['slot']))
    address = row.get('portraitUrl' if kind == 'member' else 'imageUrl', '')
    if address:
        if not address.startswith(base + '/'):
            raise ValueError('画像URLは新しい共通ルート内で指定してください: ' + address)
        relative = unquote(urlsplit(address).path[len(urlsplit(base).path) + 1:])
        candidate = root / relative
        if not candidate.resolve().is_relative_to(root.resolve()):
            raise ValueError('Image path escapes media root')
        return candidate if candidate.is_file() else None
    from github_manifest_to_video import find_image
    return find_image(root / 'images', kind, str(row['category']), int(row['slot']))



def generation_marker(path, generation, width, height):
    value = 'eb4b26c1' + generation
    if len(value) != 40 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid generation marker')
    bits = ''.join(f'{int(c, 16):04b}' for c in value)
    image = Image.new('RGB', (width, height), 'black')
    draw = ImageDraw.Draw(image)
    for i, bit in enumerate(bits):
        x0 = (i % 20) * width // 20
        x1 = (i % 20 + 1) * width // 20 - 1
        y0 = (i // 20) * height // 8
        y1 = (i // 20 + 1) * height // 8 - 1
        draw.rectangle((x0, y0, x1, y1), fill='white' if bit == '1' else 'black')
    image.save(path)

def build_common(root, output, base):
    manifest = read_json(root / 'data/roster_manifest.json')
    from prepare_video_roster_manifest import discover, POSTER_FOLDERS
    posters = list(manifest.get('posters', []))
    known = {(r.get('category'), r.get('slot')) for r in posters if isinstance(r, dict)}
    for folder, category in POSTER_FOLDERS:
        for slot in discover(root / 'images/posters' / folder):
            if (category, slot) not in known:
                posters.append({'category': category, 'slot': slot, 'enabled': True})
    manifest['posters'] = posters
    records = []
    skipped = []
    ignored_portrait_urls = []
    keys = set()
    for field, kind in [('members', 'member'), ('posters', 'poster')]:
        for row in manifest.get(field, []):
            if not isinstance(row, dict) or not row.get('enabled', True):
                continue
            if kind == 'member' and not row.get('showPortrait', True):
                continue
            category, slot = row.get('category'), row.get('slot')
            if not isinstance(category, str) or not category or '|' in category or type(slot) is not int or slot < 0:
                raise ValueError('Invalid semantic image key')
            key = f'{kind}|{category}|{slot}'
            if key in keys:
                raise ValueError('Duplicate key: ' + key)
            keys.add(key)
            path = source_image(root, row, kind, base)
            if kind == 'member' and row.get('portraitUrl'):
                expected = '' if path is None else base + '/' + quote(path.relative_to(root).as_posix(), safe='/')
                if unquote(row['portraitUrl']) != unquote(expected):
                    ignored_portrait_urls.append({'key': key, 'configuredUrl': row['portraitUrl'], 'resolvedUrl': expected})
            if path is None:
                skipped.append(key)
                continue  # Missing keys use the Wizard's local image.
            records.append((key, path))
    if len(records) > 128:
        raise ValueError('共通画像は128枠までです')
    output.mkdir(parents=True, exist_ok=True)
    if not records:
        return None, skipped
    with tempfile.TemporaryDirectory(prefix='ebk-common-') as tmp:
        frames = []
        legacy_lines = []
        generation_lines = []
        hashes = []
        for i, (key, path) in enumerate(records):
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image)
                width, height = image.size
                frame = Path(tmp) / f'{i:04}.png'
                image.convert('RGB').resize((1280, 720), Image.Resampling.LANCZOS).save(frame)
            frames.append(frame)
            address = base + '/' + quote(path.relative_to(root).as_posix(), safe='/')
            legacy_frame = i * 3 + 1
            generation_frame = (i + 1) * 3 + 1
            legacy_lines.append(f'{legacy_frame}|{key}|{address}|aspect={width/height:.8f}|width={width}|height={height}|fit=stretch|sample={legacy_frame/30:.8f}|bad=0')
            generation_lines.append(f'{generation_frame}|{key}|{address}|aspect={width/height:.8f}|width={width}|height={height}|fit=stretch|sample={generation_frame/30:.8f}|bad=0')
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        generation_payload = {
            'format': 'ebk-roster-v1',
            'fps': 30,
            'framesPerEntry': 3,
            'sampleFrame': 1,
            'generationMarker': 'eb4b26c1-v1',
            'records': [{'key': records[i][0], 'sha256': hashes[i]} for i in range(len(records))]
        }
        generation = hashlib.sha256(json.dumps(
            generation_payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')
        ).encode('utf-8')).hexdigest()[:32]
        video_name = 'roster_' + generation + '.mp4'
        frame_map_name = 'frame_map_' + generation + '.txt'
        marker = Path(tmp) / 'generation.png'
        generation_marker(marker, generation, 1280, 720)
        # New immutable URL: 3 marker frames first, then the ordinary 3-frame entries.
        slides.encode([marker] + frames, output / video_name, 1280, 720)
        video_sha256 = hashlib.sha256((output / video_name).read_bytes()).hexdigest()
        # Fixed compatibility URL deliberately keeps the old frame layout without the
        # marker. Existing worlds using roster.mp4 + frame_map.txt therefore do not shift.
        slides.encode(frames, output / 'roster.mp4', 1280, 720)
    result = copy.deepcopy(manifest)
    for row in result.get('members', []):
        if not isinstance(row, dict) or type(row.get('slot')) is not int or not row.get('category'):
            continue
        path = source_image(root, row, 'member', base)
        row['portraitUrl'] = '' if path is None else base + '/' + quote(path.relative_to(root).as_posix(), safe='/')
    result['videoRoster'] = {
        'enabled': True, 'status': 'ready', 'generation': generation, 'format': 'ebk-roster-v1',
        'fps': 30, 'framesPerEntry': 3, 'sampleFrame': 1,
        'generationMarkerFrame': 1, 'frameCount': (len(records) + 1) * 3,
        'videoUrl': base + '/common/' + video_name,
        'frameMapUrl': base + '/common/' + frame_map_name,
        'sha256': video_sha256
    }
    write_json(output / 'manifest.json', result)
    generation_map_text = '\n'.join(generation_lines) + '\n'
    legacy_map_text = '\n'.join(legacy_lines) + '\n'
    (output / frame_map_name).write_text(generation_map_text, encoding='utf-8')
    (output / 'frame_map.txt').write_text(legacy_map_text, encoding='utf-8')
    write_json(output / 'build_report.json', {
        'captured': len(records), 'fallbackKeys': skipped, 'sourceHashes': hashes,
        'ignoredPortraitUrls': ignored_portrait_urls, 'generation': generation,
        'videoSha256': video_sha256
    })
    return {
        'id': 'common', 'manifestPath': 'common/manifest.json',
        'videoPath': 'common/' + video_name, 'format': 'ebk-roster-v1',
        'generation': generation
    }, skipped


def build(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Media root must be an existing regular directory')
    root = root.resolve()
    slides.checked_tree(root)
    config = read_json(root / 'data/room_media_slides.json')
    base = config['pagesBaseUrl'].rstrip('/')
    url = urlsplit(base)
    if url.scheme != 'https' or not url.hostname or url.username or url.query or url.fragment:
        raise ValueError('公開済みのHTTPSルートURLが必要です')
    # Stage all groups before updating even one published group.
    with tempfile.TemporaryDirectory(prefix='ebk-media-root-') as tmp:
        stage = Path(tmp)
        for directory in ['data', 'images', 'media', 'themes']:
            if (root / directory).is_dir():
                shutil.copytree(root / directory, stage / directory)
        (stage / 'themes').mkdir(exist_ok=True)
        (stage / 'media/room-slides').mkdir(parents=True, exist_ok=True)
        generated = stage / 'generated'
        generated.mkdir()
        modules = []
        if (stage / 'data/roster_manifest.json').is_file():
            common, _ = build_common(stage, generated / 'common', base)
            if common:
                modules.append(common)
        card_manifest = stage / 'data/clubcard_manifest.json'
        if card_manifest.is_file() and read_json(card_manifest).get('cards'):
            cards.build(stage, base)
            built_cards = read_json(stage / 'docs/ebk-clubcards/manifest.json')
            card_generation = str(built_cards.get('videoRoster', {}).get('generation', ''))
            card_format = str(built_cards.get('videoRoster', {}).get('format', ''))
            if card_format not in ('ebk-clubcards-v2', 'ebk-clubcards-v1'):
                raise ValueError('ClubCard生成形式を確認できません: ' + card_format)
            modules.append({'id': 'clubcards', 'manifestPath': 'ebk-clubcards/manifest.json',
                            'videoPath': 'ebk-clubcards/cards.mp4', 'format': card_format,
                            'generation': card_generation})
        slides.build(stage, stage / 'data/room_media_slides.json')
        room_manifest = read_json(stage / 'docs/ebk-room-media/manifest.json')
        modules.append({'id': 'roomMedia', 'manifestPath': 'ebk-room-media/manifest.json',
                        'format': 'ebk-room-media-v1', 'generation': str(room_manifest.get('generation', ''))})
        themes.build(stage / 'themes')
        theme_catalog = read_json(stage / 'themes/theme_catalog.json')
        modules.append({'id': 'themes', 'manifestPath': 'themes/theme_catalog.json',
                        'format': 'ebk-theme-catalog-v1', 'generation': str(theme_catalog.get('generation', ''))})
        if (stage / 'docs').exists():
            for group in (stage / 'docs').iterdir():
                if group.is_dir():
                    shutil.copytree(group, generated / group.name)
        write_json(generated / 'ebk_media_root.json', {'schemaVersion': 1, 'format': 'ebk-media-root-v1', 'modules': modules})
        # Atomicity at the remote end is provided by the single generated commit.
        for directory in ['common', 'ebk-clubcards', 'ebk-room-media']:
            src = generated / directory
            if not src.exists():
                continue
            target = root / directory
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
        (root / 'themes').mkdir(exist_ok=True)
        shutil.copyfile(stage / 'themes/theme_catalog.json', root / 'themes/theme_catalog.json')
        shutil.copyfile(generated / 'ebk_media_root.json', root / 'ebk_media_root.json')
    print('Built isolated media root:', root.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    build(args.root)
