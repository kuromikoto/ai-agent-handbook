#!/usr/bin/env python3
"""构建前把分散的 Markdown 汇总到 docs/，供 MkDocs 使用。

仓库里 md 分散在根目录和 00-preface/ ~ 07-conclusion/ 各篇目录，
而 MkDocs 要求 docs_dir 必须是配置文件的子目录，不能是仓库根。
本脚本在构建时临时生成 docs/，不改动仓库原有结构。

用法：python scripts/mkdocs_prepare.py
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# 需要汇总的目录（章/篇目录 + 图片资源）
CHAPTER_RE = re.compile(r"^\d{2}-")          # 00-preface, 01-architecture ...
ASSET_DIRS = {"assets"}
# 根目录只搬 md，其余文件（LICENSE、配置文件等）不进 docs
SKIP_FILES = {"mkdocs.yml", "requirements.txt", ".python-version", "python-version"}


def main():
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)

    n = 0

    # 1) 根目录的 md
    for p in sorted(ROOT.glob("*.md")):
        if p.name in SKIP_FILES:
            continue
        shutil.copy2(p, DOCS / p.name)
        n += 1

    # 2) 各篇/章目录
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or d.name == DOCS.name:
            continue
        if d.name.startswith(".") or d.name in {"scripts", "dist", "site", "book", "docs"}:
            continue
        if not (CHAPTER_RE.match(d.name) or d.name in ASSET_DIRS):
            continue
        shutil.copytree(d, DOCS / d.name, dirs_exist_ok=True)
        n += sum(1 for _ in (DOCS / d.name).rglob("*.md"))

    # 3) 为缺少 README.md 的篇目录补一个索引页
    #    README.md 会被 MkDocs 渲染成 index.html，这样 README 里
    #    [架构篇](./01-architecture/) 这类目录链接才能正常跳转。
    for d in sorted(DOCS.iterdir()):
        if not d.is_dir() or (d / "README.md").exists() or (d / "index.md").exists():
            continue
        cands = sorted(d.glob("*.md"))
        if not cands:
            continue
        intro = next((f for f in cands if "导读" in f.name), cands[0])
        shutil.copy2(intro, d / "README.md")
        print(f"[mkdocs_prepare] {d.name}/README.md <- {intro.name}")

    if n == 0:
        print("[mkdocs_prepare] 没有找到任何 .md，检查仓库结构", file=sys.stderr)
        return 1

    print(f"[mkdocs_prepare] 已生成 {DOCS}，共 {n} 个 md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
