"""atlas.db 的数据生成器。

所有随机数都用固定种子，所以任何人跑出来的库**完全一致** ——
文档里贴的每个查询结果你都能原样复现，不会出现"我这儿怎么是 37 行"的困惑。

数据不是随便撒的，埋了几条真实业务规律，让后面的分析题有东西可挖：
  · 金卡客户下单频率是普通客户的 3 倍
  · 618 / 双 11 有明显订单高峰
  · 约 15% 客户从未下单、约 8% 产品从未卖出（供 LEFT JOIN 使用）
  · 约 6% 订单从未支付（供反连接使用）
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 42
DB = Path(__file__).resolve().parent.parent / "data" / "atlas.db"
SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "01_schema.sql"

rng = random.Random(SEED)

# ---------------------------------------------------------------- 品类树
# (id, 名称, 父 id)  —— 三层：大类(1-5) → 子类(11-52) → 单品类不建第四层
CATEGORIES = [
    (1, "电子产品", None), (2, "家居生活", None), (3, "服饰鞋包", None),
    (4, "食品饮料", None), (5, "图书", None),
    (11, "手机", 1), (12, "电脑", 1), (13, "音频", 1), (14, "配件", 1),
    (21, "家具", 2), (22, "厨具", 2), (23, "收纳", 2),
    (31, "男装", 3), (32, "女装", 3), (33, "运动鞋", 3),
    (41, "零食", 4), (42, "饮料", 4), (43, "生鲜", 4),
    (51, "技术书", 5), (52, "文学书", 5),
]

# 每个子类下的产品命名素材：(品牌池, 型号池, 价格区间)
PRODUCT_TEMPLATES = {
    11: (["星尘", "极光", "磐石", "轻羽"], ["Pro", "Max", "Air", "Neo", "Lite"], (1299, 6999)),
    12: (["thinkplus", "云端", "锐界", "墨影"], ["14 寸", "15 寸", "16 寸", "轻薄本"], (3299, 12999)),
    13: (["声阔", "静界", "律动"], ["降噪版", "运动版", "监听版"], (199, 2499)),
    14: (["闪连", "智充", "线匠"], ["65W", "100W", "三合一", "编织款"], (29, 399)),
    21: (["木言", "北欧屋", "简舍"], ["实木款", "布艺款", "折叠款"], (399, 4999)),
    22: (["炊大皇", "锐厨", "一勺"], ["不粘锅", "蒸锅", "刀具套装"], (59, 999)),
    23: (["收纳家", "方格", "净界"], ["三层", "抽屉式", "壁挂"], (19, 299)),
    31: (["衣品", "棉序", "硬核"], ["衬衫", "夹克", "西裤", "卫衣"], (89, 799)),
    32: (["柔漾", "云纱", "拾光"], ["连衣裙", "针织衫", "半身裙"], (99, 899)),
    33: (["疾风", "缓震", "越野者"], ["跑鞋", "板鞋", "训练鞋"], (199, 1299)),
    41: (["脆脆屋", "食光", "咸淡"], ["薯片", "坚果", "肉脯", "饼干"], (9, 99)),
    42: (["清源", "气泡站", "茶叙"], ["气泡水", "冷萃茶", "果汁"], (3, 29)),
    43: (["鲜直达", "田间", "晨露"], ["蔬菜包", "水果盒", "鸡蛋"], (12, 129)),
    51: (["O'Reilly", "Manning", "人民邮电"], ["SQL 必知必会", "数据库系统概念", "高性能 MySQL"], (49, 189)),
    52: (["译文", "理想国", "读库"], ["小说集", "散文选", "传记"], (29, 129)),
}

CITIES = ["深圳", "广州", "杭州", "上海", "北京", "南京", "武汉", "成都",
          "西安", "厦门", "福州", "长沙", "苏州", "重庆", "合肥"]
SURNAMES = list("王李张刘陈杨黄赵吴周徐孙马朱胡林郭何高罗")
GIVEN = ["伟", "芳", "娜", "敏", "静", "强", "磊", "洋", "艳", "勇",
         "军", "杰", "娟", "涛", "明", "超", "秀英", "霞", "平", "刚",
         "浩然", "子轩", "雨欣", "梓涵", "思远", "嘉怡", "宇轩", "若曦"]
DEPT = ["销售部", "技术部", "市场部", "客服部", "财务部"]


def _name() -> str:
    return rng.choice(SURNAMES) + rng.choice(GIVEN)


def build() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys = ON")

    # ---------------- 品类
    conn.executemany(
        "INSERT INTO categories (category_id, name, parent_id, sort_order) VALUES (?,?,?,?)",
        [(cid, name, pid, i) for i, (cid, name, pid) in enumerate(CATEGORIES)],
    )

    # ---------------- 产品：150 个，分到 15 个子类，每类 10 个
    leaf_ids = [c[0] for c in CATEGORIES if c[2] is not None]
    products = []
    pid = 0
    for cat_id in leaf_ids:
        brands, models, (lo, hi) = PRODUCT_TEMPLATES[cat_id]
        for _ in range(10):
            pid += 1
            cost = round(rng.uniform(lo, hi) * 0.62, 2)
            price = round(cost * rng.uniform(1.25, 2.1), 2)
            products.append((
                pid,
                f"SKU{cat_id:02d}{pid:04d}",
                f"{rng.choice(brands)} {rng.choice(models)} {rng.choice(['A','B','C','S'])}{rng.randint(1,9)}",
                cat_id, price, cost,
                rng.choice([0, 3, 8, 15, 26, 40, 55, 88, 120, 200]),
                1 if rng.random() > 0.08 else 0,
                (date(2021, 1, 1) + timedelta(days=rng.randint(0, 1200))).isoformat(),
            ))
    conn.executemany(
        """INSERT INTO products
           (product_id, sku, name, category_id, price, cost, stock, is_active, launched_on)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        products,
    )

    # ---------------- 客户：300 个，15% 从未下单
    customers = []
    for i in range(1, 301):
        tier = rng.choices(["basic", "silver", "gold"], weights=[62, 28, 10])[0]
        customers.append((
            i, f"{_name()}", f"1{rng.choice('3589')}{rng.randint(10**8, 10**9 - 1)}",
            rng.choice(CITIES), tier,
            {"basic": 0, "silver": 20000, "gold": 80000}[tier],
            (date(2022, 1, 1) + timedelta(days=rng.randint(0, 1000))).isoformat() + " 09:00:00",
            1 if rng.random() > 0.05 else 0,
        ))
    conn.executemany(
        """INSERT INTO customers
           (customer_id, name, phone, city, tier, credit_limit, created_at, is_active)
           VALUES (?,?,?,?,?,?,?,?)""",
        customers,
    )

    # ---------------- 员工：1 个 CEO + 4 层，共 26 人
    employees = []
    names = [_name() for _ in range(26)]
    employees.append((1, names[0], "CEO", None, "2018-03-01", 120000, "管理层"))
    # 4 个 VP（2-5），直接向 CEO 汇报
    for i, dept in enumerate(["销售部", "技术部", "市场部", "客服部"], start=2):
        employees.append((i, names[i - 1], f"{dept} VP", 1,
                          f"2019-0{i}-15", rng.randint(55000, 70000), dept))
    # 8 个经理（6-13），各挂一个 VP
    for i in range(6, 14):
        boss = 2 + (i - 6) % 4
        dept = employees[boss - 1][6]
        employees.append((i, names[i - 1], f"{dept} 经理", boss,
                          f"2020-0{(i % 9) + 1}-10", rng.randint(28000, 42000), dept))
    # 13 个一线（14-26），各挂一个经理
    for i in range(14, 27):
        boss = 6 + (i - 14) % 8
        dept = employees[boss - 1][6]
        employees.append((i, names[i - 1], f"{dept} 专员", boss,
                          f"2021-0{(i % 9) + 1}-05", rng.randint(9000, 18000), dept))
    conn.executemany(
        """INSERT INTO employees
           (employee_id, name, title, manager_id, hired_on, salary, dept)
           VALUES (?,?,?,?,?,?,?)""",
        employees,
    )

    # ---------------- 订单：3000 单，2023-01 ~ 2024-12
    # 下单客户池：排除 15% 从未下单的人；金卡客户被抽中概率更高
    buyers = [c[0] for c in customers if rng.random() > 0.15]
    weights = {c[0]: {"basic": 1, "silver": 2, "gold": 3}[c[4]] for c in customers}
    buyer_pool = [c for c in buyers]
    buyer_weights = [weights[c] for c in buyer_pool]
    sales_ids = list(range(14, 27))          # 一线销售负责接单

    # 上架最晚的 12 个产品当作"新品"，从未卖出过 —— LEFT JOIN 的练习素材
    never_sold = {p[0] for p in sorted(products, key=lambda x: x[8], reverse=True)[:12]}
    sold_pool = [p for p in products if p[0] not in never_sold]

    orders, items, payments = [], [], []
    item_id = 0
    oid = 0
    start = date(2023, 1, 1)
    total_days = (date(2024, 12, 31) - start).days

    for _ in range(3000):
        oid += 1
        d = start + timedelta(days=rng.randint(0, total_days))
        # 大促加权：6/18 和 11/11 前后 5 天订单量翻倍
        for promo in (date(2023, 6, 18), date(2023, 11, 11),
                      date(2024, 6, 18), date(2024, 11, 11)):
            if abs((d - promo).days) <= 5 and rng.random() < 0.45:
                d = promo + timedelta(days=rng.randint(-3, 3))
                break
        ts = f"{d.isoformat()} {rng.randint(8,22):02d}:{rng.randint(0,59):02d}:00"
        status = rng.choices(
            ["paid", "shipped", "pending", "cancelled", "refunded"],
            weights=[38, 42, 8, 8, 4],
        )[0]
        shipped = None
        if status in ("shipped", "refunded"):
            shipped = (d + timedelta(days=rng.randint(1, 4))).isoformat() + " 10:00:00"
        orders.append((
            oid, f"SO{d.strftime('%Y%m')}{oid:05d}",
            rng.choices(buyer_pool, weights=buyer_weights)[0],
            rng.choice(sales_ids), status, ts, shipped,
            rng.choice([None, None, None, "客户要求周末送达", "含赠品", "加急"]),
        ))

        # 明细：1~5 行
        for _ in range(rng.choices([1, 2, 3, 4, 5], weights=[42, 28, 16, 9, 5])[0]):
            item_id += 1
            p = rng.choice(sold_pool)
            items.append((
                item_id, oid, p[0], rng.randint(1, 4),
                p[4],                       # 下单时价格快照
                rng.choices([0, 0.05, 0.1, 0.15, 0.2], weights=[60, 15, 12, 8, 5])[0],
            ))

        # 支付：paid/shipped 必有 1 笔；pending 约 6% 有定金；cancelled 无；refunded 有正负两笔
        if status in ("paid", "shipped"):
            payments.append((oid, 1, rng.choice(["alipay", "wechat", "card", "balance"]), ts, 0))
        elif status == "pending" and rng.random() < 0.06:
            payments.append((oid, 1, "balance", ts, 0))
        elif status == "refunded":
            payments.append((oid, 1, rng.choice(["alipay", "wechat"]), ts, 0))
            payments.append((oid, -1, "alipay", (d + timedelta(days=3)).isoformat() + " 15:00:00", 1))

    conn.executemany(
        """INSERT INTO orders
           (order_id, order_no, customer_id, employee_id, status, ordered_at, shipped_at, note)
           VALUES (?,?,?,?,?,?,?,?)""",
        orders,
    )
    conn.executemany(
        """INSERT INTO order_items
           (item_id, order_id, product_id, quantity, unit_price, discount)
           VALUES (?,?,?,?,?,?)""",
        items,
    )

    # 支付金额按订单实际金额（含折扣）回填
    conn.execute("""
        UPDATE orders SET status = status
    """)
    pay_rows = []
    for (order_id, sign, method, ts, is_refund) in payments:
        row = conn.execute("""
            SELECT ROUND(SUM(quantity * unit_price * (1 - discount)), 2)
            FROM order_items WHERE order_id = ?
        """, (order_id,)).fetchone()
        amount = (row[0] or 0) * sign
        pay_rows.append((order_id, amount, method, ts, is_refund))
    conn.executemany(
        """INSERT INTO payments (order_id, amount, method, paid_at, is_refund)
           VALUES (?,?,?,?,?)""",
        pay_rows,
    )

    # ---------------- 用户：给注入实验用
    users = [
        ("admin", "Admin@2024", "admin", "AK-9F2A-77C1"),
        ("alice", "alice123", "user", "AK-3B8D-12E4"),
        ("bob", "qwerty", "user", "AK-5C7A-90F2"),
        ("carol", "carol2024", "user", "AK-1E4F-33B8"),
        ("dave", "pass1234", "user", "AK-7A2C-55D9"),
    ]
    conn.executemany(
        "INSERT INTO users (username, password, role, api_key) VALUES (?,?,?,?)", users
    )

    conn.commit()

    # ---------------- 统计报告
    print(f"库文件: {DB}")
    print(f"大小  : {DB.stat().st_size / 1024:.0f} KB")
    for t in ("categories", "products", "customers", "employees",
              "orders", "order_items", "payments", "users"):
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<14} {n:>6} 行")
    orphan_c = conn.execute("""
        SELECT COUNT(*) FROM customers c
        WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id)
    """).fetchone()[0]
    orphan_p = conn.execute("""
        SELECT COUNT(*) FROM products p
        WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.product_id = p.product_id)
    """).fetchone()[0]
    print(f"  无订单客户 {orphan_c} / 无销量产品 {orphan_p}")
    conn.close()


if __name__ == "__main__":
    build()
