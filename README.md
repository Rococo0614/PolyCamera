# 偏振相机硕士课题调研

**建立日期：** 2026-09-21
**方向更新：** 2026-10-23
**当前工作目录：** `/home/jiangrui/PolyCamera`

## 0. 当前主线（2026-10-23 更新）

经过对偏振辅助三维视觉、公开数据和近期工作的初步核查，当前优先主线调整为：

> **面向复杂材质与异构深度传感器的偏振辅助鲁棒深度增强**

第一轮跨场景审计后，优先验证的具体问题已收窄为：

> **透明/反光场景中“有值但错误”的深度异常检测，以及在未见真实传感器上的受控修正。**

当前阶段不预设某个网络模块，而是先完成以下问题闭环：

```text
商品级主动双目 / D-ToF / I-ToF 的系统误差
        ↓
偏振信息是否在这些失效区域提供非冗余几何线索
        ↓
已有融合方法是否过拟合已见传感器或理想偏振输入
        ↓
面向未知传感器与退化偏振的可靠性建模和深度增强
        ↓
有设备后进行跨设备实物验证
```

主数据集暂定为 `HAMMER`，主评测协议为按材质分层、留一场景和留一传感器测试。完整研究章程见：

- `06_depth_enhancement_research_architecture.md`
- `07_depth_enhancement_execution_plan.md`
- `08_depth_landscape_and_gap.md`
- `depth_research/README.md`

此前的透明目标分割路线不删除，作为低风险兜底和可选前端任务保留。

## 1. 早期方案（现作为兜底路线）

### 宽方向

> 透明物体目标分割与三维感知方法研究

### 更稳妥的技术主线

> 偏振辅助的透明/高反光目标分割与边界优化

### 可选扩展

> 偏振-RGB-D 融合的透明目标三维定位、深度补全或已知物体 6D 位姿估计

当前不把“偏振、分割、深度、点云、位姿、机器人抓取”全部作为必做内容。建议采用：

```text
公开偏振分割数据复现
        ↓
偏振表示与可靠融合改进
        ↓
自有相机外部测试
        ↓
RGB-D 三维定位/位姿扩展
```

## 2. 当前判断

### 已确认

- 偏振辅助透明/玻璃分割已经有公开数据、代码和成熟 baseline。
- `RGBP-Glass` 是当前最适合作为第一实验的数据集：包含 RGB、AoLP、DoLP 和像素级玻璃 mask。
- 偏振 6D 位姿有 `Polarimetric Pose Prediction / PPP` 公开工作和数据。
- 透明物体 RGB-D 三维感知有 `ClearPose`、`ClearGrasp` 等公开数据，但它们不包含偏振信息。
- 本轮检索没有发现一个像 ClearPose 那样大规模、同时包含“偏振 + RGB-D + 透明物体 mask + 6D pose”的统一公开数据集。

### 尚未确认

- 目标相机的具体类型：RGB 三色偏振还是单色 DoFP 偏振相机。
- 目标相机是否能够输出原始 0°/45°/90°/135° 数据。
- 相机 SDK、Linux 支持、同步触发、曝光控制和数据格式。
- 课题组最终更偏向分割、三维重建、位姿估计还是应用展示。
- 是否有 RGB-D 相机、转台、标定板、受控光源或可借用的实验设备。

## 3. 透明分割兜底方案结构

### 主任务：偏振辅助透明目标分割

使用 RGBP-Glass 复现 RGB-only、AoLP/DoLP 融合和 PGSNet baseline，再尝试：

- AoLP 的周期编码：`sin(2*AoLP)`、`cos(2*AoLP)`；
- 基于 `S0`、DoLP、饱和度和噪声的偏振可靠性估计；
- reliability-aware RGB/偏振自适应融合；
- 透明边界感知 loss 或 boundary head；
- 面向轻量部署的模型压缩和推理优化；
- 从公开相机域到自有相机域的少样本适配。

### 扩展任务：RGB-D 三维感知

在分割 mask 基础上增加：

```text
目标 mask
→ 深度 ROI
→ 点云/三维中心/尺寸
→ 已知物体点云配准或 PnP
→ 可选 6D pose
```

三维部分建议作为第二阶段，不作为开题初期唯一主线。

## 4. 文件说明

- `01_topic_and_research_questions.md`：选题动机、科学/工程问题、候选贡献和风险。
- `02_datasets_and_prior_work.md`：数据集、代表性论文、代码地址和可复现性判断。
- `03_one_month_plan.md`：一个月调研、复现和开题准备计划。
- `04_hardware_and_data_collection.md`：相机选型、标定、数据采集和计算资源规划。
- `05_polarization_camera_physical_models.md`：从 Stokes/Mueller 测量方程到 DoFP、标定、Fresnel/SfP 和应用链路的物理模型报告。
- `06_depth_enhancement_research_architecture.md`：新主线的目标、研究问题、系统架构、评价协议和成功标准。
- `07_depth_enhancement_execution_plan.md`：按证据、数据、基线、方法和实物验证拆分的执行计划。
- `08_depth_landscape_and_gap.md`：产品技术、近期论文、公开数据及候选研究缺口。
- `09_execution_log.md`：按日期记录实际执行、数据结果、失败与下一步，不把计划当结果。
- `10_advisor_one_page.md`：可直接用于和导师沟通的题目、问题、路线、初步证据和风险摘要。
- `depth_research/`：公开数据分析、指标计算、选择性下载和后续实验代码。

基线代码的实际可复现性审计见 `depth_research/evidence/reproduction_audit.md`。
- `demo/polarization-camera-models/index.html`：基于清华紫模板的公式推导型 HTML PPT，含 presenter/notes/观众屏同步。
- `literature_matrix_template.csv`：后续逐篇阅读时使用的文献矩阵模板。

## 5. 目前的决策原则

1. 先跑通公开 baseline，再购买高价设备。
2. 先保证“偏振分割”能独立毕业，再把三维作为扩展。
3. 不把“RGB 拼接四个偏振通道”直接当作主要创新。
4. 贡献优先放在偏振标定、物理表示、可靠融合、跨相机泛化和下游任务收益上。
5. 所有公开数据都要核对下载可用性、许可证和传感器差异。
