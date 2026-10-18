# Phase 5 batch 04：Complex Numbers / Vectors 契约提案

准备日期：2026-10-18。**status=draft，reviewer=null，等待 Claude Code 数学与契约审查。**
本文仅为设计，未加入任何 Pydantic 模型、checker、运行时模板或发布记录。
对应[四题完整数学稿](batch-04-review.md)。以下类型名称均为拟议名称。

## 1. 范围与现状

按本次明确列出的四题保留 coverage 编号 **17–20**。任务标题的“16–20”
与四题清单不一致；本次不自行补题 16，也不声称已有 20 个审核模板。

| 位置 | 当前能力 / 限制 | 本批必要变化（待批准） |
| --- | --- | --- |
| `app/core/parsing.py` | 已允许常量 `I`、`pi`；仅有界标量运算 | 保持白名单、语法和预算；不添加 `arg/acos/asin/diff/limit` 或向量语法 |
| `ComputationSpec` | 没有 complex/vector 专属成员；`EquationSpec` 已有 variable/left/right | 新增 principal_argument/vector_angle/line_intersection_3d；复数多项式复用 equation |
| `Context` / `solve_equation` | 显式拒绝 complex；实数 continuous_domain 不能用于复数多项式 | 在受限多项式分支处理复数，不把实数域算法直接放开 |
| `DomainSpec` | complex 的 constraints 只允许 eq/ne；域扰动会同步变量数系 | 复用；补查其他域约束入口，禁止涉及复数变量的排序谓词 |
| `RuleParameters` / `AssumptionCheck` | 按 operation 有限 union/注册表 | 仅增加本文列出的成员；不以字符串规则名或说明文本代替数学证据 |
| `Template.check_references` | 部分逻辑假定 check 有 variable | 对新种类按 kind/operation 明确分派，校验实际 computation 绑定 |
| `validate_expressions` | 当前只遍历 Model 和 list，**不会遍历 tuple** | 将 tuple 纳入递归；每个分量仍经过同一 parser 和符号作用域校验 |
| `ConclusionResult` | classification 只支持驻点分类 | 直线关系使用独立 typed payload，避免把驻点枚举和空间关系混用 |
| 隔离/API | 已有有界 worker、超时和 Unknown 回退 | 不新增任意可调用入口，不提高预算；后续真实隔离/API 验收另行审查 |

## 2. 共同契约

- 所有新模型沿用 `Model(extra=forbid)`；kind/operation 均为有限 Literal。
- `Expr` 指现有 `MathExpression`。所有**计算输入**字段 source 必须非空；LaTeX-only
  字段仅用于展示，不能由 checker 解析。`I*p` 可输入，`Arg(I*p)` 不可作为 source。
  计算生成的输出（包括交点坐标）允许 source=null，不被当作新的输入再次解析。
- 先在原始未求值树检查每个中间运算的定义性，再对**计算副本** `.doit()`，
  然后 simplify。规范化不能抹掉 `0/0`、原始分母或非法实数中间值。
  未规范化树上的 assumptions 查询也须谨慎；不要把所有节点的 `.is_*`
  查询当作安全规范化的替代。
- 只替换已声明参数；未解决的自由变量、无法决定的零性/有限性/实性/顺序、
  未支持结构或计算异常均为 Unknown。有限精度近似和采样不能充当证明。
- 扰动只改一项拥有者条件。新 checker 不读取 expected report、数学说明、
  `expected_failure_mechanisms` 或历史审核状态来制造数学结果。
- Assumption 是前提证据。前提不成立本身不能自动使 step invalid；step 必须
  另行证明运算未定义、断言不适型或与实际完整结果矛盾。

## 3. ComputationSpec 提案

### 3.1 PrincipalArgumentSpec

```text
kind: principal_argument
expression: Expr
branch: negative_pi_open_positive_pi_closed  # 唯一允许值，(-pi, pi]
```

