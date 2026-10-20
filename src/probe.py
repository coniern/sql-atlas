"""把文档里要用到的关键查询一次性跑一遍，输出真实结果。

写教程时最容易出的问题是"我记得应该是这样"，这个小工具的作用就是
让文档里每个数字都能被追溯：跑一遍 probe.py，结果与 md 里贴的一致。

用法：python src/probe.py [章节]
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q import DB, render  # noqa: E402

CASES: list[tuple[str, str]] = []


def case(title: str, sql: str) -> None:
    CASES.append((title, sql))


# ══════════════════════ 第 3 章：查询基础 ══════════════════════
case("3.1 订单状态分布", """
SELECT status, COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM orders), 1) AS pct
FROM orders GROUP BY status ORDER BY n DESC
""")

case("3.2 NULL 的三值逻辑：NULL = NULL 是 NULL", """
SELECT NULL = NULL AS "NULL=NULL",
       NULL <> NULL AS "NULL<>NULL",
       NULL IS NULL AS "IS NULL",
       COALESCE(NULL, 'fallback') AS "COALESCE",
       1 + NULL AS "1+NULL"
""")

case("3.3 COUNT(*) 会数 NULL，COUNT(列) 不会", """
SELECT COUNT(*) AS "COUNT(*)",
       COUNT(shipped_at) AS "COUNT( shipped_at )",
       COUNT(*) - COUNT(shipped_at) AS "差=未发货"
FROM orders
""")

case("3.4 WHERE 里用 = NULL 会静默返回 0 行", """
SELECT
  (SELECT COUNT(*) FROM orders WHERE shipped_at = NULL)    AS "错误写法 =",
  (SELECT COUNT(*) FROM orders WHERE shipped_at IS NULL)   AS "正确写法 IS",
  (SELECT COUNT(*) FROM orders WHERE shipped_at IS NOT NULL) AS "已发货"
""")

case("3.5 浮点误差：REAL 存金额的代价", """
SELECT 0.1 + 0.2 AS "0.1+0.2",
       ROUND(0.1 + 0.2, 2) AS "ROUND后",
       0.1 + 0.2 = 0.3 AS "等号判断",
       CAST(19.99 * 100 AS INTEGER) AS "19.99*100 截断"
""")

case("3.6 真实数据的金额合计误差", """
SELECT ROUND(SUM(quantity * unit_price * (1 - discount)), 2) AS "四舍五入",
       SUM(CAST(ROUND(quantity * unit_price * (1 - discount) * 100) AS INTEGER)) / 100.0 AS "按分累加",
       ROUND(SUM(quantity * unit_price * (1 - discount))
             - SUM(CAST(ROUND(quantity * unit_price * (1 - discount) * 100) AS INTEGER)) / 100.0, 6) AS "差额"
FROM order_items
""")

case("3.7 GROUP BY 与 HAVING", """
SELECT tier, COUNT(*) AS 客户数, ROUND(AVG(credit_limit), 0) AS 平均额度
FROM customers
GROUP BY tier
HAVING COUNT(*) > 50
ORDER BY 平均额度 DESC
""")

case("3.8 日期函数：按月统计销售额", """
SELECT strftime('%Y-%m', o.ordered_at) AS 月份,
       COUNT(DISTINCT o.order_id) AS 订单数,
       ROUND(SUM(i.quantity * i.unit_price * (1 - i.discount)), 0) AS 销售额
FROM orders o JOIN order_items i ON i.order_id = o.order_id
WHERE o.status IN ('paid', 'shipped')
  AND o.ordered_at >= '2024-01-01'
GROUP BY 月份 ORDER BY 月份
""")

# ══════════════════════ 第 4 章：JOIN ══════════════════════
case("4.1 INNER JOIN 丢掉没有订单的客户", """
SELECT
  (SELECT COUNT(*) FROM customers) AS 客户总数,
  (SELECT COUNT(DISTINCT customer_id) FROM orders) AS 有订单客户,
  (SELECT COUNT(DISTINCT c.customer_id)
     FROM customers c JOIN orders o ON o.customer_id = c.customer_id) AS INNER_JOIN后
