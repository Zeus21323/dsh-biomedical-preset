"""
文献综述辅助函数。加载本技能时，宿主会将以下函数自动载入 Python 内核：

 verify_dois, crossref_lookup, search_openalex, expand_citations,
 extract_dois, style_pass

模块顶层只包含定义（函数、导入和字面量常量），因此能够通过 sidecar AST
检查；所有涉及网络或宿主运行时的操作都位于函数体内。

本文件由 OpenAI4S 内置的 `skills/literature-review/kernel.py`
（origin=openai4s）移植到本仓库的垂直技能目录。网络访问统一经过
`host.web_fetch`，绝不使用 `urllib.request`：在单元格内用 urllib 发出的请求
既不受出站允许列表约束，也不受 SSRF 防护。仍保留 `urllib.parse`，但仅用于编码。
"""

import json
import re
import time
import urllib.parse

DOI_PATTERN = r"10\.\d{4,9}/[^\s\"'`\]\}—–&|]+"


def lr_sdk():
    """不受重新绑定影响的 SDK 句柄——参见 pdf-explore/kernel.py:pdf_sdk。"""
    import host

    return host


def litrev_contact() -> str | None:
    """用于礼貌访问池 API 请求头的用户联系邮箱；不可用或遭拒时返回 None。"""
    # get_user_email 以普通 str 返回地址；没有地址时会抛出
    # host.ContactEmailUnavailable（ContactEmailDeclined 是其子类）。
    # 此处有意使用宽泛的 `except Exception`，以同时覆盖宿主调用失败
    # （本辅助函数运行于分析内核，而宿主会直接拒绝该调用）的情形：
    # User-Agent 中礼貌访问池所需的 `mailto:` 后缀只是尽力而为，绝不应导致获取失败。
    try:
        r = lr_sdk().get_user_email()
    except Exception:
        return None
    return (r or None) if isinstance(r, str) else None


def litrev_get(url: str, timeout: float = 15) -> dict | None:
    """GET `url` 并解码 JSON。遇到 HTTP 429 时等待 2 秒重试一次；任何错误均返回 None。"""
    c = litrev_contact()
    ua = "ClaudeScience-literature-review/1.0" + (f" (mailto:{c})" if c else "")
    ua = ua.encode("ascii", "ignore").decode("ascii")
    for attempt in (0, 1):
        try:
            # 通过宿主发出请求，而非 urllib。在单元格内使用 urllib 发出的请求
            # 既不受出站允许列表约束，也不受 SSRF 防护，因此该技能的流量过去会
            # 绕过产品专门设置的这道边界。宿主调用支持 `user_agent`，所以迁移后
            # 仍能保留下方用于礼貌访问池的身份标识。
            response = lr_sdk().web_fetch(
                url, format="json", timeout=timeout, user_agent=ua
            )
            if response.get("error"):
                # 429 会以软错误字符串返回；因限流而放弃前，仍值得重试一次。
                if "429" in str(response["error"]) and attempt == 0:
                    time.sleep(2)
                    continue
                return None
            return json.loads(response.get("content") or "null")
        except Exception:
            return None
    return None


def quote_doi_path(doi: str) -> str:
    """对 DOI 路径进行 URL 编码；先解码各路径段，使已编码的 %28 不会被重复编码
    （调用方可以传入任一形式）。"""
    return "/".join(
        urllib.parse.quote(urllib.parse.unquote(seg), safe="") for seg in doi.split("/")
    )


def crossref_year(m: dict) -> int | None:
    """从 Crossref `message` 记录中安全提取出版年份。"""
    dp = (m.get("published") or {}).get("date-parts") or [[None]]
    return (dp[0] or [None])[0]


def short_authors(names: list[str]) -> str | None:
    """将作者列表压缩成笔记形式：最多保留前三个姓名，以分号分隔
    （姓名内部可以包含逗号）；若还有更多作者或任何条目缺少姓名，则追加
    'et al.'。记录完全不含作者姓名时返回 None。

    每个辅助函数的默认输出都携带作者信息，使据此创建的工作笔记能够让姓名
    始终与 DOI 和年份同行——如果根据一条不含作者的笔记填写 `(作者 年份)`，
    姓名就会来自参数化记忆，而记忆只会给出貌似合理、未必属于该论文的姓名。
    """
    kept = [n.strip() for n in names if n and n.strip()]
    if not kept:
        return None
    more = len(names) > 3 or len(kept) < len(names)
    return "; ".join(kept[:3]) + (" et al." if more else "")


