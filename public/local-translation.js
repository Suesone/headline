/* No remote translation endpoints, keys, telemetry, or persistent text cache. */
(function (root) {
  'use strict';
  const isLoopback = hostname => ['localhost', '127.0.0.1', '[::1]', '::1'].includes(hostname);
  function splitText(text, size = 1800) {
    if (typeof text !== 'string' || text.length > 60000) throw new Error('每次最多翻译 60,000 个字符。');
    if (!Number.isInteger(size) || size < 100) throw new Error('Invalid chunk size');
    const chunks = []; let rest = text.trim();
    while (rest.length > size) {
      let end = rest.lastIndexOf('\n', size);
      if (end < size / 2) end = rest.lastIndexOf('. ', size);
      if (end < size / 2) end = rest.lastIndexOf(' ', size);
      if (end < size / 2) end = size;
      if (end > 0 && /[\uD800-\uDBFF]/.test(rest[end - 1])) end--;
      chunks.push(rest.slice(0, end).trim()); rest = rest.slice(end).trim();
    }
    if (rest) chunks.push(rest);
    return chunks;
  }
  class LocalTranslator {
    constructor(environment = root) {
      this.environment = environment; this.engine = 'browser'; this.browser = null; this.cache = new Map(); this.pending = new Map();
    }
    setEngine(engine) {
      if (!['browser', 'ollama'].includes(engine)) throw new Error('只支持本地翻译引擎');
      this.engine = engine;
    }
    async prepare() {
      if (this.engine === 'browser') {
        if (!this.environment.Translator) throw new Error('此浏览器没有内置本地翻译。请使用支持 Translator API 的桌面 Chrome，或按说明启动本地阅读器与 Ollama。');
        if (this.browser) return;
        const options = {sourceLanguage: 'en', targetLanguage: 'zh'};
        const state = await this.environment.Translator.availability(options);
        if (state === 'unavailable') throw new Error('此设备暂不支持英文到中文的本地翻译。请使用本地阅读器。');
        // Only reached from an explicit user translation click; language packs may download.
        this.browser = await this.environment.Translator.create(options);
      } else {
        if (!isLoopback(this.environment.location.hostname)) throw new Error('Ollama 仅在本地阅读器使用。请在电脑上运行 python3 -m scripts.local_reader，再打开它显示的本机地址。');
        const response = await this.environment.fetch('/api/local/status', {cache: 'no-store', signal: AbortSignal.timeout(5000)});
        if (!response.ok) throw new Error('本地阅读器未运行，或 Ollama 尚未准备好。');
        const status = await response.json();
        if (!status.ready || status.local_only !== true) throw new Error(status.message || '本地模型尚未就绪。');
        this.model = status.model;
      }
    }
    async translate(text, {signal, progress = () => {}} = {}) {
      if (!text.trim()) return '';
      const engine = this.engine;
      const key = engine + ':' + (this.model || '') + ':' + text;
      if (this.cache.has(key)) return this.cache.get(key);
      // A second click never creates another inference for the same text.
      if (this.pending.has(key)) return this.pending.get(key);
      const work = (async () => {
        const chunks = splitText(text); const output = [];
        for (const [i, chunk] of chunks.entries()) {
          signal?.throwIfAborted(); progress(i, chunks.length);
          let translated;
          if (engine === 'browser') {
            if (!this.browser) throw new Error('请先启用本地翻译');
            translated = await this.browser.translate(chunk);
          } else {
            if (!isLoopback(this.environment.location.hostname) || !this.model) throw new Error('仅允许已验证的本地阅读器');
            const response = await this.environment.fetch('/api/local/translate', {method: 'POST',
              headers: {'Content-Type': 'application/json', 'X-Headline-Local': '1'},
              body: JSON.stringify({text: chunk}), signal});
            if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.message || '本地模型翻译失败，请查看本机运行状态。'); }
            translated = (await response.json()).text;
          }
          signal?.throwIfAborted();
          if (typeof translated !== 'string' || !translated.trim()) throw new Error('本地模型没有返回译文');
          output.push(translated.trim()); progress(i + 1, chunks.length);
        }
        const result = output.join('\n\n'); this.cache.set(key, result);
        if (this.cache.size > 300) this.cache.delete(this.cache.keys().next().value);
        return result;
      })();
      this.pending.set(key, work);
      try { return await work; } finally { this.pending.delete(key); }
    }
    clear() { this.cache.clear(); }
  }
  const api = {LocalTranslator, splitText, isLoopback};
  if (typeof module !== 'undefined') module.exports = api;
  root.HeadlineLocal = api;
})(globalThis);