""")

case("4.2 LEFT JOIN：没订单的客户显示 NULL", """
SELECT c.name, c.city, COUNT(o.order_id) AS 订单数
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_id
HAVING COUNT(o.order_id) = 0
ORDER BY c.name LIMIT 5
""")

case("4.3 WHERE 把 LEFT JOIN 变成 INNER JOIN（最经典的坑）", """
SELECT
  (SELECT COUNT(*) FROM customers c
     LEFT JOIN orders o ON o.customer_id = c.customer_id) AS "LEFT JOIN 总行数",
  (SELECT COUNT(*) FROM customers c
     LEFT JOIN orders o ON o.customer_id = c.customer_id
     WHERE o.status = 'paid') AS "加了 WHERE o.status 之后"
""")

case("4.4 一对多 JOIN 导致的行数膨胀", """
SELECT
  (SELECT COUNT(*) FROM orders) AS 订单数,
  (SELECT COUNT(*) FROM orders o JOIN order_items i ON i.order_id = o.order_id) AS JOIN明细后,
  ROUND((SELECT COUNT(*) FROM orders o JOIN order_items i ON i.order_id = o.order_id)
        * 1.0 / (SELECT COUNT(*) FROM orders), 2) AS 膨胀倍数
""")

case("4.5 一对多 JOIN 后对订单级金额求和会翻倍", """
SELECT
  (SELECT ROUND(SUM(amount), 2) FROM payments WHERE is_refund = 0) AS 正确支付总额,
  (SELECT ROUND(SUM(p.amount), 2)
     FROM orders o
     JOIN order_items i ON i.order_id = o.order_id
     JOIN payments p ON p.order_id = o.order_id AND p.is_refund = 0) AS 三表JOIN后,
  ROUND((SELECT SUM(p.amount) FROM orders o
         JOIN order_items i ON i.order_id = o.order_id
         JOIN payments p ON p.order_id = o.order_id AND p.is_refund = 0)
        / (SELECT SUM(amount) FROM payments WHERE is_refund = 0), 2) AS 放大倍数
""")

case("4.6 自连接：同一城市里消费额更高的客户对", """
SELECT a.name AS 客户A, b.name AS 客户B, a.city
FROM customers a
JOIN customers b ON a.city = b.city AND a.customer_id < b.customer_id
WHERE a.tier = 'gold' AND b.tier = 'gold'
ORDER BY a.city LIMIT 5
""")

case("4.7 反连接三兄弟：NOT IN / NOT EXISTS / LEFT JOIN", """
SELECT
  (SELECT COUNT(*) FROM customers c
     WHERE c.customer_id NOT IN (SELECT customer_id FROM orders)) AS "NOT IN",
  (SELECT COUNT(*) FROM customers c
     WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id)) AS "NOT EXISTS",
  (SELECT COUNT(*) FROM customers c
     LEFT JOIN orders o ON o.customer_id = c.customer_id
     WHERE o.order_id IS NULL) AS "LEFT JOIN + IS NULL"
""")

case("4.8 NOT IN 遇 NULL 全盘失效", """
SELECT
  (SELECT COUNT(*) FROM customers c
     WHERE c.customer_id NOT IN (SELECT employee_id FROM employees)) AS "子查询无NULL",
  (SELECT COUNT(*) FROM customers c
     WHERE c.customer_id NOT IN (
        SELECT manager_id FROM employees WHERE manager_id IS NOT NULL)) AS "过滤掉NULL"
