"""事务实验室：亲眼看一次"半途失败的事务"会发生什么。

跑法：python examples/01_transaction_lab.py
（操作在临时副本上进行，你的 data/atlas.db 不会被动到）
"""

import shutil
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "atlas.db"
TMP = DB.parent / "_tx_lab.db"


def show(title):
    print(f"\n{'═' * 62}\n{title}\n{'═' * 62}")


def main() -> None:
    if not DB.exists():
        sys.exit("先运行 python src/seed.py 生成数据库")
    shutil.copy(DB, TMP)

    a = sqlite3.connect(TMP)          # 会话 A（写者）
    b = sqlite3.connect(TMP)          # 会话 B（旁观者）
    pid = 3
    print(f"3 号产品初始库存: {a.execute('SELECT stock FROM products WHERE product_id=?', (pid,)).fetchone()[0]}")

    # ---------- 实验 1：原子性 ----------
    show("实验 1 · 事务内一条成功 + 一条违反 CHECK")
    a.execute("BEGIN")
    a.execute("UPDATE products SET stock = stock - 1 WHERE product_id = ?", (pid,))
    print(f"① 扣库存成功。会话A看到的库存: "
          f"{a.execute('SELECT stock FROM products WHERE product_id=?', (pid,)).fetchone()[0]}（未提交，自己可见）")
    print(f"② 会话B看到的库存: "
          f"{b.execute('SELECT stock FROM products WHERE product_id=?', (pid,)).fetchone()[0]}（别人不可见 = 隔离）")
    try:
        a.execute("INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
                  "VALUES (1, 1, -5, 10)")          # CHECK (quantity > 0) 必炸
    except sqlite3.Error as e:
        print(f"③ 第二条语句报错: {e}")
    print("④ 注意！此时事务还挂着，①的修改还没撤销 ——")
    a.rollback()
    print(f"   显式 ROLLBACK 后库存: "
          f"{a.execute('SELECT stock FROM products WHERE product_id=?', (pid,)).fetchone()[0]}")
    print("\n   教训：语句失败不会自动回滚整个事务，异常处理里必须有 rollback。")

    # ---------- 实验 2：隐式回滚 ----------
    show("实验 2 · 不 commit 直接关闭连接 = 自动回滚")
    a.execute("BEGIN")
    a.execute("UPDATE products SET stock = stock - 5 WHERE product_id = ?", (pid,))
    a.close()                                     # 什么都没说就走了
    b2 = sqlite3.connect(TMP)
    print(f"库存 = {b2.execute('SELECT stock FROM products WHERE product_id=?', (pid,)).fetchone()[0]}（修改消失）")

    # ---------- 实验 3：SQLite 的写锁 ----------
    show("实验 3 · 两个连接同时写（SQLite 的库级写锁）")
    a = sqlite3.connect(TMP)
    a.execute("BEGIN IMMEDIATE")
    a.execute("UPDATE products SET price = price WHERE product_id = 1")
    print("① 会话A 拿到写锁（BEGIN IMMEDIATE）")
    try:
        b.execute("BEGIN IMMEDIATE")              # B 也想写
    except sqlite3.OperationalError as e:
        print(f"② 会话B 立刻撞锁: {e}")
    a.commit()
    print("③ A 提交后锁释放，B 重试就能成功 —— SQLite 就是这样'串行化'的")
    a.close(); b.close(); b2.close()

    show("总结")
    print("""· 原子性：两条语句要么全成，要么全不作数 —— 靠 BEGIN/COMMIT/ROLLBACK
· 隔离性：未提交的数据别人看不见（SQLite 用单写者锁直接做到）
· 一旦 COMMIT，ROLLBACK 救不了你 —— 需要补偿事务（反向 UPDATE）
· 报错的事务不是自动回滚，是挂起等待你的指令""")

    TMP.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
