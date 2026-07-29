---
author: e3mydu1f,Kimi
version:
date modified: July 26th 2026, 1:36 pm
date created: July 26th 2026, 12:35 pm
---
本规范基于 Google 的 Python 规范，进行了修改和更新。
>Google python规范源地址为为 https://google.github.io/styleguide/pyguide.html
## 1 背景 (Background)

Python 是 Google 主要的动态语言。这份规范列出了 Python 程序的 **"该做"与"不该做"**。Google 提供了 Vim 配置，并推荐团队使用 ~~(已过时，不推荐)**Black** 或 **Pyink** 自动格式化工具~~**Ruff**来避免格式争论。

---

## 2 Python 语言规则 (Language Rules)

### 2.1 Lint — 代码静态检查

**核心要求**：必须运行 `ruff check` 检查代码。

- **抑制警告**：如果 ruff 的某条警告不适用，用行内注释 `# noqa: 规则代码` 精确关闭，并附上解释说明理由。也可使用更具可读性的 `# ruff: ignore[规则名]` 语法。禁止使用无差别的 `# noqa` 关闭当前行所有规则。
- **未使用参数**：推荐在函数开头用 `del unused_arg` 删除并注释说明，而不是用 `_` 前缀或下划线赋值（这些会破坏按名传参且不能真正确保参数未被使用）。

```python
# Yes
def viking_cafe_order(spam: str, beans: str, eggs: str | None = None) -> str:
    del beans, eggs  # Unused by vikings.
    return spam + spam + spam
```

**补充说明**：
- 单行抑制示例：`x = 1  # noqa: F841  # 该变量由外部框架反射使用`
- 代码块范围抑制使用 `# ruff: disable[规则代码]` 与 `# ruff: enable[规则代码]` 成对包裹
- 文件级抑制在文件头部使用 `# ruff: noqa: 规则代码`

---
### 2.2 Imports — 导入规则

**核心原则**：只导入**包和模块**，不直接导入**类、函数或类型**（`typing`、`collections.abc`、`typing_extensions`、`six.moves` 除外）。

| 场景 | 推荐写法 |
|------|---------|
| 导入包/模块 | `import x` |
| 从包中导入模块 | `from x import y` |
| 名称冲突/太长/太泛 | `from x import y as z` |
| 标准缩写 | `import numpy as np` |

**禁止相对导入**，即使模块在同一包内，也要用完整包名。

```python
# Yes
from sound.effects import echo
echo.EchoFilter(input, output, delay=0.7, atten=4)

# No
import jodie  # 不清楚作者想导入哪个 jodie
```

### 2.3 Packages — 包路径

**所有新代码**必须使用完整包名导入模块。不要假设主二进制文件所在目录在 `sys.path` 中。

### 2.4 Exceptions — 异常处理

- **用内置异常**：如 `ValueError` 表示前置条件被破坏。
- **`assert` 不能替代逻辑**：`assert` 可能在优化模式下被移除，不能用于关键逻辑验证。
- **自定义异常**：必须继承现有异常类，名称以 `Error` 结尾，避免重复（如 `foo.FooError`）。
- **禁止裸 `except:`**：除非重新抛出异常，或在程序最外层做隔离保护。
- **`try/except` 块要尽量小**：避免隐藏真正的错误。
- **用 `finally` 做清理**。

```python
# Yes
if minimum < 1024:
    raise ValueError(f'Min. port must be at least 1024, not {minimum}.')
port = self._find_next_open_port(minimum)
if port is None:
    raise ConnectionError(f'Could not connect to service on port {minimum} or higher.')
assert port >= minimum, (  # 不依赖此 assert 的结果
    f'Unexpected port {port} when minimum was {minimum}.')
```

### 2.5 Mutable Global State — 可变全局状态

**避免可变全局状态**。如果必须使用：
- 在模块级或类属性中声明，名前加 `_` 表示内部使用。
- 通过公共函数/方法访问。
- 在注释中解释设计原因。

**模块级常量**是允许的，且受鼓励，命名全大写下划线分隔：
```python
_MAX_HOLY_HANDGRENADE_COUNT = 3
SIR_LANCELOTS_FAVORITE_COLOR = "blue"
```

### 2.6 Nested/Local/Inner Classes and Functions — 嵌套类与函数

