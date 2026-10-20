# LEARNING · 四周学会 SQL（附自测标准）

> 这份计划按"每周 4~6 小时"设计。原则和 quant-from-zero 一样：**每个查询都亲手跑，改坏它，看报错**。读懂 ≠ 会写。

## 开始前（30 分钟）

```bash
python build.py                 # 建库 + 自检
python src/q.py                 # 交互练习器
```

可选装备（强烈推荐）：
- [DB Browser for SQLite](https://sqlitebrowser.org/)：打开 `data/atlas.db`，用眼睛看表长什么样
- `pip install sqlalchemy`：只有第 12 章需要

## 第 1 周 · 数据的地基（docs/00 ~ 02）

| 顺序 | 内容 | 自测过关线 |
|---|---|---|
| 1 | 00-学习地图 | 能画出 9 张表的关系草图 |
| 2 | 01-关系模型与范式 | 说清 orders 为什么不存 customer_name |
| 3 | 02-DDL与约束 | 手写一张带 CHECK + FK 的表并故意插错数据看报错 |

**动手题**：给 `customers` 加一列 `birthday TEXT`，然后插入一个 `tier='vip'` 的客户，把**两种报错信息**原样抄下来。报错信息是最好的老师。

**过关自测**：
- [ ] 1NF/2NF/3NF 各用一句话说清
- [ ] `NOT NULL` 为什么拦不住 `''`？
- [ ] SQLite 的 `STRICT` 表解决什么问题？

## 第 2 周 · 查询的主战场（docs/03 ~ 05）

| 顺序 | 内容 | 自测过关线 |
|---|---|---|
| 1 | 03-查询基础 | 看到查询结果能反推 GROUP BY 逻辑 |
| 2 | 04-JOIN全解 | **最重要**：三个陷阱都能现场复现 |
| 3 | 05-子查询 | 把相关子查询改写成窗口函数 |

**动手题（按顺序做）**：
1. 复现"LEFT JOIN + WHERE 退化成 INNER"（4.3），然后用"过滤挪进 ON"修复
2. 复现"JOIN 后 SUM 放大 2.64 倍"（4.4），用"先聚合再 JOIN"修复
3. 查出"从没下过单的 48 个客户"，三种写法各写一遍

**过关自测**：
- [ ] 不看文档解释 `COUNT(*)` 和 `COUNT(列)` 的区别
- [ ] 不看文档写出"NOT IN 遇 NULL 清零"的例子
- [ ] WHERE / ON / HAVING 的执行顺序

## 第 3 周 · 窗口函数与引擎内部（docs/06 ~ 09）

| 顺序 | 内容 | 自测过关线 |
|---|---|---|
| 1 | 06-窗口函数 | 组内 TopN 三段式闭眼写 |
| 2 | 07-递归CTE | 把品类树和员工汇报链各查一遍 |
| 3 | 08-事务与并发 | 跑 examples/01_transaction_lab.py 并解释每个输出 |
| 4 | 09-索引与执行计划 | **复现"半套索引慢 10 倍"实验** |

**动手题**：
1. 用窗口函数算"每个客户订单数占其所在城市的比例"
2. 用递归 CTE 查"员工 15 号的完整上级链"（从直属经理到 CEO）
3. 复现 9.2 的三阶段索引实验（`python src/probe.py` 看完整输出）
4. 给 `products(category_id, is_active)` 写复合索引并 EXPLAIN 验证

**过关自测**：
- [ ] ROW_NUMBER/RANK/DENSE_RANK 在 [100,100,90] 上的输出
- [ ] 为什么移动平均必须写 ROWS BETWEEN
- [ ] UNION 和 UNION ALL 在递归里的生死区别
- [ ] 说清"半套索引更慢"的原理（SCAN/SEARCH 术语）

## 第 4 周 · 工程视角（docs/10 ~ 14）

| 顺序 | 内容 | 自测过关线 |
|---|---|---|
| 1 | 10-建模模式 | 三种树形存法各适用什么场景 |
| 2 | 11-SQL注入与防御 | 跑 examples/02_injection_demo.py 并解释每一行输出 |
| 3 | 12-SQLAlchemy与ORM | 跑 examples/03_orm_demo.py，解释 31→2 |
| 4 | 13-方言差异速查 | 通读即可（工具章） |
| 5 | 14-性能优化实战 | 独立完成 examples/04_slow_query.py 的同款分析 |

**毕业项目（综合全部内容）**：给 atlas.db 新增 `coupons`（优惠券）和 `coupon_redemptions`（核销记录）两张表，要求：
1. 合理的外键和 CHECK 约束（金额、有效期）
2. 至少一个触发器（核销时写 audit_log）
3. 写三个查询：最抢手的券（窗口函数）、领了没用的人（反连接）、按月核销趋势（LAG 环比）
4. 为第 3 个查询设计索引并用 EXPLAIN 验证
5. 全程参数化（写个 Python 脚本演示）

## 自测答案要点

> 不给完整答案 —— 答案都在文档里。这里只列"答对时你应该说出哪些关键词"。

- **1NF/2NF/3NF**：原子值 / 消除部分依赖 / 消除传递依赖
- **NOT NULL vs ''**：空串是"有值"，参与比较和聚合的行为完全不同；约定"没有值一律 NULL"
- **COUNT 区别**：NULL 行数差距 = 该列缺失数
- **半套索引**：优化器选了 `SEARCH o USING INDEX` 但另一侧 `SCAN i`，外层循环 × 全表扫描；补齐索引后两侧都 SEARCH
- **ROWS BETWEEN**：默认 RANGE 会把 ORDER BY 键相同的行一起纳入窗口
- **UNION vs UNION ALL（递归）**：去重能让成环数据终止
- **31→2**：懒加载每访问一次关系属性发一条 SQL；selectinload 用 IN 一次取完
- **优化第一原则**：先测量 → 一次改一处 → 保留对照 → 验证结果一致

## 学完之后

- 想深入 PostgreSQL：官方文档的 "Part II. The SQL Language" + `EXPLAIN ANALYZE`
- 想深入 MySQL：《高性能 MySQL》第 4~6 章（索引、查询优化、高级特性）
- 想深入建模：《Data and Reality》+ Kimball 维度建模
- 想深入安全：PortSwigger 的 SQL injection labs（免费靶场，合法练习）
- 系统刷题：LeetCode 数据库题库按"简单→中等"顺序，配本仓库的窗口函数章
