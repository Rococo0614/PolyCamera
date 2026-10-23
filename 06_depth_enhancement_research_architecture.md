# 偏振辅助深度增强：研究目标与总体架构

**版本：** v0.1
**日期：** 2026-10-23
**状态：** 选题验证阶段，不将候选方法提前写成既定创新

## 1. 一句话定义

> 研究商品级深度传感器在透明、反光、弱纹理和深度边界处的系统性失效，利用单帧偏振提供的反射与表面方向线索，建立能够判断模态可靠性、适应不同深度传感器的深度增强方法。

## 2. 为什么这个问题值得研究

商品级三维产品主要采用主动双目、结构光、直接 ToF 或间接 ToF。它们不是随机地“偶尔不准”，而是存在由测量机理导致的系统误差：

- 主动/被动双目依赖对应关系，弱纹理、遮挡、远距离和深度边界容易产生空洞、抖动或模糊；
- ToF 依赖主动光返回，透明、半透明、镜面反射和多次反射会造成错误距离与多径干扰；
- 错误深度如果直接作为监督或三维融合输入，会进一步污染深度网络、点云、重建和抓取系统；
- 不同传感器的失效分布不同，因此仅针对某一型号训练的修复模型可能无法迁移。

偏振观测与表面法向、入射角、折射率和反射成分有关。在深度传感器失效的复杂材质区域，它可能提供与 RGB 和原始深度不同的线索。但偏振自身也会在低光、过曝、低 DoLP、混合反射、标定误差和去马赛克伪影下失效，因此不能无条件融合。

## 3. 研究边界

### 3.1 必做范围

1. 建立商品级深度错误的可重复量化协议；
2. 证明偏振在至少一类困难区域提供可测量的增益；
3. 检查现有方法在跨场景、跨传感器和偏振退化下的稳定性；
4. 如果缺口成立，提出并验证一个可靠性/泛化改进；
5. 输出深度图、误差/置信度图和点云示例。

### 3.2 暂不承诺

- 不从零设计偏振相机；
- 不把完整 SfP、NeRF、6D 位姿和机器人抓取同时设为必做；
- 不在没有真值的情况下宣称毫米级三维精度；
- 不把简单通道拼接或普通注意力模块单独作为创新；
- 不在公开数据尚未证明问题前购买昂贵设备。

### 3.3 兜底路线

如果深度主线因数据、环境或复现问题无法推进，保留现有的 `RGBP-Glass` 偏振透明分割路线。两条路线共享偏振表示、可靠性估计和跨相机标定基础。

## 4. 研究问题与可证伪假设

### RQ1：问题是否真实且具有产品意义？

**H1：** 主动双目、D-ToF 和 I-ToF 在材质、距离和边界维度上呈现显著不同的系统误差。

验证方式：在 HAMMER 高精度真值上统计每种传感器的 RMSE、MAE、缺失率、P95 误差，并按普通/反光/透明材质、距离和边界分层。

否证条件：三类传感器在上述分层中没有稳定差异，或误差主要来自数据配准而非测量机理。

### RQ2：偏振是否提供非冗余价值？

**H2：** 在部分深度失效区域，偏振特征与深度错误存在可重复关系，加入偏振比 RGB-only 或 raw-depth-only 基线更有效。

验证方式：比较 raw depth、RGB-only、material-mask-only、朴素偏振融合和 PPFT；绘制收益相对于材质、DoLP、强度、饱和度及偏振一致性残差的条件曲线，并在同一材质内部检验偏振增量。

否证条件：偏振收益只来自模型参数量、数据泄漏或 RGB 强度，不在困难区域保持。

### RQ3：现有方法是否真正跨传感器泛化？

**H3：** 在训练时未见过的深度传感器或不同错误分布上，现有融合模型会明显退化，且可能出现负迁移。

验证方式：三组 leave-one-sensor-out：

```text
训练 D-ToF + I-ToF，测试主动双目
训练主动双目 + I-ToF，测试 D-ToF
训练主动双目 + D-ToF，测试 I-ToF
```

同时进行留一场景、留一材质类别和不同稀疏度/噪声模式测试。

严格协议中，模型选择只使用训练中的两类传感器和独立验证场景；被留出的真实传感器不能出现在训练、超参数选择或 early stopping 中。最终一次性在留出传感器的测试场景上评估。另设 few-shot adaptation 作为单独协议，不能与 zero-shot 结果混报。

否证条件：现有模型在严格无泄漏设置下已经稳定跨传感器泛化，此时不再以该点作为主要创新。

