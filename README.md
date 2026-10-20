# sql-atlas · SQL 从入门到防御的全景知识库

> 一个**每个结论都能亲手复现**的 SQL 知识库。
> 14 章教程 + 9 张手绘原理图 + 1 个自带数据的可运行练习库，覆盖关系模型、查询、事务、索引、建模、注入攻防与 ORM。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![SQLite](https://img.shields.io/badge/SQLite-3.35%2B-green) ![License](https://img.shields.io/badge/License-MIT-green) ![测试](https://img.shields.io/badge/示例-4个全部可跑-brightgreen)

## 和其他 SQL 教程的三个不同

1. **自带一个"真实感"数据库** —— `data/atlas.db`：300 客户、3000 订单、6000 明细，埋了业务规律（大促高峰、金卡客户高频、无订单客户、无销量产品）。所有查询输出都贴在文档里，你跑出来的结果和文档**逐字一致**（数据由固定种子生成）。
2. **坑全部实测** —— 不说"JOIN 会膨胀"这种空话，直接给你数字：一对多 JOIN 后 SUM 放大 2.64 倍；只给外键一侧建索引，查询慢 10 倍；`NOT IN` 遇 NULL 结果清零。每个数字都能用 `python src/probe.py` 复现。
3. **从 SELECT 讲到 SQL 注入** —— 市面教程停在"会写查询"，这里一路讲到位：为什么 `= NULL` 查不到东西、为什么注入的根因是"数据变代码"、sqlmap 的 84 个 tamper 脚本在绕什么、ORM 的 N+1 实测 31 条 SQL → 2 条。

## 3 分钟跑通

```bash
git clone https://github.com/coniern/sql-atlas.git
cd sql-atlas
python build.py        # 一键：建库 + 灌数据 + 跑全部自检（无需安装任何包）
```

然后：

```bash
python src/q.py "SELECT status, COUNT(*) FROM orders GROUP BY status"
```

```
┌───────────┬──────┐
│ status    │ n    │
├───────────┼──────┤
│ shipped   │ 1311 │
│ paid      │ 1088 │
│ pending   │  261 │
│ cancelled │  231 │
│ refunded  │  109 │
└───────────┴──────┘
```

看到这张表，环境就绪了。零依赖：只用 Python 标准库的 sqlite3。

## 内容地图（14 章 · 每章有实测和自测题）

```
原理篇                    查询篇                    引擎篇                    工程篇
docs/01-关系模型与范式     docs/03-查询基础           docs/08-事务与并发         docs/11-SQL注入与防御
docs/02-DDL与约束         docs/04-JOIN全解          docs/09-索引与执行计划     docs/12-SQLAlchemy与ORM
                          docs/05-子查询             docs/10-建模模式          docs/13-方言差异速查
                          docs/06-窗口函数
                          docs/07-递归CTE
                                                    docs/14-性能优化实战（收尾）
docs/00-学习地图.md ← 从这里开始（含路线图和四周计划）
```

### 九张原理图（GitHub 直接渲染）

| 图 | 位置 |
|---|---|
| 数据库整体 ER 图 | 00-学习地图 |
| 七种 JOIN 集合图 | 04-JOIN全解 |
| B+ 树与查询执行流程 | 09-索引与执行计划 |
| 窗口函数：聚合不折叠行 | 06-窗口函数 |
| 递归 CTE 工作队列 | 07-递归CTE |
| 四级隔离 × 三种异常 | 08-事务与并发 |
| SQL 注入原理与手法谱系 | 11-SQL注入与防御 |
| SQLAlchemy 分层架构 | 12-SQLAlchemy与ORM |

## 仓库里几个有代表性的实测结论

| 结论 | 出处 |
|---|---|
| `WHERE x = NULL` 静默返回 0 行，不报错 | 03 章 |
| 一对多 JOIN 后对订单金额 SUM，放大 2.64 倍 | 04 章 |
| `NOT IN` 的子查询含一个 NULL，整个结果清零 | 04 章 |
| 金额用 REAL：6048 行明细两种合计差 0.48 元 | 03 章 |
| 只给外键一侧建索引，JOIN 查询反而慢 10 倍；补齐后快 110 倍 | 09 章 |
| 对索引列套函数（`CAST`/`+0`）→ 计划退化为全表扫描 | 09 章 |
| 每多一个索引，1 万行写入慢约 10% | 09 章 |
| 事务中一条语句失败后事务"挂起"，必须显式 ROLLBACK | 08 章 |
| ORM 懒加载 31 条 SQL → `selectinload` 2 条，快 4 倍 | 12 章 |
| `admin'--` 免密登录；参数化后同输入返回空 | 11 章 |

全部可复现：

```bash
python src/probe.py        # 打印所有实测数据
python examples/01_transaction_lab.py    # 事务实验室
python examples/02_injection_demo.py     # 注入实验（只对本地演示库）
python examples/03_orm_demo.py           # N+1 实测（需 sqlalchemy）
python examples/04_slow_query.py         # 慢查询优化全流程
```

## 目录结构

```
sql-atlas/
├── README.md
├── LEARNING.md             # 四周学习计划 + 自测答案要点
├── build.py                # 一键重建 + 自检
├── src/
│   ├── seed.py             # 数据生成器（固定种子，结果可复现）
│   ├── q.py                # 交互式 SQL 练习器（零依赖）
│   └── probe.py            # 全部实测结论的采集脚本
├── sql/01_schema.sql       # 建表脚本（注释里写了每个设计决策的理由）
├── docs/                   # 14 章教程
├── examples/               # 4 个可运行实验
├── images/                 # 9 张 SVG 原理图
└── data/atlas.db           # 练习数据库（也可删掉用 seed.py 重建）
```

## 知识来源

本项目消化吸收了四个开源项目的精华，并引用其设计思想：

- [microsoft/sql-server-samples](https://github.com/microsoft/sql-server-samples)（11.3k★）— 官方示例库（Northwind/AdventureWorks/WideWorldImporters）的建模思想、T-SQL 特性清单
- [sqlalchemy/sqlalchemy](https://github.com/sqlalchemy/sqlalchemy)（12.2k★）— Core/ORM 分层架构、关系加载策略、examples 中的树形建模模式
- [sqlitebrowser/sqlitebrowser](https://github.com/sqlitebrowser/sqlitebrowser)（24.7k★）— SQLite 能力边界（窗口函数/CTE/触发器/PRAGMA）、"用 GUI 直观检查数据"的学习方法
- [sqlmapproject/sqlmap](https://github.com/sqlmapproject/sqlmap)（38.7k★）— 六类注入技术分类、84 个 tamper 脚本的攻防视角

## 免责声明

第 11 章的注入实验**仅限在本仓库自带的演示数据库上进行**。对未授权系统进行渗透测试属于违法行为（《刑法》第 285/286 条）。

## License

MIT