**允许使用**，但有限制：
- 仅当需要**闭包捕获局部变量**（除 `self` 或 `cls` 外）时才嵌套。
- 不要为了"隐藏"函数而嵌套；更好的做法是在模块级用 `_` 前缀命名，这样测试仍可访问。

### 2.7 Comprehensions & Generator Expressions — 推导式

**简单场景可以使用**，但：
- **禁止多个 `for` 子句或复杂过滤条件**。
- **优先可读性，而非简洁性**。

```python
# Yes
result = [mapping_expr for value in iterable if filter_expr]

# No（多个 for，难读）
result = [(x, y) for x in range(10) for y in range(5) if x * y > 10]
```

### 2.8 Default Iterators and Operators — 默认迭代器

对支持默认迭代器的类型（list、dict、file 等），**直接使用默认方式**，而非调用方法。

```python
# Yes
for key in adict: ...
if obj in alist: ...
for line in afile: ...
for k, v in adict.items(): ...

# No
for key in adict.keys(): ...
for line in afile.readlines(): ...
```

### 2.9 Generators — 生成器

**可以使用**。生成器函数的 docstring 中用 `Yields:` 而非 `Returns:`。如果生成器管理昂贵资源，确保强制清理（可用上下文管理器 PEP-0533）。

### 2.10 Lambda Functions — Lambda 表达式

**单行场景允许使用**。如果超过 60-80 字符或多行，应定义为普通嵌套函数。

对于常见操作（如乘法），优先使用 `operator` 模块：
```python
# Yes
from operator import mul
# 用 mul 而非 lambda x, y: x * y
```

### 2.11 Conditional Expressions — 条件表达式（三元运算符）

**简单场景可用**。每个部分（真值表达式、条件、假值表达式）必须能放在一行内。复杂时改用完整 `if` 语句。

```python
# Yes
one_line = 'yes' if predicate(value) else 'no'

# No（假值部分换行不当）
bad_line_breaking = ('yes' if predicate(value) else
                     'no')
```

### 2.12 Default Argument Values — 默认参数值

**可以使用，但禁止用可变对象做默认值**。

```python
# Yes
def foo(a, b=None):
    if b is None:
        b = []

def foo(a, b: Sequence = ()):  # 空元组不可变，OK

# No
def foo(a, b=[]): ...           # 列表可变！
def foo(a, b=time.time()): ...   # 只在模块加载时求值一次
def foo(a, b: Mapping = {}): ... # 字典可变！
```

### 2.13 Properties — 属性装饰器

**允许使用**，但应满足普通属性访问的预期：**廉价、直接、不令人惊讶**。

- 仅当需要**简单计算**或**控制访问**时使用。
- 如果只是简单地 get/set 内部属性，不如直接公开属性。
- 用 `@property` 装饰器实现，不要手写 descriptor。
- 继承中使用 property 要小心，不要用 property 实现子类可能需要扩展覆盖的计算逻辑。

### 2.14 True/False Evaluations — 真假值判断

**尽可能使用隐式布尔判断**，但有例外：

| 场景 | 推荐写法 |
|------|---------|
| 判断 `None` | `if foo is None:` |
| 布尔变量为 False | `if not x:` |
| 区分 `False` 和 `None` | `if not x and x is not None:` |
| 序列是否为空 | `if seq:` / `if not seq:` |
| 整数与 0 比较 | `if i % 10 == 0:`（整数比较显式更安全）|

```python
# Yes
if not users:
    print('no users')

# No
if len(users) == 0:
    print('no users')
```

**注意**：`numpy` 数组在隐式布尔上下文中可能抛出异常，用 `.size` 判断空值。

### 2.16 Lexical Scoping — 词法作用域

**允许使用**（嵌套函数引用外层变量）。注意 Python 的变量绑定规则：如果在内层函数中对某变量赋值，Python 会将其视为局部变量。

### 2.17 Function and Method Decorators — 装饰器

**谨慎使用**，只在有明显优势时使用。

- 装饰器应遵循函数导入和命名规范。
- 装饰器文档字符串应明确说明它是装饰器。
- **避免在装饰器中依赖外部资源**（文件、socket、数据库），因为装饰器在定义时（导入时）执行。
- **避免 `staticmethod`**：写成模块级函数。
- **`classmethod` 仅限**：命名构造函数，或修改必要的全局状态（如进程级缓存）。

### 2.18 Threading — 线程

**不要依赖内置类型的原子性**。Python 内置类型的操作在某些边界情况下并非原子（如自定义了 `__hash__` 或 `__eq__`）。

