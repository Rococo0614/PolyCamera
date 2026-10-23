# 偏振辅助深度增强：执行方案

**版本：** v0.1
**日期：** 2026-10-23

## 当前进度

```text
Phase 0 研究协议       完成
Phase 1 证据与可用性   第一版完成（22 篇论文、12 类产品；若干开放性待核实）
Phase 2 小样本证明     进行中（scene10/12/13 共四个视角；H1/H5 跨场景初步成立，H2 有弱偏振反例）
Phase 3 基线复现       仅完成源码/环境静态审计，尚未运行模型
Phase 4 方法实验       未启动，Gate 3 前禁止启动
Phase 5 实物验证       未启动，无设备
```

## 1. 执行原则

1. 先证明问题，再设计方法；
2. 先锁定数据、划分和指标，再启用自动实验；
3. 论文报告值只算外部证据，本项目必须独立复算；
4. 每个结论区分“文献声称、代码核查、独立复现、实物验证”四级证据；
5. 一次实验只回答一个假设，并记录代码、配置、随机种子、显存和运行时间；
6. 数据集测试集在最终模型冻结前不得用于调参。

## 2. 当前资源与约束

截至 2026-10-23：

- GPU：NVIDIA GeForce RTX 5090 D，约 24 GB 显存；
- 根分区剩余：约 14--17 GB，随缓存变化；
- HAMMER 完整 ZIP：170,457,339,555 bytes，约 159 GiB；
- 当前 Python 基础环境没有 NumPy/PyTorch；
- PPFT 公开实现依赖 PyTorch 1.10、CUDA 11.3、Apex 和自编译 DCN，与新 GPU/新驱动存在兼容风险。

因此当前可以做：文献核查、选择性样本下载、统计代码和轻量分析。当前不可以直接做：完整 HAMMER 下载和 PPFT 全量训练。

当前机器设置 10 GiB 空闲磁盘安全线；低于该值停止继续抽样和安装模型依赖。选择性审计暂限最多 12 帧，完整训练建议准备约 400 GiB 独立数据盘。

## 3. 工作分解

### Phase 0：研究协议固化

**目标：** 避免边做边换问题。

任务：

- [x] 明确主线、非目标和兜底路线；
- [x] 定义 RQ/Hypothesis 和否证条件；
- [x] 定义数据划分、指标和 baseline 层级；
- [x] 建立独立 `depth_research/` 目录；
- [ ] 与导师确认题目表述和仪器/算法工作量比例。

输出：`06_depth_enhancement_research_architecture.md`。

### Phase 1：证据地图与数据可用性

**目标：** 判断问题是否已经被近期工作完整解决，并确认实验资产真实可用。

任务：

1. 整理至少 20 篇核心论文，重点覆盖：
   - 深度传感器失效与 HAMMER；
   - Polarized 3D、DPS-Net、PPFT、ReCAP2；
   - sensor/domain-agnostic depth completion；
   - CDPR、Poppy、PolarDepth 等 2026 工作；
   - 透明/反光物体深度与机器人应用。
2. 建立产品矩阵：测量原理、公开 SDK、同步、原始数据、典型失效和当前在售状态；
3. 核对每项数据/代码/权重/许可，不把项目页存在等同于可复现；
4. 重点核实 HAMMER 偏振四象限顺序。其论文补充材料与 PPFT 预处理代码的角度描述存在疑点，PPFT 源码也明确写有“by guess”。

输出：

- `08_depth_landscape_and_gap.md`；
- `depth_research/evidence/literature_matrix.csv`；
- `depth_research/evidence/product_matrix.csv`；
- 数据访问状态表。

**Gate 1：** 如果 HAMMER 偏振定义无法核实，只能将其用于“学习特征”复现，不能把 AoLP/法向关系作为精确物理结论。

### Phase 2：小样本问题证明

**目标：** 不训练大模型，先用原始观测证明 H1，并初步检查 H2。

任务：

1. 用 HTTP Range 读取 HAMMER ZIP 中央目录；
2. 从训练和测试场景各选择若干相隔较远的帧；
3. 每帧只下载以下模态：
   - RGB；
   - polarization 2x2 composite；
   - D435/L515/I-ToF warped depth；
   - rendered GT depth；
   - normal、instance/material label（若对应文件可用）；
4. 计算：
   - 各传感器全图/材质/边界/距离分层误差；
   - missing depth 与 silent wrong depth；
   - S0/S1/S2、DoLP/AoLP、物理残差和启发式质量图；
   - 深度误差与偏振量之间的条件统计；
5. 形成至少三张开题图：传感器错误热图、材质误差图、偏振条件收益/相关性图。

输出：

- `depth_research/results/sample_audit/metrics.csv`；
- `depth_research/results/sample_audit/figures/`；
- 一页“问题存在性”结论。

