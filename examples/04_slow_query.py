"""慢查询优化实战：同一需求，从 3 个 SCAN 到索引命中。

跑法：python examples/04_slow_query.py
完整流程对应 docs/14-性能优化实战.md：测量 → 改写 → 建索引 → 验证。
"""

import shutil
import sqlite3
import sys
import time
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "atlas.db"
TMP = DB.parent / "_perf_lab.db"

SLOW = """
SELECT c.city,
       COUNT(DISTINCT c.customer_id)                     AS 金卡客户数,
       COUNT(DISTINCT o.order_id)                        AS 订单数,
       SUM(i.quantity * i.unit_price * (1 - i.discount)) AS 销售额
FROM customers c, orders o, order_items i
WHERE c.customer_id = o.customer_id
  AND i.order_id = o.order_id
  AND c.tier = 'gold'
  AND strftime('%Y', o.ordered_at) = '2024'
  AND o.status IN ('paid','shipped')
GROUP BY c.city
ORDER BY 销售额 DESC
"""

FAST = """
WITH sales AS (
  SELECT order_id, SUM(quantity * unit_price * (1 - discount)) AS amt
  FROM order_items GROUP BY order_id
)
SELECT c.city,
       COUNT(DISTINCT c.customer_id) AS 金卡客户数,
       COUNT(o.order_id)             AS 订单数,
       ROUND(SUM(s.amt), 0)          AS 销售额
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
JOIN sales  s ON s.order_id   = o.order_id
WHERE c.tier = 'gold'
  AND o.ordered_at >= '2024-01-01' AND o.ordered_at < '2025-01-01'
  AND o.status IN ('paid','shipped')
GROUP BY c.city
ORDER BY 销售额 DESC
LIMIT 5
"""


def bench(conn: sqlite3.Connection, sql: str, n: int = 40) -> float:
    conn.execute("SELECT 1").fetchall()
    t = time.perf_counter()
    for _ in range(n):
        conn.execute(sql).fetchall()
    return (time.perf_counter() - t) / n * 1000


def plan(conn: sqlite3.Connection, sql: str) -> str:
    return " | ".join(r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + sql))


def main() -> None:
    if not DB.exists():
        sys.exit("先运行 python src/seed.py")
    shutil.copy(DB, TMP)
    conn = sqlite3.connect(TMP)

    print("=" * 70)
    print("第 0 步 · 测量：先看执行计划，再测耗时")
    print("=" * 70)
    print(f"  计划: {plan(conn, SLOW)}")
    t0 = bench(conn, SLOW)
    print(f"  耗时: {t0:.2f} ms（40 次平均）")
    print("  两个 SCAN = 每次全扫 3000+6048 行")

    print("\n" + "=" * 70)
    print("第 1 步 · 改写：函数包列 → 范围条件；先聚合再 JOIN")
    print("=" * 70)
    t1 = bench(conn, FAST)
    print(f"  改写后: {t1:.2f} ms（快 {t0/t1:.1f}×）")
    print(f"  计划: {plan(conn, FAST)}")

    print("\n" + "=" * 70)
    print("第 2 步 · 建索引：按查询模式设计（等值在前，范围在后）")
    print("=" * 70)
    conn.executescript("""
    CREATE INDEX idx_customers_tier ON customers(tier, city);
    CREATE INDEX idx_orders_cdate   ON orders(customer_id, ordered_at);
    CREATE INDEX idx_items_order    ON order_items(order_id);
    """)
    conn.execute("ANALYZE")
    t2 = bench(conn, FAST)
    print(f"  加索引后: {t2:.2f} ms（比初始快 {t0/t2:.1f}×，比纯改写快 {t1/t2:.1f}×）")
    print(f"  计划: {plan(conn, FAST)}")

    print("\n" + "=" * 70)
    print("第 3 步 · 验证结果正确性（改写不能改变结果！）")
    print("=" * 70)
    slow_top = conn.execute(SLOW + " LIMIT 3").fetchall()
    fast_all = conn.execute(FAST).fetchall()
    fast_top = fast_all[:3]
    match = all(
        a[0] == b[0] and abs(a[3] - b[3]) < 1
        for a, b in zip(slow_top, fast_top)
    )
    for row in fast_top:
        print(f"  {row[0]:<4} 客户{row[1]:>3} 订单{row[2]:>4} 销售额 {row[3]:>12,.0f}")
    print(f"\n  两种写法 TOP3 一致: {'✓ 通过' if match else '✗ 不一致，改写有 bug！'}")

    print("\n" + "=" * 70)
    print("结论：改写（3 个 SCAN→2 个）+ 索引（SCAN→SEARCH）= 量级提升")
    print("守则：先测量 → 每次只改一处 → 保留对照 → 上线前验证结果一致")
    print("=" * 70)

    conn.close()
    TMP.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