参数代入后输入必须是已证有限的闭复数。先检查原式所有节点定义性，再检查输入
是否为零。零输入返回 `undefined`（Arg(0) 未定义），不接受 SymPy 的 nan 作为值；
无法决定是否为零则 Unknown。

非零输入在 trusted 代码构造 `sp.arg(z)`，检查其为已证实且有限的实数并满足
$-\pi<\theta\le\pi$。需要时执行同一分支规范化；未解决的分支不作数值猜测。
该结果是 `numeric_value`，包括精确的含 $\pi$ 的值。

初始支持本题的闭非零虚轴值；其他输入只有在精确证明定义性、非零、结果实性、
分支归属后才能建立结果，否则 Unknown。复数对数的分支不在本批范围内。

### 3.2 复用 EquationSpec，有限放开复数多项式

不增加第二个 number_system 字段，也不另建重复的 ComplexEquationSpec。
数系唯一来源仍是 problem.variables 与其一致的 domain_binding。

```text
kind: equation
variable: z
left: Expr   # 本题 z**2+1
right: Expr  # 本题 0
effective number system: real 或 complex（由域拥有者决定）
```

实数路径保持现有能力。复数路径本批仅支持：

1. 参数代入后，左右原始树都是受限的单变量多项式运算：有理常量、指定变量、
   加减乘、有界非负整数幂、已证明非零的有理常量除法。不能先约分再认定是多项式；
   含变量分母、函数调用、其他自由变量的原式均不在这个子集。
2. 差多项式为一次或二次，系数均为闭有理数，最高项系数非零。零多项式、
   常数式、次数越界在该新增路径返回 Unknown，不推断未经审查的退化情形。
3. 本批 complex 输入域为无附加约束的 $\mathbb C$。eq/ne 限制虽然能由
   DomainSpec 表达，初始复数求解器不承诺支持，遇到时 Unknown。
4. trusted 代码在 `S.Complexes` 上求解；只有证明结果是完整有限集合，且每根
   代回原式成立，才标记 complete。对本题用因式分解/二次多项式的完整性佐证。
   ConditionSet、未决成员判断不能宣称 complete。

复数符号必须由扰动后的 Context 新建，不能复用 baseline 的 real=True 符号。
任何通用 evaluator 的前置 admissible_domain 检查也必须按这个受限分支处理，
不能让旧的 real-only 检查在新求解器之前错误地截断。

有意义的方程无根：`solution_set=EmptySet, completeness=complete,
well_formedness=NoSolution`。这不等于 ContradictoryConditions。

**排序边界：** DomainSpec 的已有验证器继续拒绝 complex 域排序约束；
problem.domain_constraints、域选择以及涉及该变量的其他约束入口也需核查。
以实际数系/符号作用域拒绝针对复数变量的 lt/le/gt/ge；不能错误拒绝独立实参数的
大小关系。非法输入是 schema/语义验证错误，求解能力不足是 Unknown。
教学步骤“复用实数平方非负定理”保存在专用 typed check 中，不构造复数 `Ge`
对象，也不把该排序命题作为原题的域限制。

### 3.3 VectorAngleSpec

```text
ScalarVector = tuple[Expr, Expr] | tuple[Expr, Expr, Expr]
kind: vector_angle
u: ScalarVector
v: ScalarVector
```

u/v 维度必须相同且恰为 2 或 3；JSON 表示为分量数组。逐分量调用原 parser，
不允许字符串内的 list/tuple/matrix。参数代入后须为闭、有限实数向量。
分量复数或非有限数不作为可计算的欧氏实向量；不支持/未决输入返回 Unknown，
而不是偷换为 Hermitian 内积。

