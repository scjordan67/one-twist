# Phase 5 batch 05：额外三道 Mode C 数学草稿

准备于 2026-10-18，工作目录 One-Twist-content，分支 phase5-content。
**所有新增 sample/config 均为 draft，reviewer=null；本稿请求 Claude Code 独立审核。**
未写入正式 Challenge 目录，不代表数学批准、代码批准或发布。

## 范围、契约与类别选择

本次仅增加固定的 Judge the AI 内容，不增加 Explorer 模板，不计入 20 个模板。
复用既有 AIDerivationSample / SampleRubric / Problem / Step 和八个 ReasonCategory，
不引入新数学模型、typed spec、运行时 checker、解析函数或枚举成员。
复数及空间向量的公式作为展示数学保存在 latex 中，source=null；
三角题的 equation computation 只使用现有类型。所有非空 source 仍由原 parser 校验。
Mode C 将来依据审核后的完整 rubric 元组评分，反馈必须说明它来自人工审核，
不能宣称运行时引擎证明了这些复数/向量推导。

| 草稿 | 主题 | 私有 category | 推导 / 最终结论 | 首个缺陷 |
| --- | --- | --- | --- | --- |
| [sample-006](batch-05-mode-c-drafts/sample-006.json) | 主值反正弦丢失另一个根 | flawed | not_sound / incorrect | step-002 |
| [sample-007](batch-05-mode-c-drafts/sample-007.json) | 未归一化幅角被接受为主值 | missing_condition | not_sound / incorrect | step-003 |
| [sample-008](batch-05-mode-c-drafts/sample-008.json) | 零向量归一化错误，最终非存在结论正确 | wrong_derivation_right_answer | not_sound / correct | step-002 |

现有 sample-001/002 是两道 correct 对照，本次保持其内容和公开状态。
类别选择按“总库有正确对照，新增覆盖三种指定缺陷”处理：将来审核发布后，
八题在 correct / missing_condition / wrong_derivation_right_answer / flawed
四类中恰好各两道，而不是把新增题全部归入 flawed。每题判断标准在规定数据下均
可精确证明，无须捏造 not_established 或 Unknown 来扩充类别。

另附 [draft Mode C 配置](batch-05-mode-c-drafts/challenges) practice-011/012/013，
分别引用 sample-006/007/008；这三份配置也是本次审核对象，尚未进入正式目录。
每题均使用中性的标题、3 步、3 个 premise 选择和既有全部 8 个 reason 选择。
不按答案裁剪选项。template_id=null，不依赖未来 batch3/4 模型或模板 provenance。

元组顺序固定为：

(derivation, conclusion, step_id, assumption_id, reason_category)

以下列出的是**全部**可接受组合，不按各列笛卡尔积拼接；其余有效格式组合均不匹配。
premise-001 是第一缺陷所需的相关前提，另外两项是已满足但不能修复缺陷的干扰项。
not_established 指数学上未获得所声称结论，不是“程序暂时没求出来”；
本批有明确证明/反例，所以不接受它来替换已经确定的 correct 或 incorrect。
rubric.reason_if_unknown 均为 null。若审查发现标准确实未建立，应保持 draft，
使用现有未知标准机制处理，不能通过猜测答案发布。

## Sample 006 — 丢失三角函数分支

**原题。** 求 $\sin x=1/2$ 在 $0\le x<2\pi$ 上的完整解集，弧度制。
原题没有将 $x$ 限制在反正弦的主值区间。

| Step | 提议推导 | 实际数学判断 |
| --- | --- | --- |
| step-001 | $\alpha=\arcsin(1/2)=\pi/6$ | Valid：这是正确的主值计算 |
| step-002 | 在给定全区间断言 $\sin x=\sin\alpha\iff x=\alpha=\pi/6$ | Invalid：首次丢解 |
| step-003 | 声称原题完整解集 $S=\{\pi/6\}$ | Invalid：完整性声称错误 |

