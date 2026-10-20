"""一键重建整个数据库：删旧库 → 建表 → 灌数据 → 跑全部示例自检。

跑法：python build.py
输出：data/atlas.db（固定种子，任何机器上结果完全一致）
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run(args: list[str]) -> bool:
    print(f"\n$ {' '.join(args)}")
    r = subprocess.run([PY, *args], cwd=ROOT)
    return r.returncode == 0


def main() -> None:
    steps = [
        (["src/seed.py"], "① 建库灌数据（固定种子 42）"),
        (["src/q.py", "SELECT COUNT(*) AS 订单数 FROM orders"], "② 自检：行数对得上吗"),
        (["examples/01_transaction_lab.py"], "③ 自检：事务行为正常吗"),
        (["examples/02_injection_demo.py"], "④ 自检：注入实验可复现吗"),
        (["examples/04_slow_query.py"], "⑤ 自检：优化流程可复现吗"),
    ]
    ok = all(run(args) for args, _ in steps)
    print("\n" + "═" * 50)
    print("✅ 全部就绪！从这些开始：" if ok else "❌ 有步骤失败，看上面的报错")
    if ok:
        print("""
  python src/q.py                    # 交互式 SQL 练习器
  python src/probe.py                # 打印全部实测结论
  打开 docs/00-学习地图.md            # 从学习地图开始
  DB Browser for SQLite 打开 data/atlas.db   # 可视化翻数据
""")


if __name__ == "__main__":
    main()
