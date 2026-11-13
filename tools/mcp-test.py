#!/usr/bin/env python3
"""biomedical_mcp.py 的离线自检（不联网）。

跑法：python tools/mcp-test.py   （用 DSH 自带的 python 3.12 或任意 >=3.9）

覆盖：工具清单、协议版本协商、并发（慢调用不堵快调用）、notifications/cancelled、
单次调用总时限、NCBI tool/email/api_key 参数、PubMed 摘要 XML 解析、紧凑 JSON 输出。
"""
import importlib.util
import io
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.join(HERE, "..", "mcp", "biomedical_mcp.py")

os.environ["NCBI_EMAIL"] = "someone@example.org"
os.environ.pop("NCBI_API_KEY", None)
spec = importlib.util.spec_from_file_location("biomedical_mcp", MCP)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

passed, failed = [], []


def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(("ok   " if cond else "FAIL ") + name + (" — " + detail if detail else ""))


# ── 工具清单与协议
specs = m.tool_specs()
check("工具清单 51 个", len(specs) == 51, str(len(specs)))
check("工具名不重复", len({s["name"] for s in specs}) == len(specs))
check("pubmed_search_articles 有 include_abstract 参数",
      "include_abstract" in next(s for s in specs if s["name"] == "pubmed_search_articles")["inputSchema"]["properties"])
init = m.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
check("协议版本按客户端请求协商", init["result"]["protocolVersion"] == "2025-03-26")
init2 = m.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})
check("未知协议版本回落到最新", init2["result"]["protocolVersion"] == m.SUPPORTED_PROTOCOLS[0])

# ── 领域过滤
check("每个工具都属于某个领域", all(m.domain_of(t["name"]) for t in specs),
      ",".join(t["name"] for t in specs if not m.domain_of(t["name"])))
check("--domains 解析", m.parse_domains(["x.py", "--domains", "structure,chemistry"], {}) == {"structure", "chemistry"})
check("BIO_MCP_DOMAINS 环境变量", m.parse_domains([], {"BIO_MCP_DOMAINS": "literature"}) == {"literature"})
check("all / 未给出 = 全部启用", m.parse_domains(["--domains", "all"], {}) is None and m.parse_domains([], {}) is None)
check("未知领域被忽略", m.parse_domains(["--domains", "nope,genome"], {}) == {"genome"})
saved = m.ACTIVE_DOMAINS
m.ACTIVE_DOMAINS = {"structure", "chemistry"}
listed = m.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/list"})["result"]["tools"]
check("tools/list 只返回启用领域的工具", listed and all(m.domain_of(t["name"]) in m.ACTIVE_DOMAINS for t in listed), str(len(listed)))
blocked = m.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "pubmed_search_articles", "arguments": {"query": "x"}}})
check("调用未启用领域的工具返回可读错误", blocked["result"]["isError"] and "没有启用" in blocked["result"]["content"][0]["text"])
m.ACTIVE_DOMAINS = saved

# ── NCBI 参数
u = m._ncbi_params("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=x")
check("NCBI 请求带 tool 与 email", "tool=dsh-biomedical-mcp" in u and "email=someone%40example.org" in u, u)
check("非 NCBI 请求不加参数", m._ncbi_params("https://rest.ensembl.org/x?y=1") == "https://rest.ensembl.org/x?y=1")
check("错误信息隐藏 api_key", "SECRET" not in m._redact("https://eutils.ncbi.nlm.nih.gov/a?api_key=SECRET&db=x"))
check("无 key 时 NCBI 限速 3 次/秒", m.HOST_RATE[m.NCBI_HOST] == 3.0)

# ── 摘要解析
xml = """<?xml version="1.0"?><!DOCTYPE PubmedArticleSet>
<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article><Abstract>
<AbstractText Label="BACKGROUND">Bg <i>text</i>.</AbstractText><AbstractText Label="RESULTS">Res.</AbstractText>
</Abstract></Article></MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>456</PMID><Article></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
orig_http = m._http
m._http = lambda url, **kw: xml
ab = m._pubmed_abstracts(["123", "456"])
m._http = orig_http
check("摘要解析带 Label 与内嵌标签", ab.get("123") == "BACKGROUND: Bg text. RESULTS: Res.", repr(ab.get("123")))
check("无摘要的文献不出现", "456" not in ab)


# ── 并发 / 取消 / 时限：用假工具驱动真实 main() 循环
def slow(p):
    m._sleep(float(p.get("s", 2)))
    return {"slept": p.get("s", 2)}


def fast(p):
    return {"fast": True, "nested": {"a": [1, 2]}}


m.HANDLERS["t_slow"] = slow
m.HANDLERS["t_fast"] = fast


def run_session(lines, budget=None, settle=0.0):
    if budget is not None:
        m.CALL_BUDGET = budget
    r, w = os.pipe()
    out = io.StringIO()
    got = []
    lock = threading.Lock()

    class Out:
        def write(self, s):
            with lock:
                got.append((time.monotonic(), s))

        def flush(self):
            pass

    old_in, old_out = sys.stdin, sys.stdout
    sys.stdin = os.fdopen(r, "r")
    sys.stdout = Out()
    t = threading.Thread(target=m.main)
    t.start()
    with os.fdopen(w, "w") as wf:
        for item in lines:
            if isinstance(item, (int, float)):
                time.sleep(item)
                continue
            wf.write(json.dumps(item) + "\n")
            wf.flush()
        time.sleep(settle)
    t.join(10)
    sys.stdin, sys.stdout = old_in, old_out
    msgs = []
    for ts, s in got:
        for ln in s.splitlines():
            if ln.strip():
                msgs.append((ts, json.loads(ln)))
    return msgs


def call(rid, name, args=None):
    return {"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}


t0 = time.monotonic()
msgs = run_session([call(1, "t_slow", {"s": 1.5}), call(2, "t_fast")], budget=100, settle=2.0)
order = [msg["id"] for _, msg in msgs]
check("慢调用不堵快调用（快的先回）", order[:2] == [2, 1], str(order))
fast_text = next(msg for _, msg in msgs if msg["id"] == 2)["result"]["content"][0]["text"]
check("返回紧凑 JSON（无缩进换行）", "\n" not in fast_text and ": " not in fast_text, fast_text)

msgs = run_session([call(7, "t_slow", {"s": 3}), 0.2,
                    {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 7}}],
                   budget=100, settle=1.0)
check("取消后不再回响应", all(msg.get("id") != 7 for _, msg in msgs), str(msgs))

start = time.monotonic()
msgs = run_session([call(9, "t_slow", {"s": 5})], budget=1.0, settle=0.5)
elapsed = time.monotonic() - start
resp = next((msg for _, msg in msgs if msg.get("id") == 9), None)
check("超出总时限立即报错而不是干等",
      resp is not None and resp["result"]["isError"] and "时限" in resp["result"]["content"][0]["text"] and elapsed < 3,
      "%.1fs %s" % (elapsed, resp and resp["result"]["content"][0]["text"][:60]))

print("\n结果：%d 通过，%d 失败" % (len(passed), len(failed)))
sys.exit(1 if failed else 0)
