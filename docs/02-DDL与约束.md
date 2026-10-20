# 02 · DDL、约束与触发器：让数据库替你挡脏数据

> 一句话：应用代码会崩、会被绕过、会忘写校验；约束在数据库层兜底，是最后一道防线。

## 2.1 先认识 atlas.db 的表定义

完整定义在 [`sql/01_schema.sql`](../sql/01_schema.sql)。挑一段看：

```sql
CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    phone         TEXT    UNIQUE NOT NULL,
    tier          TEXT    NOT NULL DEFAULT 'basic'
                          CHECK (tier IN ('basic', 'silver', 'gold')),
    credit_limit  REAL    NOT NULL DEFAULT 0 CHECK (credit_limit >= 0),
    ...
);
```

六种约束各司其职：

| 约束 | 挡住什么 | 实测效果 |
|---|---|---|
| `PRIMARY KEY` | 重复身份 | 每表一个，SQLite 里自动是行索引 |
| `UNIQUE` | 重复业务键 | 插重复手机号 → `UNIQUE constraint failed: customers.phone` |
| `NOT NULL` | 缺关键信息 | 拒绝插入，但注意它管不住空字符串 `''`（见 2.4） |
| `CHECK` | 业务规则 | `tier='vip'` → `CHECK constraint failed: tier IN (...)` |
| `FOREIGN KEY` | 引用不存在的行 | 删被引用的品类 → `FOREIGN KEY constraint failed` |
| `DEFAULT` | 漏填 | 自动补 `'basic'` |

## 2.2 SQLite 的类型系统：亲和性是坑还是糖？

SQLite 列的"类型"只是**建议**，不是强约束：

```sql
CREATE TABLE t1(a INTEGER);
INSERT INTO t1 VALUES ('5');     -- 能插
SELECT a, typeof(a) FROM t1;     -- 5 | integer   ← 字符串'5'被转换了

CREATE TABLE t2(a INTEGER);
INSERT INTO t2 VALUES ('abc');   -- 也能插！！
SELECT a, typeof(a) FROM t2;     -- abc | text    ← 同一列混着 integer 和 text
```

同一列里既有数字又有文本，统计查询随时炸。**3.37+ 的 `STRICT` 表才真正拦住**：

```sql
CREATE TABLE t3(a INTEGER) STRICT;
INSERT INTO t3 VALUES ('abc');
-- ERROR: cannot store TEXT value in INTEGER column t3.a
```

这个设计的教育意义：MySQL 早期同样宽松（`''` 和 `0` 互转引发过无数事故），PostgreSQL 一贯严格。**建表时想清楚你要哪种，而不是放任默认**。数字对比：

```sql
SELECT '5' = 5;        -- SQLite: 1（宽松转换）  PostgreSQL: 报错（严格）  MySQL: 1
SELECT '' = 0;         -- MySQL: 1 ← 无数 bug 的来源
```

## 2.3 外键：声明了不等于生效（SQLite 特性）

atlas.db 的外键逻辑上存在，但 SQLite **默认不检查外键**！每个连接必须显式打开：

```python
conn = sqlite3.connect("atlas.db")
conn.execute("PRAGMA foreign_keys = ON")   # 不写这句，外键就是摆设
```

实测关掉会发生什么：

```sql
-- foreign_keys=OFF 时：
DELETE FROM categories WHERE category_id = 1;   -- 成功！
-- 此刻 products 表里 40 个产品指向一个不存在的品类 —— "孤儿行"
```

这也是面试高频题："外键有什么坏处？"——除了每写一行多一次父表检查，**高并发场景的锁竞争**和**分库分表后外键失效**是它被大厂从 OLTP 表里移除的真实原因。移除外键后，一致性责任转移到应用层 + 定期对账（第 10 章）。

`ON DELETE` 的三种动作实测：

```sql
-- ON DELETE RESTRICT：有产品挂着 → 拒绝删除品类（默认行为）
-- ON DELETE CASCADE：删订单自动删明细（atlas.db 的 order_items 就是这么定义的）
-- ON DELETE SET NULL：删父行，子行外键置空（适合"员工离职但订单还留着"）
```

## 2.4 NULL、空串、默认值：三种"没有"的区别

```sql
-- NOT NULL 约束拦得住 NULL，拦不住空字符串：
INSERT INTO customers (name, phone) VALUES ('', '13800000000');  -- name='' 插入成功！
```

实践约定：**"没有值"统一用 NULL，永远不用空串**。因为空串参与比较和聚合的行为和 NULL 完全不同（第 3 章三值逻辑细讲）。检查时两者都要防：

```sql
WHERE name IS NULL OR TRIM(name) = ''
```

## 2.5 生成列：派生数据的官方解法

第 1 章说"派生数据不落库"，但总额这类值每次现算又浪费。生成列是折中——**声明计算规则，数据库负责维护**：

```sql
CREATE TABLE order_totals (
    order_id INTEGER PRIMARY KEY,
    qty      INTEGER,
    price    REAL,
    total    REAL GENERATED ALWAYS AS (qty * price) STORED
);
INSERT INTO order_totals (order_id, qty, price) VALUES (1, 3, 19.9);
SELECT * FROM order_totals;
```

```
order_id  qty   price   total
1         3     19.9    59.699999999999996    ← 顺便见证 REAL 浮点误差（第 3 章收尸）
```

`STORED` 占空间但读得快；`VIRTUAL` 不占空间每次现算。生成列还能建索引 —— 这是"冗余但不失控"的正确姿势。

## 2.6 触发器：数据库里的"钩子"

atlas.db 的审计触发器，产品价格一变就自动留痕：

```sql
CREATE TRIGGER trg_product_price_audit
AFTER UPDATE OF price ON products
FOR EACH ROW
WHEN OLD.price <> NEW.price
BEGIN
    INSERT INTO audit_log (table_name, action, row_id, old_value, new_value)
    VALUES ('products', 'UPDATE_PRICE', NEW.product_id,
            CAST(OLD.price AS TEXT), CAST(NEW.price AS TEXT));
END;
```

实测（改 1 号产品价格）：

```sql
UPDATE products SET price = price * 0.5 WHERE product_id = 1;
SELECT * FROM audit_log ORDER BY log_id DESC LIMIT 1;
```

```
table_name  action         row_id  old_value  new_value
products    UPDATE_PRICE   1       3896.55    1948.275
```

触发器适合**审计、级联维护这类"与业务无关的机械记录"**。但不适合业务规则：

> 危险信号：如果触发器里在写"改库存、发通知、算积分"，快跑。业务逻辑散落在触发器里 = 没人知道一行 INSERT 到底触发了什么，排查问题时它们是隐形的。应用层做业务，触发器只做簿记。

## 2.7 用 DB Browser 亲手看一遍

装 [DB Browser for SQLite](https://sqlitebrowser.org/)（就是 24.7k★ 的 sqlitebrowser 项目），打开 `data/atlas.db`：

1. **Database Structure** 页签看表和索引 —— 和本章的 DDL 对照
2. **Browse Data** 页签翻 `orders` 表，肉眼确认"status 有 5 种值"
3. **Execute SQL** 页签贴本章任何查询 —— 改坏它，看报错

"先看见数据再写查询"能省一半的调试时间。

## 自测

1. `CHECK (age >= 0)` 和应用层 `if age < 0: raise` 有什么本质区别？（提示：绕过应用层的路径有几条？）
2. 为什么 SQLite 默认不启用外键检查？这个默认值害过谁？
3. 生成列 `STORED` 和 `VIRTUAL` 怎么选？
4. `NOT NULL` 为什么拦不住 `''`？你们团队应该用什么约定规避？