### RQ4：如何判断两种模态何时可信？

**H4：** 对原始深度和偏振分别估计空间可靠性，并进行受约束的残差修正，比无条件特征融合在跨传感器和退化输入下更稳健。

验证方式：比较无门控、单偏振门控、单深度门控、双可靠性以及 oracle reliability；同时评价精度和不确定度校准。

否证条件：可靠性分支不能预测误差、只增加参数量，或在独立测试集上没有显著收益。

### RQ5：能否检测“有值但错误”的深度？

**H5：** 相比只使用 raw depth 有效位、RGB 或局部平滑残差，偏振特征能提高透明/反光区域 valid-but-wrong depth 的检测能力，并使后续修正优于只对零值做 depth completion。

验证方式：在 raw depth 非零像素上按绝对/相对误差阈值构造错误标签，报告 AUROC、AUPRC、校准误差和 risk-coverage；分别比较 DoLP/AoLP/物理残差、RGB-D baseline 和融合模型。阈值敏感性必须报告，不能只挑一个有利阈值。

否证条件：偏振异常分数在跨场景/跨传感器上接近随机，或收益完全由材质 mask/物体类别先验解释。

## 5. 总体系统架构

```text
                              ┌──────────────────────────┐
I0/I45/I90/I135 或 Stokes ──►│ 偏振标准化与质量检查     │
                              │ S0/S1/S2, DoLP/AoLP      │
                              │ 饱和/低照/物理残差       │
                              └────────────┬─────────────┘
                                           │ polar features + q_pol
                                           ▼
┌──────────────────────┐        ┌──────────────────────────┐
│ 商品级原始深度        │───────►│ 双分支特征与可靠性建模   │
│ AS / D-ToF / I-ToF   │ q_dep  │ sensor-agnostic fusion  │
└──────────┬───────────┘        └────────────┬─────────────┘
           │                                  │
           │         可选 RGB / viewing ray ──┘
           ▼                                  ▼
   原始误差统计                         深度残差 + uncertainty
                                              │
                                              ▼
                                  enhanced metric depth
                                              │
                             ┌────────────────┴───────────────┐
                             ▼                                ▼
                     分层二维深度指标                   点云/法向/边界指标
```

说明：上图是研究架构，不是已经确定的网络结构。前两阶段只需要左侧的数据与指标链路；只有 H3/H4 得到证据后才实现右侧候选模型。

### 5.1 Gate 3 通过后的候选实现

```text
Polar input
[S0, S1/S0, S2/S0, pair residual, valid mask, viewing ray]
       │
       ├─ Polar encoder ─► polar feature ─► q_pol ─┐
       │                                           │
RGB ───┼─ frozen/general visual encoder ───────────┼─► residual fusion
       │                                           │      │
Raw depth
[depth, valid mask, local residual, gradient]
       └─ Depth encoder ─► depth feature ─► q_dep ─┘      │
                                                            ├─► p_bad / error type
                                                            ▼
                                              depth residual + log variance
                                                            │
                                         raw depth identity-preserving update
                                                            ▼
                                              metric depth + uncertainty
```

设计约束：

- 预测 raw depth 的残差而非无条件重画整张深度，减少已可靠区域退化；
- 先显式区分 missing、valid-correct 和 valid-but-wrong，再由 `p_bad` 控制修正强度；异常检测和深度修正分别报告，避免只凭最终 RMSE 掩盖错误检测失败；
- `q_pol` 和 `q_dep` 分别建模，不把高 DoLP 直接等同于高可靠；
- 对 raw depth 有效但与偏振冲突的区域显式输出不确定度；
- 使用 sensor dropout、真实 sensor mixing 和受控 corruption，避免记忆单一错误 pattern；
- 极低质量偏振输入下应可退化为 RGB-D/sensor-depth 基线，而不是强制使用偏振；
- 训练损失候选包括 robust depth、depth-gradient/normal、校准 NLL、可靠 raw-depth 保持和高置信偏振一致性；
- 是否保留 RGB foundation、点云分支或测试时优化，由 Gate 3 的消融结果决定，不预先堆叠。

必须与参数量匹配的普通 concat/attention、GAA-TSO 类几何融合和 Depth Prompting 类 sensor-bias 方法比较，才能说明收益来自偏振可靠性而非网络容量。

## 6. 数据与评测架构

### 6.1 主数据：HAMMER

HAMMER 同时包含：

- LUCID Phoenix RGB+P；
- Intel RealSense D435 主动双目深度；
- Intel RealSense L515 D-ToF 深度；
- LUCID Helios I-ToF 深度；
- 高精度物体/场景模型渲染的 metric depth；
- 法向、实例/材质相关标注及相机参数。

