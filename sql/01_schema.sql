-- ============================================================
--  atlas.db · 建表脚本
--  一个能覆盖 SQL 全部核心语法的电商库（SQLite 3.35+）
--
--  设计原则：
--  1. 故意保留几处"看起来合理但会踩坑"的设计（金额用 REAL、日期用 TEXT），
--     在 docs 里逐一拆解为什么要这么改 —— 这比给你一个完美 schema 更有用。
--  2. 故意留空位：没下过单的客户、没卖出的产品、没支付的订单，
--     这样 LEFT JOIN / 反连接 / NOT EXISTS 才有东西可演示。
--  3. 树形结构出现两次（品类、员工汇报链），用来对比递归 CTE 的两种写法。
-- ============================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS users;

-- ------------------------------------------------------------
-- 客户：tier 分三档，city 故意不做规范化（后面讲范式时会拿它开刀）
-- ------------------------------------------------------------
CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    phone         TEXT    UNIQUE NOT NULL,
    city          TEXT    NOT NULL,
    tier          TEXT    NOT NULL DEFAULT 'basic'
                          CHECK (tier IN ('basic', 'silver', 'gold')),
    credit_limit  REAL    NOT NULL DEFAULT 0 CHECK (credit_limit >= 0),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

-- ------------------------------------------------------------
-- 品类：parent_id 自引用，三层树（大类 → 子类 → 单品类）
-- 这是"邻接表"模型，第 10 章会拿它和物化路径/嵌套集对比
-- ------------------------------------------------------------
CREATE TABLE categories (
    category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    parent_id     INTEGER REFERENCES categories(category_id) ON DELETE RESTRICT,
    sort_order    INTEGER NOT NULL DEFAULT 0
);

-- ------------------------------------------------------------
-- 产品：cost 和 price 用 REAL 存"元" —— 埋了一个浮点误差的雷
-- stock 允许为负，因为仓库允许超卖后补货（业务上真实存在）
-- ------------------------------------------------------------
CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    sku           TEXT    UNIQUE NOT NULL,
    name          TEXT    NOT NULL,
    category_id   INTEGER NOT NULL REFERENCES categories(category_id),
    price         REAL    NOT NULL CHECK (price >= 0),
    cost          REAL    NOT NULL CHECK (cost >= 0),
    stock         INTEGER NOT NULL DEFAULT 0,
    is_active     INTEGER NOT NULL DEFAULT 1,
    launched_on   TEXT
);

-- ------------------------------------------------------------
-- 员工：manager_id 自引用，四层汇报链（CEO 的 manager_id 为 NULL）
-- ------------------------------------------------------------
CREATE TABLE employees (
    employee_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    title         TEXT    NOT NULL,
    manager_id    INTEGER REFERENCES employees(employee_id),
    hired_on      TEXT    NOT NULL,
    salary        REAL    NOT NULL,
    dept          TEXT    NOT NULL
);

-- ------------------------------------------------------------
-- 订单：status 四种，其中 cancelled/refunded 在统计时要特殊处理
-- 没有 order_total 字段 —— 这是刻意的：总额从明细算出来，避免冗余不一致
-- （第 1 章讲范式时会解释为什么这里"不加冗余字段"是对的）
-- ------------------------------------------------------------
CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no      TEXT    UNIQUE NOT NULL,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    employee_id   INTEGER REFERENCES employees(employee_id),
    status        TEXT    NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled', 'refunded')),
    ordered_at    TEXT    NOT NULL,
    shipped_at    TEXT,
    note          TEXT
);

-- ------------------------------------------------------------
-- 明细：unit_price 是"下单时"的价格快照（价格会变，历史订单不能跟着变）
-- 这是数据库设计里"冗余但必要"的经典例子
-- ------------------------------------------------------------
CREATE TABLE order_items (
    item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    REAL    NOT NULL CHECK (unit_price >= 0),
    discount      REAL    NOT NULL DEFAULT 0 CHECK (discount BETWEEN 0 AND 1)
);

-- ------------------------------------------------------------
-- 支付：一个订单可能分多笔付（部分退款场景），也可能一笔没有（未付）
-- 这种"一对多 + 可为空"的组合是 LEFT JOIN 练习的最佳素材
-- ------------------------------------------------------------
CREATE TABLE payments (
    payment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    amount        REAL    NOT NULL,
    method        TEXT    NOT NULL CHECK (method IN ('alipay', 'wechat', 'card', 'balance')),
    paid_at       TEXT    NOT NULL,
    is_refund     INTEGER NOT NULL DEFAULT 0
);

-- ------------------------------------------------------------
-- 审计表：由触发器自动写入，用来演示"触发器能做什么、为什么危险"
-- ------------------------------------------------------------
CREATE TABLE audit_log (
    log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name    TEXT    NOT NULL,
    action        TEXT    NOT NULL,
    row_id        INTEGER,
    old_value     TEXT,
    new_value     TEXT,
    changed_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ------------------------------------------------------------
-- 用户表：明文密码 + 字符串拼接查询 —— 这是教科书级别的反面教材
-- 第 11 章会用它演示 SQL 注入，然后一步步修好
-- ------------------------------------------------------------
CREATE TABLE users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password      TEXT    NOT NULL,          -- 反面教材：明文
    role          TEXT    NOT NULL DEFAULT 'user',
    api_key       TEXT
);

-- ------------------------------------------------------------
-- 索引：先只建主键/唯一约束自带的索引，
-- 其余索引留到第 9 章"现场建"，这样才能测量出真实的性能差异
-- ------------------------------------------------------------

-- 触发器：价格变动时记审计日志
CREATE TRIGGER trg_product_price_audit
AFTER UPDATE OF price ON products
FOR EACH ROW
WHEN OLD.price <> NEW.price
BEGIN
    INSERT INTO audit_log (table_name, action, row_id, old_value, new_value)
    VALUES ('products', 'UPDATE_PRICE', NEW.product_id,
            CAST(OLD.price AS TEXT), CAST(NEW.price AS TEXT));
END;
