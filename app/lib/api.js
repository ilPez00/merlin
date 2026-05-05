import { config } from './config.js';

class ApiClient {
  async chat(messages, options = {}) {
    const { tools, maxTokens = 2048, temperature = 0.7 } = options;

    const endpoint = config.apiEndpoint();
    const model = config.apiModel();
    if (!endpoint) throw new Error('No API endpoint configured');
    if (!config.get('apiKey')) throw new Error('No API key configured');

    const url = `${endpoint}/chat/completions`;
    const body = {
      model: model || 'deepseek-chat',
      messages,
      max_tokens: maxTokens,
      temperature,
      stream: false,
    };
    if (tools) body.tools = tools;

    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.get('apiKey')}`,
      },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const err = await resp.text().catch(() => '');
      throw new Error(`API ${resp.status}: ${err}`);
    }

    const data = await resp.json();
    return data.choices?.[0]?.message || { content: '', role: 'assistant' };
  }

  async chatWithVision(messages, frameB64 = null, options = {}) {
    const msgs = messages.map(m => ({ ...m }));

    if (frameB64) {
      const last = msgs[msgs.length - 1];
      const text = typeof last.content === 'string' ? last.content : '';
      last.content = [
        { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${frameB64}`, detail: 'low' } },
        { type: 'text', text },
      ];
    }

    return this.chat(msgs, options);
  }
}

export const api = new ApiClient();