**Gate 2：** 若原始数据趋势与论文不一致，优先排查单位、配准、有效 mask 和文件映射，不进入训练。

### Phase 3：基线复现与压力测试

**目标：** 独立证明偏振增益，并寻找尚未解决的失败条件。

执行顺序：

1. 原始深度与简单局部/双边补全；
2. CompletionFormer 推理；
3. PPFT 作者权重推理；
4. RGB、polar、depth 的输入消融；
5. 官方 scene split；
6. leave-one-sensor-out；
7. 仅测试时的偏振退化：
   - 高斯/泊松近似噪声；
   - 四通道增益偏差；
   - AoLP 零点偏移；
   - 通道缺失；
   - 低照、饱和和模糊；
8. 深度退化：稀疏度、随机空洞、结构化空洞、尺度/偏置和边界噪声。

所有实验写入：

```text
commit, config_hash, dataset_split, heldout_sensor,
primary_metric, material_metrics, coverage, latency,
peak_vram, seed, status, description
```

**Gate 3：** 只有出现可重复、统计显著且具有物理解释的缺口，才确定论文方法。

### Phase 4：候选方法与自动实验

**目标：** 针对 Gate 3 的结果解决一个问题，不追求堆模块。

当前候选但未锁定的架构：

```text
polar branch ──► q_pol ─┐
                         ├─► constrained residual fusion ─► depth + uncertainty
depth branch ──► q_dep ─┘
       optional RGB / viewing ray / sensor token
```

优先消融：

- 绝对深度回归 vs 残差修正；
- 无可靠性 vs 单模态可靠性 vs 双可靠性；
- 有/无 sensor token；
- 随机 sensor corruption vs 真实 sensor holdout；
- 有/无 depth-normal-polarization consistency；
- 参数量匹配的普通注意力对照。

此时再采用 autoresearch 思路：

- 冻结 `data.py`、split 和 `evaluate.py`；
- 只允许修改模型/损失/少数超参数；
- 先做短预算代理实验；
- 改善后才进入完整训练；
- 不允许自动修改测试集和主评价规则；
- 不使用单一全图 RMSE 决策，必须满足困难材质、跨传感器和复杂度约束。

具体代理协议已写入 `depth_research/program.md`；在 Gate 3 前保持禁用。

### Phase 5：设备与系统验证

**目标：** 补足仪器专业属性和论文外部有效性。

最低配置：一台 DoFP 偏振相机 + 一种 RGB-D/深度传感器。工作包括：

- 暗场、平场、四方向响应和 AoLP 零点标定；
- 内参、畸变、外参和时间同步；
- 透明、金属、黑色高反、普通漫反射对照场景；
- 公开数据训练后直接外测，再做少量适配；
- 报告跨设备性能，而不是只展示好看的点云。

## 4. 首四周里程碑

### 第 1 周

- 完成核心文献矩阵和产品矩阵；
- 完成 HAMMER 远程目录读取与选择性下载；
- 核实偏振四象限/角度定义。

### 第 2 周

- 建立 20--50 帧审计子集；
- 完成三类 raw depth 对 GT 的基本统计；
- 输出第一版问题热图。

### 第 3 周

- 完成按材质、边界、距离和偏振质量分层；
- 下载并检查 PPFT 代码/权重；
- 评估旧环境迁移方案，不急于完整训练。

### 第 4 周

- 至少完成作者权重推理或一个可运行轻量基线；
- 形成 H1/H2 的初步结论；
- 决定是否投入 leave-one-sensor-out 全量实验。

## 5. 风险与替代方案

| 风险 | 影响 | 处理 |
|---|---|---|
| HAMMER 159 GiB，本机空间不足 | 无法全量训练 | 先 Range 抽样；正式阶段使用独立数据盘 |
| 偏振角度定义不明确 | 物理分析无效 | 联系作者/核对 SDK和元数据；保留多种排列敏感性分析 |
| PPFT 依赖过旧 | 新 GPU 无法编译 | 先作者权重；再迁移 PyTorch；必要时重建轻量 baseline |
| 近期工作已覆盖可靠性融合 | 创新重叠 | 把核心转为严格跨传感器泛化、校准或实测域差异 |
| 跨传感器缺口不成立 | 原假设被否证 | 转向已由压力测试证明的退化/配准/轻量化问题 |
| 无法及时获得设备 | 缺少实物验证 | 公开数据完成主论文；设备实验作为后续外部验证 |

## 6. 完成定义

选题验证阶段完成，不等于“看完一些论文”，而必须同时得到：

1. 可追溯的文献与产品证据表；
2. 可运行的数据解析与固定评测代码；
3. 至少一个公开数据小样本审计结果；
4. 至少一个 baseline 的运行记录；
5. 一个被数据支持、也可能被数据否证的具体研究问题；
6. 一份可以直接用于开题汇报的问题链和实验图。
