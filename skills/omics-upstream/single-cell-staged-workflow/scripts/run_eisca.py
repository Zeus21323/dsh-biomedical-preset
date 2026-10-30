#!/usr/bin/env python3
"""检查固定Earlham流程并生成计划；--execute才调用Nextflow，--resume核对旧计划。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

PIPELINE = "eisca"
COMMIT = "e6953759e8153c31a92202e3f452f1bcbf0f9d08"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def run(config, out, execute=False, resume=False):
    import jsonschema
    cfg = json.loads(config.read_text(encoding="utf-8"))
    require(isinstance(cfg, dict) and isinstance(cfg.get("params"), dict), "配置需含params对象")
    for key in ("repo", "question", "design_notes", "profile"):
        require(isinstance(cfg.get(key), str) and cfg[key].strip(), f"缺少字段：{key}")
    require(re.fullmatch(r"[A-Za-z0-9_,.-]+", cfg["profile"]) is not None, "profile只能是已核实的名称列表")
    repo = (config.parent / cfg["repo"]).resolve()
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    require(head == COMMIT, "源码版本未适配")
    require(not subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], text=True).strip(), "上游已跟踪文件有修改")
    schema = json.loads((repo / "nextflow_schema.json").read_text())
    defs = schema.get("definitions", schema.get("$defs", {}))
    fields = {}
    for group in defs.values():
        fields.update(group.get("properties", {}))
    params = dict(cfg["params"])
    require(not set(params) - set(fields), "存在当前模式未知参数")
    require(not any(k in params for k in ("outdir", "run_analyses", "skip_analyses")), "outdir由包装器固定，内部阶段字段不可手工注入")
    phases = params.get("analyses", "").split(",")
    require(phases and set(phases) <= {"primary", "secondary", "tertiary"} and len(phases) == len(set(phases)), "必须显式选择primary/secondary/tertiary，不默认全跑")
    require(phases == sorted(phases, key=lambda x: ["primary", "secondary", "tertiary"].index(x)), "阶段顺序无效")
    require("input" in params, "固定上游仍要求样本表，已有h5ad也不能省略样本元数据")
    if "primary" not in phases:
        require(bool(params.get("h5ad")), "从下游继续需要h5ad")
    if PIPELINE == "eisca" and "primary" in phases:
        require(params.get("protocol") and params["protocol"] != "auto", "需要从建库记录确认protocol")
        require(params.get("aligner") in {"alevin", "star", "kallisto"}, "所选aligner未适配")
        require(params.get("fasta") and params.get("gtf"), "原始分析需要FASTA与GTF")
    if PIPELINE == "eista":
        require(params.get("technology") in {"vizgen", "xenium"}, "EISTA只适配vizgen/xenium")
    files = {"config": sha(config), "schema": sha(repo / "nextflow_schema.json")}
    for key, value in list(params.items()):
        if isinstance(value, str):
            require(not any(c in value for c in "\n\r\x00;$|&`<>"), f"参数{key}含shell控制字符，需显式安全适配")
        if fields[key].get("exists") is True:
            path = (config.parent / value).resolve()
            require(path.exists(), f"输入不存在：{key}")
            params[key] = str(path)
            if path.is_file():
                files[key] = sha(path)
    samplepath = Path(params["input"])
    with samplepath.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = [{k: v for k, v in r.items() if v != ""} for r in reader]
    require(rows and header and len(header) == len(set(header)) and all(None not in r and all(v is not None for v in r.values()) for r in rows), "样本表为空、列数错误或重复表头")
    sample_schema = json.loads((repo / "assets/schema_input.json").read_text())
    properties = sample_schema["items"]["properties"]
    # 样本路径相对于原CSV；下游阶段只需真实样本身份，不强制捏造FASTQ/图像路径。
    if "primary" in phases:
        jsonschema.Draft7Validator(sample_schema).validate(rows)
    else:
        require(all(r.get("sample") and not re.search(r"\s", r["sample"]) for r in rows), "样本表缺少有效sample")
    inventory = []
    for i, row in enumerate(rows):
        require(not set(row) - set(properties), "样本表含未知字段")
        for key, value in list(row.items()):
            if properties[key].get("exists") is True:
                path = (samplepath.parent / value).resolve()
                require(path.exists(), f"样本{i + 1}的{key}不存在")
                row[key] = str(path)
                if path.is_file():
                    files[f"sample:{i}:{key}"] = sha(path)
                else:
                    inventory.append({"sample": i, "field": key, "path": str(path),
                        "entries": [[str(p.relative_to(path)), p.stat().st_size, p.stat().st_mtime_ns]
                                    for p in sorted(path.rglob("*")) if p.is_file()]})
    require(not out.is_symlink(), "输出不能是符号链接")
    out = out.resolve()
    params["outdir"] = str(out / "results")
    params["input"] = str(out / "samplesheet.csv")
    # 原生JSON Schema检查类型/枚举；文件存在性已另查，不擅自改科学参数。
    jsonschema.Draft7Validator(schema).validate(params)
    fingerprint = hashlib.sha256(json.dumps({"params": params, "files": files, "inventory": inventory,
        "commit": head, "profile": cfg["profile"]}, sort_keys=True).encode()).hexdigest()
    if resume:
        require(execute and (out / "plan.json").is_file(), "恢复需--execute和已有plan.json")
        old = json.loads((out / "plan.json").read_text())
        require(old["fingerprint"] == fingerprint, "输入、参数或数据目录记录改变，拒绝复用旧计划")
    else:
        require(not out.exists() and not out.is_symlink(), "输出已存在；恢复请显式使用--resume")
        out.mkdir(parents=True)
    with (out / "samplesheet.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    (out / "params.json").write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    command = ["nextflow", "run", str(repo), "-profile", cfg["profile"], "-params-file", str(out / "params.json"),
               "-work-dir", str(out / "work"), "-with-report", str(out / "execution_report.html"),
               "-with-trace", str(out / "trace.tsv"), "-with-timeline", str(out / "timeline.html")]
    if resume:
        command += ["-resume"]
    plan = {"pipeline": PIPELINE, "commit": head, "status": "planned_not_run", "fingerprint": fingerprint,
            "input_sha256": files, "directory_inventory": inventory, "config": cfg, "command": command,
            "limitations": ["目录按路径/大小/mtime记录，不是逐文件内容指纹", "运行环境、远程下载与科学产物需要单独检查"]}
    def save():
        (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save()
    if execute:
        require(shutil.which("nextflow"), "未安装Nextflow；计划已保存，未运行")
        plan["status"] = "running"
        save()
        try:
            with (out / "engine.log").open("a", encoding="utf-8") as log:
                subprocess.run(command, cwd=out, stdout=log, stderr=subprocess.STDOUT, check=True)
            plan["status"] = "engine_completed_outputs_unverified"
            require((out / "trace.tsv").is_file(), "缺少执行trace，不能确认流程任务完成")
        except Exception:
            plan["status"] = "failed"
            raise
        finally:
            save()
    return plan


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--resume", action="store_true")
    a = p.parse_args(argv)
    try:
        print(run(a.config, a.out_dir, a.execute, a.resume)["status"])
        return 0
    except Exception as e:
        print(f"{PIPELINE}失败：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
