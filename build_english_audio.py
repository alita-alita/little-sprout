"""Build bundled English audio with macOS Samantha; never needs a cloud service."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import wave

ROOT = Path(__file__).resolve().parent

def valid(path):
    try:
        with wave.open(str(path)) as audio:
            return audio.getnframes() > 2000
    except (OSError, wave.Error):
        return False

def build(text):
    name = hashlib.sha256(('Samantha-160-v1:' + text).encode()).hexdigest()[:24] + '.wav'
    relative = Path('assets/audio/en') / name
    path = ROOT / relative
    if not valid(path):
        subprocess.run(['say', '-v', 'Samantha', '-r', '160', '-o', str(path),
                        '--file-format=WAVE', '--data-format=LEI16@22050', text], check=True, capture_output=True)
    if not valid(path):
        raise RuntimeError('Speech generation produced empty audio: ' + text)
    return text, relative.as_posix()

if __name__ == '__main__':
    texts = {'Apple.', 'The banana is yellow.', 'Bear sees an apple. Bear takes it home.'}
    def visit(value):
        if isinstance(value, dict):
            if value.get('lang') == 'en-US' and value.get('speech'):
                texts.add(value['speech'])
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(json.loads((ROOT / 'curriculum.json').read_text()))
    (ROOT / 'assets/audio/en').mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        mapping = dict(pool.map(build, sorted(texts)))
    (ROOT / 'english-audio.js').write_text('globalThis.SproutEnglishAudio=' + json.dumps(mapping, ensure_ascii=False) + ';\n')
    print(f'Validated {len(mapping)} English audio clips.')
