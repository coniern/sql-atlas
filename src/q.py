"""命令行 SQL 练习器：把 SQL 跑在 atlas.db 上，输出对齐的表格。

用法：
    python src/q.py "SELECT * FROM products LIMIT 5"
    python src/q.py -f sql/03_select.sql        # 跑整个文件
    python src/q.py                             # 进交互模式，逐条粘贴
    python src/q.py --explain "SELECT ..."      # 看执行计划

设计上只依赖标准库，不装任何包也能用 —— 学 SQL 不该先学装环境。
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import unicodedata
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "atlas.db"


def _width(s: str) -> int:
    """中文字符占两格，算显示宽度时要单独处理，否则表格会歪。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def _pad(s: str, w: int, align: str = "left") -> str:
    gap = w - _width(s)
    return (" " * gap + s) if align == "right" else (s + " " * gap)


def render(cur: sqlite3.Cursor, max_rows: int = 40) -> str:
    cols = [d[0] for d in cur.description] if cur.description else []
    if not cols:
        return "(无返回结果)"
    rows = cur.fetchmany(max_rows + 1)
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]

    cells = [[("NULL" if v is None else str(v)) for v in r] for r in rows]
    widths = [_width(c) for c in cols]
    for r in cells:
        for i, v in enumerate(r):
            widths[i] = max(widths[i], _width(v))

    # 数字列右对齐，看起来才像表格
    numeric = []
    for i, c in enumerate(cols):
        sample = [r[i] for r in rows if r[i] is not None][:20]
        numeric.append(bool(sample) and all(isinstance(v, (int, float)) for v in sample))

    line = "┌" + "┬".join("─" * (w + 2) for w in widths) + "┐"
    head = "│ " + " │ ".join(_pad(c, widths[i]) for i, c in enumerate(cols)) + " │"
    sep = "├" + "┼".join("─" * (w + 2) for w in widths) + "┤"
    body = [
        "│ " + " │ ".join(_pad(v, widths[i], "right" if numeric[i] else "left")
                          for i, v in enumerate(r)) + " │"
        for r in cells
    ]
    tail = "└" + "┴".join("─" * (w + 2) for w in widths) + "┘"

    out = [line, head, sep, *body, tail]
    n = cur.rowcount if cur.rowcount and cur.rowcount > 0 else len(rows)
    note = f"{len(rows)} 行"
    if truncated:
        note += f"（已截断，实际更多）"
    out.append(f"→ {note}")
    return "\n".join(out)


def run(conn: sqlite3.Connection, sql: str, max_rows: int = 40) -> None:
    stmt = sql.strip().rstrip(";")
    if not stmt:
        return
    cur = conn.cursor()
    try:
        cur.execute(stmt)
        if cur.description:
            print(render(cur, max_rows))
        else:
            conn.commit()
            print(f"→ 执行成功，影响 {cur.rowcount} 行")
    except sqlite3.Error as e:
        print(f"❌ {type(e).__name__}: {e}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="atlas.db 的 SQL 练习器")
    ap.add_argument("sql", nargs="?", help="要执行的 SQL；省略则进交互模式")
    ap.add_argument("-f", "--file", help="执行一个 .sql 文件")
    ap.add_argument("-e", "--explain", action="store_true", help="前置 EXPLAIN QUERY PLAN")
    ap.add_argument("-n", "--limit", type=int, default=40, help="最多显示多少行")
    args = ap.parse_args()

    if not DB.exists():
        sys.exit(f"找不到 {DB}\n先跑：python src/seed.py")

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")

    if args.file:
        for stmt in Path(args.file).read_text(encoding="utf-8").split(";"):
            s = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--"))
            if s.strip():
                print(f"\n── {s.strip().splitlines()[0][:70]}")
                run(conn, s, args.limit)
    elif args.sql:
        sql = args.sql
        if args.explain:
            sql = "EXPLAIN QUERY PLAN " + sql
        run(conn, sql, args.limit)
    else:
        print("交互模式：粘贴 SQL 回车执行，空行退出。")
        buf = []
        for line in sys.stdin:
            if line.strip():
                buf.append(line)
            elif buf:
                run(conn, "".join(buf), args.limit)
                buf = []
        if buf:
            run(conn, "".join(buf), args.limit)

    conn.close()


if __name__ == "__main__":
    main()
