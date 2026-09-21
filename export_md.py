# -*- coding: utf-8 -*-
"""把 index.html 算完的畫面輸出成 Obsidian 可讀的 Markdown。

網頁的數字是 JS 即時算的，直接解析 HTML 只會拿到「—」。
所以這支用無頭瀏覽器把頁面跑起來、等它算完，再走訪 DOM 轉成 md。

用法：python export_md.py
輸出：換屋數字總表_快照.md（vault 內）
"""
import io
import os
import re
import sys
import datetime

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "index.html")
VAULT = r"C:\Second Brain\Obsidian\Joan\生活\財務"
OUT = os.path.join(VAULT, "換屋數字總表_快照.md")

# 轉出來要跳過的裝飾性節點
SKIP_CLASS = {"nav", "u"}


def clean(s):
    """壓掉多餘空白，保留中文標點。"""
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def esc_cell(s):
    return clean(s).replace("|", "｜").replace("\n", " ")


def table_to_md(rows):
    """rows: list of (is_header, [cells])"""
    if not rows:
        return ""
    out = []
    head = None
    body = []
    for is_h, cells in rows:
        if head is None and is_h:
            head = cells
        else:
            body.append(cells)
    if head is None:
        # 沒有 th 的表格：第一列當表頭
        head = body.pop(0) if body else []
    ncol = max([len(head)] + [len(r) for r in body]) if (head or body) else 0
    if ncol == 0:
        return ""
    head = (head + [""] * ncol)[:ncol]
    out.append("| " + " | ".join(esc_cell(c) for c in head) + " |")
    out.append("|" + "---|" * ncol)
    for r in body:
        r = (r + [""] * ncol)[:ncol]
        out.append("| " + " | ".join(esc_cell(c) for c in r) + " |")
    return "\n".join(out)


def extract(page):
    """在瀏覽器裡把每個 section 轉成結構化資料再帶回 Python。"""
    return page.evaluate(
        r"""
() => {
  const out = [];
  const txt = el => (el.innerText || '').replace(/\u00a0/g, ' ').trim();

  document.querySelectorAll('section').forEach(sec => {
    const item = { id: sec.id || '', blocks: [] };

    const walk = (node) => {
      for (const el of node.children) {
        const tag = el.tagName.toLowerCase();

        // 看板另外用 kanban() 抓結構，這裡整塊跳過，
        // 否則泛用走訪會把每張卡片拆成一堆碎片段落。
        if (el.id === 'phases') { item.blocks.push({ t: 'kanban_here' }); continue; }

        const cls = el.className && el.className.baseVal !== undefined
          ? '' : (el.className || '');

        if (tag === 'h2' || tag === 'h3') {
          // 有幾個 h2 只是排版用的小標（inline style 縮小字級），
          // 實際上是上一節的子標題，降成 h3 才不會在大綱裡跟章節平起平坐。
          const styled = (el.getAttribute('style') || '').indexOf('font-size') >= 0;
          item.blocks.push({ t: (tag === 'h2' && styled) ? 'h3' : tag, v: txt(el) });
          continue;
        }
        if (tag === 'table') {
          const rows = [];
          el.querySelectorAll('tr').forEach(tr => {
            const cells = [];
            let isH = false;
            tr.querySelectorAll('th,td').forEach(td => {
              if (td.tagName.toLowerCase() === 'th') isH = true;
              const span = parseInt(td.getAttribute('colspan') || '1', 10);
              cells.push(txt(td));
              for (let i = 1; i < span; i++) cells.push('');
            });
            if (cells.length) rows.push([isH, cells]);
          });
          item.blocks.push({ t: 'table', rows: rows });
          continue;
        }
        if (tag === 'pre') {
          item.blocks.push({ t: 'pre', v: el.textContent.trim() });
          continue;
        }
        // 參數輸入區：把目前值抓出來，別丟掉
        if (tag === 'details') {
          const fields = [];
          el.querySelectorAll('.fld').forEach(f => {
            const lab = f.querySelector('label');
            const inp = f.querySelector('input,select');
            const unit = f.querySelector('.u');
            if (!lab || !inp) return;
            // 折疊起來的 details 內，innerText 會回空字串（它看版面）；
            // textContent 不管顯不顯示都拿得到字。
            const t2 = el2 => el2 ? (el2.textContent || '').replace(/ /g,' ').trim() : '';
            let v = inp.value;
            if (inp.tagName.toLowerCase() === 'select') {
              const o = inp.options[inp.selectedIndex];
              v = o ? o.text : v;
            }
            fields.push([t2(lab), v, unit ? t2(unit) : '']);
          });
          const sum = el.querySelector('summary');
          item.blocks.push({
            t: 'params',
            title: sum ? txt(sum).replace(/^▸\s*/, '') : '參數',
            fields: fields
          });
          continue;
        }
        if (/\b(big|grid)\b/.test(cls)) {
          // 大數字卡片
          const cards = [];
          el.querySelectorAll('.b1').forEach(c => {
            const k = c.querySelector('.k');
            const v = c.querySelector('.v');
            const n = c.querySelector('.n');
            if (k && v) cards.push([txt(k), txt(v), n ? txt(n) : '']);
          });
          if (cards.length) { item.blocks.push({ t: 'cards', cards: cards }); continue; }
        }
        if (/\bnote\b/.test(cls) || /\bsrc\b/.test(cls)) {
          const kind = /\bred\b/.test(cls) ? 'danger'
                     : /\bok\b/.test(cls) ? 'tip'
                     : /\bsrc\b/.test(cls) ? 'src' : 'info';
          item.blocks.push({ t: 'note', kind: kind, v: txt(el) });
          continue;
        }
        if (el.children.length) { walk(el); continue; }
        const s = txt(el);
        if (s) item.blocks.push({ t: 'p', v: s });
      }
    };
    walk(sec);
    out.push(item);
  });
  return out;
}
"""
    )