**唯一可接受元组：**

(not_sound, incorrect, step-002, premise-001, lost_root)

三项 premise 的公开中性描述分别是：

1. 所列候选覆盖给定区间内的每一个解。
2. 正弦方程右端在 $[-1,1]$ 内。
3. 给定解区间只包含非负角。

**完整证明。** 对实数 $x$，正弦差公式给出

$$
\sin x-\sin\alpha
=2\cos\left(\frac{x+\alpha}{2}\right)
 \sin\left(\frac{x-\alpha}{2}\right)=0.
$$

故完整实解族是 $x=\alpha+2k\pi$ 或 $x=\pi-\alpha+2k\pi$，$k\in\mathbb Z$。
代入 $\alpha=\pi/6$，得到 $\pi/6+2k\pi$ 与 $5\pi/6+2k\pi$。
两族在区间 $[0,2\pi)$ 内都只有 $k=0$；$k\ge1$ 超过上界，$k\le-1$ 低于下界。
因此恰好两个解 $\{\pi/6,5\pi/6\}$，且两者代回均为 $1/2$。
$x=5\pi/6$ 是对 Step 2 中“原方程推出唯一主值”声称的明确反例。

首错不是 Step 1，因为求 principal asin 本身正确；也不能只选后面的 Step 3，
因为丢解的等价断言已经在 Step 2 出现。主值的数值无算术错误。
最后的集合被明确称为“全部解”，所以不是一个正确但不完整的单根举例。

**修正。** 同时保留两族并与实际区间求交，不把反函数的主值当作方程全部逆像。
第二、三项 premise 均成立，仍没有排除遗漏根，因此不是修复完整性的相关前提。

**独立 SymPy。** 用 real x，在 Interval.Ropen(0,2*pi) 上对 sin(x)-1/2
调用 solveset，结果是 {pi/6,5*pi/6}；asin(1/2)=pi/6。
计算集合差得到 {5*pi/6}，并代回原式得零。相邻周期的直接验证支持范围检查；
全部周期的穷尽性来自上述证明和独立 solveset，而不是有限采样。

## Sample 007 — 一个合法 argument 候选不一定是 principal argument

**原题。** $z=i(-1)=-i$，求 $\theta=\operatorname{Arg}(z)$，固定
$-\pi<\theta\le\pi$。这里 $z\ne0$，不是 Arg(0) 的存在性问题。

| Step | 提议推导 | 实际数学判断 |
| --- | --- | --- |
| step-001 | $\alpha=\operatorname{Arg}(i)=\pi/2$，$\beta=\operatorname{Arg}(-1)=\pi$ | Valid |
| step-002 | 构造未归一化候选 $\theta_0=\alpha+\beta=3\pi/2$，验证 $e^{i\theta_0}=-i$ | Valid：尚未声称候选是主值 |
| step-003 | 接受候选，声称 $\operatorname{Arg}(-i)=\theta_0=3\pi/2$ | Missing condition / Invalid：未检查给定主值域 |

**唯一可接受元组：**

(not_sound, incorrect, step-003, premise-001, extraneous_root)

三项 premise：

1. 只有属于给定主值区间的幅角候选才能被保留。
2. 请求幅角的复数输入非零。
3. 虚数单位满足 $i^2=-1$。

这里沿用现有 extraneous_root 的公开含义“将额外候选接受为原问题的解”。
原问题是受限角度方程 $e^{i\theta}=-i$、$\theta\in(-\pi,\pi]$，
$3\pi/2$ 是未受限方程的候选，但不是该原问题的解。
因此不需要增加 branch_error 枚举，也不将正确的加法误标为 arithmetic_error。
private category=missing_condition 描述的是遗漏候选的域筛选。

**完整证明。** $e^{i\alpha}=i$，$e^{i\beta}=-1$，所以乘法给出
$e^{i(\alpha+\beta)}=-i$，这完全支持 Step 2 的候选构造。
所有实幅角为 $-\pi/2+2k\pi$，$k\in\mathbb Z$；
限制到 $(-\pi,\pi]$ 只允许 $k=0$，因为