- 线程间通信优先用 `queue.Queue`。
- 否则用 `threading` 模块及其锁原语。
- 优先用条件变量 `threading.Condition`，而非低级锁。

### 2.19 Power Features — 高级特性

**避免使用**以下"强大但危险"的特性：
- 自定义元类
- 字节码操作
- 动态继承、对象重设父类
- 导入 hack
- 反射（某些 `getattr` 用法）
- `__del__` 自定义清理

标准库内部使用这些特性（如 `abc.ABCMeta`、`dataclasses`、`enum`）是可以的。

### 2.20 Modern Python: from \_\_future\_\_ imports

**鼓励使用** `from __future__ import` 语句，使代码提前使用现代 Python 特性，便于未来升级。

例如，在需要兼容 Python 3.5 时：
```python
from __future__ import generator_stop
```

即使当前代码没有用到某个 `__future__` 特性，保留它也能防止后续修改者无意中依赖旧行为。

### 2.21 Type Annotated Code — 类型注解

**强烈鼓励**在更新代码时启用类型分析。

- 用 `pytype` 等工具在构建时做类型检查。
- 添加或修改公共 API 时，**必须包含类型注解**。
- 如果类型检查带来不良副作用，添加 TODO 或 bug 链接说明。。
---

## 3 Python 风格规则 (Style Rules)

### 3.1 Semicolons — 分号

**禁止**用分号结束行，也**禁止**用分号将多条语句放在同一行。

### 3.2 Line length — 行长度

**最大 80 字符**。

例外：长导入语句、URL/路径/长标志注释、不含空白的长字符串常量、pylint 禁用注释。

**禁止用反斜杠 `\` 显式续行**。改用括号隐式续行。

```python
# Yes
foo_bar(self, width, height, color='black', design=None, x='foo',
        emphasis=None, highlight=0)

# Yes（字符串续行用括号）
x = ('This will build a very long long '
     'long long long long long long string')

# No
if width == 0 and height == 0 and \
        color == 'red' and emphasis == 'strong':
```

**优先在最高语法层级断行**。

```python
# Yes
bridgekeeper.answer(
    name="Arthur", quest=questlib.find(owner="Arthur", perilous=True))

# No
bridgekeeper.answer(name="Arthur", quest=questlib.find(
    owner="Arthur", perilous=True))
```

### 3.3 Parentheses — 括号

**少用括号**。

- 元组可用括号，但非必须。
- `return`、`if`、`while` 中不要用不必要的括号。

```python
# Yes
if foo: bar()
return foo
return spam, beans
onesie = (foo,)  # 单元素元组用括号更清晰

# No
if (x): bar()
return (foo)
```

### 3.4 Indentation — 缩进

**4 个空格**，**禁止 Tab**。

隐式续行时，对齐起始分隔符，或悬挂缩进 4 空格。

```python
# Yes（对齐分隔符）
foo = long_function_name(var_one, var_two,
                         var_three, var_four)

# Yes（悬挂缩进 4 空格）
foo = long_function_name(
    var_one, var_two, var_three,
    var_four)
```

#### 3.4.1 Trailing commas — 尾随逗号

**推荐在容器元素换行时使用尾随逗号**。这会给 Black/Pyink 格式化器提示，将容器格式化为每行一个元素。

```python
# Yes
golomb4 = [
    0,
    1,
    4,
    6,
]

# No
golomb4 = [
    0,
    1,
    4,
    6,]  # 逗号在闭括号同行，不推荐
```

### 3.5 Blank Lines — 空行

- 顶层定义（函数/类）之间：**2 个空行**
- 方法定义之间、类 docstring 与第一个方法之间：**1 个空行**
- `def` 行后：**不要空行**
- 函数/方法内部：酌情使用单空行

### 3.6 Whitespace — 空白

- 括号/方括号/花括号**内部不要空格**：`spam(ham[1], {'eggs': 2})`
- 逗号/分号/冒号**前不要空格，后要空格**。
- 参数列表、索引、切片前**不要空格**：`spam(1)`、`dict['key']`
- **禁止行尾空格**。
- 二元运算符（`=`、`==`、`<`、`>`、`in`、`is`、`and`、`or` 等）**两侧各一个空格**。
- 算术运算符空格视情况判断。

**关键字参数和默认参数值的 `=` 两侧不加空格**，但**如果参数有类型注解，则 `=` 两侧要加空格**：

```python
# Yes
def complex(real, imag=0.0): return Magic(r=real, i=imag)
def complex(real, imag: float = 0.0): return Magic(r=real, i=imag)

