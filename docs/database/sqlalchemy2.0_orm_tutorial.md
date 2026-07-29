---
author: e3mydu1f,DouBao
version:
date modified: July 28th 2026, 5:29 pm
date created: July 28th 2026, 5:21 pm
---
# SQLAlchemy 2.0 ORM 模型编写指南（Alembic 适配版）
本指南基于 SQLAlchemy 2.0 声明式映射语法编写，所有规则均以「可被 Alembic `--autogenerate` 准确识别」为核心标准，同时覆盖工程化的代码规范与避坑要点。
> 由于本项目采用的SQLite数据库的情况特殊，所以对于 
> [[#九、本项目的SQLite 环境专属适配补充(非常重要)]]不能漏掉阅读！
## 一、指南概述
### 1.1 适用范围
- 技术栈：SQLAlchemy 2.0 + Alembic 迁移体系
- 适用场景：业务系统 ORM 模型定义、结构化数据库表设计
- 核心目标：写出可自动生成迁移、规范统一、可维护、低风险的数据库模型

### 1.2 核心前置约定
1.  所有模型继承自统一的 `DeclarativeBase` 基类，Alembic 通过基类的 `metadata` 扫描全部模型。
2.  采用 2.0 标准写法：`Mapped[T]` 做类型标注 + `mapped_column()` 定义列。
3.  所有约束、索引必须显式命名，避免匿名约束导致 Alembic 识别异常。

## 二、基础规范与通用约定
### 2.1 统一 ORM 基类
项目必须维护唯一的 ORM 基类，所有业务模型继承该基类，确保元数据统一收集。
```python
# base_model.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """项目统一 ORM 基类，Alembic target_metadata 指向本类的 metadata"""
    pass
```
> Alembic 关联说明：在 `env.py` 中配置 `target_metadata = Base.metadata`，是自动生成迁移的前提条件。

### 2.2 命名规范
| 对象类型 | 命名规则 | 示例 | 说明 |
|----------|----------|------|------|
| 表名 | 蛇形全小写，业务语义清晰 | `user_info`, `order_detail` | 禁止使用数据库关键字，建议用业务名词 |
| 列名 | 蛇形全小写 | `user_id`, `created_at` | 与表名保持风格一致 |
| 主键约束 | `pk_表名` | `pk_user_info` | 单列主键可省略命名，复合主键建议显式命名 |
| 唯一约束 | `uq_表名_字段名` | `uq_user_info_phone` | 多列组合用下划线拼接 |
| 普通索引 | `ix_表名_字段名` | `ix_order_create_time` | 多列索引用字段名依次拼接 |
| 外键约束 | `fk_子表_父表_字段` | `fk_order_user_user_id` | 便于快速识别关联关系 |
| 数据库枚举类型 | `enum_业务含义` | `enum_user_status` | 全局唯一，避免重名冲突 |

> **Alembic 关键说明**：匿名约束（不指定 name）在不同数据库中会生成随机默认名，导致 Alembic 对比结构时频繁误判为变更，**所有约束、索引必须显式命名**。

### 2.3 类型标注规范
SQLAlchemy 2.0 通过 `Mapped[T]` 的类型注解自动推断 `nullable` 属性：
- `Mapped[str]`：默认 `nullable=False`，非空列
- `Mapped[Optional[str]]` 或 `Mapped[str | None]`：默认 `nullable=True`，可空列

推荐显式标注 `nullable` 参数，兼顾可读性与明确性，避免类型推断偏差。

## 三、常用列类型编写规范
所有列定义均使用 `mapped_column()`，以下为高频类型的标准写法与 Alembic 兼容说明。

### 3.1 数值类型
```python
from sqlalchemy import Integer, BigInteger, Float, Numeric
from sqlalchemy.orm import Mapped, mapped_column

# 普通整数，常用作主键
id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

# 大整数，用于存储超大ID、金额（分）
amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

# 浮点数，用于非精确计算场景
score: Mapped[float] = mapped_column(Float, default=0.0)

# 高精度十进制，用于金融金额场景
price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
```
- **Alembic 兼容性**：可完全识别类型的新增、删除；类型变更需在 `env.py` 开启 `compare_type=True` 才能检测。

### 3.2 字符串与文本类型
```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

# 定长字符串，必须指定长度
username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

# 长文本，无长度限制，用于存储富文本、备注等
description: Mapped[Optional[str]] = mapped_column(Text, default='')
```
- **Alembic 兼容性**：String 长度变更默认无法检测，需开启 `compare_type=True`；Text 类型变更可正常识别。

### 3.3 布尔类型
```python
from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column

is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```
- **Alembic 兼容性**：完全支持，可识别新增、删除与默认值变更。

### 3.4 日期时间类型
```python
from datetime import datetime
from sqlalchemy import DateTime, Date, func
from sqlalchemy.orm import Mapped, mapped_column

# 创建时间：数据库侧默认值，推荐生产环境使用
created_at: Mapped[datetime] = mapped_column(
    DateTime,
    server_default=func.now(),
    nullable=False
)

# 更新时间：Python ORM 层触发更新
updated_at: Mapped[Optional[datetime]] = mapped_column(
    DateTime,
    onupdate=datetime.utcnow
)

# 纯日期列
due_date: Mapped[Optional[datetime]] = mapped_column(Date)
```

#### 关键属性区分（Alembic 高频踩坑点）
| 属性 | 作用层级 | 数据库表现 | Alembic 生成 DDL |
|------|----------|------------|------------------|
| `default` | Python ORM 层 | 无默认值约束，插入时由 ORM 赋值 | 不生成 DEFAULT 语句 |
| `server_default` | 数据库层 | 表结构包含 DEFAULT 约束 | 生成 DEFAULT 语句 |
| `onupdate` | Python ORM 层 | 无任何数据库逻辑，仅 ORM 更新时触发 | 不生成任何 DDL |

> 生产环境推荐使用 `server_default` 保证数据一致性；`onupdate` 仅在 ORM 操作时生效，原生 SQL 更新不会触发。

### 3.5 枚举类型（重点避坑）
推荐采用「`str + Enum`」的写法，兼顾类型安全与数据库兼容性。
```python
from enum import Enum
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

# 枚举定义
class UserStatus(str, Enum):
    DRAFT = 'draft'
    ACTIVE = 'active'
    ARCHIVED = 'archived'

# 模型中使用
status: Mapped[UserStatus] = mapped_column(
    SAEnum(UserStatus, name='enum_user_status'),
    default=UserStatus.DRAFT,
    nullable=False
)
```

#### Alembic 兼容说明
1.  **新增枚举列**：可自动识别并生成建列语句。
2.  **枚举值变更**（新增/修改/删除枚举成员）：**默认完全无法检测**，属于 autogenerate 核心盲区。
    - PostgreSQL 原生枚举：需手动编写 `ALTER TYPE ... ADD VALUE` 语句，或安装 `alembic-postgresql-enum` 插件扩展检测能力。
    - MySQL/SQLite：枚举底层通过 VARCHAR + CHECK 实现，值变更需手动调整约束。
3.  **枚举重命名**：会被识别为「删除旧枚举 + 新增新枚举」，需手动修正脚本。

> 工程化建议：枚举值变更不频繁的场景优先使用 `String` 类型存储，业务层做校验，彻底规避迁移兼容问题。

## 四、约束与索引编写规范
### 4.1 主键约束
- 单列主键直接在列上声明，Alembic 可正常识别。
- 复合主键需在多列上分别设置 `primary_key=True`。
- **注意**：主键字段的新增、删除与变更，Alembic 默认无法自动识别，需手动编写迁移脚本。

### 4.2 单列唯一约束与索引
```python
# 单列唯一约束
username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

# 单列普通索引
phone: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
```

### 4.3 复合约束与索引（__table_args__）
跨多列的唯一约束、索引必须通过 `__table_args__` 定义，且必须显式命名。

```python
__table_args__ = (
    # 复合唯一约束：同一用户下不能有重名的订单
    UniqueConstraint('user_id', 'order_no', name='uq_order_user_id_order_no'),
    # 复合索引：加速按用户+时间的组合查询
    Index('ix_order_user_id_created_at', 'user_id', 'created_at'),
)
```

#### __table_args__ 语法强制要求
1.  必须是**元组类型**，即使只有一个元素，末尾也必须加逗号。
2.  所有约束、索引都放在该元组中，按顺序排列。
3.  错误写法（缺逗号会被识别为单个对象，导致 Alembic 扫描失败）：
    ```python
    # 错误：缺少逗号
    __table_args__ = (Index('ix_xxx', 'col1'))
    # 正确
    __table_args__ = (Index('ix_xxx', 'col1'),)
    ```

### 4.4 外键约束
```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

parent_id: Mapped[int] = mapped_column(
    ForeignKey('demo_parent.id', ondelete='CASCADE'),
    nullable=False
)
```
- 外键参数格式为 `表名.列名`（字符串），不是 Python 类名。
- `ondelete='CASCADE'` 是**数据库层级联**，删除父行时数据库自动删除子行，Alembic 会生成对应外键约束。
- **Alembic 兼容性**：可识别外键的新增、删除与级联规则变更。

## 五、表间关系编写规范
### 5.1 一对多 / 多对一关系
```python
# 父表（一的一方）
class DemoParent(Base):
    __tablename__ = 'demo_parent'
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # 一对多关系：返回子对象列表
    children = relationship(
        'DemoChild',
        back_populates='parent',
        cascade='all, delete-orphan'
    )

# 子表（多的一方）
class DemoChild(Base):
    __tablename__ = 'demo_child'
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey('demo_parent.id'))
    
    # 多对一关系：返回单个父对象
    parent = relationship('DemoParent', back_populates='children')
```

#### 核心规则说明
1.  `relationship` 使用字符串类名（如 `'DemoChild'`），避免循环导入问题。
2.  `back_populates` 双向配对，双方属性名必须对应，保证对象级双向同步。
3.  **Alembic 关键说明**：`relationship` 是纯 ORM 层逻辑，**不会生成任何数据库结构**；只有外键列才会生成数据库层面的约束。修改 relationship 的参数、名称都不会触发 autogenerate 变更。

### 5.2 级联操作两层区分
| 层级 | 配置位置 | 作用范围 | Alembic 是否生成 DDL |
|------|----------|----------|----------------------|
| 数据库层级联 | `ForeignKey(ondelete='CASCADE')` | 原生 SQL 删除父行时生效 | 是 |
| ORM 层级联 | `relationship(cascade='...')` | ORM 操作删除父对象时生效 | 否 |

生产环境建议同时配置，保证原生 SQL 和 ORM 操作行为一致。

## 六、Alembic autogenerate 兼容避坑指南
### 6.1 可准确识别的变更
- 表的新增、删除
- 列的新增、删除
- 列 `nullable` 属性的变更
- 命名约束（唯一键、外键、索引）的新增、删除
- 列类型变更（需开启 `compare_type=True`）
- 服务器默认值变更（需开启 `compare_server_default=True`）

### 6.2 无法识别 / 识别错误的场景
| 变更场景 | autogenerate 表现 | 处理方式 |
|----------|-------------------|----------|
| 表名重命名 | 识别为「删除旧表 + 新增新表」 | 手动编写 `op.rename_table()` |
| 列名重命名 | 识别为「删除旧列 + 新增新列」 | 手动编写 `op.alter_column()` 重命名逻辑 |
| 索引/约束重命名 | 识别为「删除旧约束 + 新增新约束」 | 手动修正脚本，使用重命名语法 |
| 主键结构变更 | 完全无法检测 | 手动编写迁移脚本 |
| 枚举值增减 | 完全无法检测 | 手动编写枚举类型变更语句 |
| 表/列注释变更 | 默认无法检测 | 配置扩展或手动补充 |
| 视图、存储过程、触发器 | 完全不识别 | 全手动管理 |
| 业务数据变更（DML） | 完全不识别 | 手动编写数据迁移脚本 |

### 6.3 提升准确率的配置
在 `alembic/env.py` 的 `context.configure` 中添加以下参数：
```python
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    compare_type=True,            # 检测列类型及长度变更
    compare_server_default=True,  # 检测服务器默认值变更
    render_as_batch=True,         # 兼容 SQLite 的 ALTER TABLE 限制
    include_schemas=True,         # 支持多 schema 场景
)
```

### 6.4 铁律规范
**自动生成的迁移脚本必须人工审核，严禁直接执行**。
`--autogenerate` 是辅助工具，不是银弹，生成后必须逐行校验逻辑是否符合预期，避免数据丢失或结构错误。

## 七、完整模型示例
以下为符合本指南全部规范的完整示例，可直接作为项目模板使用：
```python
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Enum as SAEnum, Float,
    ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base


class StatusEnum(str, Enum):
    DRAFT = 'draft'
    ACTIVE = 'active'
    ARCHIVED = 'archived'


class DemoParent(Base):
    __tablename__ = 'demo_parent'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default='')
    status: Mapped[StatusEnum] = mapped_column(
        SAEnum(StatusEnum, name='enum_demo_status'),
        default=StatusEnum.DRAFT,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=datetime.utcnow
    )

    children = relationship(
        'DemoChild',
        back_populates='parent',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        Index('ix_demo_parent_status_active', 'status', 'is_active'),
    )


class DemoChild(Base):
    __tablename__ = 'demo_child'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey('demo_parent.id', ondelete='CASCADE'),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    due_date: Mapped[Optional[datetime]] = mapped_column(Date)

    parent = relationship('DemoParent', back_populates='children')

    __table_args__ = (
        UniqueConstraint('parent_id', 'label', name='uq_child_parent_label'),
    )
```

## 八、最佳实践总结
1.  **统一规范优先**：全项目遵循相同的命名、导入、结构规范，降低团队协作成本，提升自动生成准确率。
2.  **显式命名约束**：所有索引、唯一键、外键都指定 name 参数，避免匿名约束导致的迁移误判。
3.  **默认值分层使用**：创建时间等全局字段用 `server_default` 保证数据一致性；业务逻辑字段可用 `default`。
4.  **自动生成+人工审核**：`--autogenerate` 只做脚手架，生成后必须逐行校验，杜绝数据丢失风险。
5.  **破坏性变更平滑处理**：删表、删字段、字段重命名优先采用「新增字段→双写→下线旧字段」的多版本方案，避免不可逆操作。
6.  **枚举轻量使用**：枚举值频繁变更的场景，优先用 String 存储+业务层校验，减少迁移兼容成本。

---

## 九、本项目的SQLite 环境专属适配补充(非常重要)
### 9.1 SQLite 类型机制与 ORM 映射对应
SQLite 没有严格的静态类型系统，核心基于**类型亲和性（Type Affinity）**工作：建表时声明的类型仅作为「亲和推荐」，底层实际只有 5 种存储类（NULL / INTEGER / REAL / TEXT / BLOB），理论上任何类型的列都可以存入任意数据。

SQLAlchemy 会自动完成 ORM 类型到 SQLite 亲和类型的映射，原教程的列定义语法**无需修改**，但实际表现与主流数据库有差异，具体对应如下：

| ORM 类型 | SQLite 实际亲和类型 | 实际表现差异 | Alembic 可识别性 |
|----------|---------------------|--------------|------------------|
| `Integer` / `BigInteger` | `INTEGER` | 行为与主流数据库一致，整数存储 | 完全识别 |
| `String(N)` | `TEXT` | **长度限制完全不生效**，仅作为语义标注，不会截断超长字符串 | 可识别新增/删除；长度变更无实际意义 |
| `Text` | `TEXT` | 与 `String` 底层无任何区别，功能完全一致 | 完全识别 |
| `Boolean` | `INTEGER` | 底层存 0/1 整数，SQLAlchemy 自动与 Python 布尔值互转 | 完全识别 |
| `Float` / `Numeric` | `REAL` | 浮点数存储；`Numeric` 的精度声明不生效，实际为浮点精度 | 完全识别 |
| `DateTime` / `Date` | `TEXT` | 底层存 ISO 格式字符串，SQLAlchemy 自动与 `datetime` 对象互转 | 完全识别 |
| `Enum` | `TEXT` + CHECK 约束 | 无原生枚举类型，通过 CHECK 约束限制取值范围；约束变更无法自动检测 | 可识别列新增；枚举值变更需手动处理 |

> 核心结论：ORM 层写法完全兼容，无需调整；但不能依赖 SQLite 做数据库层面的长度校验、精度校验，相关校验需在业务代码层实现。

### 9.2 SQLite 下 Alembic 迁移的核心限制与解决方案
SQLite 的 `ALTER TABLE` 语法能力极弱，仅支持**新增列**和**重命名表**，不支持删除列、修改列类型、重命名列、删除/修改约束等常用操作，这是 SQLite 环境下迁移的最大痛点。

#### 解决方案：批量迁移模式（Batch Mode）
Alembic 提供了 `batch_alter_table` 批量模式，通过「重建表」的方式兼容所有 DDL 操作，原理是：
1.  创建一张符合新结构的临时表
2.  将旧表数据拷贝到临时表
3.  删除旧表
4.  将临时表重命名为原表名
5.  重建所有索引、外键约束

#### 开启方式
在 `alembic/env.py` 的 `context.configure` 中添加配置，开启自动批量模式：
```python
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    # SQLite 专属：自动使用批量模式处理不支持的 ALTER 操作
    render_as_batch=True,
    # 其余配置保持不变
    compare_type=True,
    compare_server_default=True,
)
```

开启后，`--autogenerate` 会自动为不兼容的 DDL 操作生成批量迁移代码，示例如下：
```python
def upgrade():
    with op.batch_alter_table('demo_parent') as batch_op:
        batch_op.drop_column('old_field')
        batch_op.alter_column('name', type_=String(200))
```

#### 注意事项
1.  **大表性能风险**：批量模式会整表重建，数据量大的表执行会很慢，且占用额外磁盘空间，大表变更需评估执行时间。
2.  **外键关联风险**：重建表过程中可能影响关联外键，建议变更前开启外键校验并备份数据。
3.  **复杂约束兼容**：部分特殊约束、自定义触发器在重建时可能丢失，生成脚本后需人工校验。

### 9.3 SQLite 约束与功能专属坑点
#### 1. 外键约束默认关闭
SQLite 为了向后兼容，**默认禁用外键约束**，即使你在 ORM 中定义了 `ForeignKey` 和 `ondelete='CASCADE'`，数据库层面也不会生效，删除父记录时子记录不会被级联删除。

##### 生效方式
必须在每次数据库连接建立后，执行 PRAGMA 指令开启：
```python
# 在 SQLAlchemy 引擎创建时添加事件监听
from sqlalchemy import create_engine, event

engine = create_engine('sqlite:///demo.db')

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()
```

Alembic 迁移环境也需要同步配置，在 `env.py` 中添加相同逻辑，保证迁移时外键约束生效。

#### 2. 枚举约束弱校验
SQLite 没有原生枚举类型，SQLAlchemy 的 `Enum` 会生成 `TEXT` 类型 + `CHECK` 约束实现取值限制。
- 优势：ORM 写法完全兼容，基础校验生效
- 劣势：枚举值的新增、修改、删除，`--autogenerate` 无法自动检测到 CHECK 约束的变化，必须手动编写迁移脚本调整。

#### 3. 主键自增的特殊规则
SQLite 中，只要列声明为 `INTEGER PRIMARY KEY`，就会默认自增，无需额外指定 `autoincrement=True`。
- 不加 `autoincrement`：复用已删除的 ID，性能更好，满足绝大多数场景
- 加 `autoincrement=True`：生成严格单调递增的 ID，永不复用，对应 SQLite 的 `AUTOINCREMENT` 关键字，性能略差

原教程的写法完全兼容，可根据业务需求选择。

### 9.4 SQLite 环境 Alembic 最佳配置模板
针对 SQLite 环境，推荐使用以下优化后的 `env.py` 核心配置，规避 90% 以上的适配问题：
```python
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # 开启批量模式，兼容 SQLite DDL 限制
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # 迁移时开启外键约束
        connection.execute(text("PRAGMA foreign_keys = ON"))
        
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # 开启批量模式
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()
```

### 9.5 原教程规则的 SQLite 适配总结
1.  **完全通用，无需修改**：
    表命名规范、列定义语法、索引/唯一约束写法、`relationship` 关系定义、`__table_args__` 语法、自动生成脚本的审核规范、版本管理流程。

2.  **仅需调整配置，无需改 ORM 代码**：
    开启 `render_as_batch=True` 兼容 DDL 限制；连接时开启外键 PRAGMA。

3.  **需要额外注意底层差异**：
    字符串长度不生效、枚举值变更无法自动检测、无数据库级精度约束，相关校验需下沉到业务代码层。

4.  **完全不适用的能力**：
    原生枚举类型、存储过程、触发器、视图的自动迁移管理，均需手动编写脚本维护。

