# Phase 5 batch 04：四题数学草稿（17–20）

准备日期：2026-10-18。四题统一 **review.status=draft，reviewer=null**。
原 coverage 的宏观批准不作为本次详细推导/契约批准。当前没有新增运行时模板、
模型或 checker；本稿待 Claude Code 审查后才可进入实现。

已经通读 PRD、batch-01/02-review 和 spec-design；沿用独立的 step / method /
conclusion 维度。本文 expected 矩阵仅为审查与将来的内容回归预期，绝不作为
运行时判定依据。新契约集中于[batch-04-spec-design.md](batch-04-spec-design.md)。

任务标题写“16–20”，明确清单只有四题 17–20。本次按这四题交付，不补造题 16。
为便于逐题审查，下文每题均包含原题、拥有者条件、完整步骤、baseline/changed/
control、首个失效点、证明、修正及独立 SymPy 计算。
步骤里的数值输出描述 baseline；将来 replay 按当前参数重新计算，不冻结原答案。
四题的 baseline/control 均无 first_invalid_step_id；全部主矩阵场景均无
first_unresolved_step_id。method 的 I 指当前未修正路径含错误，不表示修正后的
同类方法也不可用。本批没有基于成本猜测 Inconvenient，也不将可修正性自动
转换为 Needs Checking。

## 17 — 主幅角的相加需要回到固定分支

拟议 ID：`principal-argument-product`；领域 Complex Numbers；难度 introductory。

**原题。** $p\in\mathbb R$，初始 $p=1$，计算 $\operatorname{Arg}(ip)$，
全程固定主值范围 $(-\pi,\pi]$。`p-value` 唯一拥有参数 p，原题不假定 p>0。
允许单条件变化 p=-1（main）或 p=2（control）。p=0 作为定义域边界回归，
本次不作为公开允许的扰动。

**基线解法与步骤。**

1. `evaluate-factor-arguments`：令 $\alpha=\operatorname{Arg}(i)=\pi/2$，
   $\beta=\operatorname{Arg}(p)=0$。计算因子主幅角，要求两因子非零。
2. `add-principal-arguments`：直接断言
   $\operatorname{Arg}(ip)=\alpha+\beta$。该**不带归一化**的等式需要
   $-\pi<\alpha+\beta\le\pi$，基线成立。
3. `evaluate-argument-sum`：计算 $\alpha+\beta=\pi/2$。这一步仅为和的
   局部求值，不另行声称相加法则已获证明。

主方法 `unwrapped-argument-addition` 的前提：两个因子非零，且主幅角之和仍在
规定分支。前提由 typed `principal_argument_additivity` 检查，不把 p>0
写进不可变原题域，不允许把 main 变化解释成“题目条件矛盾”。
该前提在 baseline/changed/control 的状态为 satisfied/violated/satisfied。

| 场景 / p | ip | alpha | beta | 未归一化和 | 原题正确主幅角 | steps 1/2/3 | method | changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline / 1 | $i$ | $\pi/2$ | $0$ | $\pi/2$ | $\pi/2$ | V / V / V | V | false |
| changed / -1 | $-i$ | $\pi/2$ | $\pi$ | $3\pi/2$ | $-\pi/2$ | V / I / V | I | true |
| control / 2 | $2i$ | $\pi/2$ | $0$ | $\pi/2$ | $\pi/2$ | V / V / V | V | false |

V=Valid，I=Invalid Step。三种场景均 WellFormed；参考结果均 numeric_value。
changed 的首次失效点为 Step 2 `add-principal-arguments`；无未决步骤。
conclusion 维度分别为 Valid、Valid+Changed Conclusion、Valid，比较基准 numeric_value。
原推导的 changed 声称值是 $3\pi/2$，不是参考答案 $-\pi/2$。
新正确结论 Valid 不表示认可原来的错误等式。

**完整依据。** 任意非零 $z,w$ 写成 $z=r e^{i\alpha},w=s e^{i\beta}$，
其中 $r,s>0$，$\alpha,\beta\in(-\pi,\pi]$。则
$zw=rs e^{i(\alpha+\beta)}$。这证明幅角按 $2\pi$ 同余相加；主值还需唯一代表：

$$
W(\theta)=
\begin{cases}
\theta+2\pi,&\theta\le-\pi,\\
\theta,&-\pi<\theta\le\pi,\\
\theta-2\pi,&\theta>\pi.
\end{cases}
$$

这里 $\theta=\alpha+\beta\in(-2\pi,2\pi]$，故最多加减一次 $2\pi$ 即可。
尤其 **$W(-\pi)=\pi$，$W(\pi)=\pi$**；不能将右端点误写成开。
p=-1 时 $\beta=\pi$，$3\pi/2$ 在分支之外，而 $3\pi/2-2\pi=-\pi/2$。
这不是模 $2\pi$ 的乘法律失效，是把同余误写成主值等式。