# No
def complex(real, imag = 0.0): ...
def complex(real, imag: float=0.0): ...
```

**禁止用空格做垂直对齐**（如等号对齐、冒号对齐），这会成为维护负担。

### 3.7 Shebang Line — 解释器声明

大多数 `.py` 文件**不需要** `#!` 行。只有作为直接执行的入口文件才需要：
```python
#!/usr/bin/env python3
```

### 3.8 Comments and Docstrings — 注释与文档字符串

#### 3.8.1 Docstrings — 文档字符串格式

- 始终用 `"""`（三个双引号）。
- 第一行是**单行摘要**（不超过 80 字符），以句号/问号/感叹号结尾。
- 如需更多内容，空一行后写详细描述，从与首行第一个引号相同的位置开始。

#### 3.8.2 Modules — 模块文档

每个文件开头应有许可证声明，然后是描述模块内容和用法的 docstring。

```python
"""A one-line summary of the module or program, terminated by a period.

Leave one blank line.  The rest of this docstring should contain an
overall description of the module or program.  Optionally, it may also
contain a brief description of exported classes and functions and/or usage
examples.

Typical usage example:

  foo = ClassFoo()
  bar = foo.function_bar()
"""
```

**测试模块**的 docstring 不是必须的，只在有额外信息（如运行方式、特殊设置）时才写。

#### 3.8.3 Functions and Methods — 函数/方法文档

以下函数**必须**有 docstring：
- 公共 API 的一部分
- 非平凡大小
- 非显而易见的逻辑

docstring 应提供足够信息，使调用者无需阅读代码就能调用函数。

**特殊章节**（标题以冒号结尾）：
- **`Args:`**：列出每个参数名，后接冒号和描述。描述太长时悬挂缩进 2 或 4 空格。
- **`Returns:`**（生成器用 **`Yields:`**）：描述返回值语义。
- **`Raises:`**：列出所有相关异常及描述。不要记录 API 误用导致的异常（如参数校验失败的 `ValueError`）。

```python
def fetch_smalltable_rows(
    table_handle: smalltable.Table,
    keys: Sequence[bytes | str],
    require_all_keys: bool = False,
) -> Mapping[bytes, tuple[str, ...]]:
    """Fetches rows from a Smalltable.

    Retrieves rows pertaining to the given keys from the Table instance
    represented by table_handle.  String keys will be UTF-8 encoded.

    Args:
        table_handle: An open smalltable.Table instance.
        keys: A sequence of strings representing the key of each table
          row to fetch.  String keys will be UTF-8 encoded.
        require_all_keys: If True only rows with values set for all keys will be
          returned.

    Returns:
        A dict mapping keys to the corresponding table row data
        fetched. Each row is represented as a tuple of strings. For
        example:

        {b'Serak': ('Rigel VII', 'Preparer'),
         b'Zim': ('Irk', 'Invader'),
         b'Lrrr': ('Omicron Persei 8', 'Emperor')}

        Returned keys are always bytes.  If a key from the keys argument is
        missing from the dictionary, then that row was not found in the
        table (and require_all_keys must have been False).

    Raises:
        IOError: An error occurred accessing the smalltable.
    """
```

##### 3.8.3.1 Overridden Methods — 重写方法

如果方法用 `@override` 装饰器显式标记，且行为没有实质性改变，**不需要** docstring。否则需要 docstring。

#### 3.8.4 Classes — 类文档

类定义下方应有 docstring，描述类实例代表什么。公共属性（非 property）在 `Attributes` 章节中记录。

```python
class SampleClass:
    """Summary of class here.

    Longer class information...

    Attributes:
        likes_spam: A boolean indicating if we like SPAM or not.
        eggs: An integer count of the eggs we have laid.
    """
```

**Exception 子类**的 docstring 应描述异常**代表什么**，而非何时抛出。

```python
# Yes
class OutOfCheeseError(Exception):
    """No more cheese is available."""

# No
class OutOfCheeseError(Exception):
    """Raised when no more cheese is available."""
```

#### 3.8.5 Block and Inline Comments — 块注释与行内注释

- 复杂操作前放几行注释。
- 非显而易见的操作在行尾加注释。
- 注释 `#` 后至少一个空格。
- **不要描述代码做了什么**（假设读者懂 Python），而是解释**为什么这样做**和**设计意图**。

