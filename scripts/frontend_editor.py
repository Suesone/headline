"""Private loopback appearance editor; only public/ is eligible for deployment."""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = dict(titleSize=18, mobileSize=17, weight=700, spacing=15, width=1336,
                columns=3, accent='#e8576d', background='#f5f6f8', titleColor='#111111')
RANGES = dict(titleSize=(14, 28), mobileSize=(14, 26), spacing=(8, 28), width=(960, 1600))
VARIABLES = dict(titleSize='--reader-title-size', mobileSize='--reader-mobile-size',
                 weight='--reader-weight', spacing='--reader-spacing', width='--reader-width',
                 columns='--reader-columns', accent='--accent', background='--bg',
                 titleColor='--reader-title-color')
RULES = '''
.page { max-width:var(--reader-width,1336px); }
.article,.board-list .article { padding-top:var(--reader-spacing,15px);padding-bottom:var(--reader-spacing,15px); }
.article-title,.featured .article-title { font-size:var(--reader-title-size,18px);font-weight:var(--reader-weight,700);color:var(--reader-title-color,#111111); }
@media(min-width:1101px) { .news-grid { grid-template-columns:repeat(var(--reader-columns,3),minmax(0,1fr)); } }
@media(max-width:720px) { .article-title,.featured .article-title { font-size:var(--reader-mobile-size,17px); } }
'''


def validate(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError('设置字段不完整或含未知字段')
    for key, item in value.items():
        if key in RANGES:
            if type(item) is not int or not RANGES[key][0] <= item <= RANGES[key][1]:
                raise ValueError('数值超出允许范围')
        elif key in ('weight', 'columns'):
            if type(item) is not int or item not in ((500,600,700,800) if key == 'weight' else (2,3,4)):
                raise ValueError('字号粗细或列数无效')
        elif not isinstance(item, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', item):
            raise ValueError('颜色格式无效')
    return dict(value)


def stylesheet(value):
    value = validate(value)
    declarations = '\n'.join(f'  {VARIABLES[key]}: {item}{"px" if key in RANGES else ""};' for key,item in value.items())
    return '/* Saved with the local Headline editor. */\n:root {\n' + declarations + '\n}\n' + RULES


def save_settings(root, value):
    value = validate(value)
    settings = root / 'config/appearance.json'
    css = root / 'public/appearance.css'
    # Fixed destinations only; no filenames or CSS supplied by the browser.
    for path, content in ((settings,json.dumps(value,ensure_ascii=False,indent=2)+'\n'),
                          (css,stylesheet(value))):
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(content,encoding='utf-8')
        temporary.replace(path)


class EditorHandler(SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server, directory=str(server.root / 'public'))

    def log_message(self, *_):
        pass

    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','SAMEORIGIN')
        super().end_headers()

    def valid_host(self):
        return self.headers.get('Host') == self.server.authority

    def reply(self, value, content_type='application/json; charset=utf-8', status=200):
        body = (json.dumps(value,ensure_ascii=False) if content_type.startswith('application/json') else value).encode()
        self.send_response(status); self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if not self.valid_host():
            return self.reply({'error':'无效本机地址'},status=403)
        path = self.path.split('?',1)[0]
        if path == '/_editor/state':
            return self.reply(dict(settings=self.server.saved, defaults=DEFAULTS, token=self.server.token))
        if path == '/_draft.css':
            return self.reply(stylesheet(self.server.draft),'text/css; charset=utf-8')
        if path in ('/_editor/', '/_editor/editor.js', '/_editor/editor.css'):
            filename = {'/_editor/':'index.html','/_editor/editor.js':'editor.js','/_editor/editor.css':'editor.css'}[path]
            content_type = {'index.html':'text/html','editor.js':'text/javascript','editor.css':'text/css'}[filename]
            return self.reply((self.server.root / 'tools/editor' / filename).read_text(),content_type+'; charset=utf-8')
        if path.startswith('/_'):
            return self.reply({'error':'不存在'},status=404)
        # SimpleHTTPRequestHandler safely normalizes URL traversal; additionally disallow
        # symlinks escaping public/, directory listings, and non-public project paths.
        destination = Path(self.translate_path(self.path)).resolve()
        public = (self.server.root / 'public').resolve()
        if not destination.is_relative_to(public) or (destination.is_dir() and not (destination/'index.html').is_file()):
            return self.reply({'error':'不存在'},status=404)
        return super().do_GET()

    def do_HEAD(self):
        # Do not inherit a static handler that bypasses the GET path checks.
        self.send_error(405)

    def do_POST(self):
        if (not self.valid_host() or self.headers.get('Origin') != 'http://' + self.server.authority
                or not secrets.compare_digest(self.headers.get('X-Editor-Token',''), self.server.token)):
            return self.reply({'error':'仅允许从本机编辑面板保存'},status=403)
        if self.path not in ('/_editor/preview','/_editor/save'):
            return self.reply({'error':'不存在'},status=404)
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 4096:
                raise ValueError('请求大小无效')
            value = validate(json.loads(self.rfile.read(length)))
            if self.path.endswith('/save'):
                save_settings(self.server.root,value)
                self.server.saved = dict(value)
            self.server.draft = dict(value)
            self.reply({'ok':True})
        except (ValueError, UnicodeError):
            self.reply({'error':'设置无效，未保存'},status=400)
        except OSError:
            self.reply({'error':'本地文件无法写入，请检查文件权限'},status=500)


def make_server(root=ROOT, port=8766):
    root = Path(root)
    saved = validate(json.loads((root/'config/appearance.json').read_text()))
    server = ThreadingHTTPServer(('127.0.0.1',port),EditorHandler)
    server.root, server.saved, server.draft = root, saved, dict(saved)
    server.token = secrets.token_hex(32)
    server.authority = f'127.0.0.1:{server.server_port}'
    return server


def main():
    parser = argparse.ArgumentParser(description='Headline 本机外观编辑器')
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--no-browser',action='store_true')
    args = parser.parse_args()
    try:
        server = make_server(port=args.port)
    except OSError:
        raise SystemExit('编辑器未启动：端口可能已占用。请关闭之前的编辑器再试。')
    url = f'http://{server.authority}/_editor/'
    print(f'本机外观编辑器：{url}\n保存只修改本地项目；线上发布需另行提交。关闭此窗口或按 Control+C 退出。',flush=True)
    if not args.no_browser:
        threading.Timer(.4,lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
