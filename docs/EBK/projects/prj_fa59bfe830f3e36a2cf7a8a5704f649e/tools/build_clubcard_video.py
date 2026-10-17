#!/usr/bin/env python3
"""Build ClubCard's existing 3-frame VideoRoster, with a generation marker.

Source cards are never renumbered or rewritten. Only docs/ebk-clubcards is owned.
The marker binds the video pixels to the full metadata and source image hashes.
"""
import argparse
import copy
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
from build_room_media_slides import encode, checked_tree, MAX_SITE_BYTES

RARITIES = ['N', 'R', 'SR', 'SSR', 'UR', 'S']
WEIGHTS = [2000, 1000, 600, 400, 40, 3]
MAGIC = 'eb4b26c1'
MARKER = '.ebk-clubcards-generated'
SHEET_COLUMNS = 5
SHEET_ROWS = 2
CARDS_PER_SHEET = SHEET_COLUMNS * SHEET_ROWS
SHEET_WIDTH = 1280
SHEET_HEIGHT = 768


def validate(manifest):
    if manifest.get('schemaVersion') != 1 or type(manifest.get('revision')) is not int or manifest['revision'] < 1:
        raise ValueError('schemaVersion=1 / revision>=1 が必要です')
    rows = manifest.get('cards')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 127:
        raise ValueError('カードは1〜127枚で指定してください（世代確認1枠を別途使用）')
    layout = manifest.get('sheetLayout') or {
        'columns': SHEET_COLUMNS, 'rows': SHEET_ROWS, 'cardsPerSheet': CARDS_PER_SHEET,
        'assignmentMode': 'stableSlots'
    }
    if (not isinstance(layout, dict) or layout.get('columns') != SHEET_COLUMNS
            or layout.get('rows') != SHEET_ROWS or layout.get('cardsPerSheet') != CARDS_PER_SHEET):
        raise ValueError('ClubCardシートは固定2行×5列（10枚）です')
    assignment_mode = layout.get('assignmentMode', 'stableSlots')
    if assignment_mode not in ('stableSlots', 'numberSuffix'):
        raise ValueError('sheetLayout.assignmentModeはstableSlots/numberSuffixを指定してください')
    seen = set()
    card_ids = set()
    slots = set()
    for row in rows:
        n = row.get('cardNumber', '')
        serial = row.get('serial')
        if not isinstance(n, str) or not re.fullmatch(r'[0-9]{5}', n) or type(serial) is not int or serial != int(n) or serial in seen:
            raise ValueError('カード番号は重複のない5桁、serialと一致させてください')
        seen.add(serial)
        card_id = row.get('cardId', n)
        if (not isinstance(card_id, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', card_id)
                or card_id in card_ids):
            raise ValueError(n + ': cardIdは重複しない英数字/._- 1〜64文字で指定してください')
        card_ids.add(card_id)
        row['cardId'] = card_id
        if not isinstance(row.get('cardName'), str) or not row['cardName'].strip() or len(row['cardName']) > 120:
            raise ValueError(n + ': カード名は1〜120文字で指定してください')
        for key in ['enabled', 'exchangeEnabled', 'manualRarityWeightOverride']:
            if type(row.get(key)) is not bool:
                raise ValueError(n + ': ' + key + ' はboolが必要です')
        price = row.get('exchangePriceOverride')
        if type(price) is not int or not 0 <= price <= 100000000:
            raise ValueError(n + ': 交換価格が不正です')
        manual = row['manualRarityWeightOverride']
        if manual:
            weight = row.get('weightOverride')
            if row.get('rarityOverride') not in RARITIES or type(weight) is not int or not 0 <= weight <= 1000000:
                raise ValueError(n + ': 個別レアリティ/ウェイトが不正です')
        elif serial % 10 > 5:
            raise ValueError(n + ': 末尾6〜9には個別設定が必要です')
        if row.get('imagePath') != 'images/clubcards/cards/' + n + '.png':
            raise ValueError(n + ': 画像は images/clubcards/cards/番号.png を指定してください')
        slot = row.get('videoSlot', serial)
        if type(slot) is not int or not 0 <= slot <= 99999 or slot in slots:
            raise ValueError(n + ': VideoRoster枠が不正または重複しています')
        slots.add(slot)
        if assignment_mode == 'stableSlots':
            sheet_key = row.get('sheetKey')
            sheet_index = row.get('sheetIndex')
            if sheet_key is not None or sheet_index is not None:
                if (not isinstance(sheet_key, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', sheet_key)
                        or type(sheet_index) is not int or not 0 <= sheet_index < CARDS_PER_SHEET):
                    raise ValueError(n + ': sheetKey/sheetIndexが不正です')
    rules = manifest.get('rarityRules', {})
    if rules.get('mode') != 'cardNumberLastDigit' or rules.get('byLastDigit') != {str(i): r for i, r in enumerate(RARITIES)} or rules.get('defaultWeights') != dict(zip(RARITIES, WEIGHTS)):
        raise ValueError('既存の末尾レアリティ/標準ウェイト規則を維持してください')
    return sorted(rows, key=lambda row: row['serial'])


def resolve_sheet_placements(cards, manifest):
    layout = manifest.get('sheetLayout') or {}
    mode = layout.get('assignmentMode', 'stableSlots')
    occupied = set()
    resolved = []

    if mode == 'numberSuffix':
        for row in cards:
            number = row['cardNumber']
            key = number[:-1]
            index = int(number[-1])
            pair = (key, index)
            if pair in occupied:
                raise ValueError(number + ': 番号末尾Index方式の配置が重複しています')
            occupied.add(pair)
            resolved.append(pair)
        return mode, resolved

    if mode != 'stableSlots':
        raise ValueError('未対応のClubCardシート割当方式です: ' + str(mode))

    # Keep every explicitly saved slot first. New cards must never move an existing card.
    for row in cards:
        key = row.get('sheetKey')
        index = row.get('sheetIndex')
        if (isinstance(key, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', key)
                and type(index) is int and 0 <= index < CARDS_PER_SHEET):
            pair = (key, index)
            if pair in occupied:
                raise ValueError(row['cardNumber'] + ': sheetKey/sheetIndexが重複しています')
            occupied.add(pair)

    auto_sheet = 0
    for row in cards:
        key = row.get('sheetKey')
        index = row.get('sheetIndex')
        if (isinstance(key, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', key)
                and type(index) is int and 0 <= index < CARDS_PER_SHEET):
            resolved.append((key, index))
            continue

        # Backward-compatible generic migration: videoSlot is already a stable, purchaser-editable
        # value independent from the display list order.
        slot = row.get('videoSlot', row['serial'])
        preferred = ('slot' + str(slot // CARDS_PER_SHEET).zfill(4), slot % CARDS_PER_SHEET)
        if preferred not in occupied:
            occupied.add(preferred)
            resolved.append(preferred)
            continue

        # Only used when an explicit placement already occupies the legacy videoSlot cell.
        while True:
            candidate_key = 'auto' + str(auto_sheet).zfill(4)
            found = -1
            for candidate_index in range(CARDS_PER_SHEET):
                if (candidate_key, candidate_index) not in occupied:
                    found = candidate_index
                    break
            if found >= 0:
                pair = (candidate_key, found)
                occupied.add(pair)
                resolved.append(pair)
                break
            auto_sheet += 1
    return mode, resolved


def sheet_image(paths, width=SHEET_WIDTH, height=SHEET_HEIGHT):
    """Build one logical 2x5 sheet.

    Each source is intentionally stretched into its cell. At runtime EBK maps that
    cell UV back onto the normal card surface, restoring the card's display aspect
    while allowing ten cards to share one captured VideoRoster texture.
    """
    image = Image.new('RGB', (width, height), 'black')
    resampling = getattr(Image, 'Resampling', Image).LANCZOS
    for index, path in enumerate(paths):
        if index >= CARDS_PER_SHEET:
            break
        if path is None:
            continue
        column = index % SHEET_COLUMNS
        row = index // SHEET_COLUMNS
        x0 = column * width // SHEET_COLUMNS
        x1 = (column + 1) * width // SHEET_COLUMNS
        y0 = row * height // SHEET_ROWS
        y1 = (row + 1) * height // SHEET_ROWS
        with Image.open(path) as source:
            frame = ImageOps.exif_transpose(source).convert('RGBA').resize((x1 - x0, y1 - y0), resampling)
            cell = Image.new('RGB', (x1 - x0, y1 - y0), 'black')
            cell.paste(frame, (0, 0), frame)
            image.paste(cell, (x0, y0))
    return image


def marker_image(generation, width, height):
    bits = ''.join(format(int(c, 16), '04b') for c in MAGIC + generation)
    image = Image.new('RGB', (width, height), 'black')
    draw = ImageDraw.Draw(image)
    for i, bit in enumerate(bits):
        if bit == '1':
            x, y = i % 20, i // 20
            draw.rectangle((x * width // 20, y * height // 8, (x + 1) * width // 20 - 1, (y + 1) * height // 8 - 1), fill='white')
    return image


def build(root, base_url):
    from urllib.parse import urlsplit, quote
    base_url = base_url.rstrip('/')
    url = urlsplit(base_url)
    if url.scheme != 'https' or not url.hostname or url.query or url.fragment or url.username or any(c.isspace() for c in base_url):
        raise ValueError('公開先のHTTPS Pages URLが必要です')
    source = root / 'data/clubcard_manifest.json'
    if not source.exists():
        print('ClubCard source is not configured; skipped')
        return None
    manifest = json.loads(source.read_text(encoding='utf-8-sig'))
    if manifest.get('cards') == []:
        print('ClubCard has no cards yet; skipped')
        return None
    cards = copy.deepcopy(validate(manifest))
    checked_tree(root / 'images/clubcards')
    checked_tree(root / 'docs')
    images = []
    for row in cards:
        image = root / row['imagePath']
        if not image.is_file() or image.stat().st_size > 50 * 1024 * 1024:
            raise ValueError('カード画像がありません/50MiB超過: ' + str(image))
        with Image.open(image) as im:
            if max(im.size) > 2048 or min(im.size) < 1 or getattr(im, 'n_frames', 1) != 1:
                raise ValueError('静止画像を2048px以下にしてください: ' + row['cardNumber'])
        row['imageSha256'] = hashlib.sha256(image.read_bytes()).hexdigest()
        row['videoSlot'] = row.get('videoSlot', row['serial'])
        images.append(image)

    common_config = manifest.get('commonTextures', {})
    if common_config is None:
        common_config = {}
    if not isinstance(common_config, dict):
        raise ValueError('commonTexturesはobjectで指定してください')
    common_specs = [
        ('cardBack', 'cardBackPath', 'clubcard|back|0', 'images/clubcards/common/cardback.png'),
        ('package', 'packagePath', 'clubcard|package|0', 'images/clubcards/common/package.png')
    ]
    common_images = []
    common_hashes = []
    for name, config_key, capture_key, default_path in common_specs:
        relative = common_config.get(config_key, default_path)
        if not isinstance(relative, str) or not relative.startswith('images/clubcards/common/') or '..' in relative or '\\' in relative:
            raise ValueError(config_key + ' は images/clubcards/common/ 配下を指定してください')
        image = root / relative
        if not image.is_file():
            continue
        if image.stat().st_size > 50 * 1024 * 1024:
            raise ValueError(name + '画像が50MiBを超えています')
        with Image.open(image) as im:
            if max(im.size) > 2048 or min(im.size) < 1 or getattr(im, 'n_frames', 1) != 1:
                raise ValueError(name + 'は静止画像2048px以下にしてください')
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        common_images.append((name, capture_key, relative, image))
        common_hashes.append({'name': name, 'captureKey': capture_key, 'path': relative, 'sha256': digest})

    assignment_mode, placements = resolve_sheet_placements(cards, manifest)
    for i, row in enumerate(cards):
        row['sheetKey'] = placements[i][0]
        row['sheetIndex'] = placements[i][1]

    sheet_keys = sorted({row['sheetKey'] for row in cards})
    sheet_ordinals = {key: ordinal for ordinal, key in enumerate(sheet_keys)}
    sheet_count = len(sheet_keys)
    sheet_paths = [[None] * CARDS_PER_SHEET for _ in range(sheet_count)]
    image_by_serial = {cards[i]['serial']: images[i] for i in range(len(cards))}
    for row in cards:
        sheet_key = row['sheetKey']
        sheet = sheet_ordinals[sheet_key]
        cell = row['sheetIndex']
        row['sheet'] = sheet
        row['index'] = cell
        row['captureKey'] = 'clubcard|sheet|' + sheet_key
        row['sampleFrame'] = (sheet + 1) * 3 + 1
        row['sampleTimeSeconds'] = row['sampleFrame'] / 30
        if sheet_paths[sheet][cell] is not None:
            raise ValueError(row['cardNumber'] + ': シート配置が重複しています')
        sheet_paths[sheet][cell] = image_by_serial[row['serial']]

    normalized_layout = {
        'columns': SHEET_COLUMNS, 'rows': SHEET_ROWS, 'cardsPerSheet': CARDS_PER_SHEET,
        'assignmentMode': assignment_mode
    }
    generation = hashlib.sha256(json.dumps({
        'cards': cards,
        'commonTextures': common_hashes,
        'revision': manifest['revision'],
        'format': 'ebk-clubcards-v2',
        'sheetLayout': normalized_layout
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:32]
    result = copy.deepcopy(manifest)
    result['sheetLayout'] = normalized_layout
    result['cards'] = cards
    generated_common = {}
    for i, item in enumerate(common_images):
        name, capture_key, relative, image = item
        sample_frame = (sheet_count + i + 1) * 3 + 1
        generated_common[name] = {
            'captureKey': capture_key,
            'sourcePath': relative,
            'sourceSha256': common_hashes[i]['sha256'],
            'sampleFrame': sample_frame,
            'sampleTimeSeconds': sample_frame / 30
        }
    result['videoRoster'] = {'status': 'ready', 'generation': generation, 'format': 'ebk-clubcards-v2',
                            'videoUrl': base_url + '/ebk-clubcards/cards.mp4',
                            'frameMapUrl': base_url + '/ebk-clubcards/frame_map.txt',
                            'fps': 30, 'framesPerEntry': 3, 'sampleFrame': 1,
                            'headerKey': 'clubcard|generation|0', 'headerTimeSeconds': 1 / 30,
                            'width': SHEET_WIDTH, 'height': SHEET_HEIGHT,
                            'sheetColumns': SHEET_COLUMNS, 'sheetRows': SHEET_ROWS,
                            'cardsPerSheet': CARDS_PER_SHEET, 'sheetCount': sheet_count,
                            'sheetKeys': sheet_keys,
                            'frameCount': (sheet_count + len(common_images) + 1) * 3,
                            'commonTextures': generated_common}
    target = root / 'docs/ebk-clubcards'
    if target.exists() and not (target / MARKER).is_file():
        raise ValueError('未所有のdocs/ebk-clubcardsは上書きしません')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ebk-clubcards-') as temporary:
        stage = Path(temporary) / 'output'
        stage.mkdir()
        header = Path(temporary) / 'generation.png'
        marker_image(generation, SHEET_WIDTH, SHEET_HEIGHT).save(header)
        sheet_frames = []
        for sheet in range(sheet_count):
            target_sheet = Path(temporary) / ('sheet_' + sheet_keys[sheet] + '.png')
            sheet_image(sheet_paths[sheet]).save(target_sheet)
            sheet_frames.append(target_sheet)
        encode([header] + sheet_frames + [item[3] for item in common_images],
               stage / 'cards.mp4', SHEET_WIDTH, SHEET_HEIGHT)
        result['videoRoster']['sha256'] = hashlib.sha256((stage / 'cards.mp4').read_bytes()).hexdigest()
        (stage / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        lines = ['1|clubcard|generation|0|generation|1|1|0|0|frames=3|sampleFrame=1|sample=0.033333|bad=0']
        for sheet in range(sheet_count):
            frame = (sheet + 1) * 3 + 1
            time = frame / 30
            sheet_key = sheet_keys[sheet]
            lines.append(f"{frame}|clubcard|sheet|{sheet_key}|sheet://{sheet_key}|1|1|0|0|frames=3|sampleFrame=1|sample={time:.6f}|bad=0")
        for name, capture_key, relative, image in common_images:
            row = generated_common[name]
            parts = capture_key.split('|')
            address = base_url + '/' + quote(relative, safe='/')
            lines.append(f"{row['sampleFrame']}|{parts[0]}|{parts[1]}|{parts[2]}|{address}|1|1|0|0|frames=3|sampleFrame=1|sample={row['sampleTimeSeconds']:.6f}|bad=0")
        (stage / 'frame_map.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        (stage / MARKER).write_text('EBK ClubCard generated output v2 / 2x5 sheets\n')
        total = sum(p.stat().st_size for p in (root / 'docs').rglob('*') if p.is_file() and not p.is_relative_to(target))
        if total + sum(p.stat().st_size for p in stage.iterdir()) > MAX_SITE_BYTES:
            raise ValueError('Pages公開データが900MiBを超えます')
        # Build and verify before touching the previously published generation.
        swap = Path(tempfile.mkdtemp(prefix='.ebk-clubcards-', dir=target.parent))
        try:
            shutil.copytree(stage, swap / 'new')
            if target.exists(): target.rename(swap / 'previous')
            try: (swap / 'new').rename(target)
            except BaseException:
                if (swap / 'previous').exists(): (swap / 'previous').rename(target)
                raise
        finally: shutil.rmtree(swap)
    print(f'ClubCard: {len(cards)} cards / {sheet_count} sheets (2x5), generation {generation}')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--pages-base-url', default='')
    args = parser.parse_args()
    base = args.pages_base_url
    if not base:
        base = json.loads((args.root / 'data/room_media_slides.json').read_text(encoding='utf-8-sig'))['pagesBaseUrl']
    build(args.root.resolve(), base)
