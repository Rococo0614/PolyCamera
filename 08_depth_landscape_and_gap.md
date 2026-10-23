# 偏振辅助三维与深度增强：技术版图和候选缺口

**检索状态：** 第一轮，更新至 2026-10-23。此文档区分已核验事实与待实验假设，不替代正式系统综述。

## 1. 产品与测量技术

### 1.1 主动双目

代表设备：Intel RealSense D435/D455 一类主动双目产品。通过左右匹配和主动红外纹理估计视差。

主要失效：遮挡、弱纹理、远距离投影衰减、边缘、重复纹理和部分反射场景。HAMMER 使用 D435，并报告其深度通常较稀疏、抖动和边界模糊，但在其采集条件下对部分玻璃/反光对象优于两类 ToF。

### 1.2 D-ToF / I-ToF

HAMMER 使用 RealSense L515 表示 D-ToF，使用 LUCID Helios 表示 I-ToF。二者均可能受到透明/反光材质、低返回强度和多径干扰影响，但错误形式不同：无效值和“看似有效但实际错误”的比例不同。

L515 是历史代表设备，后续产品调研不能把它直接当作当前采购推荐；论文结论主要用于代表测量原理。

### 1.3 DoFP 偏振相机

HAMMER 使用 LUCID Phoenix RGB+P 相机与 Sony Polarsens 传感器。当前工业偏振相机还包括基于 Sony IMX250/IMX264 等传感器的 LUCID、Teledyne FLIR 等产品。

工业产品页面主要强调反光抑制、划痕/应力/材料检测；“偏振相机 + 商品级深度相机”的通用融合仍主要停留在研究或定制系统层面。

### 1.4 2026 年仍可查到的当前产品参照

本轮只用官方产品页核查“产品存在/在产”，具体采购前仍需重新询价和核对 datasheet：

- RealSense D455：当前官方商店仍列出的主动双目 RGB-D；
- LUCID Phoenix/Triton IMX264MZR/MYR：当前 5 MP 单色/彩色 DoFP 偏振产品；
- Teledyne FLIR BFS-U3-51S5P-C：官方标记为 `In Production` 的 IMX250MZR 偏振相机；
- LUCID Helios2/Helios2+：当前工业 I-ToF 系列；
- Basler blaze、ifm O3D/O3R：当前工业 ToF 参照产品。

这说明课题对应的两类硬件都已经商品化，但“买一台偏振相机和一台深度相机”并不自动形成产品：配准、同步、质量判断、错误修正和算力成本才是系统工作量。

## 2. 关键公开数据

### HAMMER

- 论文：*On the Importance of Accurate Geometry Data for Dense 3D Vision Tasks*；
- 数据：<https://github.com/Junggy/HAMMER-dataset>；
- 13 个室内场景，RGB+P、D435、L515、Helios 和高精度渲染真值；
- 官方数据页声明采用 MIT license，并明确允许商业使用；
- 优点：同一场景下比较多种商品级深度原理；
- 风险：完整 ZIP 约 159 GiB；场景数不大；视频相邻帧高度相关；偏振角度描述需要核实。
- 划分风险：PPFT 的 train/val/test 为 scene2--10 / scene11--12 / scene13--14，并非 HAMMER 官方 scene2--11 / scene12--14；scene13/14 还是相同轨迹下的不同光照变体。

### DPS-Net RPS/IPS

- 论文：*DPS-Net: Deep Polarimetric Stereo Depth Estimation*, ICCV 2023；
- 代码：<https://github.com/Ethereal-Tian/DPS-Net>；
- 适合：偏振双目和弱纹理；
- 风险：双偏振相机硬件成本、标定复杂，真实集深度真值来源需审查。

### DeepSfP / SPW

- 有偏振与表面法向；
- 适合验证偏振表示和法向，不直接承担通用 metric depth 评测。

### PTOD

- 随 PolarDepth 2026 提出，包含 RGB、偏振、depth 和透明区域 mask；
- 论文给出的规模为 2,878 个场景，分辨率 612 x 512，偏振相机为 FLIR Blackfly-S；
- 深度真值并非直接用商品相机拍透明表面：作者将透明物体替换为同几何不透明复制品，用 RealSense D435i 获取 metric depth，再以 Depth Anything V2、ECC 配准和 scale/shift refinement 生成稠密深度；
- 论文与项目页可访问，但截至 2026-10-23，GitHub 只有一个 README 提交并写明代码/数据“will be publicly available soon”；项目页的数据需要表单申请，公开入口未形成可直接复现链路；
- 因此 PTOD 暂列为待申请的外部验证候选，不能作为当前执行依赖。

### 3DReflecNet（外部问题证据，不作为主训练集）