**修正。** Step 2 改为 $\operatorname{Arg}(ip)=W(\alpha+\beta)$，或直接从
虚轴上 $ip$ 的位置求主幅角。p=0 时输入为零，根本不存在 Arg，不能通过 wrap
或令 Arg(0)=0 修复。

**独立 SymPy。** trusted 构造 `sp.arg(sp.I*p)` 得 1/-1/2 对应
$\pi/2,-\pi/2,\pi/2$；因子和为 $\pi/2,3\pi/2,\pi/2$。
同时计算单位方向 `z/Abs(z)` 与 `cos(theta)+I*sin(theta)` 一致并验证分支。
额外检验 `arg(-1)=pi`、`arg(0)=nan`（后者不是数学值）、
因子 $(-i,-i)$ 的和 $-\pi$ 应归一化为 $\pi$，因子 $(-1,-1)$ 的和
$2\pi$ 应归一化为零。见独立测试，不调用未来 checker。

## 18 — 实数域无解的序关系证明不能迁移到复数域

拟议 ID：`real-square-to-complex-domain`；领域 Complex Numbers；难度 introductory。

**原题。** 求 $z^2+1=0$ 的全部解，初始 $z\in\mathbb R$。
唯一可变条件 `admissible-domain` 使用 DomainConditionBinding：

| choice_id | 数系 | 该条件拥有的约束 |
| --- | --- | --- |
| all-real（baseline） | real | 无 |
| all-complex（main） | complex | 无 |
| nonnegative-real（control） | real | $z\ge0$ |

没有其他参数或固定的 z 排序限制。control 只收紧同一个域条件，仍保持无解；
main 切换到 complex 时不会遗留实数假设或 control 的非负约束。

**基线解法与步骤。**

1. `rearrange-square-equation`：$z^2+1=0\iff z^2=-1$。
   纯移项在实数和复数域均成立（现有 equation_transform 可复用）。
2. `real-square-nonnegative`：对实际域中的每个 z 使用 $z^2\ge0$。
   依赖 `real_order_available`，其作用域是输入域，不是方程的根集。
3. `claim-no-solutions`：因 $-1<0$，断言原方程完整解集为 $\varnothing$。
   baseline 这是有效的实数序关系反证；此断言仍需对当前原题独立验证。

| 场景 / 域 | 原方程完整解集 | Step 1 移项 | Step 2 平方非负 | Step 3 空集断言 | method | formed | changed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline / $\mathbb R$ | $\varnothing$ | V | V | V | V | NoSolution | false |
| changed / $\mathbb C$ | $\{-i,i\}$ | V | I | I | I | WellFormed | true |
| control / $[0,\infty)$ | $\varnothing$ | V | V | V | V | NoSolution | false |

参考结果均 solution_set/complete，比较基准 symbolic_formula（完整集合）。
conclusion 为 V、V+Changed Conclusion、V。main 首次失效点为 Step 2；
没有 Unknown。作者重用的 changed 结论 $\varnothing$ 是错误的。
`real_order_available` 的状态为 satisfied/violated/satisfied。

**完整依据。** 对任意实数 z，若 z>=0，其平方非负；若 z<0，(-z)>0，
$z^2=(-z)^2>0$。所以实数上 $z^2+1\ge1$，不可能为零。任意实数子域
（包括非负半轴）同样无解。无根不是原有条件自相矛盾，按现有约定报告 NoSolution。

复数域上不提供可与实数同样使用的有序域结构。若强行要求所有平方非负，
$i^2=-1$ 会违背有序域平方非负及 $1>0$ 的性质。具体到原方程：

$$z^2+1=(z-i)(z+i)=0\quad\Longleftrightarrow\quad z=i\ \text{或}\ z=-i.$$

复数域无零因子，以上因式分解给出**恰好**两根，均代回为零。Step 2 的失效
是实数定理在当前复数域不适型，不是尝试计算“复数大小”的结果。
不能拿“没有实根”推出“没有复根”。

**修正。** 在复数域用该因式分解或等价的二次方程法，返回 $\{-i,i\}$。
不得把“z²>=0”作为复数域的附加限制来挽救旧证明。来自用户域数据的排序谓词
应被验证器拒绝；教学步骤由 typed check 展示其不适用，不能构造一般复数不等式。

**独立 SymPy。** 使用无实数假设的 `Symbol('z')` 分别在 S.Reals、S.Complexes、
`Interval(0,oo)` 上 solveset，得 $\varnothing,\{-i,i\},\varnothing$。
另外显式展开 `(z-I)*(z+I)`、验证两根及 degree=2。域切换不能只在 real=True
符号上把 solveset 的 domain 参数改为 Complexes。