trusted 代码用有界标量求和计算 $D=\sum u_jv_j$、$U=\sum u_j^2$、
$V=\sum v_j^2$。若已证 $U=0$ 或 $V=0$，返回夹角 undefined；这是已知
不存在，不是 Unknown。坐标数据仍有意义，well_formedness=WellFormed。
非零时证明 $U,V>0$，构造 $r=D/(\sqrt U\sqrt V)$，精确验证 $-1\le r\le1$，
再在 trusted 代码构造 acos，结果取 $[0,\pi]$。不对浮点越界静默 clamp。
未解决的范围/等式比较返回 Unknown。

### 3.4 LineIntersection3DSpec

```text
Line3D:
  origin: tuple[Expr, Expr, Expr]
  direction: tuple[Expr, Expr, Expr]

kind: line_intersection_3d
first: Line3D
second: Line3D
```

所有分量为闭、有限实标量，方向须已证非零。t/s 是 checker 内部不同的 real Dummy，
其范围固定为 $\mathbb R$；无需在 problem.variables 中暴露。各分量不得包含它们。
本提案不引入任意参数曲线或矩阵输入。

零方向不能作为直线；返回 `undefined`，well_formedness=Undefined，并明确原因。
未知方向是否非零则 Unknown。不能把零方向静默解释为点。

以 origin $P,Q$、direction $d,e$ 构造**全部三个**残差：

$$P_j+t d_j-Q_j-s e_j=0,\qquad j=1,2,3.$$

对这 3 条线性方程使用精确消元 / linsolve；只有完整的共同解或不相容证明
才建立结论。唯一解须代回所有分量。不能由投影的唯一解推断空间相交。
方向叉积用三个显式标量分量计算，不接受用户可控的 Matrix/numpy 对象。

| 关系 | 必要证据 |
| --- | --- |
| intersecting | 三式有唯一公共参数解，求出的共同点两边坐标完全相等 |
| skew | 三式无解，且方向不平行（不能把“无交点”等同于“异面”） |
| parallel_distinct | 三式无解，方向平行 |
| coincident | 方向平行、origin 差也在同一方向，三式有一参数解族 |

平行性、相容性或解族结构不能确定时 Unknown。叉积为零与否需确证，不能
只依赖 Python truthiness。分类与全部坐标求解应互相一致，否则返回 Unknown。

## 4. Step 与 Assumption 的有限成员

下表参数模型是独立设计，不是新规则 DSL。相同字段可由一个 Literal union
模型共用；不新增通用 AST 或证明语言。

| operation | union / 字段 | 绑定和证据 |
| --- | --- | --- |
| evaluate_argument_factors / principal_argument_product / evaluate_argument_sum | RuleParameters；left,right: Expr；branch 固定 | 要求实际 computation 为 principal_argument，两个因子乘积与原式一致；先逐树查定义性再验证乘积相等 |
| principal_argument_additivity | AssumptionCheck；同上因子和 branch | kind 同名；计算非零及原始和是否在主分支；不生成 step verdict |
| equation_transform（已有） | RuleParameters；before/after | 第18题移项，完整解集对比使用当前数系；新复数路径仅在上述受限多项式内 |
| real_square_nonnegative | RuleParameters；variable: Identifier | 绑定实际 equation 的变量；trusted 构造该变量的平方，检查实际域是否支持实数平方非负定理；复数域给不适型证据，不实例化 Ge(complex,0) |
| real_order_available | AssumptionCheck；variable: Identifier | kind 同名；由实际域建立实数有序结构前提；本题 real 域 satisfied，complex 域 violated |
| claim_empty_solution_set | RuleParameters；无附加参数 | 绑定实际 equation；独立求完整原题解集，EmptySet 为 Valid，确证的非空根为反证；不读作者结论 |
| vector_metrics / normalize_vector_dot / evaluate_vector_angle | RuleParameters；无附加参数 | 必须绑定实际 vector_angle；分别计算 D/U/V、检查非零后算比例、检查定义域后算角 |
| vector_norms_nonzero | AssumptionCheck；无附加参数 | kind 同名；从实际向量的 U/V 判断；不把非零约束固化到原题 |
| line_xy_candidates | RuleParameters；无附加参数 | 必须绑定实际 line_intersection_3d；仅声称解 x/y 投影两式，唯一候选才输出参数；投影退化时 Unknown |
| verify_line_common_point | RuleParameters；first_parameter,second_parameter: Expr | 闭有限实参数，代回实际两线的三个分量；一个已证非零残差即反证；含未决残差而无反证则 Unknown |
| claim_line_relation | RuleParameters；relation: LineRelation | 与实际三式独立求出的完整关系比较；不是以关系名作证据 |
| line_directions_nonzero | AssumptionCheck；无附加参数 | kind 同名；逐条方向检查平方范数 |