""")

# ══════════════════════ 第 6 章：窗口函数 ══════════════════════
case("6.1 每个城市销售额最高的 2 个客户（Top-N per group）", """
WITH s AS (
  SELECT c.customer_id, c.name, c.city,
         SUM(i.quantity * i.unit_price * (1 - i.discount)) AS 销售额
  FROM customers c
  JOIN orders o ON o.customer_id = c.customer_id
  JOIN order_items i ON i.order_id = o.order_id
  WHERE o.status IN ('paid', 'shipped')
  GROUP BY c.customer_id
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY city ORDER BY 销售额 DESC) AS rn
  FROM s
)
SELECT city, name, ROUND(销售额, 0) AS 销售额, rn
FROM ranked WHERE rn <= 2 AND city IN ('深圳','上海','北京')
ORDER BY city, rn
""")

case("6.2 ROW_NUMBER / RANK / DENSE_RANK 的差别", """
WITH v(x) AS (VALUES (100),(100),(90),(80),(80),(80),(70))
SELECT x,
       ROW_NUMBER() OVER (ORDER BY x DESC) AS rn,
       RANK()       OVER (ORDER BY x DESC) AS rnk,
       DENSE_RANK() OVER (ORDER BY x DESC) AS drnk
FROM v
""")

case("6.3 同比环比：LAG 取上月", """
WITH m AS (
  SELECT strftime('%Y-%m', ordered_at) AS ym,
         ROUND(SUM(i.quantity * i.unit_price * (1 - i.discount)), 0) AS 销售额
  FROM orders o JOIN order_items i ON i.order_id = o.order_id
  WHERE o.status IN ('paid','shipped') AND o.ordered_at >= '2024-06-01'
  GROUP BY ym
)
SELECT ym AS 月份, 销售额,
       LAG(销售额) OVER (ORDER BY ym) AS 上月,
       ROUND(销售额 - LAG(销售额) OVER (ORDER BY ym), 0) AS 环比,
       ROUND(100.0 * (销售额 - LAG(销售额) OVER (ORDER BY ym))
             / LAG(销售额) OVER (ORDER BY ym), 1) AS 环比百分比