def kanban(page):
    """搬遷採購看板：每欄一個階段，卡片是 .it，金額在 .amt input 裡。"""
    return page.evaluate(
        r"""
() => {
  const txt = el => el ? (el.innerText || '').replace(/\u00a0/g, ' ').trim() : '';
  const cols = [];
  document.querySelectorAll('#phases .ph').forEach(col => {
    const items = [];
    col.querySelectorAll('.it').forEach(c => {
      const cb  = c.querySelector('input[type=checkbox]');
      const amt = c.querySelector('.amt input');
      const nm  = c.querySelector('.nm');
      const mt  = c.querySelector('.mt');
      // .bd 底下除了 .nm 與 .mv（移動按鈕）之外的那個 div 是備註小字
      let note = '';
      const bd = c.querySelector('.bd');
      if (bd) {
        for (const d of bd.children) {
          if (d.tagName.toLowerCase() === 'div' &&
              !d.classList.contains('nm') && !d.classList.contains('mv')) {
            note = txt(d); break;
          }
        }
      }
      items.push({
        name: txt(nm),
        tag: txt(mt),
        note: note,
        amount: amt ? (parseInt(amt.value, 10) || 0) : 0,
        on: cb ? cb.checked : true,
        must: !!(cb && cb.disabled)
      });
    });
    cols.push({
      phase: txt(col.querySelector('.ph-t')),
      subtotal: txt(col.querySelector('.ph-s')),
      items: items
    });
  });
  return cols;
}
"""
    )


def kanban_md(cols):
    """看板轉成每階段一張表，含小計與「不買」標記。"""
    L = []
    for c in cols:
        head = clean(c["phase"]).replace("\n", "　")
        sub = clean(c.get("subtotal", ""))
        L.append("")
        L.append("**" + head + ("　小計 " + sub if sub else "") + "**")
        L.append("")
        L.append("| 買 | 品項 | 金額 | 搬運 | 備註 |")
        L.append("|---|---|---:|---|---|")
        for it in c["items"]:
            if it["must"]:
                mark = "固定"
            else:
                mark = "✅" if it["on"] else "✖︎"
            L.append("| " + mark
                     + " | " + esc_cell(it["name"])
                     + " | " + format(it["amount"], ",")
                     + " | " + esc_cell(it.get("tag", ""))
                     + " | " + esc_cell(it.get("note", "")) + " |")
    return L