第17题三个步骤的含义不同：计算因子幅角、声称不归一化可直接相加、计算该和。
即使第二步错误，第三步的纯算术仍可局部正确，不把它伪装成正确 Arg。
第18题 real_square_nonnegative 的断言范围是实际输入域上所有 z；不是仅在
方程根上作空集蕴含。复数的 z=i 直接否定这一推广。

绑定检验：含变量的字段只能引用相符的 computation 变量；因子乘积必须对应原题；
无参数规则也必须严格检查 computation.kind。规则不能凭一份无关的小例子为原题
提供“验证”。Assumption 模型的 kind/check 一致性规则按新成员同步扩展，不再统一
读取 `.variable`。未知 kind/operation 或不匹配绑定不得回退到成功。

## 5. 输出与比较

第17题与第19题使用已有 numeric_value / undefined；第18题使用已有 solution_set。
第20题提议新增：

```text
LineRelation = intersecting | skew | parallel_distinct | coincident
LineRelationOutcome:
  relation: LineRelation
  intersection_point: tuple[Expr, Expr, Expr] | null

ConclusionResult:
  status: 现有值 | line_relation
  line_relation: LineRelationOutcome | null
  value: MathExpression  # 建立结果时仍需展示字段，无 source 也可

ConclusionComparison.basis: 现有值 | line_relation
```

只有 status=line_relation 时允许且必须提供 line_relation。
只有 relation=intersecting 时允许且必须提供唯一 intersection_point；
coincident 无唯一交点，不能伪造一个作为完整答案。各坐标为实际计算生成的表达式。
现有 stationary classification 的枚举及验证保持独立。

直线比较先比较关系：不同即 changed=True；相同且为 intersecting，再精确比较
共同点三个坐标；同为其他关系时，针对本题“关系与唯一交点”的目标 unchanged。
不能比较 t/s 参数值来判断几何结论改变（control 正是重参数化）。
内部比较使用已求得的精确标量元组与关系，不读取输出 LaTeX、构造分类符号，
或将关系编码成浮点数。未解决坐标比较为 changed=null。

第19题 nonzero→zero 是 numeric_value→undefined，changed=True；
well_formedness 仍 WellFormed，说明向量有意义但请求的夹角不存在。
第17题 Arg(0) 则属于该表达式的内在定义域之外，well_formedness=Undefined。
这些区分须在 API 字段与解释中保持一致。

## 6. 批准后实施与真实审查范围

此处只列待办，不表示已实施：按 union/注册表扩展模型与有限 checker、tuple
递归验证及符号绑定；保留全部历史模板行为；增加真实 worker 和 API 回归。
需覆盖四题所有 baseline/changed/control、Unknown/超时回退、Arg(0)、负轴端点、
复数排序拒绝、非多项式/变量分母拒绝、维度错误、零方向、平行/重合、
候选仅满足两个分量、恶意分量 source 以及现有 Challenge 三模式。

前端/公开 API 的新状态兼容性应在实现审查时验证，不能凭后端通过就宣称可发布。
独立数学测试通过仅支持本次审查；数学批准后才开始实现，完整代码与真实回归
通过 Claude Code 审查之后才允许 reviewed/发布。