## 19 — 零向量不能归一化，也没有这里定义的夹角

拟议 ID：`vector-angle-zero-norm`；领域 Vectors；难度 introductory。

**原题。** 对实向量 $u=(a,0)$、$v=(1,1)$，计算标准欧氏夹角
$\theta\in[0,\pi]$，初始 a=1。`a-value` 唯一拥有参数 a。
允许 a=0（main）、a=2（control）；原题不把 a!=0 写成永久限制。

**基线解法与步骤。**

1. `compute-vector-metrics`：
   $u\cdot v=a$，$\|u\|=\sqrt{a^2}=|a|$，$\|v\|=\sqrt2$。
2. `normalize-vector-dot`：在 $\|u\|\|v\|\ne0$ 下计算
   $r=(u\cdot v)/(\|u\|\|v\|)=a/(|a|\sqrt2)$。
3. `evaluate-vector-angle`：使用 $\theta=\arccos(r)$，基线得到 $\pi/4$。

方法前提 `vector_norms_nonzero` 作用于实际两个向量；checker 另查非零后再除法，
不能把“前提已标 true”作为除法合法性证据。
该前提在 baseline/changed/control 的状态为 satisfied/violated/satisfied。

| 场景 / a | u | dot | U=norm²(u) | V=norm²(v) | r | 正确夹角 | steps 1/2/3 | method | changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline / 1 | $(1,0)$ | 1 | 1 | 2 | $1/\sqrt2$ | $\pi/4$ | V / V / V | V | false |
| changed / 0 | $(0,0)$ | 0 | 0 | 2 | 未定义（0/0） | 未定义 | V / I / I | I | true |
| control / 2 | $(2,0)$ | 2 | 4 | 2 | $1/\sqrt2$ | $\pi/4$ | V / V / V | V | false |

三个场景的向量均 WellFormed。参考 status 分别 numeric_value、undefined、
numeric_value。结论维度 V、V+Changed Conclusion、V；basis=numeric_value，
main 的 changed 来自已知数值到已知未定义的状态变化。首次失效为 Step 2，
无未决步骤。Step 3 无合法 r，不能说“arccos(0)=pi/2 所以零向量夹角90度”。

**完整依据。** 对非零实向量，Cauchy–Schwarz 保证比值属于 [-1,1]。
本题 a!=0 时

$$r=\frac{a}{|a|\sqrt2}=\begin{cases}1/\sqrt2,&a>0,\\-1/\sqrt2,&a<0.\end{cases}$$

故正 a 的夹角恒为 $\pi/4$，负 a 的夹角为 $3\pi/4$。a=0 时范数为零，
$u/\|u\|$ 无定义；关系 $u\cdot v=\|u\|\|v\|\cos\theta$ 退化为
$0=0$，不能确定唯一角度。标准欧氏夹角仅对非零向量定义，因此这是已证明
的未定义，不是引擎 Unknown。也不能把 a 从 $\sqrt{a^2}$ 中直接消掉并丢弃零点。

**修正。** 归一化前检查两个范数；零向量时说明夹角未定义。若任务需要方向，
应补充非零前提或更换非零向量，但这会改变问题条件，不能在当前 main 场景
偷偷修改 a。保留 $|a|$ 以免负 a 返回错误角度。

**独立 SymPy。** 通过两个分量的显式求和求 D/U/V，再计算 exact acos。
得到 a=1 与 a=2 时同为 $\pi/4$，a=0
只计算已证零分母，不执行除法；另外 a=-1 得 $3\pi/4$。
测试还验证两个零向量均不具有方向及 3D 平行/反平行的端点角 0/pi。

## 20 — 二维投影交点不能代替三维共同解

拟议 ID：`line-intersection-all-coordinates`；领域 Vectors；难度 intermediate。

**原题。** 对实参数 t,s 求两条空间直线的位置关系及有唯一交点时的交点：

$$\ell_1(t)=(t,0,0),\qquad \ell_2(s)=(0,s,c),\qquad c=0\ \text{初始}.$$

main 仅将 `c-value` 从 0 改为 1。为提供合法且保持方法的独立 control，
**提议加入方向缩放参数 b，需随本稿批准**：写作
$\ell_2(s)=(0,bs,c)$，初始 b=1，control 仅改 `b-value`:1→2，仍 c=0。
这保留指定的原题/main，control 只是对同一几何直线的重参数化。
若只改 c，任何非零值都会破坏相交结论，不能伪造“c=2 是合法不破坏 control”。
每条允许路径从 baseline 出发恰好改一个参数，不允许同时改 b 与 c。