FROM m ORDER BY ym
""")

case("6.4 累计销售额（running total）与移动平均", """
WITH d AS (
  SELECT date(ordered_at) AS 日期,
         ROUND(SUM(i.quantity * i.unit_price * (1 - i.discount)), 0) AS 当日
  FROM orders o JOIN order_items i ON i.order_id = o.order_id
  WHERE o.status IN ('paid','shipped') AND o.ordered_at >= '2024-11-01'
    AND o.ordered_at < '2024-11-12'
  GROUP BY 日期
)
SELECT 日期, 当日,
       SUM(当日) OVER (ORDER BY 日期) AS 累计,
       ROUND(AVG(当日) OVER (ORDER BY 日期 ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS 三日移动均
FROM d ORDER BY 日期
""")

case("6.5 占比与累计占比：帕累托分析（深圳 TOP 客户）", """
WITH s AS (
  SELECT c.name, c.city,
         SUM(i.quantity * i.unit_price * (1 - i.discount)) AS 销售额
  FROM customers c
  JOIN orders o ON o.customer_id = c.customer_id
  JOIN order_items i ON i.order_id = o.order_id
  WHERE o.status IN ('paid','shipped') AND c.city = '深圳'
  GROUP BY c.customer_id
)
SELECT name AS 客户, ROUND(销售额, 0) AS 销售额,
       ROUND(100.0 * 销售额 / SUM(销售额) OVER (), 1) AS 占比,
       ROUND(100.0 * SUM(销售额) OVER (ORDER BY 销售额 DESC)
             / SUM(销售额) OVER (), 1) AS 累计占比
FROM s ORDER BY 销售额 DESC LIMIT 6
""")

# ══════════════════════ 第 7 章：递归 CTE ══════════════════════
case("7.1 品类树：带上层路径和层级", """
WITH RECURSIVE tree(category_id, name, depth, path) AS (
  SELECT category_id, name, 0, name FROM categories WHERE parent_id IS NULL
  UNION ALL
  SELECT c.category_id, c.name, t.depth + 1, t.path || ' / ' || c.name
  FROM categories c JOIN tree t ON c.parent_id = t.category_id
)
SELECT depth AS 层级, name, path AS 路径 FROM tree ORDER BY path LIMIT 9
""")

case("7.2 某品类的所有子孙（向下查）", """
WITH RECURSIVE sub(id) AS (
  SELECT category_id FROM categories WHERE name = '电子产品'
  UNION ALL
  SELECT c.category_id FROM categories c JOIN sub s ON c.parent_id = s.id
)
SELECT COUNT(*) AS 电子产品子类数 FROM sub
""")

case("7.3 每个员工到 CEO 的汇报链", """
WITH RECURSIVE chain(employee_id, name, title, depth, path) AS (
  SELECT employee_id, name, title, 0, name FROM employees WHERE manager_id IS NULL
  UNION ALL
  SELECT e.employee_id, e.name, e.title, c.depth + 1, c.path || ' → ' || e.name
  FROM employees e JOIN chain c ON e.manager_id = c.employee_id
)
SELECT depth AS 层级, title AS 职位, path AS 汇报链
FROM chain WHERE depth <= 2 ORDER BY depth, path LIMIT 6
""")

case("7.4 用递归算斐波那契（验证递归本身）", """
WITH RECURSIVE fib(n, a, b) AS (
  SELECT 1, 0, 1
  UNION ALL
  SELECT n + 1, b, a + b FROM fib WHERE n < 12
)
SELECT n, a AS fib_n FROM fib
""")

# ══════════════════════ 第 9 章：索引 ══════════════════════
case("9.1 建索引前的执行计划", """
EXPLAIN QUERY PLAN
SELECT * FROM orders WHERE customer_id = 42
""")

case("9.2 索引的真实效果（现场测量）", """
SELECT '见下方 timing 段落'
""")

# ══════════════════════ 第 11 章：注入 ══════════════════════
case("11.1 拼接式查询被注入改写", """
SELECT '见 examples/03_injection_demo.py'
""")


def timed(conn: sqlite3.Connection, sql: str, n: int = 200) -> float:
    t = time.perf_counter()
    for _ in range(n):
        conn.execute(sql).fetchall()
    return (time.perf_counter() - t) / n * 1000


def index_benchmark() -> None:
    """索引章节的核心数据：三类查询，建索引前后各跑 N 次取平均。

    重点保留"半套索引更慢"的实测 —— 这不是 bug，是优化器选了个
    看起来更聪明、实际更蠢的计划。第 9 章会完整拆解。
    """
    tmp = DB.parent / "_bench.db"
    shutil.copy(DB, tmp)
    conn = sqlite3.connect(tmp)

    q_simple = "SELECT * FROM orders WHERE customer_id = 42"
    q_join = """SELECT o.order_id, o.ordered_at, SUM(i.quantity*i.unit_price) AS amt
                FROM orders o JOIN order_items i ON i.order_id=o.order_id
                WHERE o.customer_id = 42 GROUP BY o.order_id"""

    def bench(sql: str, n: int = 300) -> float:
        conn.execute("SELECT 1").fetchall()
        t = time.perf_counter()
        for _ in range(n):
            conn.execute(sql).fetchall()
        return (time.perf_counter() - t) / n * 1000

    def plan(sql: str) -> str:
        return " | ".join(r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + sql))

    print("\n" + "═" * 70)
    print("9.2 索引实测（各跑 300 次取平均，单位 ms）")
    print("═" * 70)

    s0, j0 = bench(q_simple), bench(q_join)
    print(f"  初始状态（无二级索引）")
    print(f"    单表 WHERE      {s0:7.3f} ms   {plan(q_simple)}")
    print(f"    JOIN 聚合       {j0:7.3f} ms   {plan(q_join)}")

    conn.execute("CREATE INDEX idx_orders_customer ON orders(customer_id)")
    conn.execute("ANALYZE")
    s1, j1 = bench(q_simple), bench(q_join)
    print(f"\n  ① 只给 orders(customer_id) 建索引")
    print(f"    单表 WHERE      {s1:7.3f} ms   （{s0/s1:5.1f}× 更快）")
    print(f"    JOIN 聚合       {j1:7.3f} ms   （{j0/j1:5.2f}× —— 反而更慢！）")
    print(f"    计划：{plan(q_join)}")

    conn.execute("CREATE INDEX idx_items_order ON order_items(order_id)")
    conn.execute("ANALYZE")
    s2, j2 = bench(q_simple), bench(q_join)
    print(f"\n  ② 再给 order_items(order_id) 建索引（补齐外键另一侧）")
    print(f"    单表 WHERE      {s2:7.3f} ms")
    print(f"    JOIN 聚合       {j2:7.3f} ms   （比初始快 {j0/j2:5.1f}×，比①快 {j1/j2:5.1f}×）")
    print(f"    计划：{plan(q_join)}")

    print("\n  索引失效：对索引列套函数")
    for q, label in (
        ("SELECT * FROM orders WHERE customer_id = 42", "直接用列"),
        ("SELECT * FROM orders WHERE customer_id + 0 = 42", "列 + 0"),
        ("SELECT * FROM orders WHERE CAST(customer_id AS TEXT) = '42'", "CAST 成文本"),
        ("SELECT * FROM orders WHERE customer_id = '42'", "右值是字符串"),
        ("SELECT * FROM orders WHERE customer_id LIKE '42'", "LIKE 匹配数字串"),
    ):
        print(f"    {label:<18} {plan(q)}")

    print("\n  复合索引的最左前缀：INDEX ON (customer_id, status)")
    conn.execute("DROP INDEX IF EXISTS idx_orders_customer")
    conn.execute("DROP INDEX IF EXISTS idx_items_order")
    conn.execute("DROP INDEX IF EXISTS idx_orders_cover")
    conn.execute("CREATE INDEX idx_orders_cs ON orders(customer_id, status)")
    conn.execute("ANALYZE")
    for q, label in (
        ("SELECT * FROM orders WHERE customer_id = 42", "只查 customer_id"),
        ("SELECT * FROM orders WHERE customer_id = 42 AND status = 'paid'", "两列都用"),
        ("SELECT * FROM orders WHERE status = 'paid'", "只查 status（跳过最左）"),
        ("SELECT * FROM orders WHERE customer_id = 42 ORDER BY status", "顺带消除排序"),
    ):
        print(f"    {label:<22} {plan(q)}")

    print("\n  覆盖索引：查询的列全在索引里，不回表")
    conn.execute("DROP INDEX idx_orders_cs")
    conn.execute("CREATE INDEX idx_orders_cover ON orders(customer_id, status, ordered_at)")
    conn.execute("ANALYZE")
    q_cover = "SELECT customer_id, status, ordered_at FROM orders WHERE customer_id = 42"
    q_back = "SELECT customer_id, status, ordered_at, note FROM orders WHERE customer_id = 42"
    print(f"    三列都在索引里      {plan(q_cover)}")
    print(f"    多查一个 note 列    {plan(q_back)}")

    print("\n  索引的写代价：批量 INSERT 10000 行耗时（含 COMMIT）")
    for label, setup in (
        ("无二级索引", "DROP INDEX IF EXISTS idx_orders_customer"),
        ("有 1 个二级索引", "CREATE INDEX idx_orders_customer ON orders(customer_id)"),
    ):
        conn.execute("DROP INDEX IF EXISTS idx_orders_cover")
        conn.executescript(setup)
        t = time.perf_counter()
        conn.execute("BEGIN")
        conn.executemany(
            "INSERT INTO orders (order_no, customer_id, employee_id, status, ordered_at)"
            " VALUES (?, 1, 1, 'pending', '2024-12-31 10:00:00')",
            [(f"BENCH{i:06d}",) for i in range(10000)],
        )
        conn.execute("COMMIT")
        ms = (time.perf_counter() - t) * 1000
        print(f"    {label:<16} {ms:7.1f} ms / 10000 行")
        # 清理掉这批测试数据，别污染后面的实验
        conn.execute("DELETE FROM orders WHERE order_no LIKE 'BENCH%'")
        conn.commit()

    conn.close()
    tmp.unlink(missing_ok=True)


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    for title, sql in CASES:
        if sql.strip().startswith("SELECT '见"):
            continue
        print("\n" + "═" * 70)
        print(title)
        print("═" * 70)
        cur = conn.cursor()
        try:
            cur.execute(sql)
            print(render(cur, 12))
        except sqlite3.Error as e:
            print(f"❌ {e}")
    index_benchmark()
    conn.close()


if __name__ == "__main__":
    main()
