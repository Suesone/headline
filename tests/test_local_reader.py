from functools import partial
from http.server import ThreadingHTTPServer
import json
import subprocess
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest
from scripts import local_reader as local


def test_model_and_cloud_redirection_rejected():
    for name in ['qwen3:cloud', 'https://cloud.example/model', '../model', 'qwen3-cloud']:
        with pytest.raises(ValueError):
            local.validate_model(name)
    assert local.validate_model('qwen3:4b') == 'qwen3:4b'
    runtime = local.LocalRuntime()
    runtime.call = lambda *a, **k: {'remote_host': 'https://example.org'}
    with pytest.raises(ValueError):
        runtime.verify_model()
    with pytest.raises(ValueError):
        local.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.org')


def test_runtime_owns_cloud_disabled_loopback_process(monkeypatch):
    captured = {}
    class Process:
        def __init__(self, args, **kwargs):
            captured.update(kwargs)
        def poll(self):
            return None
    monkeypatch.setattr(local.shutil, 'which', lambda _: '/official/ollama')
    monkeypatch.setattr(local.subprocess, 'Popen', Process)
    class Socket:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def connect_ex(self, address): return 1
    monkeypatch.setattr(local.socket, 'socket', Socket)
    runtime = local.LocalRuntime()
    monkeypatch.setattr(runtime, 'call', lambda *a, **k: {})
    runtime.start()
    assert captured['env']['OLLAMA_NO_CLOUD'] == '1'
    assert captured['env']['OLLAMA_HOST'] == '127.0.0.1:11435'
    assert captured['stdout'] == captured['stderr'] == subprocess.DEVNULL
    assert runtime.status()['ready']


def test_local_http_rejects_cross_site_and_remote_model_injection():
    class Runtime:
        calls = []
        def status(self): return {'ready': True, 'local_only': True}
        def translate(self, text): self.calls.append(text); return '测试译文'
    runtime = Runtime()
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(local.ReaderHandler, runtime=runtime))
    worker = threading.Thread(target=server.serve_forever, daemon=True);worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    def post(payload, origin=base):
        return urlopen(Request(base + '/api/local/translate', data=json.dumps(payload).encode(),
            headers={'Origin': origin, 'Content-Type': 'application/json', 'X-Headline-Local': '1'}))
    try:
        with pytest.raises(HTTPError) as error:
            post({'text': 'private'}, 'https://evil.example')
        assert error.value.code == 403 and runtime.calls == []
        with pytest.raises(HTTPError) as error:
            post({'text': 'private', 'model': 'remote:cloud'})
        assert error.value.code == 400 and runtime.calls == []
        with post({'text': 'private'}) as result:
            assert json.load(result)['text'] == '测试译文'
        assert runtime.calls == ['private']
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base + '/api/local/status', headers={'Host': 'evil.example'}))
        assert error.value.code == 403
    finally:
        server.shutdown();server.server_close();worker.join()


def test_translate_rejects_truncated_output_and_keeps_prompts_local(monkeypatch):
    runtime = local.LocalRuntime();runtime.ready = True
    class Process:
        def poll(self): return None
    runtime.process = Process()
    calls = []
    def call(path, payload=None, **kwargs):
        calls.append((path, payload))
        return {} if path == '/api/show' else {'message': {'content': '不完整'}, 'done_reason': 'length'}
    monkeypatch.setattr(runtime, 'call', call)
    with pytest.raises(RuntimeError, match='上限'):
        runtime.translate('Private English text')
    assert calls[1][0] == '/api/chat' and calls[1][1]['messages'][1]['content'] == 'Private English text'
    assert runtime.base == 'http://127.0.0.1:11435'


def test_gemini_requires_explicit_upload_free_tier_and_key(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    for allow, free, key in [(False, True, 'x'*30), (True, False, 'x'*30), (True, True, '')]:
        runtime = local.GeminiRuntime(allow_upload=allow, free_tier_confirmed=free, api_key=key)
        monkeypatch.setattr(local.sys.stdin, 'isatty', lambda: False)
        runtime.start()
        assert not runtime.status()['ready']
        with pytest.raises(RuntimeError):
            runtime.translate('Must never be sent')
    with pytest.raises(ValueError):
        local.GeminiRuntime(model='gemini-4-argon')


def test_gemini_request_key_is_header_only_and_never_in_status(monkeypatch):
    key = 'secret-for-test-not-real-key-12345'
    runtime = local.GeminiRuntime(allow_upload=True, free_tier_confirmed=True, api_key=key, max_requests=1)
    runtime.start()
    import io
    class Transport:
        requests = []
        def open(self, request, timeout):
            self.requests.append(request)
            return io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'译文'}]}}]}).encode())
    transport = Transport(); monkeypatch.setattr(local, 'DIRECT', transport)
    assert runtime.translate('Selected title only') == '译文'
    request = transport.requests[0]
    assert request.full_url == 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent'
    assert key not in request.full_url and request.get_header('X-goog-api-key') == key
    payload = json.loads(request.data)
    assert payload['contents'][0]['parts'][0]['text'] == 'Selected title only'
    assert not any(k in payload for k in ['tools','cachedContent','fileData'])
    assert key not in json.dumps(runtime.status())
    assert runtime.status()['local_only'] is False and runtime.status()['provider'] == 'gemini'
    with pytest.raises(RuntimeError, match='上限'):
        runtime.translate('Cannot exceed budget')
    assert len(transport.requests) == 1
    runtime.close(); assert runtime.api_key == ''


def test_gemini_quota_pause_never_retries_or_leaks_error_body(monkeypatch):
    import io
    runtime = local.GeminiRuntime(allow_upload=True, free_tier_confirmed=True, api_key='x'*30)
    runtime.start()
    class Transport:
        calls = 0
        def open(self, request, timeout):
            self.calls += 1
            raise HTTPError(request.full_url, 429, 'secret error', {}, io.BytesIO(b'sensitive-key-or-text'))
    transport = Transport();monkeypatch.setattr(local,'DIRECT',transport)
    with pytest.raises(RuntimeError, match='暂停') as error:
        runtime.translate('Private text')
    assert 'sensitive' not in str(error.value) and not runtime.status()['ready']
    with pytest.raises(RuntimeError):
        runtime.translate('Another text')
    assert transport.calls == 1


def test_gemini_incomplete_translation_is_rejected(monkeypatch):
    import io
    runtime = local.GeminiRuntime(allow_upload=True, free_tier_confirmed=True, api_key='x'*30)
    runtime.start()
    class Transport:
        def open(self, *args, **kwargs):
            return io.BytesIO(json.dumps({'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'partial'}]}}]}).encode())
    monkeypatch.setattr(local,'DIRECT',Transport())
    with pytest.raises(RuntimeError, match='未完整'):
        runtime.translate('Long text')
