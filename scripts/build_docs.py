#!/usr/bin/env python3
"""把仓库里的 Markdown 构建成静态站点，输出 dist/。

- 保持 pretty URL（xx/yy.md -> /xx/yy/），与已发布的链接结构一致
- 左侧导航按「篇」分组、可折叠、自然排序（第 10 章排在第 9 章之后）
- 导航文字取 md 的一级标题，而非文件名
- 非 md 资源（图片等）按原结构拷贝，保证 ../assets/... 相对路径可用
"""
import html
import os
import re
import posixpath
import shutil
import sys
from pathlib import Path
from string import Template

import markdown
from pygments.formatters import HtmlFormatter

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" if (ROOT / "docs").is_dir() else ROOT
OUT = ROOT / "dist"
SITE_NAME = os.environ.get("SITE_NAME", "AI Agent HandBook")

# 构建时不参与扫描的文件/目录
ROOT_SKIP = {".git", ".github", "scripts", "node_modules", "dist", "book",
             "site", "__pycache__", ".venv", "venv", "build_docs.py",
             "requirements.txt"}
# 导航里不显示（仍会生成页面）
HIDE_FROM_NAV = {"README_EN"}
# 一级分组显示名（键为目录名）
GROUP_NAMES = {
    "00-preface": "前言",
    "01-architecture": "架构篇",
    "02-build": "构建篇",
    "03-run": "运行篇",
    "04-governance": "治理篇",
    "05-optimization": "调优篇",
    "06-case-study": "案例篇",
    "07-conclusion": "结语",
}
ROOT_GROUP = "全书概览"

TEMPLATE = Template("""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title><style>$css</style></head>
<body><div class="wrap">
<aside class="nav">
<div class="site">$site</div>
<input id="q" class="filter" type="search" placeholder="过滤章节…" autocomplete="off">
$nav
</aside>
<main class="content">$content</main>
</div>
<script>$js</script></body></html>""")

BASE_CSS = """
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
       color:#24292f; line-height:1.75; }
.wrap { display:flex; max-width:1320px; margin:0 auto; }

.nav { flex:0 0 300px; padding:20px 12px 60px; border-right:1px solid #eaeef2;
       height:100vh; overflow:auto; position:sticky; top:0; }
.nav .site { font-weight:700; font-size:16px; margin:0 8px 12px; }
.nav .filter { width:calc(100% - 16px); margin:0 8px 14px; padding:7px 10px;
       font-size:13px; border:1px solid #d0d7de; border-radius:6px; background:#f6f8fa;
       outline:none; font-family:inherit; }
.nav .filter:focus { background:#fff; border-color:#0969da; box-shadow:0 0 0 3px rgba(9,105,218,.15); }

.nav details { margin-bottom:2px; }
.nav summary { cursor:pointer; list-style:none; padding:6px 8px; border-radius:6px;
       font-size:13px; font-weight:600; color:#1f2328; user-select:none; }
.nav summary::-webkit-details-marker { display:none; }
.nav summary::before { content:"\\25B8"; display:inline-block; width:14px;
       color:#8c959f; transition:transform .15s; }
.nav details[open] > summary::before { transform:rotate(90deg); }
.nav summary:hover { background:#f3f4f6; }

.nav ul { list-style:none; margin:0; padding:0 0 6px; }
.nav li { margin:1px 0; }
.nav a { display:block; padding:5px 8px 5px 22px; border-radius:6px; font-size:13.5px;
       color:#57606a; text-decoration:none; line-height:1.5; }
.nav a:hover { background:#f3f4f6; color:#1f2328; }
.nav a.active { background:#ddf4ff; color:#0969da; font-weight:600;
       box-shadow:inset 2px 0 0 #0969da; }

.content { flex:1; min-width:0; max-width:900px; padding:36px 44px 80px; }
.content h1 { font-size:2em; border-bottom:1px solid #eaeef2; padding-bottom:.3em; margin-top:0; }
.content h2 { font-size:1.5em; border-bottom:1px solid #eaeef2; padding-bottom:.3em; margin-top:2em; }
.content h3 { font-size:1.2em; margin-top:1.6em; }
code { background:#f6f8fa; padding:.2em .4em; border-radius:6px; font-size:85%; }
pre { background:#f6f8fa; padding:16px; border-radius:6px; overflow:auto; }
blockquote { margin:0; padding:0 1em; color:#57606a; border-left:.25em solid #d0d7de; }
table { border-collapse:collapse; display:block; overflow:auto; max-width:100%; }
th,td { border:1px solid #d0d7de; padding:6px 13px; }
th { background:#f6f8fa; }
img { max-width:100%; }
hr { border:0; border-top:1px solid #eaeef2; margin:2em 0; }
@media (max-width:860px) {
  .wrap { display:block; }
  .nav { width:100%; height:auto; position:static; border-right:none;
         border-bottom:1px solid #eaeef2; padding-bottom:20px; }
  .content { padding:20px; }
}
"""

JS = """
(function(){
  var a = document.querySelector('.nav a.active');
  if (a) {
    var d = a.closest('details');
    if (d) { d.open = true; }
    var box = document.querySelector('.nav');
    box.scrollTop = a.offsetTop - box.clientHeight / 2;
  }
  var q = document.getElementById('q');
  var items = [].slice.call(document.querySelectorAll('.nav li'));
  var groups = [].slice.call(document.querySelectorAll('.nav details'));
  q.addEventListener('input', function(){
    var v = this.value.trim().toLowerCase();
    items.forEach(function(li){
      li.style.display = (!v || li.textContent.toLowerCase().indexOf(v) >= 0) ? '' : 'none';
    });
    groups.forEach(function(d){ if (v) { d.open = true; } });
  });
})();
"""


