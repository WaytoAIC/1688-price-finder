"""调 Claude:走本机已登录的 Claude Code CLI(`claude -p`),不需要单独的 API Key。

模型用环境变量覆盖:PRICE1688_MODEL(核对/搜索词,默认 claude-sonnet-4-6)、PRICE1688_FACTS_MODEL(读标题,默认同上)。
换模型前先跑 evals/run_eval.py,错放率变高就别换——新模型不一定在这个任务上更好。
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(HERE, '..', 'prompts')
MODEL = os.environ.get('PRICE1688_MODEL', 'claude-sonnet-4-6')
FACTS_MODEL = os.environ.get('PRICE1688_FACTS_MODEL', MODEL)

# 子进程只带这些环境变量。代理变量必须保留:需要代理才能连上官方接口的网络里,
# 丢了代理会直连,被拒成 403「地区不允许」。
KEEP_ENV = ('HOME', 'PATH', 'USER', 'SHELL', 'LANG', 'LC_ALL', 'TERM', 'TMPDIR',
            'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
            'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')


class LLMError(RuntimeError):
    pass


def _env():
    # 在 Claude Code 会话里再起 `claude -p` 时,宿主可能改写接口地址导致鉴权错配 → 给子进程一份干净环境
    if not (os.environ.get('CLAUDECODE') or os.environ.get('CLAUDE_CODE_CHILD_SESSION')):
        return None
    return {k: os.environ[k] for k in KEEP_ENV if k in os.environ}


def ask_json(prompt_name, payload, model=None, timeout=600):
    """提示词模板里的 {INPUT} 换成 payload 的 JSON,调一次 Claude,解析出一个 JSON 对象。失败重试一次。
    API 报错(余额不足/未登录/地区限制)直接抛错——报错文本里的 {"error":…} 绝不能当成结果。"""
    with open(os.path.join(PROMPTS, prompt_name)) as fp:
        task = fp.read().replace('{INPUT}', json.dumps(payload, ensure_ascii=False, indent=1))
    cmd = ['claude', '-p', task, '--output-format', 'json', '--tools', '', '--strict-mcp-config',
           '--no-session-persistence', '--model', model or MODEL]
    last = ''
    for _ in (1, 2):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=_env(),
                               stdin=subprocess.DEVNULL, cwd=os.path.expanduser('~'))
        except FileNotFoundError:
            raise LLMError('找不到 claude 命令:先安装 Claude Code 并登录')
        except subprocess.TimeoutExpired:
            last = f'超时 {timeout}s'
            continue
        try:
            out = json.loads(r.stdout)
        except ValueError:
            last = (r.stdout or r.stderr)[:200]
            continue
        text = out.get('result') or ''
        if out.get('is_error') or text.startswith('API Error'):
            raise LLMError(text[:200])
        m = re.search(r'\{.*\}', text, re.S)
        if not m:
            last = text[:200]
            continue
        res = json.loads(m.group(0))
        if isinstance(res, dict) and set(res) <= {'error', 'type', 'message'}:
            raise LLMError(text[:200])
        return res
    raise LLMError(f'Claude 调用失败:{last}')


def align(res, keys):
    """模型偶尔改写 key(去空格/换成序号):按 key 取不到且条数一样时按顺序对齐。"""
    if isinstance(res, dict) and not any(k in res for k in keys) and len(res) == len(keys):
        return dict(zip(keys, res.values()))
    return res if isinstance(res, dict) else {}