def crossref_authors(m: dict) -> str | None:
    """从 Crossref `message` 记录提取适合笔记使用的作者姓氏。"""
    return short_authors(
        [a.get("family") or a.get("name") or "" for a in (m.get("author") or [])]
    )


def openalex_authors(w: dict) -> str | None:
    """从 OpenAlex 成果记录提取适合笔记使用的作者完整显示名。"""
    return short_authors(
        [
            ((a.get("author") or {}).get("display_name") or "")
            for a in (w.get("authorships") or [])
        ]
    )


def litrev_head(url: str, timeout: float = 10) -> int | None:
    """对 `url` 发出 HEAD 请求且不跟随重定向；返回源服务器自身的状态
    （因此 doi.org 对已注册 DOI 返回 302，对未注册 DOI 返回 404，而不是返回
    出版商的状态）。遇到 429 时等待 2 秒重试一次。仅当无法取得任何状态
    （连接失败/超时）时返回 None。"""
    c = litrev_contact()
    ua = (
        ("ClaudeScience-literature-review/1.0" + (f" (mailto:{c})" if c else ""))
        .encode("ascii", "ignore")
        .decode("ascii")
    )

    for attempt in (0, 1):
        try:
            # `host.web_fetch(method="HEAD")` 有意不跟随重定向，这正是此处的目的：
            # doi.org 自身返回 302 表示 DOI 已注册，而重定向后的出版商可能因付费墙
            # 对一个确实存在的 DOI 返回 403。
            probe = lr_sdk().web_fetch(
                url, method="HEAD", timeout=timeout, user_agent=ua
            )
            if probe.get("error"):
                return None
            status = int(probe.get("status") or 0)
            if status == 429 and attempt == 0:
                time.sleep(2)
                continue
            # 0 表示完全无法取得状态，因此报告为 None；这与该函数一直对失效连接
            # 返回的“未知”一致，并且与 404 明确区分。
            return status or None
        except Exception:
            return None
    return None


def verify_dois(dois: list[str]) -> dict[str, dict]:
    """逐个通过 Crossref 解析 DOI；对于 DataCite/mEDRA/arXiv DOI，则以
    doi.org HEAD 请求作为回退。返回 {doi: {ok, title?, authors?, year?, journal?,
    retracted?, registry?, error?}}，其中：
    ok=True——能够解析（Crossref 命中，或 doi.org 返回 2xx/3xx）；
    ok=False——不能解析（doi.org 返回 404；可能是伪造或拼写错误）；
    ok=None——无法核验（网络/瞬时错误/5xx）；不要将其标记为伪造。
    只有 Crossref 命中时，`retracted` 才是 True/False；注册机构不是 Crossref
    或查找结果未经核验时，该值为 None。"""
    out: dict[str, dict] = {}
    for d in dois:
        d = d.strip()
        # 没有任何注册机构会在 DOI 后缀中使用 `.`、`..` 或空路径段；预先拒绝这些
        # 情况，避免服务器/CDN 的点段规范化让伪造标识符看起来能够解析。先解码
        # 整个字符串再拆分，使编码后的 `..`（`%2E%2E`）以及含 `..` 的编码斜杠
        # （`a%2F..%2Fb`）都会显现为 `..` 路径段。
        segs = urllib.parse.unquote(d).split("/")
        if any(seg in ("", ".", "..") for seg in segs[1:]):
            out[d] = {"ok": False, "error": "dot-segment in DOI"}
            continue
        enc = quote_doi_path(d)
        j = litrev_get(f"https://api.crossref.org/works/{enc}")
        time.sleep(0.06)
        if j and "message" in j:
            m = j["message"]
            title = (m.get("title") or [""])[0]
            upd = [u.get("type", "") for u in (m.get("update-to") or [])]
            retracted = (
                any("retract" in t.lower() for t in upd)
                or str(m.get("subtype") or "").lower() == "retraction"
                or title.upper().startswith("RETRACTED")
            )
            out[d] = {
                "ok": True,
                "title": title,
                "authors": crossref_authors(m),
                "year": crossref_year(m),
                "journal": (m.get("container-title") or [""])[0],
                "retracted": retracted,
                "registry": "crossref",
            }
            continue
        # Crossref 未命中或发生瞬时错误——doi.org 是跨注册机构的权威解析器，
        # 因此由它的结果决定 ok。
        code = litrev_head(f"https://doi.org/{enc}")
        if code is not None and 200 <= code < 400:
            out[d] = {"ok": True, "registry": "non-crossref", "retracted": None}
        elif code == 404:
            out[d] = {"ok": False}
        else:
            out[d] = {"ok": None, "error": "unverified (network)", "retracted": None}
    return out