- CVPR 2026，超过 22 TB；
- 12 万以上合成实例、1000 个以上真实采集，覆盖透明、金属、光滑低纹理等材料；
- 论文显示当前匹配、SfM、NeRF/3DGS 和表面重建在这些材料上系统退化；
- 不包含本课题需要的偏振+商品级深度配对，规模也不适合本硕士课题下载训练，但可作为“复杂材质三维问题仍有现实价值”的独立证据。

## 3. 代表性工作与结论

### Polarized 3D（ICCV 2015）

用粗深度消除偏振法向歧义，再提高表面细节。物理意义清晰，但对象级假设和受控条件较强。

### DPS-Net（ICCV 2023）

将偏振相关体与 RGB stereo matching 结合，针对弱纹理和非朗伯区域。它回答的是“偏振如何帮助双目”，不是多种商品深度输入的统一增强。

### PPFT（CVPR 2024）

- 论文：<https://arxiv.org/abs/2404.04318>；
- 代码：<https://github.com/lastbasket/Polarization-Prompt-Fusion-Tuning>；
- 在 HAMMER 上联合三种 sensor depth 与偏振；
- 相比 CompletionFormer，论文报告主动双目、D-ToF、I-ToF RMSE 分别约改善 24.4%、29.7%、25.3%；
- 补充材料还测试了训练中未出现的 8/16 线合成 LiDAR 稀疏模式，说明其对新稀疏 pattern 有一定泛化；
- 关键限制：真实传感器实验是“训练包含多种传感器，分别测试各传感器”。合成稀疏 pattern 不等同于对一个未见真实测量原理及其系统误差的迁移，因此严格 leave-one-real-sensor-out 仍需验证；公开环境也较旧。

### Depth Prompting（CVPR 2024）

- 论文：*Depth Prompting for Sensor-Agnostic Depth Estimation*；
- 不使用偏振，但直接研究 sensor-agnostic depth completion；
- 已系统测试 sparsity、sampling pattern、scan range、NYU/KITTI 跨域和商业传感器零/少样本推理；
- 是跨传感器主线必须比较或借鉴的工作，避免把已有 domain-agnostic 思路重新命名；
- 它主要处理稀疏度/采样/量程分布偏移，没有使用偏振，也没有专门解决透明/反光导致的“数值有效但物理错误”的深度，因此本课题必须证明偏振对这部分错误有额外价值。

### ReCAP2（Knowledge-Based Systems 2025）

- DOI：<https://doi.org/10.1016/j.knosys.2025.114498>；
- 标题：*Rectified and context-aware polarization prompting for robust depth enhancement*；
- 直接延续 PPFT，处理跨模态表征和上下文提示；
- 当前未发现开放全文/代码，必须取得完整论文后再精确界定与本课题的差异。

### CDPR（IEEE TMM 2026）

- 论文：<https://arxiv.org/abs/2604.11097>；
- 代码：<https://github.com/YrjNEU/CDPR-main>；
- 面向 RGB+偏振的单目深度，已经包含 confidence-aware gated fusion；
- 因而“设计一个偏振置信度门控”不能单独作为本课题创新；其输入不含商品级 raw sensor depth，与多传感器增强仍有区别。

### Poppy（ECCV 2026）

- 论文：<https://arxiv.org/abs/2603.27891>；
- 代码：<https://github.com/irnkim/poppy>；
- 测试时用可微偏振物理约束修正冻结的 RGB 法向基础模型；
- 说明“基础模型 + 测试时物理引导”是强竞争路线，但其目标是法向，运行开销较大。

### PolarDepth（ICML 2026）

- 论文：<https://proceedings.mlr.press/v306/dong26i.html>；
- 面向透明物体的单目 RGB+偏振 metric depth；
- 引入折射率、天顶角、方位角等物理先验和 PTOD 数据；
- 补充材料在人工标注透明 mask 的 HAMMER 子集上做了 PTOD fine-tune / joint fine-tune 跨域评测，但不使用三类 raw sensor depth 作为输入；
- 作者明确指出弱偏振材料和低偏振区域仍是限制；
- 与本课题的区别应落在 raw depth sensor enhancement、跨传感器和可靠性评测，而不是泛称“透明物体偏振深度”。

### GAA-TSO（2025）

- 面向透明/高反物体的 RGB-D 深度补全；
- 已使用图像分支、点云分支、深度 confidence、自适应邻域和 gated 2D/3D 融合；
- 在 ClearGrasp、TransCG、STD 等数据及机器人抓取上验证；
- 因此“增加点云分支”“根据深度置信度门控”“验证抓取收益”都已有直接先例。本课题必须回答偏振相对于这些 RGB-D 几何方法的额外价值，以及未知真实传感器下的稳定性。

### PolFusion+（TPAMI 2026）

