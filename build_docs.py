#!/usr/bin/env python3
"""把仓库里的 Markdown 构建成静态站点，输出 dist/。"""
import html
import os
import re
import shutil
import sys
from pathlib import Path
from string import Template

import markdown
from pygments.formatters import HtmlFormatter

ROOT = Path(__file__).resolve().parents[1]
# md 放在 docs/ 就用 docs/，散在根目录就扫根目录
DOCS = ROOT / "docs" if (ROOT / "docs").is_dir() else ROOT
OUT = ROOT / "dist"
SITE_NAME = os.environ.get("SITE_NAME", ROOT.name)
SKIP = {".git", ".github", "scripts", "node_modules", "dist", "site",
        "__pycache__", ".venv", "venv"}

TEMPLATE = Template("""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title><style>$css</style></head>
<body><div class="wrap">
<aside class="nav"><div class="site">$site</div><ul>$nav</ul></aside>
<main class="content">$content</main>
</div></body></html>""")

BASE_CSS = """
* { box-sizing: border-box; }
body { margin:0; font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
       color:#24292f; line-height:1.7; }
.wrap { display:flex; max-width:1200px; margin:0 auto; }
.nav { flex:0 0 260px; padding:24px 16px; border-right:1px solid #eaeef2;
       height:100vh; overflow:auto; position:sticky; top:0; }
.nav .site { font-weight:700; margin-bottom:16px; }
.nav ul { list-style:none; margin:0; padding:0; }
.nav a { display:block; padding:4px 8px; border-radius:6px; font-size:14px;
         color:#57606a; text-decoration:none; }
.nav a:hover { background:#f3f4f6; }
.nav a.active { background:#ddf4ff; color:#0969da; font-weight:600; }
.content { flex:1; min-width:0; max-width:820px; padding:32px 40px; }
h1 { font-size:2em; border-bottom:1px solid #eaeef2; padding-bottom:.3em; }
h2 { font-size:1.5em; border-bottom:1px solid #eaeef2; padding-bottom:.3em; }
code { background:#f6f8fa; padding:.2em .4em; border-radius:6px; font-size:85%; }
pre { background:#f6f8fa; padding:16px; border-radius:6px; overflow:auto; }
blockquote { margin:0; padding:0 1em; color:#57606a; border-left:.25em solid #d0d7de; }
table { border-collapse:collapse; } th,td { border:1px solid #d0d7de; padding:6px 13px; }
img { max-width:100%; }
@media (max-width:800px) { .wrap{display:block;} .nav{height:auto;position:static;
  border-right:none;border-bottom:1px solid #eaeef2;} .content{padding:20px;} }
"""


def collect_md():
    return [p.relative_to(DOCS) for p in sorted(DOCS.rglob("*.md"))
            if not any(x in SKIP or x.startswith(".") for x in p.relative_to(DOCS).parts)]


def out_path(rel):
    if rel.parent == Path(".") and rel.stem.lower() in ("readme", "index"):
        return OUT / "index.html"
    return OUT / rel.parent / rel.stem / "index.html"


def url_of(rel):
    p = out_path(rel).relative_to(OUT)
    return "/" if str(p.parent) == "." else f"/{p.parent.as_posix()}/"


def title_of(text, rel):
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else rel.stem.replace("-", " ").title()


def rewrite_links(html_str):
    """把 .md 之间的链接改写成 pretty URL（仅处理同级链接）。"""
    def fix(m):
        raw = m.group(1)
        if raw.startswith(("http://", "https://", "mailto:", "#")):
            return m.group(0)
        path, _, frag = raw.partition("#")
        if not path.endswith(".md"):
            return m.group(0)
        path = path[:-3].replace("./", "").lstrip("/")
        suffix = f"#{frag}" if frag else ""
        return f'href="/{"" if path in ("", "index", "README") else path + "/"}{suffix}"'
    return re.sub(r'href="([^"]+\.md(?:#[^"]*)?)"', fix, html_str)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    mds = collect_md()
    if not mds:
        print(f"[build_docs] 在 {DOCS} 下没找到 .md 文件", file=sys.stderr)
        return 1

    css = HtmlFormatter(style="default").get_style_defs(".codehilite") + BASE_CSS
    nav = "\n".join(
        f'<li><a href="{url_of(r)}" data-url="{url_of(r)}">{html.escape(r.stem)}</a></li>'
        for r in mds)

    for rel in mds:
        text = (DOCS / rel).read_text(encoding="utf-8")
        body = rewrite_links(markdown.markdown(
            text, extensions=["extra", "codehilite", "toc"]))
        url = url_of(rel)
        dest = out_path(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(TEMPLATE.substitute(
            title=html.escape(title_of(text, rel)), site=html.escape(SITE_NAME),
            nav=nav.replace(f'data-url="{url}"', f'data-url="{url}" class="active"'),
            content=body, css=css), encoding="utf-8")
        print(f"[build_docs] {rel} -> {dest.relative_to(ROOT)}")

    for asset in ("assets", "static", "images"):
        if (DOCS / asset).is_dir():
            shutil.copytree(DOCS / asset, OUT / asset, dirs_exist_ok=True)

    print(f"[build_docs] 完成，共 {len(mds)} 页，输出 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