#### 3.8.6 Punctuation, Spelling, and Grammar

注释要注意标点、拼写和语法。写得好的注释更容易阅读。

### 3.10 Strings — 字符串

格式化字符串可用 **f-string**、`%` 运算符或 `format` 方法。用最佳判断选择。

```python
# Yes
x = f'name: {name}; score: {n}'
x = '%s, %s!' % (imperative, expletive)
x = '{}, {}'.format(first, second)

# No（用 + 拼接格式化）
x = 'name: ' + name + '; score: ' + str(n)
```

**禁止在循环中用 `+`/`+=` 累积字符串**，这可能导致 O(n²) 时间复杂度。改用列表 `append` 后 `''.join()`，或用 `io.StringIO`。

```python
# Yes
items = ['<table>']
for last_name, first_name in employee_list:
    items.append('<tr><td>%s, %s</td></tr>' % (last_name, first_name))
items.append('</table>')
employee_table = ''.join(items)
```

**引号风格**：一个文件中统一用 `'` 或 `"`。需要避免转义时可用另一种引号。

多行字符串优先用 `"""`。如果不需要额外缩进空格，用拼接单引号字符串或 `textwrap.dedent()`。

#### 3.10.1 Logging — 日志

日志函数的**第一个参数必须是字符串字面量**（不要用 f-string！），参数作为后续参数传入。这样日志实现可以收集未展开的模板字符串，且避免渲染不会被输出的日志。

```python
# Yes
logging.info('Current $PAGER is: %s', os.getenv('PAGER', default=''))

# No
logging.info(f'Current $PAGER is: {os.getenv("PAGER", default="")}')
```

#### 3.10.2 Error Messages — 错误消息

错误消息（异常消息、用户可见消息）遵循三原则：
1. 精确匹配实际错误条件
2. 插值部分清晰可识别
3. 支持简单自动化处理（如 grep）

```python
# Yes
if not 0 <= p <= 1:
    raise ValueError(f'Not a probability: {p=}')

# No
if p < 0 or p > 1:  # 对 float('nan') 也成立！
    raise ValueError(f'Not a probability: {p=}')
```

### 3.11 Files, Sockets, and similar Stateful Resources — 资源管理

**显式关闭**文件、socket 及类似有状态资源。

**优先用 `with` 语句**：
```python
with open("hello.txt") as hello_file:
    for line in hello_file:
        print(line)
```

不支持 `with` 的对象用 `contextlib.closing()`。

**不要依赖 `__del__` 自动清理**：垃圾回收时机不确定，可能导致资源泄漏。

### 3.12 TODO Comments — TODO 注释

TODO 注释格式：
```python
# TODO: crbug.com/192795 - Investigate cpufreq optimizations.
```

- 必须全大写 `TODO:`，后跟资源链接（最好是 bug 链接），再跟 `-` 和解释字符串。
- 避免用个人/团队名作为上下文。
- 如果是"未来某个时间做某事"，要给出**具体日期**或**具体事件**。

旧格式（`TODO(crbug.com/xxx)`、`TODO(username)`）已不鼓励用于新代码。

### 3.13 Imports formatting — 导入格式

- **每行一个导入**（`typing` 和 `collections.abc` 例外，允许一行导入多个符号）。
- 导入放在文件顶部，模块注释和 docstring 之后，全局变量之前。

**分组顺序**（从最通用到最特定）：
1. `from __future__ import ...`
2. Python 标准库
3. 第三方模块/包
4. 代码仓库子包导入
5. ~~（已废弃）同顶层子包的应用特定导入~~ — 新代码不需要单独分组

每组内按模块完整包路径**字典序**排序（忽略大小写）。

```python
import collections
import queue
import sys

from absl import app
from absl import flags
import bs4
import tensorflow as tf

from book.genres import scifi
from myproject.backend import huxley
from otherproject.ai import mind
```

### 3.14 Statements — 语句

**每行一条语句**。

例外：如果整个语句能放一行，测试结果可以和 `if` 放同一行。但 `try/except` 绝对不行，`if` 有 `else` 也不行。

```python
# Yes
if foo: bar(foo)

# No
if foo: bar(foo)
else:   baz(foo)

try:               bar(foo)
except ValueError: baz(foo)
```

### 3.15 Accessors — 访问器

