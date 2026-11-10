# 共享偏振表示相关论文地图

**更新日期：** 2026-11-10

本文区分“已经实际用于本项目设计/实验的工作”和“应补入的直接竞争工作”。论文被列入不等于
结果已经复现；没有全文或代码时，只记录可公开核实的边界。

## 1. 当前已经实际借助的核心工作

| 工作 | 本项目借助的内容 | 当前用途 |
|---|---|---|
| Farid & Adelson, *Separating Reflections and Lighting Using ICA*, CVPR 1999 | 多偏振观测作为不同混合、统计独立分层 | 传统无学习基线 |
| Schechner, Shamir & Kiryati, *Polarization and Statistical Analysis of Scenes Containing a Semireflector*, JOSA A 2000 | 半反射介质、表面方向、互信息、噪声/角度误差与根本歧义 | 物理假设与失败边界 |
| Kong, Tai & Shin, *A Physically-Based Approach to Reflection Separation*, CVPR 2012 / TPAMI 2014 | 空间变化入射角、约束优化、三偏振图分层 | 传统物理强基线候选 |
| Wieschollek et al., *Separating Reflection and Transmission Images in the Wild*（ReflectNet）, ECCV 2018 | canonical projection、残差 T/R、曲面/动态范围/非刚性合成 | P3 仿真设计、早期学习基线 |
| Lei et al., *Polarized Reflection Removal With Perfect Alignment in the Wild*, CVPR 2020 | PHX050S-P + IMX250MZR 单曝光四方向、M-R 采集、先 R 后 T 两阶段网络、807 对数据 | 与自有设备最接近的真实数据/网络基线 |
| Lyu et al., *Reflection Separation Using a Pair of Unpolarized and Polarized Images*, NeurIPS 2019；TPAMI 扩展 2023 | 物理成像、半反射面方向、欠定问题、物理引导级联网络 | 物理 stem 和少观测对照 |
| Li et al., *Reflection Separation via Multi-Bounce Polarization State Tracing*, ECCV 2020 | 四方向单曝光、多次反射 Mueller/Stokes tracing、PolarNet/FusionNet、合成与真实数据 | P3 物理仿真与监督分层参考 |
| Wen, Zheng & Lu, *Polarization Guided Specular Reflection Separation*, TIP 2021 | 偏振色度、颜色聚类、ADMM 联合 RGB/偏振分离 | 可执行 MATLAB 传统强基线 |
| Yao et al., *PolarFree*, CVPR 2025 | PolaRGB 6,500 对数据、RGB+四方向+AoLP/DoLP、diffusion prior、公开 checkpoint | P0/P1 主数据与当前强学习基线 |
| Liu et al., *ShareCMP*, TCSVT 2025 | 共享双分支编码器、四方向 PGA、UPLight/ZJU 下游分割 | 冻结编码器跨任务验证设计 |

此外，PDD 公开数据用于去马赛克/噪声代理；SHDocs 用于此前 OCR 选择效应对照；HAMMER/PPFT
仅保留为历史偏振质量与可靠性方法，不作为反光分离精度证据。

## 2. 必须补入的直接竞争工作

### 2.1 Wang, Zhang & Chen：Dual-stream attention guidance

**论文：** *Polarized Reflection Removal with Dual-Stream Attention Guidance*, Pattern Recognition 157,
110945，2025（online 2024），DOI `10.1016/j.patcog.2024.110945`。

- 输入多通道偏振图；
- 两个流同时预测 reflection 与 transmission；
- 用 differential feature fusion 促进两流通信；
- 在真实偏振反光数据上评测。

它已经覆盖“偏振双流 + T/R 同时预测 + 跨流交互”，是下述 2026 cross dual-stream 工作的直接前序，
也意味着“双分支”不能作为本项目创新。

### 2.2 Bian, Monno & Okutomi：Polarization-to-Polarization

**论文：** *Reflection Removal Using Recurrent Polarization-to-Polarization Network*, ICASSP 2024；
后续开放扩展发表于 Machine Vision and Applications 2026。代码：<https://github.com/wjbian/RP2PN>。

- 输入四方向 mixed 偏振图及 intensity/DoP/difference cues；
- R-LSTM-Net 与 T-Net 依次、循环估计；
- 输出不是单张强度 T/R，而是四方向 polarized T/R；
- 灰度实验使用 Lei 2020 数据；扩展工作使用 Mitsuba 3 生成 2,024 组彩色偏振 T/R，另用
  LUCID PHX050S-Q + IMX250MYR 采集 45 组真实彩色测试数据。

它与我们“潜变量应保留偏振、任务输出可重投影”的物理约束非常接近，是仿真器和 T/R 辅助头的
直接基线。

### 2.3 Deng et al.：Cross dual-stream + polarization restoration