完整压缩包约 159 GiB，本机当前空间不足。第一阶段使用 HTTP Range 选择性抽取小样本；正式训练前必须准备至少 250--400 GiB 的独立数据盘。

### 6.2 外部验证候选

- DPS-Net 的 RPS/IPS：偏振双目，适合检查双目路线，但其真实深度真值来源需单独审查；
- DeepSfP / SPW：有偏振和法向，适合验证偏振质量/法向分支，不适合作为 metric depth 主数据；
- PTOD / PolarDepth：透明物体 RGB+偏振+深度，需确认完整数据与许可是否已公开；
- 后续自采：只作为外部验证，不在开题阶段承担大规模训练数据职责。

## 7. 固定评测协议

### 7.1 数据划分

1. 官方 scene split，用于复现；
2. leave-one-scene-out，用于场景泛化；
3. leave-one-sensor-out，用于核心假设 H3；
4. material-aware split，避免相邻视频帧泄漏；
5. corruption split，仅在测试时注入偏振/深度退化。

禁止把同一轨迹的相邻帧随机拆到训练和测试两侧。

PPFT 公开列表实际使用 `scene2--10` 训练（5253 帧）、`scene11--12` 验证（1008 帧）、`scene13--14` 测试（946 帧），与 HAMMER 官方“scene2--11 train、scene12--14 test”不完全相同。复现必须明确写成 `PPFT split`，不能称为 HAMMER official split。HAMMER 补充材料还说明最后两个测试场景具有相同位姿/轨迹但不同光照，因此 scene13/14 应视为同一几何设置的光照变体，不能在统计显著性中当作两个完全独立场景。

### 7.2 主指标

- metric depth：RMSE、MAE、AbsRel、delta1/2/3；
- 系统偏差：mean/median signed error 与正负误差比例，用于区分测到背景、前景漂移和无效值；
- 有效性：coverage、invalid rate、错误但未被置无效的比例；
- 异常检测：valid-but-wrong depth 的 AUROC/AUPRC、阈值敏感性和 risk-coverage；
- 视场公平性：sensor support/FoV fraction 与 support 内 coverage 分开报告；最终使用标定/warp 几何或跨帧有效域并集得到静态 support mask，小样本阶段的单帧非零外接框只作诊断；
- 尾部风险：P95/P99 absolute error、bad-pixel rate；
- 局部结构：边界带 RMSE、depth-gradient error、normal angular error；
- 困难材料：reflective/transparent 子集单独报告；
- 材质内部与边界分开：对 material mask 适度腐蚀后报告 interior error，避免把所有收益/失败都归因于配准和轮廓；
- 工程性：参数量、显存、延迟和吞吐。

若输出 uncertainty，再报告 NLL、误差-置信度相关性、risk-coverage 曲线和 AUSE/ECE 类校准指标。

### 7.3 主要比较

```text
B0 raw sensor depth
B1 RGB-only / depth-only completion
B2 naive RGB/polar/depth concatenation
B3 CompletionFormer
B4 PPFT
B5 近期 ReCAP2（若代码或可复现细节可得）
Ours 仅在缺口验证后定义
```

## 8. 预期论文贡献层级

### C1：必须完成

一个严格的数据和评测协议，量化不同深度产品在复杂材质上的空洞、FoV 与 valid-but-wrong 失效，并避免视频帧和传感器域泄漏。

### C2：论文核心

如果 H3/H5 成立，提出面向未知传感器/错误分布的偏振辅助深度异常检测与受控修正方法；如果假设不成立，则转向经实验证实的其他缺口，不强行包装。

### C3：仪器专业特色

偏振测量质量、相机标定、跨传感器配准、误差传播与小规模实物系统验证。

### C4：就业展示

PyTorch/OpenCV 数据管线、可复现实验、C++/ONNX 部署或实时点云演示。C4 不替代科学贡献。

## 9. 决策门槛

进入模型创新阶段前必须同时满足：

1. 至少抽取并正确解析一组 HAMMER 多模态样本；
2. 原始深度对 GT 的指标与论文描述趋势一致；
3. 四方向偏振排列、角度约定和预处理链路得到核实；
4. 至少一个公开 baseline 可推理或复现；
5. 留一传感器/退化测试确实暴露稳定缺口；
6. 测试划分无同轨迹帧泄漏。

若第 5 条不满足，则停止“跨传感器可靠性”方法开发，重新选择有证据的缺口。