def is_skipped(rel: Path) -> bool:
    if any(p in ROOT_SKIP for p in rel.parts):
        return True
    return any(p.startswith(".") for p in rel.parts[:-1])


def collect_md():
    out = []
    for p in sorted(DOCS.rglob("*.md")):
        rel = p.relative_to(DOCS)
        if not is_skipped(rel):
            out.append(rel)
    return out


def nat_key(s: str):
    """自然排序：第 10 章排在 第 9 章 之后。"""
    return tuple((0, int(t)) if t.isdigit() else (1, t.lower())
                 for t in re.split(r"(\d+)", s))


def dest_of(rel: Path) -> Path:
    if rel.parent == Path(".") and rel.stem.lower() in ("readme", "index"):
        return OUT / "index.html"
    return OUT / rel.parent / rel.stem / "index.html"


def url_of(rel: Path) -> str:
    p = dest_of(rel).relative_to(OUT)
    return "/" if str(p.parent) == "." else f"/{p.parent.as_posix()}/"


def clean_inline(s: str) -> str:
    return re.sub(r"[*_`~]", "", s).strip()


def title_of(text: str, rel: Path) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        return clean_inline(m.group(1))
    return rel.stem.replace("-", " ").title()


def rewrite_assets(html_str: str, rel: Path):
    """把 ../assets/x.png 这类相对路径按 md 所在目录解析成 /assets/x.png。

    pretty URL 让页面多了一层目录（xx/yy.md -> /xx/yy/），
    若不改写，../ 会退错层级导致图片 404。
    """
    def fix(m):
        attr, raw = m.group(1), m.group(2)
        if raw.startswith(("http://", "https://", "data:", "//", "/", "#")):
            return m.group(0)
        norm = posixpath.normpath((rel.parent.as_posix() + "/" + raw).lstrip("/"))
        return f'{attr}="/{norm}"'
    return re.sub(r'(src)="([^"]+)"', fix, html_str)


def rewrite_md_links(html_str: str, rel: Path):
    def fix(m):
        raw = m.group(1)
        if raw.startswith(("http://", "https://", "mailto:", "#", "/")):
            return m.group(0)
        path, _, frag = raw.partition("#")
        if not path.lower().endswith(".md"):
            return m.group(0)
        target = Path(re.sub(r"/+", "/", (rel.parent / path).as_posix()).lstrip("/"))
        try:
            resolved = (DOCS / target).resolve().relative_to(DOCS.resolve())
        except ValueError:
            return m.group(0)
        if not (DOCS / resolved).exists():
            return m.group(0)
        return f'href="{url_of(resolved)}{"#" + frag if frag else ""}"'
    return re.sub(r'href="([^"]+\.md(?:#[^"]*)?)"', fix, html_str)


def build_nav(mds, current: Path):
    groups, roots = {}, []
    for rel in mds:
        if rel.stem in HIDE_FROM_NAV:
            continue
        if rel.parent == Path("."):
            roots.append(rel)
        else:
            groups.setdefault(rel.parent.as_posix(), []).append(rel)

    def li(rel, label):
        url = url_of(rel)
        cls = ' class="active"' if rel == current else ""
        return f'<li><a href="{url}"{cls}>{html.escape(label)}</a></li>'

    parts = []
    if roots:
        roots.sort(key=lambda r: (url_of(r) != "/", nat_key(r.stem)))
        parts.append(
            f'<details><summary>{html.escape(ROOT_GROUP)}</summary><ul>'
            + "".join(li(r, title_of((DOCS / r).read_text(encoding="utf-8"), r)) for r in roots)
            + "</ul></details>")

    for g in sorted(groups, key=nat_key):
        items = sorted(groups[g],
                       key=lambda r: (r.stem.lower() not in ("readme", "index"),
                                      nat_key(r.stem)))
        body = "".join(
            li(r, title_of((DOCS / r).read_text(encoding="utf-8"), r)) for r in items)
        open_attr = " open" if current.parent.as_posix() == g else ""
        name = GROUP_NAMES.get(g, g)
        parts.append(f'<details{open_attr}><summary>{html.escape(name)}</summary>'
                     f'<ul>{body}</ul></details>')
    return "".join(parts)


def copy_assets(mds):
    md_set = {str(DOCS / r) for r in mds}
    for p in DOCS.rglob("*"):
        if not p.is_file() or str(p) in md_set:
            continue
        rel = p.relative_to(DOCS)
        if is_skipped(rel):
            continue
        d = OUT / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, d)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    mds = collect_md()
    if not mds:
        print(f"[build_docs] 在 {DOCS} 下没找到 .md 文件", file=sys.stderr)
        return 1

    css = HtmlFormatter(style="default").get_style_defs(".codehilite") + BASE_CSS
    titles = {}
    for rel in mds:
        titles[rel] = title_of((DOCS / rel).read_text(encoding="utf-8"), rel)

    for rel in mds:
        text = (DOCS / rel).read_text(encoding="utf-8").replace("\u00a0", " ")
        body = rewrite_md_links(rewrite_assets(markdown.markdown(
            text, extensions=["extra", "codehilite", "toc", "tables"]), rel), rel)
        dest = dest_of(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(TEMPLATE.substitute(
            title=html.escape(titles[rel]), site=html.escape(SITE_NAME),
            nav=build_nav(mds, rel), content=body, css=css, js=JS),
            encoding="utf-8")
        print(f"[build_docs] {rel} -> {dest.relative_to(ROOT)}")

    copy_assets(mds)
    print(f"[build_docs] 完成，共 {len(mds)} 页，输出 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