- 关注偏振测量自身的低照噪声、长曝光模糊和饱和，融合一对短曝光/长曝光偏振快照以恢复物理一致的 DoP/AoP；
- 说明偏振输入质量已有专门恢复方法，不能把“处理低照/过曝偏振”笼统声称为首次；
- 它要求成对退化曝光，且作者明确指出不适用于偏振视频和普通 RGB，也不处理 raw sensor depth；
- 本课题更合理的做法是把它作为上游替代/竞争方案，在单帧商品传感器约束下研究质量感知和失效退化，而不是再做完整偏振图像恢复网络。

## 4. 已排除的伪创新

- 第一次用偏振改善深度；
- 第一次将 AoLP/DoLP 输入神经网络；
- 第一次使用预训练 RGB 模型融合偏振；
- 第一次做偏振置信度门控；
- 第一次利用偏振处理透明物体；
- 第一次加入点云分支、深度 confidence 或 gated 2D/3D 融合；
- 只在 HAMMER 官方划分上比 PPFT 高一点。

## 5. 当前最有希望的候选缺口

### 候选 A：严格的未知传感器泛化

问题：现有“multi-sensor”结果是否依赖训练时见过每一种传感器的错误分布？

证据状态：PPFT 正文显示训练包含全部真实传感器；补充材料验证了未见的合成 8/16 线 LiDAR pattern，但不是严格 leave-one-real-sensor-out。尚需取得 ReCAP2 全文并检查其协议。

### 候选 B：双模态可靠性与校准

问题：不仅判断偏振是否可信，也判断 raw depth 是空洞、随机噪声还是系统性错误，并输出可校准的不确定度。

证据状态：CDPR 已做 RGB/偏振 latent confidence；ReCAP2 已做 context-aware rectification。必须把差异限定在 raw sensor depth、双可靠性、跨传感器和校准，而不是普通 gating。

### 候选 C：偏振测量退化下的鲁棒性

问题：四通道响应误差、AoLP 零点、低照、过曝、去马赛克和跨相机域变化会否让融合方法产生负迁移？

价值：连接仪器标定与算法；无设备阶段可用受控 corruption 初步验证，设备到位后做真实外测。

边界：需要与 PolFusion+ 等偏振恢复工作区分。本课题关注的是退化偏振对深度融合的风险、单帧回退和跨相机校准，不以生成“更好看的偏振图”为目标。

### 当前推荐组合

初步数据进一步将问题收窄为：

> 以“valid-but-wrong / silent depth error 的检测与修正”为任务核心，以 A 的 leave-one-real-sensor-out 为评价协议，以 B 的双模态可靠性为方法候选，以 C 作为仪器特色和压力测试。

最终题目暂写为：

> **面向异构深度传感器的偏振可靠性感知深度增强方法研究**

该题目只有在 leave-one-sensor-out 和退化测试证明缺口后才正式锁定。

若多场景审计继续支持当前趋势，更具体的题目可写为：

> **面向透明与反光场景的偏振引导深度异常检测与跨传感器增强**

## 6. 当前最重要的复现风险

HAMMER 补充材料将四幅偏振图描述为 `0/90/180/270`，而常规线偏振恢复和 PPFT 代码使用 `0/45/90/135`。PPFT 的 `process_hammer.py` 对四象限映射还留有“by guess, not sure”的源码注释。

因此第一轮实验必须：

1. 查 HAMMER 原始元数据和 LUCID 输出格式；
2. 联系数据作者或寻找公开 issue/说明；
3. 对可能排列做敏感性检查；
4. 在未核实前，不把计算出的 AoLP 当作绝对物理方向；
5. 把这一点写进复现报告，而不是静默沿用代码。

### 6.1 已完成的初步核查

LUCID 2026 更新的官方 Pixel Formats 文档确认：`PolarizedAngles_0d_45d_90d_135d_*` 的四个通道按 `0/45/90/135` 顺序输出；Sony 原始 2x2 物理像元布局则是另一回事，不能直接套到作者保存的四象限 composite。

对 HAMMER `scene13_traj1_1/000000` 的四象限做三种可能的正交配对检验，平均相对 pair-sum residual 为：

```text
(q0+q1) vs (q2+q3): 0.149
(q0+q2) vs (q1+q3): 0.055  <- PPFT 假设对应的正交配对
(q0+q3) vs (q1+q2): 0.118
```

这较强支持 `q0/q2` 和 `q1/q3` 分别是两组正交方向，因此 DoLP 幅值分析的风险下降；但该检验不能确定哪个象限绝对对应 0°，也不能确定 AoLP 零点和符号，后者仍需作者元数据或标定图确认。

这一差异对研究设计有直接影响：DoLP 在交换正交对、交换对内方向时通常保持不变，而 AoLP 会发生常量旋转、符号翻转或 `pi/2` 偏移。同一数据集内的网络可能把固定偏移“学进去”，但换相机后会形成域偏移。因此，AoLP 零点/坐标约定应作为跨相机实验的显式校准变量，而不是隐藏在预处理代码中。