def build_md(secs, cols, today):
    L = []
    for sec in secs:
        for b in sec["blocks"]:
            t = b["t"]
            if t == "kanban_here":
                L.extend(kanban_md(cols))
                continue
            if t == "h2":
                L.append("\n## " + clean(b["v"]))
            elif t == "h3":
                L.append("\n### " + clean(b["v"]))
            elif t == "cards":
                L.append("")
                for k, v, n in b["cards"]:
                    line = "- **" + clean(k) + "**：" + clean(v)
                    if clean(n):
                        line += "　（" + clean(n) + "）"
                    L.append(line)
            elif t == "table":
                md = table_to_md(b["rows"])
                if md:
                    L.append("")
                    L.append(md)
            elif t == "pre":
                L.append("")
                L.append("```")
                L.append(b["v"])
                L.append("```")
            elif t == "params":
                if not b["fields"]:
                    continue
                L.append("")
                L.append("<details>")
                L.append("<summary>" + clean(b["title"]) + "（目前值）</summary>")
                L.append("")
                L.append("| 參數 | 值 | 單位 |")
                L.append("|---|---|---|")
                for lab, v, u in b["fields"]:
                    L.append("| " + esc_cell(lab) + " | " + esc_cell(str(v)) + " | " + esc_cell(u) + " |")
                L.append("")
                L.append("</details>")
            elif t == "note":
                kind = b["kind"]
                if kind == "src":
                    L.append("")
                    L.append("> " + clean(b["v"]).replace("\n", "\n> "))
                else:
                    cal = {"danger": "danger", "tip": "tip", "info": "info"}[kind]
                    body = clean(b["v"])
                    lines = body.split("\n")
                    title = lines[0] if lines else ""
                    rest = lines[1:]
                    L.append("")
                    L.append("> [!" + cal + "] " + title)
                    for r in rest:
                        L.append("> " + r)
            elif t == "p":
                L.append("")
                L.append(clean(b["v"]))

    return "\n".join(L)


def main():
    url = "file:///" + SRC.replace("\\", "/")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        pg.goto(url)
        pg.wait_for_timeout(1200)
        # 確認真的算完了：第一張大卡不能還是「—」
        probe = pg.inner_text("#k_be")
        if "—" in probe or not probe.strip():
            print("頁面尚未算完，抓到：" + repr(probe), file=sys.stderr)
            sys.exit(2)
        secs = extract(pg)
        cols = kanban(pg)
        b.close()

    today = datetime.date.today().isoformat()
    body = build_md(secs, cols, today)

    fm = """---
aliases: [換屋數字快照, 換屋總表快照]
parent: "[[Joan/生活/財務/換屋數字總表_說明]]"
type: reference
status: active
created: {today}
updated: {today}
owner: Joan
verified: {today}
canonical: false
description: 換屋數字總表網頁的純文字快照，給 AI 與全文搜尋用；數字為 {today} 當下的試算結果
---

# 換屋數字總表（純文字快照）

> [!warning] 這份是快照，不是正本
> 正本是可即時重算的網頁 → https://joanzhang45.github.io/fang-calc/
> 本檔給 AI 讀取與 Obsidian 全文搜尋用。**數字是 {today} 當下的值**，
> 改過網頁參數之後要重新匯出，否則這裡會是舊的。
> 重新匯出：在 `fang-calc` 專案跑 `python export_md.py`。
>
> 檔案地圖與各數字的正本歸屬 → [[Joan/生活/財務/換屋數字總表_說明|換屋數字總表]]
""".format(today=today)

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(fm + body + "\n")

    print("寫入：" + OUT)
    print("位元組：" + str(os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
