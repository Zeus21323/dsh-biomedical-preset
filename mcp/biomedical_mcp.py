#!/usr/bin/env python3
"""生物医学模式（biomedical）本机 MCP 服务：公开生物医学数据源的本地实现，无第三方依赖，纯标准库。

设计：
  - stdio + JSON-RPC 2.0（MCP 基础协议），一行一条消息
  - 一个进程承载 22 个数据域，工具名形如 `<domain>_<tool>`
  - 全部直连公共 REST API，不经过任何网关、不需要私有 token

运行： python biomedical_mcp.py
"""
import json
import sys
import time
import gzip
import io
from urllib import request as urlrequest
from urllib import parse as urlparse
from urllib import error as urlerror

UA = "dsh-biomedical-mcp/1.0"
TIMEOUT = 45
RETRIES = 4
RETRY_CODES = (429, 500, 502, 503, 504)


def _http(url, data=None, headers=None, method=None, timeout=TIMEOUT, retries=None):
    limit = RETRIES if retries is None else int(retries)
    hdrs = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip"}
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        hdrs.setdefault("Content-Type", "application/json")
    last = None
    for attempt in range(limit + 1):
        try:
            req = urlrequest.Request(url, data=body, headers=hdrs, method=method)
            with urlrequest.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                text = raw.decode("utf-8", "replace")
                try:
                    return json.loads(text)
                except Exception:
                    return text
        except urlerror.HTTPError as exc:
            raw = exc.read()
            if exc.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            snippet = raw.decode("utf-8", "replace")[:400]
            if exc.code in RETRY_CODES and attempt < limit:
                # 429 退避更久，500/503 短退避即可
                time.sleep((5.0 if exc.code == 429 else 2.0) * (attempt + 1))
                last = "HTTP %d: %s" % (exc.code, snippet)
                continue
            raise RuntimeError("HTTP %d for %s :: %s" % (exc.code, url, snippet))
        except Exception as exc:
            last = "%s: %s" % (type(exc).__name__, exc)
            if attempt < limit:
                time.sleep(1.2 * (attempt + 1))
                continue
            raise RuntimeError(last)
    raise RuntimeError(last or "request failed")


def _trim(value, depth=0, max_items=25):
    """限制返回体积，避免把整页原始 JSON 灌进上下文。"""
    if depth > 4:
        return str(value)[:200]
    if isinstance(value, list):
        out = [_trim(v, depth + 1, max_items) for v in value[:max_items]]
        if len(value) > max_items:
            out.append("... 共 %d 项" % len(value))
        return out
    if isinstance(value, dict):
        return {k: _trim(v, depth + 1, max_items) for k, v in list(value.items())[:40]}
    if isinstance(value, str) and len(value) > 600:
        return value[:600] + "…"
    return value


# --------------------------------------------------------------------------
# 工具实现
# --------------------------------------------------------------------------

def biomart_query(p):
    """Ensembl BioMart：XML over GET（自动跟随 308），返回 TSV 行。"""
    dataset = p.get("dataset", "hsapiens_gene_ensembl")
    attrs = [a.strip() for a in str(p.get("attributes",
             "ensembl_gene_id,hgnc_symbol,chromosome_name,start_position,end_position")).split(",") if a.strip()]
    filt = p.get("filter") or ""
    filters = ""
    if filt:
        for pair in str(filt).split(";"):
            if ":" in pair:
                name, _, value = pair.partition(":")
                filters += '<Filter name="%s" value="%s"/>' % (name.strip(), value.strip())
    xml = ('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE Query>'
           '<Query virtualSchemaName="default" formatter="TSV" header="1" '
           'uniqueRows="1" count="" datasetConfigVersion="0.6">'
           '<Dataset name="%s" interface="default">%s%s</Dataset></Query>'
           % (dataset, filters, "".join('<Attribute name="%s"/>' % a for a in attrs)))
    # www.ensembl.org 会 308 跳到归档主机（跳转会丢 query），asia 主机可直连
    host = p.get("host", "asia.ensembl.org")
    text = _http("https://%s/biomart/martservice?" % host +
                 urlparse.urlencode({"query": xml}), retries=2, timeout=40)
    raw = text if isinstance(text, str) else json.dumps(text)
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return {"dataset": dataset, "rows": [], "note": "无结果或查询语法错误"}
    header = lines[0].split("\t")
    rows = [dict(zip(header, ln.split("\t"))) for ln in lines[1: int(p.get("max_results", 20)) + 1]]
    return {"dataset": dataset, "total_lines": len(lines) - 1, "rows": rows}


def biomart_gene_info(p):
    return biomart_query({"filter": "hgnc_symbol:" + p["gene"],
                          "attributes": p.get("attributes",
                                              "ensembl_gene_id,hgnc_symbol,entrezgene_id,"
                                              "chromosome_name,start_position,end_position,strand,"
                                              "gene_biotype,description"),
                          "max_results": int(p.get("max_results", 5))})


def zinc_search(p):
    # ZINC 的 JSON API 已下线（现返回 HTML）；优先原样尝试，失败则回退 PubChem。
    key = p.get("inchikey") or p.get("smiles") or p.get("name")
    if not key:
        raise RuntimeError("需要 inchikey / smiles / name 之一")
    kinds = ("inchikey", "smiles", "smiles") if p.get("inchikey") else ("smiles", "smiles", "smiles")
    try:
        raw = _http("https://zinc.docking.org/substances.json?" +
                    urlparse.urlencode({kinds[0]: key, "limit": int(p.get("max_results", 5))}),
                    retries=1, timeout=20)
        if isinstance(raw, list) and raw:
            return {"source": "ZINC", "compounds": _trim(raw)}
        raise RuntimeError("ZINC 未返回结构化数据")
    except Exception as exc:
        ns = "inchikey" if p.get("inchikey") else "smiles"
        d = _http("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/%s/%s/cids/JSON"
                  % (ns, urlparse.quote(str(p["inchikey"] or p["smiles"]), safe="")))
        cids = ((d.get("IdentifierList") or {}).get("CID") or []) if isinstance(d, dict) else []
        return {"source": "PubChem（ZINC 回退）",
                "note": "ZINC 公开 JSON 接口已下线：%s" % str(exc)[:100],
                "query": key, "pubchem_cids": cids[: int(p.get("max_results", 5))],
                "hint": "需要供应商/可购买性时用 chemistry_pubchem_properties，或改用 ZINC 网页版"}