$$
-\pi<-\frac{\pi}{2}+2k\pi\le\pi
\quad\Longleftrightarrow\quad
-\frac14<k\le\frac34.
$$

唯一整数是零，故主幅角恰为 $-\pi/2$。
Step 2 的 $\theta_0=3\pi/2$ 对应 $k=1$，满足单位方向方程但超出主值区间。
减去 $2\pi$ 得到正确主值。分支约定右端闭：$\operatorname{Arg}(-1)=\pi$，
不能写成 $-\pi$；本题从头到尾没有切换 convention。

第一缺陷是 Step 3：题目和 Step 2 明确只把和称为 unwrapped candidate。
若把 Step 2 改写成主值直接相加的等式，首错会前移，但那不是这份固定样本。
最终主值是明确错误，不能接受 not_established 或 sound。
非零和 $i^2=-1$ 都已满足，不能代替缺失的分支筛选。

**修正。** 对候选减去 $2\pi$，同时核对单位方向和主值区间，再称为 Arg。

**独立 SymPy。** arg(I)+arg(-1)=3*pi/2，exp(3*pi*I/2)=-I；
该候选不属于 Interval.Lopen(-pi,pi)，而 arg(-I)=-pi/2 属于。
另分别在该分支 solveset(cos(theta)=0) 与 solveset(sin(theta)=-1)，
两集合相交恰为 {-pi/2}，独立确认唯一性；同时检验 -pi 被排除、pi 被包含。

## Sample 008 — 错误归一化不能被正确最终答案洗白

**原题。** 对实三维向量 $u=(0,0,0)$、$v=(1,1,0)$，判断标准欧氏夹角
是否定义；若定义，给出角度。原向量数据完全有意义。
题目明确所有展示等式都被断言，最后一行不会撤回前面的等式。

| Step | 提议推导 | 实际数学判断 |
| --- | --- | --- |
| step-001 | $\|u\|=0$，$\|v\|=\sqrt2$ | Valid |
| step-002 | $\frac{u}{\|u\|}=(0/0,0/0,0/0)=(0,0,0)$ | Invalid：首次非法除零 |
| step-003 | 从 Step 1 的 $\|u\|=0$ 得出 $\angle(u,v)$ 未定义 | Valid：独立的标准定义判断 |

**唯一可接受元组：**

(not_sound, correct, step-002, premise-001, zero_divisor)

三项 premise：

1. 被其欧氏范数除的向量具有非零范数。
2. 向量各分量是实数。
3. 两向量具有相同维度。

**完整证明。** 由范数定义 $\|u\|^2=0$，$\|v\|^2=2$。
标准非定向欧氏夹角只对两条非零向量定义：

$$
\theta=\arccos\left(\frac{u\cdot v}{\|u\|\|v\|}\right)\in[0,\pi].
$$

本题分母为零，点积也为零，不能作除法；$0/0$ 未定义，并非零。
若从定义尝试给 $u$ 找单位方向，任何有限实数倍 $\lambda u$ 都还是零向量，
其范数为零而非一，故不可能得到单位方向。
将点积关系写成 $0=0\cos\theta$ 对所有实 $\theta$ 都成立，不能选择唯一角度，
尤其不能据零点积声称夹角为 $\pi/2$。

最终“夹角未定义”是标准定义下已证明的正确答案，不是无法计算的 Unknown。
但 Step 2 明确断言了一个不存在的商等于零向量；Step 3 只引用 Step 1
并没有撤回 Step 2 或把它标为被拒绝的试算，所以整个展示链 as written 为 not_sound。
Step 3 独立正确与 earlier invalid claim 可以同时成立。
这与 sample-004 的“两次根集错误抵消”不同：本题是一次无意义的中间运算，
随后靠原有数据给出正确结论，进一步测试答案正确不等于所有推导成立。