**论文：** *Polarization Information Restoration for Visual Reflection Removal via Cross Dual-Stream Network*,
Knowledge-Based Systems 341, 115811，2026，DOI `10.1016/j.knosys.2026.115811`。

公开可核实信息：

- 提出 polarization-guided cross dual-stream network；
- 主题是同时进行 visual reflection removal 与 polarization information restoration；
- 关键词包括 polarization imaging、two-stream network、reflection removal；
- 参考文献覆盖 Kong、Lyu、Lei、ReflectNet、RP2PN、PolarFree、dual-stream attention、PolAttNet、
  偏振去模糊、去雾和水下任务。

用户已从全文观察到该方法采用双分支并估计 T/R。当前公开索引没有摘要全文、开放 PDF、代码或
数据入口，因此以下内容尚不能仅凭标题确认：具体四方向输入、偏振恢复目标、损失函数、数据集、
split 和数值结果。若提供论文 PDF，应优先做逐模块和逐表格审计。

**对本项目的影响：** “双流 + T/R + 偏振恢复”已经被覆盖。我们的候选贡献必须进一步证明：

1. 编码器不是只服务反光去除；
2. 编码器冻结后可接不同任务头；
3. 相对 S0/RGB、重复通道、噪声副本和打乱 `(Q,U)` 有稳定增量；
4. 遵守 Stokes 重投影/角度旋转，并对低 DoLP、饱和和去马赛克失败给出质量门控。

### 2.4 其他应纳入矩阵的近期方法

| 工作 | 价值 | 优先级 |
|---|---|---|
| Pang et al., *Progressive Polarization Based Reflection Removal via Realistic Training Data Generation*, Pattern Recognition 2022 | 偏振驱动合成数据与 progressive 网络 | B |
| Zhang et al., *Polarized Reflection Removal with Difference Feature Attention Guidance*, Applied Optics 2022 | 偏振差分特征 | B |
| Wang & Miyazaki, *PolAttNet*, IEEE Access 2025 | 多注意力偏振反光去除 | B |
| Li et al., *Polarized Color Image Denoising*, CVPR 2023 | IMX250MYR RAW、噪声模型、同时恢复强度与 DoLP/AoLP | A（P2/RAW 链） |
| Zhou et al., *Learning to Deblur Polarized Images*, IJCV 2025 | 偏振约束恢复与下游去雾/反光 | B |

## 3. 去雾、水下与感知迁移的物理来源

| 工作 | 提供的依据 |
|---|---|
| Schechner, Narasimhan & Nayar, *Polarization-Based Vision Through Haze*, Applied Optics 2003 | direct transmission + polarized airlight 的去雾模型 |
| Schechner & Karpel, *Recovery of Underwater Visibility and Structure by Polarization Analysis*, IEEE JOE 2005 | 水下 direct signal + backscatter 分解 |
| Treibitz & Schechner, *Active Polarization Descattering*, TPAMI 2009 | 主动偏振去散射与可辨识条件 |
| Shen et al., *U²PNet*, IEEE TCYB 2024 | 单幅偏振 mosaic、T-net/B∞-net、无监督水下恢复 |
| ShareCMP, TCSVT 2025 | UPLight 四方向水下分割与 ZJU 道路分割，验证共享偏振特征接口 |

这些论文支撑的是“多个任务都测量同一偏振光场”，不自动证明同一编码器可迁移。迁移仍需冻结
编码器和匹配任务头实验。

## 4. 当前建议的基线优先级

### 必须执行或复核

1. 无学习：`mean4/min4/virtual_min` + Wen 2021 ADMM；
2. 真实单曝光灰度：Lei 2020；
3. 偏振到偏振 T/R：RP2PN；
4. 大规模彩色数据：PolarFree checkpoint；
5. 双流直接竞争：Wang 2025；
6. Deng 2026：拿到全文后判断能否复现，至少作为最近工作对照。

### 主要用于设计而非必须复现

- ReflectNet：canonical projection 和合成器；
- Multi-bounce state tracing：Mueller/Fresnel 物理和仿真；
- Lyu：少观测物理引导；
- Polarized Color Image Denoising：RAW 噪声与偏振保持；
- ShareCMP：共享编码器和跨任务评测。

## 5. 仍需从 Deng 2026 全文提取的信息

1. 输入是四方向 RAW、重建 RGB-P，还是强度 + DoLP/AoLP；
2. 两个 stream 分别表示什么；
3. T/R 是单张强度还是四方向偏振层；
4. “polarization restoration”的监督量是 Stokes、DoLP/AoLP、四方向还是潜特征；
5. 是否满足 `I = T + R` 或 Stokes 重投影约束；
6. 使用何种数据集、相机、split、训练/测试域；
7. 是否公开代码、权重和数据；
8. 是否做 RGB/S0、错误偏振、通道数匹配和跨任务迁移对照。

上述第 8 项很可能仍是本项目与单任务双流网络的关键差异。
