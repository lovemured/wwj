#!/usr/bin/env node
/**
 * 通用 MCP SSE 调试器。
 *
 * 用法示例：
 *   MCP_AUTH='Token token=xxx, device=pc_web, version_code=9.9.9' \
 *     node tools/mcp/mcp_sse_cli.mjs --list
 *   MCP_AUTH='Bearer duli_xxx' \
 *     node tools/mcp/mcp_sse_cli.mjs --tool list_customers \
 *       --args '{"corp_id":"...","tab_type":"my","page":1,"per_page":10}'
 *
 * MCP_AUTH 直接作为 Authorization 请求头使用；也可使用 LXCRM_TOKEN
 * 自动生成当前励销云业务 Token 请求头。不要把 Token 写入命令历史或文件。
 */

const HOST = (process.env.MCP_HOST || 'https://mcp-test.weiwenjia.com').replace(/\/$/, '');
const BASE = process.env.MCP_BASE || '/mcp-servers/lxcrm-test';
const AUTH = process.env.MCP_AUTH || (process.env.LXCRM_TOKEN
  ? `Token token=${process.env.LXCRM_TOKEN}, device=pc_web, version_code=9.9.9`
  : '');

function usage() {
  console.log(`用法:
  node tools/mcp/mcp_sse_cli.mjs --list
  node tools/mcp/mcp_sse_cli.mjs --tool <工具名> [--args '<JSON>']

环境变量:
  MCP_HOST       MCP 域名，默认 https://mcp-test.weiwenjia.com
  MCP_BASE       MCP 路径，默认 /mcp-servers/lxcrm-test
  MCP_AUTH       完整 Authorization 值，例如 Bearer duli_xxx
  LXCRM_TOKEN    旧版励销云业务 Token（未设置 MCP_AUTH 时使用）
`);
}

function parseArgs(argv) {
  const out = { list: false, tool: '', args: {}, timeout: 15000 };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') out.help = true;
    else if (arg === '--list') out.list = true;
    else if (arg === '--tool') out.tool = argv[++i] || '';
    else if (arg === '--args') out.args = JSON.parse(argv[++i] || '{}');
    else if (arg === '--timeout') out.timeout = Number(argv[++i] || 15000);
    else throw new Error(`未知参数: ${arg}`);
  }
  return out;
}

function authHeaders(accept) {
  const headers = { Accept: accept };
  if (AUTH) headers.Authorization = AUTH;
  return headers;
}

async function withTimeout(promise, ms) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`超时（${ms}ms）`)), ms);
  });
  try { return await Promise.race([promise, timeout]); }
  finally { clearTimeout(timer); }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help || (!options.list && !options.tool)) { usage(); return; }

  const sse = await withTimeout(fetch(`${HOST}${BASE}/sse`, {
    headers: authHeaders('text/event-stream'),
  }), options.timeout);
  console.log(`SSE status: ${sse.status} ${sse.headers.get('content-type') || ''}`);
  if (!sse.ok || !sse.body) throw new Error(`SSE 连接失败: HTTP ${sse.status}`);

  let endpoint;
  const reader = sse.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  const readSse = (async () => {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let split;
      while ((split = buffer.indexOf('\n\n')) !== -1) {
        const event = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        let name = 'message';
        let data = '';
        for (const line of event.split(/\r?\n/)) {
          if (line.startsWith('event:')) name = line.slice(6).trim();
          if (line.startsWith('data:')) data += line.slice(5).trim();
        }
        if (name === 'endpoint') endpoint = data;
      }
    }
  })().catch(() => {});

  for (let i = 0; i < 100 && !endpoint; i += 1) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!endpoint) throw new Error('未收到 SSE endpoint 事件');

  const post = async (payload) => {
    const url = endpoint.startsWith('http') ? endpoint : HOST + endpoint;
    const response = await withTimeout(fetch(url, {
      method: 'POST',
      headers: { ...authHeaders('application/json'), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }), options.timeout);
    const body = await response.text();
    let parsed = body;
    try { parsed = JSON.parse(body); } catch (_) { /* 允许空响应或文本响应 */ }
    console.log(`POST ${payload.method} -> HTTP ${response.status}`);
    if (typeof parsed === 'string' ? parsed : Object.keys(parsed).length) {
      console.log(JSON.stringify(parsed, null, 2));
    }
    if (!response.ok) throw new Error(`MCP 请求失败: HTTP ${response.status}`);
    return parsed;
  };

  await post({
    jsonrpc: '2.0', id: 1, method: 'initialize',
    params: {
      protocolVersion: '2024-11-05', capabilities: {},
      clientInfo: { name: 'mcp-sse-cli', version: '1.0.0' },
    },
  });
  await post({ jsonrpc: '2.0', method: 'notifications/initialized', params: {} });

  if (options.list) {
    await post({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} });
  } else {
    await post({
      jsonrpc: '2.0', id: 2, method: 'tools/call',
      params: { name: options.tool, arguments: options.args },
    });
  }
  await reader.cancel();
  await readSse;
}

main().catch((error) => {
  console.error(`错误: ${error.message}`);
  process.exitCode = 1;
});
