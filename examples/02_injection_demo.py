"""SQL 注入实验：同一输入，拼接 vs 参数化的两种命运。

跑法：python examples/02_injection_demo.py
全程只操作本仓库自己的数据库（users 表是专门造的反面教材），
演示原理用 —— 拿这些手法碰任何别人的系统都是违法的。
"""

import shutil
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "atlas.db"
TMP = DB.parent / "_inject_lab.db"


def vulnerable_login(db: sqlite3.Connection, username: str, password: str):
    """❌ 教科书式漏洞：字符串拼接。任何代码审查都该拦下这种写法。"""
    sql = ("SELECT username, role, api_key FROM users "
           "WHERE username='" + username + "' AND password='" + password + "'")
    print(f"   实际执行的 SQL:\n     {sql}")
    return db.execute(sql).fetchone()


def safe_login(db: sqlite3.Connection, username: str, password: str):
    """✔ 参数化：SQL 结构与数据彻底分离，输入永远只是值。"""
    sql = "SELECT username, role, api_key FROM users WHERE username=? AND password=?"
    return db.execute(sql, (username, password)).fetchone()


def main() -> None:
    if not DB.exists():
        sys.exit("先运行 python src/seed.py")
    shutil.copy(DB, TMP)
    db = sqlite3.connect(TMP)

    print("=" * 62)
    print("users 表内容（明文密码，反面教材）")
    print("=" * 62)
    for row in db.execute("SELECT username, password, role FROM users"):
        print(f"   {row[0]:<8} {row[1]:<12} {row[2]}")

    attacks = [
        ("正常用户",      "alice",   "alice123",      "正常登录"),
        ("注释掉密码",    "admin'--", "whatever",      "免密登录 admin"),
        # 经典恒真式 ' OR '1'='1 其实返回空：AND 优先级高于 OR，
        # 密码条件还在生效。真攻击必须注释掉后半段 —— 这个细节本身就是教材。
        ("恒真式+注释",   "' OR '1'='1' --", "x",      "返回第一个用户"),
        ("UNION 偷数据",  "' UNION SELECT 'hacked','admin','AK-STEAL'--", "x", "伪造一行数据"),
    ]

    for name, user, pwd, expect in attacks:
        print(f"\n{'═' * 62}")
        print(f"攻击: {name}（预期效果: {expect}）")
        print(f"输入: username={user!r}")
        print("─" * 62)
        r = vulnerable_login(db, user, pwd)
        print(f"   ❌ 拼接版结果: {r if r else '（空）'}")

        print("─" * 62)
        r = safe_login(db, user, pwd)
        print(f"   ✔ 参数化版结果: {r if r else '（空）—— 输入被当成普通字符串'}")

    print(f"\n{'═' * 62}")
    print("结论")
    print("═" * 62)
    print("""· 拼接版：四种输入全部达成攻击目的 —— 数据变成了代码
· 参数化版：全部返回空 —— 恶意输入只是'一个不存在用户名'
· 防御不靠'过滤特殊字符'（sqlmap 有 84 个 tamper 绕过手法），
  靠的是参数化 + 最小权限 + 错误信息不外泄（纵深防御）
· 这些 payload 只对演示库生效。对未授权系统使用 = 刑法 285/286 条""")

    db.close()
    TMP.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