**基线解法与步骤。**

1. `solve-xy-projection`：联立 x/y 两分量 $t=0$、$0=bs$，在 b=1（或2）时
   得候选 $(t,s)=(0,0)$。此步只声称求投影候选，没有声称是完整空间交点。
2. `claim-common-point`：声称这一候选给出相同空间点原点。
   baseline 中代回两线均为 (0,0,0)，故有效。
3. `claim-intersecting`：声称关系 intersecting，交点原点。
   此结论必须与全部三式的独立求解结果比较。

实际方向 $d=(1,0,0)$、$e=(0,b,0)$。方向非零是直线数据的前提；
baseline/main/control 都满足。投影候选只是必要条件，不设“投影一定足够”
作为不可验证的前提来跳过 Step 2。
`line_directions_nonzero` 在三个场景都为 satisfied；main 的失效由非零 z 残差
直接建立，不依赖一个被标 violated 的假设。

| 场景 / (c,b) | 两式候选 (t,s) | 候选在 first 上 | 候选在 second 上 | first-second 残差 | 三式公共参数解 | 正确关系 / 交点 | steps 1/2/3 | method | changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline / (0,1) | (0,0) | (0,0,0) | (0,0,0) | (0,0,0) | {(0,0)} | intersecting / (0,0,0) | V / V / V | V | false |
| changed / (1,1) | (0,0) | (0,0,0) | (0,0,1) | (0,0,-1) | $\varnothing$ | skew / 无交点 | V / I / I | I | true |
| control / (0,2) | (0,0) | (0,0,0) | (0,0,0) | (0,0,0) | {(0,0)} | intersecting / (0,0,0) | V / V / V | V | false |

三种场景均 WellFormed（异面仍是合法的两条直线数据）。参考结果使用提议的
line_relation typed payload，比较基准 line_relation；结论 V、V+Changed Conclusion、V。
main 首次失效点为 Step 2 `claim-common-point`，而非本身正确的投影计算。
独立的 skew 结论不为原作者“相交”声称背书。

**完整依据。** 联立所有坐标：

$$t=0,\qquad -bs=0,\qquad -c=0.$$

b=1 或2 时，前两式唯一确定 t=s=0；第三式成立当且仅当 c=0。
所以 c=0 时唯一交点为原点，c=1 时三式不相容。
无交点还不足以推出异面，需要排除平行：

$$d\times e=(0,0,b)\ne0.$$

因此 c=1 的两线不平行且无交点，按空间直线分类为异面。
还可由标量三重积独立佐证：$(Q-P)\cdot(d\times e)=bc$，main 为1不为零，
两线不共面。control 的 b=2 不改变方向所在的一维子空间，故几何结果不变。

**修正。** Step 1 后将候选代回第三分量；失败即不能宣布相交。完整算法联立
全部三个分量，再以方向平行性区分 skew 与 parallel_distinct；也单独识别
coincident，不把重合直线的一参数解族当作唯一交点。

**独立 SymPy。** 用 real t/s、残差 `(t,-b*s,-c)` 调用
`linsolve(residuals,(t,s))` 得上表；另外只解前两个分量在三场景均得 {(0,0)}，
展示误判来源。叉积以三个标量分量显式计算，三重积 main=1。
额外计算不相交平行线及重合线，确保“无交点即异面”的错误没有藏在验证中。

## 独立计算与审查边界

独立数学测试位于 [tests/test_phase5_batch04_math.py](../../tests/test_phase5_batch04_math.py)。
该文件仅用直接构造的 SymPy 对象与显式数学断言，不导入 app、未来 typed spec、
checker 或作者预期文本。它是数学复算，不是运行时/API 回归，也不提前实现 checker。
所有带未求值结构的复算均先 `.doit()` 再 simplify。

主矩阵共 12 场景，包含四个 non-breaking control，另有必要的定义域/端点/
平行退化数学见证。第20题额外 b 参数属于本次具体审查范围。
在 Windows / 本 worktree 中的实际运行结果如下：

| 验证 | 实测结果 |
| --- | --- |
| `uv run --frozen python -c 'import sympy; print(sympy.__version__)'` | 1.14.0 |
| `uv run --frozen pytest tests/test_phase5_batch04_math.py -q` | **29 passed in 0.18s** |

本次仅新增两个审查文档和一个独立数学测试文件；未修改 app、frontend、已有
审查稿、依赖锁文件或公开题库。没有把这次 scoped 结果称为全量后端或 API 验收。

数学/契约批准之后才实现；实现后提交完整代码与真实隔离/API 回归给 Claude Code。
本阶段不设置 reviewed、不移动文件到 public loader、不发布，不修改 master 或其他 worktree。