Getter/Setter 只在提供有意义的行为时才使用：
- 获取/设置操作复杂或成本高
- 设置会触发状态失效或重建

如果只是简单读写内部属性，**直接公开属性**。可以用 `@property` 处理简单逻辑。

命名遵循 `get_foo()` / `set_foo()`。

### 3.16 Naming — 命名规范

**名称应具有描述性**。避免缩写，特别是对外部读者不熟悉的缩写。

#### 3.16.1 应避免的名字

- 单字符名（例外：循环计数器 `i,j,k`、异常标识符 `e`、文件句柄 `f`、私有类型变量 `_T`、数学算法中的标准符号）
- 包/模块名中的连字符 `-`
- `__double_leading_and_trailing__`（Python 保留）
- 冒犯性词汇
- 无意义包含类型的变量名（如 `id_to_name_dict`）

#### 3.16.2 命名约定

| 类型 | 公开 | 内部 |
|------|------|------|
| 包 | `lower_with_under` | |
| 模块 | `lower_with_under` | `_lower_with_under` |
| 类 | `CapWords` | `_CapWords` |
| 异常 | `CapWords` | |
| 函数 | `lower_with_under()` | `_lower_with_under()` |
| 全局/类常量 | `CAPS_WITH_UNDER` | `_CAPS_WITH_UNDER` |
| 全局/类变量 | `lower_with_under` | `_lower_with_under` |
| 实例变量 | `lower_with_under` | `_lower_with_under` (protected) |
| 方法名 | `lower_with_under()` | `_lower_with_under()` (protected) |
| 函数/方法参数 | `lower_with_under` | |
| 局部变量 | `lower_with_under` | |

- 模块内相关类和顶层函数可以放在一起，**不需要像 Java 那样一个类一个文件**。
- 模块名用 `lower_with_under.py`，不要用 `CapWords.py`（会与类名混淆）。
- 单元测试文件名和方法名用 `lower_with_under`，如 `test_<method_under_test>_<state>`。

#### 3.16.3 File Naming — 文件名

- 必须用 `.py` 扩展名
- **禁止用连字符 `-`**
- 如需无扩展名执行，用符号链接或 bash wrapper

#### 3.16.4 数学符号例外

数学密集型代码中，如果短变量名与参考论文/算法中的标准符号一致，允许使用。但需：
1. 在注释/docstring 中引用来源
2. 公共 API 仍用描述性名称
3. 用 `pylint: disable=invalid-name` 关闭警告

### 3.17 Main — 入口函数

可执行文件的主功能应放在 `main()` 函数中，并用 `if __name__ == '__main__':` 保护。

使用 absl 时：
```python
from absl import app

def main(argv: Sequence[str]):
    ...

if __name__ == '__main__':
    app.run(main)
```

否则：
```python
def main():
    ...

if __name__ == '__main__':
    main()
```

**顶层代码在导入时就会执行**，注意不要调用函数、创建对象或执行不应在导入时运行的操作。

### 3.18 Function length — 函数长度

**优先写小而聚焦的函数**。没有硬性限制，但如果超过约 40 行，考虑是否能拆分。

### 3.19 Type Annotations — 类型注解

#### 3.19.1 General Rules — 一般规则

- 熟悉 PEP 484 类型提示。
- `self`/`cls` 一般不需要注解（除非需要 `Self`）。
- `__init__` 的返回值不需要注解（总是 `None`）。
- 不需要注解所有函数，但至少注解**公共 API**。
- 尽可能用更具体的类型。禁止用 `Any` 类型注解。

#### 3.19.2 Line Breaking — 换行

类型注解后函数签名常变长，遵循缩进规则：
- 每个参数和返回类型放独立行
- 最后一个参数后加逗号，使返回类型也能独占一行

```python
# Yes
def my_method(
    self,
    first_var: int,
    second_var: Foo,
    third_var: Bar | None,
) -> int:
    ...
```

类型太长时，考虑用**类型别名**。

#### 3.19.3 Forward Declarations — 前向声明

如果需要在类定义前引用该类，用 `from __future__ import annotations` 或字符串形式：

```python
# Yes
from __future__ import annotations

class MyClass:
    def __init__(self, stack: Sequence[MyClass]) -> None: ...

# 或
class MyClass:
    def __init__(self, stack: Sequence['MyClass']) -> None: ...
```

#### 3.19.4 Default Values — 默认值与注解

**有类型注解且有默认值时，`=` 两侧加空格**：