def crossref_lookup(ref_string: str) -> dict | None:
    """根据自由文本引文（作者/标题/年份）查找 DOI。以
    {doi, title, authors, year, score} 返回 Crossref 的最佳匹配，或返回 None。
    当你掌握引文详情却不知道 DOI 时使用——这是猜测 DOI 的替代方案。"""
    q = urllib.parse.quote(ref_string)
    j = litrev_get(f"https://api.crossref.org/works?query.bibliographic={q}&rows=1")
    items = (j or {}).get("message", {}).get("items", [])
    if not items:
        return None
    m = items[0]
    return {
        "doi": m.get("DOI"),
        "title": (m.get("title") or [""])[0],
        "authors": crossref_authors(m),
        "year": crossref_year(m),
        "score": m.get("score"),
    }


def search_openalex(query: str, n: int = 10, filters: str = "") -> list[dict]:
    """搜索 OpenAlex（开放学术索引，约收录 2.5 亿项成果）。最多返回 n 项结果，
    格式为 [{doi, title, authors, year, cited_by, venue, oa_url}]。`filters` 是 OpenAlex
    过滤字符串，例如 'from_publication_date:2022-01-01'。"""
    q = urllib.parse.quote(query)
    flt = f"&filter={filters}" if filters else ""
    c = litrev_contact()
    mailto = f"&mailto={urllib.parse.quote(c)}" if c else ""
    j = litrev_get(
        f"https://api.openalex.org/works?search={q}&per-page={min(n, 25)}"
        f"&sort=cited_by_count:desc{flt}{mailto}"
    )
    out = []
    for w in (j or {}).get("results", [])[:n]:
        loc = w.get("primary_location") or {}
        venue = ((loc.get("source") or {}) or {}).get("display_name")
        out.append(
            {
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                "title": w.get("title"),
                "authors": openalex_authors(w),
                "year": w.get("publication_year"),
                "cited_by": w.get("cited_by_count"),
                "venue": venue,
                "oa_url": (w.get("open_access") or {}).get("oa_url"),
            }
        )
    return out


def expand_citations(doi: str, n_backward: int = 50, n_forward: int = 15) -> dict:
    """通过 OpenAlex 沿引文图谱向两个方向各扩展一步。
    `references` 是向后扩展——论文自身的参考文献（出向引用），通过
    `filter=cited_by:<id>` 获取，并按被引次数由高到低排序。
    `cited_by` 是向前扩展——引用该论文的文献（入向引用），通过
    `filter=cites:<id>` 获取。每项格式为 {doi, title, authors, year, cited_by}。
    共发出三次 OpenAlex 请求（若列表查询降级为不请求 `authorships`，最多五次）；
    若 OpenAlex 未收录该 DOI，或列表端点受到限流，则返回空列表。"""
    c = litrev_contact()
    mailto = f"&mailto={urllib.parse.quote(c)}" if c else ""
    enc = quote_doi_path(doi)
    work = litrev_get(f"https://api.openalex.org/works/doi:{enc}?select=id{mailto}")
    work_id = ((work or {}).get("id") or "").rsplit("/", 1)[-1]
    if not work_id:
        return {"references": [], "cited_by": []}

    def _rows(results: list) -> list[dict]:
        out = []
        for w in results or []:
            out.append(
                {
                    "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                    "title": w.get("title"),
                    "authors": openalex_authors(w),
                    "year": w.get("publication_year"),
                    "cited_by": w.get("cited_by_count"),
                }
            )
        return out

    def _list(filter_expr: str, n: int) -> list[dict]:
        base = (
            f"https://api.openalex.org/works?filter={filter_expr}"
            f"&sort=cited_by_count:desc&per-page={min(n, 100)}{mailto}"
        )
        j = litrev_get(
            base + "&select=doi,title,publication_year,cited_by_count,authorships"
        )
        if j is None:
            j = litrev_get(base + "&select=doi,title,publication_year,cited_by_count")
        return _rows((j or {}).get("results", []))

    return {
        "references": _list(f"cited_by:{work_id}", n_backward),
        "cited_by": _list(f"cites:{work_id}", n_forward),
    }