**修正。** 在 Step 1 得零范数后直接报告标准夹角未定义，删去非法归一化。
实分量与同维度均已满足，仍不使除零合法；不是相关的修复前提。

**独立 SymPy。** 显式标量求和给出平方范数 0、2，分母为零。
trusted 构造未求值 0/0 的计算副本，其 doit() 返回 nan，不能解释为数值零。
不对 nan 继续套 acos。另计算点积恒等式余项为零，说明它未能选出唯一角度。

## 验证、公开边界与下一步

[独立数学及既有内容契约测试](../../tests/test_phase5_mode_c_extra_math.py) 将原式、
展示步骤、完整接受元组一并锁定。数学运算使用直接 SymPy 对象；
含 parser 保留树的计算先 .doit() 再 simplify。
测试还使用现有 loader 验证这六份 draft JSON 的 schema、符号与引用，
确认草稿不会出现在公开列表、不能被评分，并确认原有 correct 对照仍可用。

本次不将任何新文件标为 reviewed，连内存中的新样本也不伪造 reviewer。
未测试的“审核后评分路径”不声称已经验收。
数学审核通过后才可发布 JSON，并补充对已审核标准的实际评分/API 回归；
任何发布路径仍必须同时有 reviewed sample 和 reviewed Mode C config。
原有以 5 samples / 10 configs 为固定计数的契约测试，需要在批准后的发布改动中
准确更新至 8 / 13，并继续验证全体四类均有正确覆盖。

实际验证（Windows，SymPy 1.14.0；均使用本 worktree 的既有环境）：

| 命令 / 范围 | 结果 |
| --- | --- |
| uv run --frozen pytest tests/test_phase5_mode_c_extra_math.py -q | **18 passed in 1.41s** |
| uv run --frozen pytest -q | **554 passed, 3 failed**, 1 warning, 117.00s |
| 单独复跑下列三个既有 batch1 隔离 API 用例 | **1 passed, 2 failed**, 1 warning, 11.98s |
| uv run --frozen pytest tests/test_challenge_contracts.py tests/test_challenge_sample_math.py tests/test_challenge_grading.py tests/test_phase5_mode_c_extra_math.py -q | **129 passed**, 1 warning, 14.72s |

全量失败位于 tests/test_phase5_batch01_engine.py 的
test_approved_scenario_through_real_spawn_api：

- [4-baseline]：deadline_exceeded，3.015s；单独复跑仍超时，3.109s。
- [4-restricted-control]：deadline_exceeded，3.047s；单独复跑通过。
- [5-baseline]：deadline_exceeded，3.000s；单独复跑仍超时，3.063s。

单独复跑命令为：

~~~~powershell
uv run --frozen pytest 'tests/test_phase5_batch01_engine.py::test_approved_scenario_through_real_spawn_api[4-baseline]' 'tests/test_phase5_batch01_engine.py::test_approved_scenario_through_real_spawn_api[4-restricted-control]' 'tests/test_phase5_batch01_engine.py::test_approved_scenario_through_real_spawn_api[5-baseline]' -q
~~~~

这些是已有引擎/API 用例中的真实 3 秒隔离 deadline 失败，不归类为数学反例，
也没有修改超时、跳过测试或掩盖结果。单独复跑不收集新增测试仍有两例超时；
目前不据此推断更具体的性能根因。应用代码与既有测试无 diff。
本次直接涉及的既有 Challenge 契约、评分、内容数学和新增草稿测试全部通过，
但**全量回归尚未全绿**，需作为后续验收限制告知 reviewer。
唯一 warning 为已有 Starlette/HTTPX 弃用提示。

这次审查阶段仅新增本稿、3 份 sample、3 份 draft config 和独立测试文件；
不修改 app、frontend、正式样本、正式配置、已有数学模型或主目录。
提交仅记录 phase5-content 的草稿与复算证据，保留指定 Co-Authored-By。
