# 共享偏振表示相关论文地图

**更新日期：** 2026-11-11

本文区分“已经实际用于本项目设计/实验的工作”和“应补入的直接竞争工作”。论文被列入不等于
结果已经复现；没有全文或代码时，只记录可公开核实的边界。

## 1. 当前已经实际借助的核心工作

| 工作 | 本项目借助的内容 | 当前用途 |
|---|---|---|
| Farid & Adelson, *Separating Reflections from Images by Use of Independent Component Analysis*, JOSA A 1999 | 两幅正交检偏图作为同一 T/R 的不同全局线性混合，以统计独立性做 ICA 分层 | 传统无学习基线 |
| Schechner, Shamir & Kiryati, *Polarization-Based Decorrelation of Transparent Layers: The Inclination Angle of an Invisible Surface*, ICCV 1999 | 用 Fresnel 权重反演两层，以重建层去相关估计半反射面的入射角并标注 T/R | 从任意 ICA 混合矩阵到物理混合矩阵 |
| Schechner, Shamir & Kiryati, *Polarization and Statistical Analysis of Scenes Containing a Semireflector*, JOSA A 2000 | 双表面内部反射、表面方向、互信息、噪声/角度误差与根本歧义 | 物理假设与失败边界 |
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

上述传统路线的约束演进是：全局线性混合与统计独立 → Fresnel 系数和表面方向 → 完整概率分布与
双表面内部反射 → 空间变化系数场和多尺度约束优化。其共同边界包括 T/R 相关或相似纹理、低偏振
效应下的噪声放大、多图配准，以及厚玻璃多次反射、ghosting、曲面/粗糙界面和偏振照明造成的
模型失配。学习方法应补充局部结构和语义先验，而不是删除物理重投影与质量门控。

### 1.1 偏振反光网络的恢复层级与采集审计

| 工作 | 偏振输入与强度/偏振输出 | 训练数据 | 真实采集硬件与场景 |
|---|---|---|---|
| ReflectNet, ECCV 2018 | 3 张相差 45° 的 RGB 偏振图；canonical projection 得到 `I⊥/I∥`；网络预测 RGB 残差与权重，输出可观察的强度 `T/R`，不输出四方向 polarized `T/R` | PLACE2 图像对合成；模拟 HDR 动态范围、edge-aware reflection、非刚性变化、曲面和手动检偏角误差 | URD 约 28 个高分辨率 RAW 城市半反射场景；Sony Alpha 6000 / Canon EOS 7D + 镜前线偏振片手动旋转，三方向顺序采集 |
| Lei et al., CVPR 2020 | 四方向 RAW + intensity/DoLP/AoLP/过曝掩码；RNet 先估计单通道强度 `R`，TNet 再估计单通道强度 `T`；不恢复逐角 `T/R` | 807 组真实 M-R 数据，超过 100 类玻璃 | LUCID PHX050S-P + Sony IMX250MZR 单色 DoFP，单曝光四方向；黑布挡住透射得到 `R`，再拍 `M`，在线性 RAW 域计算 `T=M−R`；日常门窗及平面/曲面、薄/厚、有色/无色玻璃 |
| Multi-bounce, ECCV 2020 | PolarNet 逐角预测 `{Tφ,Rφ}`；FusionNet 输出最终彩色强度 `T/R`；PSE 用 Stokes/Mueller 多次反射模型重建四方向输入 | 10,000 组合成混合图 + 13 个真实训练场景 | LUCID PHX050S-Q + Sony IMX250MYR 彩色 DoFP，单曝光四方向；26 个静态场景，每景一组无玻璃偏振 GT 与 6–12 组不同玻璃角度/位置混合图，13/13 划分 |
| Deng et al., KBS 2026 | 已确认 cross dual-stream、`T/R` 估计与 polarization restoration 联合方向；具体输入和偏振恢复监督尚未开放核实 | 数据集、split 和损失待全文 | 相机型号、DoFP/旋转偏振片、采集场景均待全文，不推测 |

因此需要严格区分三种主张：`polarization-to-intensity`、`polarization-to-polarization`，以及带四方向
重投影的物理闭环。仅把四方向图送入网络，并不能证明输出或潜表示保留了偏振物理。

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

## 6. 通用预训练模型与 2026 年新增直接竞争工作

完整能力审计、论文内数值、模型选型与机制对照见
[`FOUNDATION_MODELS.md`](FOUNDATION_MODELS.md)。以下发现修正“仅用小型ImageNet主干，暂不考虑DINO”的早期建议：

| 工作 | 本次核验内容 | 对本项目的影响 |
|---|---|---|
| *Revisiting Shape from Polarization in the Era of Vision Foundation Models*，arXiv:2603.04817v1，2026预印本 | 冻结DINOv3 ConvNeXt-Base + 偏振UNet；三真实集平均法向误差12.54°，w/o polar为18.43°，w/o DINO为15.03°；并非每个子集都优于MoGe2 | 小型DINO应进入强预训练基线；噪声增强与预训练/偏振贡献需分别消融 |
| *Learning Polarization Image Restoration with General Restoration Priors*，arXiv:2609.30728v1，2026预印本 | 归一化Stokes、强度/偏振分支、InstructIR预训练、门控与复合退化恢复 | 与当前模块方案高度相关；“归一化Stokes+预训练+门控”本身不足以作为创新；代码/数据入口本次未确认 |
| *WindowSeat*，CVPRW 2026 | 通用图像编辑DiT经LoRA适配为反光恢复，公开Qwen-Image-Edit-2509版本和评测脚本 | 新增强RGB-only任务参照，不将不同数据集PSNR混比，不因此启动大模型训练 |
| *PolarVLM*，arXiv:2605.07574v1，2026预印本 | LLaVA/CLIP偏振分支、物理问答；论文主指标为LLM 1–10分评判 | 预训练语言视觉适配已有先例；不能用VQA评分替代偏振恢复精度 |
| *SegRGB-X*，arXiv:2603.28023v1，2026预印本 | LoRA-CLIP、多模态共享Transformer、联合分割训练 | 通用多模态分割已有竞争；联合训练仍不同于跨任务冻结迁移 |
| *DORIS*，arXiv:2610.17991v2，2026-11-10更新 | RGB/偏振/退化语义联合水下恢复；同结构移除偏振后PSNR仅下降约0.1244dB，SSIM反而提高 | 偏振收益具有任务和指标依赖，不能预设一定大幅提升；UPLight分割数据仍不等于水下清晰GT |
| *PBP-SAM*，Applied Optics 2026，DOI 10.1364/AO.607332 | 仅摘要确认偏振边界提示+SAM adapter/LoRA；全文与数值待核 | SAM可适配偏振已有先例，不代表原始SAM会直接使用偏振测量 |

新的重点应是：**强预训练基线上，输入信息、物理损失、质量门控分别有多少可归因增量，以及同一冻结编码器能否带着增量跨任务迁移。**
