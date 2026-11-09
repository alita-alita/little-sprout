"""Build an allowlisted HTTP-function ZIP. Does not open or deploy resources."""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ['server.py','storage.py','cloudbase_http.py','cloud_server.py','cloudbase_server.py','learning.py','practice.py',
         'scf_bootstrap','requirements-cloudbase.txt','index.html','app.js','sync-model.js','model.js',
         'content.js','icons.js','study-model.js','study-ui.js','speech.js','repeat.js',
         'english-audio.js','chinese-audio.js','curriculum.json','styles.css','v1.css','study.css',
         'course_editor.py','course_builder.py','course_images.py','editor_audio.py','course-editor.js',
         'course-editor.css','course-builder.js','image-generator.js','image-options.js','tabletop.js']


def build(destination, dependencies):
    dependencies = Path(dependencies).resolve()
    if not (dependencies/'psycopg').is_dir() or not (dependencies/'psycopg_binary').is_dir():
        raise ValueError('请先在与云函数匹配的 Linux/Python3.11 环境安装 requirements-cloudbase.txt 到 third_party')
    if list(dependencies.rglob('*.dylib')):
        raise ValueError('检测到 macOS 动态库；请使用 Linux 构建依赖')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT/name,name)
        for file in (ROOT/'assets').rglob('*'):
            if file.is_file() and not file.is_symlink() and file.suffix in ('.png','.mp3'):
                archive.write(file,file.relative_to(ROOT))
        for file in dependencies.rglob('*'):
            if file.is_file() and not file.is_symlink() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                archive.write(file,Path('third_party')/file.relative_to(dependencies))
    return destination


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--deps',default='third_party')
    parser.add_argument('--out',default='dist/little-sprout-cloudbase.zip')
    args=parser.parse_args()
    print(build(args.out,args.deps))