def html_decode(s: str) -> str:
    """为提取 DOI 执行最小限度的 HTML 实体解码（lt/gt/amp/nbsp/slash）。"""
    for a, b in (
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&amp;", "&"),
        ("&nbsp;", " "),
        ("&#x2F;", "/"),
        ("&#47;", "/"),
    ):
        s = s.replace(a, b)
    return s


def extract_dois(text: str) -> list[str]:
    """从 `text` 中提取所有形似 DOI 的字符串（供 verify_dois 使用）。
    处理包括：HTML 解码、平衡 SICI 圆括号、在 `</` 处截断，并移除 Markdown/
    标点尾缀。"""
    decoded = html_decode(text)
    out: set[str] = set()
    for m in re.findall(DOI_PATTERN, decoded):
        d = m.split("</")[0]
        if d.count("<") != d.count(">"):
            d = d.split("<")[0]
        # 移除尾部 Markdown/标点字符。旧正则 `(?:\*\*|__|[...])+$` 存在歧义
        # （`*`/`_` 同时出现在分支和字符类中），遇到很长的连续 `**` 时会发生
        # 灾难性回溯；对相同字符集使用 str.rstrip 与其完全等价，而且始终是线性的。
        d = d.rstrip("_]*>`,;:")
        if d.endswith("."):
            d = d[:-1]
        while d.endswith(")") and d.count("(") < d.count(")"):
            d = d[:-1]
        if len(d) > 8:
            out.add(d)
    return sorted(out)


def style_pass(draft: str, model: str | None = None) -> dict:
    """确定性的文本静态检查。返回 {ok, issues:[{code,note}]}，其中每个 code
    均属于 EMDASH/HONEST/PROCNOTE/PARENDOI/LONGHEAD/FLATSTRUCT。

    按设计不调用 LLM：草稿经常引用从网页/论文中检索到的第三方文本，而要求
    智能体执行自由文本修复建议会形成间接提示注入通道。确定性的正则代码才是
    关键检查机制。接受但忽略 `model` 参数。"""
    del model
    issues: list[dict] = []
    w = len(draft.split()) or 1
    em = draft.count("—")
    if em > 6 and 1000 * em / w > 8:
        issues.append(
            {
                "code": "EMDASH",
                "note": f"{em} em-dashes ({1000*em/w:.0f}/1kw); replace most with comma/colon/period, keep at most one per paragraph",
            }
        )
    m = re.search(
        r"\b(the\s+|an?\s+)?honest(ly)?\s+(answer|summary|read|reading|look|perspective|assessment|appraisal|take|view)\b",
        draft,
        re.I,
    )
    if m:
        issues.append(
            {
                "code": "HONEST",
                "note": f"{m.group(0)!r}: drop the framing, write the sentence it was guarding",
            }
        )
    if re.search(
        r"(DOIs?\s+(were\s+)?verif|verified against (CrossRef|PubMed)|no retraction|current as of)",
        draft,
        re.I,
    ):
        issues.append(
            {"code": "PROCNOTE", "note": "process-narration line present; delete it"}
        )
    if re.search(r"\]\(https://doi\.org/[^)\s]*\([^)\s]*\)", draft):
        issues.append(
            {
                "code": "PARENDOI",
                "note": "DOI href contains literal ; URL-encode as %28 %29 so the markdown link survives simpler renderers",
            }
        )
    h2 = [ln for ln in draft.split("\n") if ln.startswith("## ")]
    long_h2 = [ln for ln in h2 if len(ln.split()) > 8]
    if len(long_h2) >= 2:
        issues.append(
            {
                "code": "LONGHEAD",
                "note": f"{len(long_h2)} headings read as sentences; shorten to <=6-word noun phrases",
            }
        )
    if len(h2) >= 7 and not any(ln.startswith("### ") for ln in draft.split("\n")):
        issues.append(
            {
                "code": "FLATSTRUCT",
                "note": f"{len(h2)} top-level sections, no subsections; group related ## under a parent and demote to ###",
            }
        )
    return {"ok": len(issues) == 0, "issues": issues}