def pubmed_search(p):
    term = p["query"]
    retmax = int(p.get("max_results", 10))
    es = _http("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" +
               urlparse.urlencode({"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json"}))
    ids = (es.get("esearchresult", {}) or {}).get("idlist", []) if isinstance(es, dict) else []
    if not ids:
        return {"query": term, "total": 0, "articles": []}
    sm = _http("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" +
               urlparse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"}))
    result = (sm.get("result", {}) if isinstance(sm, dict) else {})
    arts = []
    for pm in ids:
        it = result.get(pm) or {}
        arts.append({
            "pmid": pm,
            "title": it.get("title"),
            "journal": it.get("fulljournalname") or it.get("source"),
            "date": it.get("pubdate"),
            "authors": [a.get("name") for a in (it.get("authors") or [])[:6]],
            "doi": next((x.get("value") for x in (it.get("articleids") or [])
                         if x.get("idtype") == "doi"), None),
        })
    return {"query": term, "total": int((es.get("esearchresult", {}) or {}).get("count", 0)),
            "articles": arts}


def pubmed_metadata(p):
    sm = _http("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" +
               urlparse.urlencode({"db": "pubmed", "id": p["pmid"], "retmode": "json"}))
    it = ((sm.get("result") or {}).get(p["pmid"]) or {}) if isinstance(sm, dict) else {}
    return {"pmid": p["pmid"], "title": it.get("title"),
            "journal": it.get("fulljournalname"), "date": it.get("pubdate"),
            "authors": [a.get("name") for a in (it.get("authors") or [])[:10]],
            "ids": {x.get("idtype"): x.get("value") for x in (it.get("articleids") or [])},
            "abstract_hint": "用 efetch 取摘要：%s" % (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=%s&retmode=xml" % p["pmid"])}


def pubmed_related(p):
    d = _http("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?" +
              urlparse.urlencode({"dbfrom": "pubmed", "db": "pubmed", "id": p["pmid"],
                                  "retmode": "json", "cmd": "neighbor_score"}))
    links = (((d.get("linksets") or [{}])[0].get("linksetdbs") or [{}])[0].get("links") or []) \
        if isinstance(d, dict) else []
    return {"pmid": p["pmid"], "related": links[: int(p.get("max_results", 20))]}


def chembl_compound(p):
    q = p["name"]
    d = _http("https://www.ebi.ac.uk/chembl/api/data/molecule/search.json?" +
              urlparse.urlencode({"q": q, "limit": int(p.get("max_results", 5))}))
    out = []
    for m in (d.get("molecules") or [])[: int(p.get("max_results", 5))] if isinstance(d, dict) else []:
        out.append({"chembl_id": m.get("molecule_chembl_id"),
                    "name": m.get("pref_name"),
                    "type": m.get("molecule_type"),
                    "max_phase": m.get("max_phase"),
                    "smiles": ((m.get("molecule_structures") or {}) or {}).get("canonical_smiles")})
    return {"query": q, "compounds": out}


def chembl_bioactivity(p):
    d = _http("https://www.ebi.ac.uk/chembl/api/data/activity.json?" +
              urlparse.urlencode({"molecule_chembl_id": p["chembl_id"],
                                  "limit": int(p.get("max_results", 20))}))
    acts = []
    for a in (d.get("activities") or []) if isinstance(d, dict) else []:
        acts.append({"target": a.get("target_pref_name"), "type": a.get("standard_type"),
                     "value": a.get("standard_value"), "units": a.get("standard_units"),
                     "pchembl": a.get("pchembl_value"), "assay": a.get("assay_chembl_id")})
    return {"chembl_id": p["chembl_id"], "activities": acts}


def chembl_target(p):
    d = _http("https://www.ebi.ac.uk/chembl/api/data/target/search.json?" +
              urlparse.urlencode({"q": p["query"], "limit": int(p.get("max_results", 5))}))
    out = [{"chembl_id": t.get("target_chembl_id"), "name": t.get("pref_name"),
            "type": t.get("target_type"), "organism": t.get("organism")}
           for t in ((d.get("targets") or []) if isinstance(d, dict) else [])]
    return {"query": p["query"], "targets": out}


def biorxiv_preprint(p):
    srv = p.get("server", "biorxiv")
    d = _http("https://api.biorxiv.org/details/%s/%s" % (srv, p["doi"]))
    return _trim(d)


def biorxiv_recent(p):
    srv = p.get("server", "biorxiv")
    d = _http("https://api.biorxiv.org/details/%s/%s/%s/%s" %
              (srv, p["date_from"], p["date_to"], int(p.get("cursor", 0))))
    return _trim(d)


def clinicaltrials_search(p):
    q = {"query.term": p["query"], "pageSize": int(p.get("max_results", 5)),
         "format": "json"}
    if p.get("status"):
        q["filter.overallStatus"] = p["status"]
    d = _http("https://clinicaltrials.gov/api/v2/studies?" + urlparse.urlencode(q))
    out = []
    for s in (d.get("studies") or []) if isinstance(d, dict) else []:
        pr = (s.get("protocolSection") or {})
        ident = pr.get("identificationModule") or {}
        st = pr.get("statusModule") or {}
        out.append({"nct_id": ident.get("nctId"), "title": ident.get("briefTitle"),
                    "status": st.get("overallStatus"), "start": st.get("startDateStruct"),
                    "phase": (pr.get("designModule") or {}).get("phases")})
    return {"query": p["query"], "total": (d.get("totalCount") if isinstance(d, dict) else None),
            "studies": out}


def clinicaltrials_get(p):
    return _trim(_http("https://clinicaltrials.gov/api/v2/studies/%s?format=json" % p["nct_id"]))


def ensembl_lookup(p):
    q = p["query"]
    species = p.get("species", "homo_sapiens")
    kind = "symbol" if not str(q).startswith("ENS") else "id"
    d = _http("https://rest.ensembl.org/lookup/%s/%s/%s?content-type=application/json"
              % (kind, species, q))
    return {"query": q, "id": d.get("id"), "display_name": d.get("display_name"),
            "biotype": d.get("biotype"), "seq_region": d.get("seq_region_name"),
            "start": d.get("start"), "end": d.get("end"), "strand": d.get("strand"),
            "description": d.get("description")}


def ensembl_sequence(p):
    region = p.get("region")
    url = ("https://rest.ensembl.org/sequence/region/%s/%s?content-type=text/plain"
           % (p.get("species", "homo_sapiens"), region)) if region else \
          ("https://rest.ensembl.org/sequence/id/%s?content-type=text/plain;type=%s"
           % (p["stable_id"], p.get("seq_type", "genomic")))
    seq = _http(url)
    s = seq if isinstance(seq, str) else json.dumps(seq)
    return {"length": len(s.replace("\n", "")), "sequence_head": s[:300],
            "note": "已截断返回；完整序列请按需用 region 分段取"}


def ensembl_overlap(p):
    feat = p.get("feature", "gene")
    d = _http("https://rest.ensembl.org/overlap/region/%s/%s?feature=%s;content-type=application/json"
              % (p.get("species", "homo_sapiens"), p["region"], feat))
    return {"region": p["region"], "features": _trim(d)}


def gnomad_variant(p):
    # gnomAD v4 的字段是 variant(variantId:, dataset:)；若只给 rsID 或坐标，
    # 先用 variant_search 解析出 variant_id。失败则回退 Ensembl 人群频率。
    ds = p.get("dataset", "gnomad_r4")
    key = p.get("variant_id") or p.get("rs_id")
    try:
        if not key:
            raise RuntimeError("需要 variant_id 或 rs_id")
        vid = key
        if not re.match(r"^[\dXYM]+-\d+-[ACGT]+-[ACGT]+$", str(vid)):
            s = _http("https://gnomad.broadinstitute.org/api",
                      data={"query": "query($q:String!,$ds:DatasetId!)"
                                     "{variant_search(query:$q,dataset:$ds){variant_id}}",
                            "variables": {"q": str(key), "ds": ds}}, method="POST")
            hits = ((s.get("data") or {}).get("variant_search") or []) if isinstance(s, dict) else []
            if not hits:
                raise RuntimeError("variant_search 无结果：%s" % key)
            vid = hits[0]["variant_id"]
        d = _http("https://gnomad.broadinstitute.org/api",
                  data={"query": "query($vid:String!,$ds:DatasetId!){variant(variantId:$vid,dataset:$ds)"
                                 "{variant_id chrom pos ref alt genome{af ac an populations{id ac an}}"
                                 " exome{af ac an} transcript_consequences{gene_symbol consequence_terms}}}",
                        "variables": {"vid": vid, "ds": ds}}, method="POST")
        if isinstance(d, dict) and d.get("errors"):
            raise RuntimeError(str(d["errors"])[:200])
        return {"source": "gnomAD", **_trim(d)}
    except Exception as exc:
        rs = p.get("rs_id")
        if not rs:
            raise RuntimeError("gnomAD 不可用（%s）；可加 rs_id 回退到 Ensembl" % str(exc)[:100])
        alt = _http("https://rest.ensembl.org/variation/human/%s?content-type=application/json" % rs)
        pops = [{"population": x.get("population"), "allele": x.get("allele"),
                 "frequency": x.get("frequency")} for x in (alt.get("populations") or [])[:20]]
        return {"source": "Ensembl variation（gnomAD 回退）",
                "note": "gnomAD 未响应：%s" % str(exc)[:120],
                "rs_id": rs, "name": alt.get("name"),
                "mappings": alt.get("mappings"), "populations": pops}


def clinvar_search(p):
    es = _http("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" +
               urlparse.urlencode({"db": "clinvar", "term": p["query"],
                                   "retmax": int(p.get("max_results", 10)), "retmode": "json"}))
    ids = ((es.get("esearchresult") or {}).get("idlist") or []) if isinstance(es, dict) else []
    return {"query": p["query"], "total": ((es.get("esearchresult") or {}).get("count")
                                           if isinstance(es, dict) else None),
            "variation_ids": ids}


def dbsnp_get(p):
    sm = _http("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" +
               urlparse.urlencode({"db": "snp", "id": p["rsid"].lstrip("rs"), "retmode": "json"}))
    return _trim(sm)


def gtex_expression(p):
    gene = p["gene"]
    d = _http("https://gtexportal.org/api/v2/expression/medianGeneExpression?" +
              urlparse.urlencode({"gencodeId": gene, "itemsPerPage": 60}))
    rows = (d.get("data") or []) if isinstance(d, dict) else []
    top = sorted(rows, key=lambda r: -(r.get("median") or 0))
    return {"gene": gene, "tissues": [{"tissue": r.get("tissueSiteDetailId"),
                                       "median_tpm": r.get("median")} for r in top[:25]]}


def gtex_tissues(p):
    d = _http("https://gtexportal.org/api/v2/dataset/tissueSiteDetail?itemsPerPage=100")
    rows = (d.get("data") or []) if isinstance(d, dict) else []
    return {"count": len(rows),
            "sites": [{"id": r.get("id"), "name": r.get("tissueSiteDetail")} for r in rows[:60]]}


def encode_search(p):
    # encodeproject.org 从部分网络极慢甚至不可达：短超时 + 失败回退 Ensembl 调控区。
    q = {"type": p.get("type", "Experiment"), "format": "json",
         "limit": int(p.get("max_results", 5))}
    if p.get("query"):
        q["searchTerm"] = p["query"]
    if p.get("assay"):
        q["assay_title"] = p["assay"]
    try:
        d = _http("https://www.encodeproject.org/search/?" + urlparse.urlencode(q),
                  timeout=12, retries=0)
        rows = (d.get("@graph") or []) if isinstance(d, dict) else []
        return {"source": "ENCODE", "total": (d.get("total") if isinstance(d, dict) else None),
                "entries": [{"accession": r.get("accession"), "assay": r.get("assay_title"),
                             "biosample": r.get("biosample_summary"),
                             "description": r.get("description")} for r in rows]}
    except Exception as exc:
        if not p.get("region"):
            raise RuntimeError("ENCODE 不可达（%s）；可传 region 参数回退到 Ensembl 调控区"
                               % str(exc)[:100])
        d = _http("https://rest.ensembl.org/overlap/region/%s/%s?feature=regulatory;content-type=application/json"
                  % (p.get("species", "homo_sapiens"), p["region"]), timeout=15, retries=1)
        feats = d if isinstance(d, list) else []
        return {"source": "Ensembl regulatory（ENCODE 回退）",
                "note": "ENCODE 未响应：%s" % str(exc)[:120],
                "region": p["region"], "count": len(feats),
                "features": [{"type": f.get("feature_type"), "id": f.get("id"),
                              "start": f.get("start"), "end": f.get("end"),
                              "description": f.get("description")} for f in feats[:25]]}


def jaspar_matrix(p):
    if p.get("matrix_id"):
        return _trim(_http("https://jaspar.genereg.net/api/v1/matrix/%s/" % p["matrix_id"]))
    q = {"search": p.get("query", ""), "page_size": int(p.get("max_results", 10))}
    if p.get("collection"):
        q["collection"] = p["collection"]
    d = _http("https://jaspar.genereg.net/api/v1/matrix/?" + urlparse.urlencode(q))
    rows = (d.get("results") or []) if isinstance(d, dict) else []
    return {"count": (d.get("count") if isinstance(d, dict) else None),
            "matrices": [{"matrix_id": r.get("matrix_id"), "name": r.get("name"),
                          "base_id": r.get("base_id"), "version": r.get("version")}
                         for r in rows]}


def interpro_domains(p):
    d = _http("https://www.ebi.ac.uk/interpro/api/entry/all/protein/uniprot/%s/" % p["accession"])
    rows = (d.get("results") or []) if isinstance(d, dict) else []
    out = []
    for r in rows:
        meta = (r.get("metadata") or {})
        out.append({"accession": meta.get("accession"), "name": meta.get("name"),
                    "type": meta.get("type"), "source": meta.get("source_database")})
    return {"uniprot": p["accession"], "count": (d.get("count") if isinstance(d, dict) else None),
            "domains": out}


def string_network(p):
    ids = p["identifiers"]
    d = _http("https://string-db.org/api/json/network?" +
              urlparse.urlencode({"identifiers": ids, "species": int(p.get("species", 9606)),
                                  "required_score": int(p.get("required_score", 400))}))
    rows = d if isinstance(d, list) else []
    return {"count": len(rows),
            "edges": [{"a": r.get("preferredName_A"), "b": r.get("preferredName_B"),
                       "score": r.get("score")} for r in rows[:40]]}


def hpa_gene(p):
    # 直接用 <gene>.json 会 404；走 search_download 接口
    d = _http("https://www.proteinatlas.org/api/search_download.php?" + urlparse.urlencode({
        "search": p["gene"], "format": "json", "compress": "no",
        "columns": "g,gs,eg,gd,chr,up,scml,ab,pc,pe"}))
    rows = d if isinstance(d, list) else []
    return {"gene": p["gene"], "count": len(rows), "records": _trim(rows)}


def pdb_entry(p):
    d = _http("https://data.rcsb.org/rest/v1/core/entry/%s" % p["pdb_id"].upper())
    return {"pdb_id": p["pdb_id"].upper(),
            "title": ((d.get("struct") or {}).get("title")),
            "method": ((d.get("exptl") or [{}])[0].get("method")),
            "resolution": (((d.get("rcsb_entry_info") or {}).get("resolution_combined")) or [None])[0],
            "deposited": ((d.get("rcsb_accession_info") or {}).get("deposit_date"))}


def pdb_search(p):
    q = {"query": {"type": "terminal", "service": "full_text",
                   "parameters": {"value": p["query"]}},
         "return_type": "entry", "request_options": {"paginate": {"start": 0,
                                                                  "rows": int(p.get("max_results", 10))}}}
    d = _http("https://search.rcsb.org/rcsbsearch/v2/query?" +
              urlparse.urlencode({"json": json.dumps(q)}))
    ids = [r.get("identifier") for r in (d.get("result_set") or [])] if isinstance(d, dict) else []
    return {"query": p["query"], "total": (d.get("total_count") if isinstance(d, dict) else None),
            "pdb_ids": ids}


def alphafold_prediction(p):
    d = _http("https://alphafold.ebi.ac.uk/api/prediction/%s" % p["accession"])
    rows = d if isinstance(d, list) else []
    return {"uniprot": p["accession"],
            "models": [{"entry_id": r.get("entryId"), "version": r.get("latestVersion"),
                        "pdb_url": r.get("pdbUrl"), "pae_url": r.get("paeImageUrl"),
                        "model_entity": r.get("uniprotDescription")} for r in rows]}


def rfam_family(p):
    fam = p["family"]
    d = _http("https://rfam.org/family/%s?content-type=application/json" % fam)
    f = (d.get("rfam") or {}) if isinstance(d, dict) else {}
    return {"family": fam, "accession": f.get("rfam_acc"), "description": f.get("description"),
            "type": f.get("type"), "seed_count": f.get("num_seed"),
            "full_count": f.get("num_full"), "clan": f.get("clan_info")}


def rfam_search(p):
    d = _http("https://rfam.org/search?content-type=application/json&q=" +
              urlparse.quote(p["query"]))
    return _trim(d)


def mygene_query(p):
    d = _http("https://mygene.info/v3/query?" + urlparse.urlencode({
        "q": p["terms"], "species": p.get("species", "human"),
        "fields": p.get("fields", "symbol,name,taxid,entrezgene,ensembl.gene,uniprot.Swiss-Prot"),
        "size": int(p.get("max_results", 10))}))
    return _trim(d)


def quickgo_annotations(p):
    q = {"geneProductId": p["uniprot"], "limit": int(p.get("max_results", 50))}
    if p.get("aspect"):
        q["aspect"] = p["aspect"]
    d = _http("https://www.ebi.ac.uk/QuickGO/services/annotation/search?" + urlparse.urlencode(q))
    rows = (d.get("results") or []) if isinstance(d, dict) else []
    return {"uniprot": p["uniprot"], "total": (d.get("numberOfHits") if isinstance(d, dict) else None),
            "annotations": [{"go_id": r.get("goId"), "name": r.get("goName"),
                             "aspect": r.get("aspect"), "evidence": r.get("goEvidence")}
                            for r in rows]}


def ols_term(p):
    ont = p["ontology"]
    term = p["term_id"]
    # OLS4 只认按 IRI 双编码的路径，不接受 GO:0006915 这种短格式
    short = term.replace(":", "_")
    iri = "http://purl.obolibrary.org/obo/" + short
    enc = urlparse.quote(urlparse.quote(iri, safe=""), safe="")
    d = _http("https://www.ebi.ac.uk/ols4/api/ontologies/%s/terms/%s" % (ont, enc))
    return {"ontology": ont, "term_id": term, "label": d.get("label"),
            "description": (d.get("description") or [None])[0],
            "is_obsolete": d.get("is_obsolete"),
            "synonyms": (d.get("synonyms") or [])[:10]}


def geo_search(p):
    d = _http("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" +
              urlparse.urlencode({"db": "gds", "term": p["term"],
                                  "retmax": int(p.get("max_results", 10)), "retmode": "json"}))
    ids = ((d.get("esearchresult") or {}).get("idlist") or []) if isinstance(d, dict) else []
    return {"term": p["term"], "total": ((d.get("esearchresult") or {}).get("count")
                                         if isinstance(d, dict) else None), "gds_ids": ids}


def pride_project(p):
    return _trim(_http("https://www.ebi.ac.uk/pride/ws/archive/v3/projects/%s" % p["accession"]))


def biostudies_search(p):
    d = _http("https://www.ebi.ac.uk/biostudies/api/v1/search?" +
              urlparse.urlencode({"query": p["query"], "pageSize": int(p.get("max_results", 10))}))
    return _trim(d)


def variant_phenotypes(p):
    # GWAS Catalog 旧 REST API 已下线（HTTP 410），改用 Ensembl variation 的
    # phenotype_associations，同样覆盖 rsID → 性状 / p 值 / 研究。
    rs = p["rs_id"]
    if not rs.startswith("rs"):
        rs = "rs" + rs
    d = _http("https://rest.ensembl.org/variation/human/%s?content-type=application/json"
              % rs)
    assoc = d.get("phenotype_or_disease") or []
    names = {}
    for a in assoc:
        for ph in (a.get("phenotypes") or []):
            names[ph.get("phenotype")] = ph.get("p_value")
    out = [{"phenotype": k, "p_value": v} for k, v in names.items()]
    out.sort(key=lambda x: (x["p_value"] is None, x["p_value"]))
    return {"rs_id": rs, "name": d.get("name"),
            "alleles": d.get("mappings"),
            "phenotype_count": len(out),
            "phenotypes": out[: int(p.get("max_results", 20))]}


def gwas_study(p):
    # 旧 GWAS Catalog /studies 同样返回 410；改从 Ensembl variation 的
    # study 信息里取，按 Study accession 反查该变异关联的全部性状。
    d = _http("https://rest.ensembl.org/variation/human/%s?content-type=application/json"
              % p["accession_id"])
    return _trim(d)


def cbioportal_studies(p):
    d = _http("https://www.cbioportal.org/api/studies")
    rows = d if isinstance(d, list) else []
    kw = (p.get("keyword") or "").lower()
    if kw:
        rows = [r for r in rows if kw in json.dumps(r, ensure_ascii=False).lower()]
    return {"count": len(rows),
            "studies": [{"study_id": r.get("studyId"), "name": r.get("name"),
                         "cancer_type": r.get("cancerTypeId"),
                         "samples": r.get("allSampleCount")}
                        for r in rows[: int(p.get("max_results", 20))]]}


def cbioportal_mutations(p):
    # 正确路径是 molecular-profiles/{profileId}/mutations/fetch，要先解析出
    # 该研究下突变类型的 molecular profile。
    prof = _http("https://www.cbioportal.org/api/studies/%s/molecular-profiles"
                 % p["study_id"])
    rows = prof if isinstance(prof, list) else []
    mut = [r for r in rows if (r.get("molecularAlterationType") == "MUTATION_EXTENDED")]
    if not mut:
        return {"study": p["study_id"], "error": "该研究没有突变数据",
                "profiles": [r.get("molecularProfileId") for r in rows]}
    profile_id = p.get("profile_id") or mut[0].get("molecularProfileId")
    sample_list = p.get("sample_list_id") or profile_id.replace("_mutations", "_all")
    # POST /mutations/fetch 的过滤器格式校验很严；GET 形式稳定可靠
    d = _http("https://www.cbioportal.org/api/molecular-profiles/%s/mutations?"
              % profile_id + urlparse.urlencode({"sampleListId": sample_list,
                                                 "entrezGeneId": int(p["entrez_gene_id"])}))
    rows2 = d if isinstance(d, list) else []
    return {"study": p["study_id"], "profile": profile_id, "gene": p["entrez_gene_id"],
            "count": len(rows2),
            "mutations": [{"protein_change": r.get("proteinChange"),
                           "mutation_type": r.get("mutationType"),
                           "sample": r.get("sampleId")} for r in rows2[:25]]}


def cellxgene_datasets(p):
    q = {"size": int(p.get("max_results", 10))}
    if p.get("query"):
        q["filter"] = json.dumps({"organism": ["Homo sapiens"]})
    d = _http("https://api.cellxgene.cziscience.com/curation/v1/collections?"
              + urlparse.urlencode(q))
    rows = d if isinstance(d, list) else []
    return {"count": len(rows),
            "collections": [{"id": r.get("collection_id"), "name": r.get("name"),
                             "doi": r.get("doi"), "datasets": len(r.get("datasets") or [])}
                            for r in rows[:25]]}


def cellguide_cell_type(p):
    # CellGuide 的 v1 REST 路径已失效；改用 OLS4 的 Cell Ontology(CL) 检索，
    # 同样能按名称/同义词定位细胞类型并拿到 CL ID。
    d = _http("https://www.ebi.ac.uk/ols4/api/search?" + urlparse.urlencode({
        "q": p["query"], "ontology": "cl",
        "rows": int(p.get("max_results", 15)), "groupField": "iri"}))
    docs = ((d.get("response") or {}).get("docs") or []) if isinstance(d, dict) else []
    return {"query": p["query"],
            "cell_types": [{"label": x.get("label"), "obo_id": x.get("obo_id"),
                            "iri": x.get("iri"), "description": (x.get("description") or [None])[0]}
                           for x in docs]}


def pubchem_search(p):
    ns = p.get("namespace", "name")
    d = _http("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/%s/%s/cids/JSON"
              % (ns, urlparse.quote(str(p["query"]), safe="")))
    cids = ((d.get("IdentifierList") or {}).get("CID") or []) if isinstance(d, dict) else []
    return {"query": p["query"], "cids": cids[: int(p.get("max_results", 10))],
            "note": "用 pubchem_properties 取属性"}


def pubchem_properties(p):
    props = "MolecularFormula,MolecularWeight,IsomericSMILES,IUPACName"
    d = _http("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/%s/property/%s/JSON"
              % (p["cid"], props))
    rows = ((d.get("PropertyTable") or {}).get("Properties") or []) if isinstance(d, dict) else []
    return rows[0] if rows else {"cid": p["cid"], "note": "not found"}


def rhea_reaction(p):
    d = _http("https://www.rhea-db.org/rhea/%s?format=json" % p["rhea_id"])
    return _trim(d)


def civic_search(p):
    query = """query($q:String!){ search(q:$q){ evidenceItems{ nodes{ id name
      evidenceType evidenceLevel significance disease{name} therapies{name}
      molecularProfile{name} } } } }"""
    d = _http("https://civicdb.org/api/graphql",
              data={"query": query, "variables": {"q": p["query"]}}, method="POST")
    return _trim(d)


def opentargets_targets(p):
    query = """query($efo:String!){ disease(efoId:$efo){ id name
      associatedTargets(page:{index:0,size:20}){ count rows{ score target{ id approvedSymbol } } } } }"""
    d = _http("https://api.platform.opentargets.org/api/v4/graphql",
              data={"query": query, "variables": {"efo": p["efo_id"]}}, method="POST")
    return _trim(d)


def openfda_labels(p):
    q = {"search": p["search"], "limit": int(p.get("max_results", 3))}
    if p.get("api_key"):
        q["api_key"] = p["api_key"]
    d = _http("https://api.fda.gov/drug/label.json?" + urlparse.urlencode(q))
    rows = (d.get("results") or []) if isinstance(d, dict) else []
    return {"search": p["search"],
            "labels": [{"brand": r.get("openfda", {}).get("brand_name"),
                        "generic": r.get("openfda", {}).get("generic_name"),
                        "indications": (r.get("indications_and_usage") or [""])[0][:400]}
                       for r in rows]}


def openfda_drugsfda(p):
    q = {"search": p["search"], "limit": int(p.get("max_results", 3))}
    d = _http("https://api.fda.gov/drug/drugsfda.json?" + urlparse.urlencode(q))
    return _trim(d)


def openalex_search(p):
    q = {"search": p["query"], "per-page": int(p.get("max_results", 10))}
    if p.get("year_from"):
        q["filter"] = "from_publication_date:%s-01-01" % p["year_from"]
    d = _http("https://api.openalex.org/works?" + urlparse.urlencode(q))
    rows = (d.get("results") or []) if isinstance(d, dict) else []
    return {"query": p["query"], "total": (d.get("meta") or {}).get("count"),
            "works": [{"id": r.get("id"), "title": r.get("title"),
                       "year": r.get("publication_year"),
                       "doi": r.get("doi"),
                       "cited_by": r.get("cited_by_count")} for r in rows]}


def arxiv_search(p):
    q = urlparse.urlencode({"search_query": p["query"],
                            "start": int(p.get("start", 0)),
                            "max_results": int(p.get("max_results", 10))})
    raw = _http("http://export.arxiv.org/api/query?" + q)
    return {"query": p["query"], "raw_head": (raw if isinstance(raw, str) else json.dumps(raw))[:1500],
            "note": "arXiv 返回 Atom XML，已截断；需要结构化可再解析该 XML"}


# --------------------------------------------------------------------------
# 工具清单
# --------------------------------------------------------------------------
TOOLS = [
    ("biomart_query", "Ensembl BioMart 通用查询（XML over GET，自动跟随跳转），返回 TSV 行。",
     {"dataset": ("string", "默认 hsapiens_gene_ensembl", False),
      "filter": ("string", "如 hgnc_symbol:TP53，多个用分号分隔", False),
      "attributes": ("string", "逗号分隔的 BioMart 属性名", False),
      "max_results": ("integer", "默认 20", False)}, biomart_query),
    ("biomart_gene_info", "BioMart 按基因符号取基础注释（Ensembl/Entrez/位置/biotype/描述）。",
     {"gene": ("string", "如 TP53", True), "max_results": ("integer", "默认 5", False)}, biomart_gene_info),
    ("zinc_search_by_structure", "按 InChIKey 或 SMILES 查 ZINC；ZINC 公开 JSON 接口已下线时自动回退 PubChem。",
     {"inchikey": ("string", "InChIKey", False), "smiles": ("string", "SMILES", False),
      "name": ("string", "化合物名", False), "max_results": ("integer", "默认 5", False)}, zinc_search),
    ("pubmed_search_articles", "PubMed 检索文献（NCBI E-utilities）。返回 PMID、标题、期刊、日期、作者、DOI。",
     {"query": ("string", "检索式，支持 PubMed 语法", True), "max_results": ("integer", "返回条数，默认 10", False)},
     pubmed_search),
    ("pubmed_get_article_metadata", "按 PMID 取文献元数据（含 DOI/PMCID）。",
     {"pmid": ("string", "PubMed ID", True)}, pubmed_metadata),
    ("pubmed_find_related", "按 PMID 找 PubMed 计算的相关文献。",
     {"pmid": ("string", "PubMed ID", True), "max_results": ("integer", "默认 20", False)}, pubmed_related),

    ("chembl_compound_search", "ChEMBL 按名称搜索化合物，返回 ChEMBL ID、SMILES、研发阶段。",
     {"name": ("string", "化合物/药物名", True), "max_results": ("integer", "默认 5", False)}, chembl_compound),
    ("chembl_get_bioactivity", "取某化合物与靶点的实验活性（IC50/Ki 等）。",
     {"chembl_id": ("string", "如 CHEMBL25", True), "max_results": ("integer", "默认 20", False)}, chembl_bioactivity),
    ("chembl_target_search", "按名称或基因符号搜索 ChEMBL 靶点。",
     {"query": ("string", "靶点名或基因符号", True), "max_results": ("integer", "默认 5", False)}, chembl_target),

    ("biorxiv_get_preprint", "按 DOI 取 bioRxiv/medRxiv 预印本元数据（非同行评议）。",
     {"doi": ("string", "预印本 DOI", True), "server": ("string", "biorxiv 或 medrxiv", False)}, biorxiv_preprint),
    ("biorxiv_recent_preprints", "按日期区间列预印本。",
     {"date_from": ("string", "YYYY-MM-DD", True), "date_to": ("string", "YYYY-MM-DD", True),
      "cursor": ("integer", "偏移，默认 0", False), "server": ("string", "biorxiv 或 medrxiv", False)}, biorxiv_recent),

    ("clinicaltrials_search_trials", "ClinicalTrials.gov v2 试验检索。",
     {"query": ("string", "检索词", True), "max_results": ("integer", "默认 5", False),
      "status": ("string", "如 RECRUITING", False)}, clinicaltrials_search),
    ("clinicaltrials_get_trial", "按 NCT 号取完整试验记录。",
     {"nct_id": ("string", "如 NCT01234567", True)}, clinicaltrials_get),

    ("genomes_ensembl_lookup", "Ensembl 按基因符号或稳定 ID 查注释（位置、biotype、转录本）。",
     {"query": ("string", "基因符号或 ENSG ID", True), "species": ("string", "默认 homo_sapiens", False)}, ensembl_lookup),
    ("genomes_ensembl_sequence", "取序列：给 region 取区间，或给 stable_id 取该 ID 序列。",
     {"region": ("string", "如 X:1000000..1001000", False), "stable_id": ("string", "如 ENST00000380152", False),
      "species": ("string", "默认 homo_sapiens", False), "seq_type": ("string", "genomic/cdna/protein", False)}, ensembl_sequence),
    ("genomes_ensembl_overlap", "查某区间内重叠的基因/转录本等特征。",
     {"region": ("string", "如 7:140424943..140624564", True), "feature": ("string", "gene/transcript/variation", False),
      "species": ("string", "默认 homo_sapiens", False)}, ensembl_overlap),

    ("variants_gnomad_get_variant", "gnomAD v4 查变异群体频率；若被限流(429)则自动回退到 Ensembl 人群频率。",
     {"variant_id": ("string", "如 1-55051215-G-GA", True),
      "rs_id": ("string", "可选，gnomAD 不可用时用于回退", False),
      "dataset": ("string", "默认 gnomad_r4", False)}, gnomad_variant),
    ("variants_clinvar_search", "ClinVar 检索（NCBI E-utilities）。",
     {"query": ("string", "如 BRCA1 pathogenic", True), "max_results": ("integer", "默认 10", False)}, clinvar_search),
    ("variants_dbsnp_get", "dbSNP 按 rsID 取记录摘要。",
     {"rsid": ("string", "如 rs7412", True)}, dbsnp_get),

    ("expression_gtex_median", "GTEx 某基因各组织中位表达（TPM，降序）。需 GENCODE ID。",
     {"gene": ("string", "如 ENSG00000141510.18", True)}, gtex_expression),
    ("expression_gtex_tissue_sites", "列 GTEx 组织位点。", {}, gtex_tissues),

    ("regulation_encode_search", "ENCODE 检索实验；该站常不可达，失败可传 region 回退到 Ensembl 调控区。",
     {"query": ("string", "检索词", False), "type": ("string", "Experiment/File 等", False),
      "assay": ("string", "如 ChIP-seq", False), "region": ("string", "如 17:7676500..7688000，用于回退", False),
      "species": ("string", "默认 homo_sapiens", False),
      "max_results": ("integer", "默认 5", False)}, encode_search),
    ("regulation_jaspar_matrix", "JASPAR 矩阵：给 matrix_id 取详情，或按关键词检索。",
     {"matrix_id": ("string", "如 MA0139.1", False), "query": ("string", "如 CTCF", False),
      "collection": ("string", "CORE 等", False), "max_results": ("integer", "默认 10", False)}, jaspar_matrix),

    ("protein_annotation_interpro_domains", "InterPro 取 UniProt 蛋白的结构域架构。",
     {"accession": ("string", "UniProt 登录号", True)}, interpro_domains),
    ("protein_annotation_string_network", "STRING v12 取蛋白互作网络。",
     {"identifiers": ("string", "基因名，多个用 %0d 分隔", True), "species": ("integer", "默认 9606", False),
      "required_score": ("integer", "默认 400", False)}, string_network),
    ("protein_annotation_hpa_gene", "Human Protein Atlas 按基因名取记录。",
     {"gene": ("string", "基因符号", True)}, hpa_gene),

    ("structures_pdb_entry", "RCSB PDB 按 PDB ID 取条目摘要。",
     {"pdb_id": ("string", "四字符 PDB ID", True)}, pdb_entry),
    ("structures_pdb_search", "RCSB PDB 全文检索。",
     {"query": ("string", "检索词", True), "max_results": ("integer", "默认 10", False)}, pdb_search),
    ("structures_alphafold_prediction", "AlphaFold DB 取 UniProt 的预测结构链接。",
     {"accession": ("string", "UniProt 登录号", True)}, alphafold_prediction),

    ("rna_rfam_family", "Rfam 家族详情（accession、类型、seed/full 数量）。",
     {"family": ("string", "如 RF00001 或 5S_rRNA", True)}, rfam_family),
    ("rna_rfam_search", "Rfam 关键词检索。",
     {"query": ("string", "如 riboswitch", True)}, rfam_search),

    ("genes_ontologies_mygene_query", "MyGene 批量解析基因符号/ID。",
     {"terms": ("string", "逗号分隔的基因名", True), "species": ("string", "默认 human", False),
      "fields": ("string", "返回字段", False), "max_results": ("integer", "默认 10", False)}, mygene_query),
    ("genes_ontologies_quickgo_annotations", "QuickGO 取 UniProt 蛋白的 GO 注释。",
     {"uniprot": ("string", "如 UniProtKB:P04637 或 P04637", True),
      "aspect": ("string", "biological_process/molecular_function/cellular_component", False),
      "max_results": ("integer", "默认 50", False)}, quickgo_annotations),
    ("genes_ontologies_ols_term", "OLS4 取本体术语详情。",
     {"ontology": ("string", "如 go、cl、efo", True), "term_id": ("string", "如 GO:0006915", True)}, ols_term),

    ("omics_archives_geo_search", "GEO 检索数据集（NCBI gds）。",
     {"term": ("string", "检索式", True), "max_results": ("integer", "默认 10", False)}, geo_search),
    ("omics_archives_pride_project", "PRIDE 按 accession 取蛋白质组项目。",
     {"accession": ("string", "如 PXD000001", True)}, pride_project),
    ("omics_archives_biostudies_search", "BioStudies/ArrayExpress 检索。",
     {"query": ("string", "检索词", True), "max_results": ("integer", "默认 10", False)}, biostudies_search),

    ("human_genetics_variant_phenotypes", "按 rsID 取变异关联的性状与 p 值（Ensembl variation；GWAS Catalog 旧 REST 已下线）。",
     {"rs_id": ("string", "如 rs7412", True), "max_results": ("integer", "默认 20", False)}, variant_phenotypes),

    ("cancer_models_cbioportal_studies", "列/筛 cBioPortal 研究。",
     {"keyword": ("string", "关键词过滤，可空", False), "max_results": ("integer", "默认 20", False)}, cbioportal_studies),
    ("cancer_models_cbioportal_mutations", "取某研究中某基因的突变（自动解析该研究的突变分子谱）。",
     {"study_id": ("string", "如 brca_tcga", True), "entrez_gene_id": ("integer", "Entrez 基因 ID", True),
      "profile_id": ("string", "可选，指定分子谱 ID", False),
      "sample_list_id": ("string", "可选，默认由谱 ID 推导为 <study>_all", False),
      "max_results": ("integer", "默认 50", False)}, cbioportal_mutations),

    ("cellguide_cellxgene_collections", "CELLxGENE Discover 列公开数据集集合。",
     {"query": ("string", "可选过滤", False), "max_results": ("integer", "默认 10", False)}, cellxgene_datasets),
    ("cellguide_search_cell_types", "按名称检索 Cell Ontology 细胞类型（OLS4/CL），返回 CL ID 与描述。",
     {"query": ("string", "如 T cell", True), "max_results": ("integer", "默认 15", False)}, cellguide_cell_type),

    ("chemistry_pubchem_search", "PubChem 按名称/SMILES/InChIKey 解析 CID。",
     {"query": ("string", "查询值", True), "namespace": ("string", "name/smiles/inchikey", False),
      "max_results": ("integer", "默认 10", False)}, pubchem_search),
    ("chemistry_pubchem_properties", "PubChem 按 CID 取分子属性。",
     {"cid": ("integer", "PubChem CID", True)}, pubchem_properties),
    ("chemistry_rhea_reaction", "Rhea 按反应 ID 取方程式与参与者。",
     {"rhea_id": ("string", "如 10000", True)}, rhea_reaction),

    ("clinical_genomics_civic_search", "CIViC GraphQL 检索癌症证据条目。",
     {"query": ("string", "如 BRAF V600E melanoma", True)}, civic_search),
    ("clinical_genomics_opentargets_disease_targets", "Open Targets 取疾病关联靶点。",
     {"efo_id": ("string", "如 EFO_0000305", True)}, opentargets_targets),

    ("drug_regulatory_openfda_labels", "openFDA 检索药品说明书。",
     {"search": ("string", "如 openfda.brand_name:\"Keytruda\"", True),
      "max_results": ("integer", "默认 3", False), "api_key": ("string", "可选", False)}, openfda_labels),
    ("drug_regulatory_openfda_drugsfda", "openFDA Drugs@FDA 检索申请记录。",
     {"search": ("string", "如 openfda.brand_name:\"Keytruda\"", True),
      "max_results": ("integer", "默认 3", False)}, openfda_drugsfda),

    ("literature_graph_openalex_search", "OpenAlex 跨学科文献检索。",
     {"query": ("string", "检索词", True), "max_results": ("integer", "默认 10", False),
      "year_from": ("integer", "起始年份，可选", False)}, openalex_search),
    ("literature_graph_arxiv_search", "arXiv 检索（返回 Atom XML 片段）。",
     {"query": ("string", "如 all:\"protein folding\"", True), "start": ("integer", "默认 0", False),
      "max_results": ("integer", "默认 10", False)}, arxiv_search),
]


def tool_specs():
    specs = []
    for name, desc, params, _fn in TOOLS:
        props, required = {}, []
        for pname, (ptype, pdesc, preq) in params.items():
            props[pname] = {"type": ptype, "description": pdesc}
            if preq:
                required.append(pname)
        specs.append({"name": name, "description": desc,
                      "inputSchema": {"type": "object", "properties": props,
                                      "required": required,
                                      "additionalProperties": False}})
    return specs


HANDLERS = {name: fn for name, _d, _p, fn in TOOLS}


# --------------------------------------------------------------------------
# MCP stdio 循环
# --------------------------------------------------------------------------
def send(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(req):
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "biomedical", "version": "1.0.0"},
            "instructions": ("生物医学模式的公开数据源本地实现，直连公共 REST API，"
                             "不依赖任何私有网关或 token。")}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tool_specs()}}
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        fn = HANDLERS.get(name)
        if not fn:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32602, "message": "unknown tool: %s" % name}}
        try:
            result = fn(args)
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text",
                             "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                "isError": False}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": "调用失败：%s" % exc}],
                "isError": True}}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if rid is None:
        return None
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": "method not found: %s" % method}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        resp = handle(req)
        if resp is not None:
            send(resp)


if __name__ == "__main__":
    main()
