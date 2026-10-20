"""N+1 问题实测：同一功能，31 条 SQL 和 2 条 SQL 的差距。

跑法：python examples/03_orm_demo.py
需要 sqlalchemy：pip install sqlalchemy
"""

import time
import sys
from pathlib import Path

try:
    from sqlalchemy import create_engine, ForeignKey, String, event, select
    from sqlalchemy.orm import (DeclarativeBase, Mapped, joinedload, mapped_column,
                                relationship, selectinload, sessionmaker)
except ImportError:
    sys.exit("需要 sqlalchemy：pip install sqlalchemy")

DB = Path(__file__).resolve().parent.parent / "data" / "atlas.db"


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    customer_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"
    order_id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.customer_id"))
    status: Mapped[str] = mapped_column(String(20))
    customer: Mapped["Customer"] = relationship(back_populates="orders")


def timed_with_sql_count(engine, label, fn):
    """既测耗时又数 SQL 条数 —— N+1 的两个证据同时抓。"""
    counter = {"n": 0}

    def _before(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    event.listen(engine, "before_cursor_execute", _before)
    t = time.perf_counter()
    result = fn()
    ms = (time.perf_counter() - t) * 1000
    event.remove(engine, "before_cursor_execute", _before)
    print(f"{label:<28} {counter['n']:3d} 条 SQL   {ms:7.1f} ms")
    return result


def main() -> None:
    if not DB.exists():
        sys.exit("先运行 python src/seed.py")
    engine = create_engine(f"sqlite:///{DB}")
    Session = sessionmaker(engine)
    N = 30

    def lazy(s):
        total = 0
        for c in s.query(Customer).limit(N):
            total += len(c.orders)          # ← 每次访问都当场补发一条 SQL
        return total

    def joined(s):
        total = 0
        for c in s.query(Customer).options(joinedload(Customer.orders)).limit(N):
            total += len(c.orders)
        return total

    def selectin(s):
        total = 0
        for c in s.query(Customer).options(selectinload(Customer.orders)).limit(N):
            total += len(c.orders)
        return total

    print(f"任务：取前 {N} 个客户及其全部订单（功能完全相同）\n")
    with Session() as s:
        r1 = timed_with_sql_count(engine, "① 默认懒加载（N+1）", lambda: lazy(s))
    with Session() as s:
        r2 = timed_with_sql_count(engine, "② joinedload（大 JOIN）", lambda: joined(s))
    with Session() as s:
        r3 = timed_with_sql_count(engine, "③ selectinload（两条 IN）", lambda: selectin(s))

    assert r1 == r2 == r3, "三种写法结果必须一致"
    print(f"\n结果一致（{r1} 条订单），但 SQL 条数 31 → 1 → 2。")
    print("""· 懒加载：1 条查客户 + N 条逐个查订单 = N+1
· joinedload：一条大 JOIN，行数膨胀（客户×订单），适合多对一
· selectinload：两条简单查询，无膨胀，一对多场景通常最优
· 大型项目防复发技巧：relationship(lazy='raise_on_sql')，
  让未预加载的访问直接报错，N+1 在测试阶段就现形""")


if __name__ == "__main__":
    main()
