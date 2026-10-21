import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

import pytest

from scripts import frontend_editor as e


def test_settings_reject_css_injection_and_unexpected_fields(tmp_path):
    for changes in ({'accent':'red; background:url(https://example.org)'}, {'width':True},
                    {'titleSize':1000}, {'columns':1}, {'filename':'../../outside'},
                    {'titleColor':'#000000;'}):
        with pytest.raises(ValueError):
            e.validate({**e.DEFAULTS,**changes})
    (tmp_path/'public').mkdir(); (tmp_path/'config').mkdir()
    (tmp_path/'public/index.html').write_text('<h1 data-editor-text="pageHeading">旧标题</h1>')
    value = {**e.DEFAULTS,'titleSize':22,'accent':'#112233'}
    e.save_settings(tmp_path,value)
    assert json.loads((tmp_path/'config/appearance.json').read_text()) == value
    css = (tmp_path/'public/appearance.css').read_text()
    assert '--reader-title-size: 22px;' in css and '--accent: #112233;' in css
    text = {**value, 'pageHeading':'<script>alert("test")</script>', 'boardColumns':1}
    e.save_settings(tmp_path,text)
    page = (tmp_path/'public/index.html').read_text()
    assert '&lt;script&gt;' in page and '<script>' not in page
    assert 'pageHeading' not in (tmp_path/'public/appearance.css').read_text()
    for bad in ('', 'x'*161, 'hello\nworld'):
        with pytest.raises(ValueError):
            e.validate({**value, 'intro':bad})


def test_editor_requires_local_host_origin_and_token_and_keeps_preview_unsaved(tmp_path):
    (tmp_path/'public').mkdir(); (tmp_path/'config').mkdir()
    (tmp_path/'public/index.html').write_text('public page')
    (tmp_path/'private-secret.txt').write_text('must stay private')
    (tmp_path/'public/escape.txt').symlink_to(tmp_path/'private-secret.txt')
    e.save_settings(tmp_path,e.DEFAULTS)
    server = e.make_server(tmp_path,0)
    thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    base = 'http://' + server.authority
    client = build_opener(ProxyHandler({}))
    def get(path,headers=None):
        return client.open(Request(base+path,headers=headers or {}))
    def post(value,headers):
        return client.open(Request(base+'/_editor/save',data=json.dumps(value).encode(),headers=headers))
    try:
        state = json.load(get('/_editor/state'))
        value = {**state['settings'],'spacing':22}
        headers = {'Origin':base,'X-Editor-Token':state['token'],'Content-Type':'application/json'}
        for bad in ({**headers,'Origin':'https://attacker.example'}, {**headers,'X-Editor-Token':'wrong'},
                    {**headers,'Host':'attacker.example'}):
            with pytest.raises(HTTPError) as error:
                post(value,bad)
            assert error.value.code == 403
        with get('/_editor/state') as response:
            assert json.load(response)['settings'] == e.DEFAULTS
        client.open(Request(base+'/_editor/preview',data=json.dumps(value).encode(),headers=headers)).close()
        assert '--reader-spacing: 22px' in get('/_draft.css').read().decode()
        assert json.loads((tmp_path/'config/appearance.json').read_text()) == e.DEFAULTS
        post(value,headers).close()
        assert json.loads((tmp_path/'config/appearance.json').read_text()) == value
        for path in ('/private-secret.txt','/escape.txt','/_editor/../../private-secret.txt'):
            with pytest.raises(HTTPError):
                get(path)
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_public_page_has_no_editor_entry():
    html = (e.ROOT/'public/index.html').read_text()
    assert 'appearance.css' in html
    for private_ui in ('open-appearance','appearance-dialog','appearance.js','/_editor/'):
        assert private_ui not in html
    assert not (e.ROOT/'public/editor').exists()