```python
# Yes
def func(a: int = 0) -> int: ...

# No
def func(a:int=0) -> int: ...
```

#### 3.19.5 NoneType

`None` 是 `NoneType` 的别名。参数可为 `None` 时必须显式声明。

推荐用 `|` 联合类型（Python 3.10+）：
```python
# Yes
def modern_or_union(a: str | int | None, b: str | None = None) -> str: ...

# No（隐式 Optional）
def implicit_optional(a: str = None) -> str: ...
```

#### 3.19.6 Type Aliases — 类型别名

复杂类型可声明别名。别名名用 `CapWords`。仅模块内使用的别名加 `_` 前缀。

```python
from typing import TypeAlias

_LossAndGradient: TypeAlias = tuple[tf.Tensor, tf.Tensor]
ComplexTFMap: TypeAlias = Mapping[str, _LossAndGradient]
```

#### 3.19.7 Ignoring Types — 忽略类型

行内用 `# type: ignore`。pytype 用户可用 `# pytype: disable=attribute-error`。

#### 3.19.8 Typing Variables — 变量类型

内部变量类型难以推断时，用**注解赋值**：
```python
a: Foo = SomeUndecoratedFunction()
```

**不再使用**行尾 `# type: Foo` 注释（Python 3.6 之前的旧方式）。

#### 3.19.9 Tuples vs Lists

- `list[T]`：单一类型重复
- `tuple[T, ...]`：单一类型重复但不可变
- `tuple[int, str, float]`：固定数量、不同类型（常用于函数返回类型）

#### 3.19.10 Type variables — 类型变量

```python
from collections.abc import Callable
from typing import ParamSpec, TypeVar

_P = ParamSpec("_P")
_T = TypeVar("_T")

def next(l: list[_T]) -> _T:
    return l.pop()
```

类型变量命名：
- 无约束、不对外可见的：`_T`、`_P`
- 有约束的：描述性名称，如 `AddableType`

#### 3.19.11 String types — 字符串类型

- **新代码不要用 `typing.Text`**（仅用于 Python 2/3 兼容）
- 文本数据用 `str`，二进制数据用 `bytes`
- 如果函数中所有字符串类型相同，用 `AnyStr`

#### 3.19.12 Imports For Typing — 类型导入

从 `typing` 和 `collections.abc` 导入类型时，**直接导入符号本身**（允许一行导入多个）。这保持注解简洁，且是全球通行做法。

```python
from collections.abc import Mapping, Sequence
from typing import Any, Generic, cast, TYPE_CHECKING
```

注解函数签名时，优先用抽象容器类型（如 `Sequence`）而非具体类型（如 `list`）。

#### 3.19.13 Conditional Imports — 条件导入

仅当类型检查所需导入必须在运行时避免时才用 `if TYPE_CHECKING:`。**这是不推荐的模式**，应优先重构代码。

```python
import typing
if typing.TYPE_CHECKING:
    import sketch

def f(x: "sketch.Sketch"): ...
```

#### 3.19.14 Circular Dependencies — 循环依赖

类型导致的循环依赖是**代码异味**，应考虑重构。技术上可用 `Any` 替代：

```python
from typing import Any

some_mod = Any  # some_mod.py imports this module.

def my_method(self, var: "some_mod.SomeType") -> None: ...
```

#### 3.19.15 Generics — 泛型

注解时**必须指定泛型类型参数**，否则会被视为 `Any`。

```python
# Yes
def get_names(employee_ids: Sequence[int]) -> Mapping[int, str]: ...

# No（会被解释为 Sequence[Any] -> Mapping[Any, Any]）
def get_names(employee_ids: Sequence) -> Mapping: ...
```

如果最佳类型参数是 `Any`，显式写出；但很多时候 `TypeVar` 更合适。

---

## 4 结语 (Parting Words)

**保持一致 (BE CONSISTENT)**。

如果你正在编辑代码，花几分钟看看周围的代码风格。如果代码用 `_idx` 做索引变量名，你也应该这样做。风格指南的目的是建立共同的编码词汇，让人们专注于**你在说什么**，而非**你怎么说**。（这一条慎用，因为本项目是一个新项目的规范初期制定而非旧项目的自我规范优化，所以应该让项目看齐此规范文档）

但一致性也有边界：不要为了保持一致而拒绝采用新风格的好处，也不要用"保持一致"作为维持旧风格的借口。代码库应该倾向于随时间向新风格收敛。