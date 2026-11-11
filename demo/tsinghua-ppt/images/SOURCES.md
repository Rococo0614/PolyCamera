# PPT 图片来源与许可

以下第一组场景图片下载自 Wikimedia Commons，用于本项目学术汇报中的工业场景示意。它们不是本项目实验数据。本文档记录原文件、作者和许可；本地 WebP 仅做尺寸压缩和格式转换。第 3–4 页另含论文原图节选，单独记录在后表。

| 本地文件 | 原文件与作者 | 许可 |
|---|---|---|
| `03-date-code.webp` | [Chips - Best before 12.01.20201.jpg](https://commons.wikimedia.org/wiki/File:Chips_-_Best_before_12.01.20201.jpg), Silverije | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `03-barcode-scan.webp` | [Package tracking barcode scanner 2.jpg](https://commons.wikimedia.org/wiki/File:Package_tracking_barcode_scanner_2.jpg), IAEA | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/) |
| `03-conveyor.webp` | [Packages on UPS conveyor belt.jpg](https://commons.wikimedia.org/wiki/File:Packages_on_UPS_conveyor_belt.jpg), U.S. Department of Agriculture / Lance Cheung | Public domain |
| `03-anpr.webp` | [ALPR License Plate Reader Cameras Pensacola Florida.jpg](https://commons.wikimedia.org/wiki/File:ALPR_License_Plate_Reader_Cameras_Pensacola_Florida_(27910151545).jpg), Tony Webster | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/) |
| `04-metal-can.webp` | [Konservendose-1.jpg](https://commons.wikimedia.org/wiki/File:Konservendose-1.jpg), Rainer Zenz | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| `04-plastic-bottles.webp` | [Labeling error, 50 cl bottles.jpg](https://commons.wikimedia.org/wiki/File:Labeling_error,_50_cl_bottles.jpg), Cjp24 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `04-shrink-bottles.webp` | [Shrink wrapped case of bottles.jpg](https://commons.wikimedia.org/wiki/File:Shrink_wrapped_case_of_bottles.jpg), Rlsheehan | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `04-standup-pouch.webp` | [Stand-up pouch.jpg](https://commons.wikimedia.org/wiki/File:Stand-up_pouch.jpg), Pkgx | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |

图注中的“Wikimedia Commons”指向本清单。后续获得自有喷码工位、工件和四方向偏振照片后，应优先替换这些场景示意图，并保留“网络示意图”和“本项目实验数据”的明确区分。

## 第 3–4 页论文图节选

以下图像只用于说明传统偏振分离方法的历史演进，均在页面内写明作者、年份、出处和图号；版权归原作者与出版方。它们不是本项目实验结果，也不用于重新评测论文性能。

| 本地文件 | 原始论文与图号 | 本地处理 |
|---|---|---|
| `03-farid-ica.webp` | H. Farid and E. H. Adelson, *Separating Reflections from Images by Use of Independent Component Analysis*, JOSA A 16(9), 1999, [author PDF](https://hfarid.org/downloads/publications/josa99.pdf), Figs. 8–9 | 从论文图中节选两幅偏振混合观测与 ICA 输出，统一灰度、并排排版；未改变图像内容 |
| `03-schechner-decorrelation.webp` | Y. Y. Schechner, J. Shamir and N. Kiryati, *Polarization-Based Decorrelation of Transparent Layers: The Inclination Angle of an Invisible Surface*, ICCV 1999, [author PDF](https://webee.technion.ac.il/people/yoav/publications/iccv99polart2.pdf), Figs. 5 and 7 | 节选检偏观测与重建层，统一灰度、并排排版；未改变图像内容 |
| `03-schechner-mi-minima.webp` | Y. Y. Schechner, J. Shamir and N. Kiryati, *Polarization and Statistical Analysis of Scenes Containing a Semireflector*, JOSA A 17(2), 2000, [author PDF](https://webee.technion.ac.il/people/yoav/publications/polarjosa.pdf), Fig. 5 | 节选互信息曲线的极小值区域，转换为 WebP 并轻微增强投影对比度；曲线内容未改动 |
| `04-reflectnet-architecture.webp` | P. Wieschollek et al., *Separating Reflection and Transmission Images in the Wild*, ECCV 2018, [CVF PDF](https://openaccess.thecvf.com/content_ECCV_2018/papers/Patrick_Wieschollek_Separating_Reflection_and_ECCV_2018_paper.pdf), Fig. 4 | 节选 canonical projection 与残差编码器架构，裁除正文和图注后转为 WebP；图内内容未改动 |
| `04-lei-two-stage.webp` | C. Lei et al., *Polarized Reflection Removal With Perfect Alignment in the Wild*, CVPR 2020, [CVF PDF](https://openaccess.thecvf.com/content_CVPR_2020/papers/Lei_Polarized_Reflection_Removal_With_Perfect_Alignment_in_the_Wild_CVPR_2020_paper.pdf), Fig. 5 | 节选四方向预处理、RNet 与 TNet 两阶段架构，裁除正文和图注后转为 WebP |
| `04-multibounce-architecture.webp` | R. Li et al., *Reflection Separation via Multi-Bounce Polarization State Tracing*, ECCV 2020, [ECVA PDF](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123580766.pdf), Fig. 2 | 节选 PolarNet、FusionNet 与 PSE 闭环架构，裁除页眉和正文后转为 WebP |

第 3 页 Kong–Tai–Shin 卡片中的流程图为本项目依据 *A Physically-Based Approach to Reflection Separation: From Physical Modeling to Constrained Optimization*, TPAMI 36(2), 2014, DOI [`10.1109/TPAMI.2013.45`](https://doi.org/10.1109/TPAMI.2013.45) 的方法描述与公开摘要重绘，不是论文原图。

第 4 页 Deng et al. 2026 卡片为本项目根据论文题名、出版元数据和已核实的 cross dual-stream / T-R / polarization-restoration 方向重绘，不是论文原图。由于没有开放全文或代码，卡片明确保留输入表示、恢复监督、相机、采集方式、数据集和场景等未知字段。

第 5 页 `05-e1b-aolp-{gt,nearest,bilinear}.webp` 由公开 PDD 2025 的 `High/Scene12` 四方向 PNG 生成：使用项目冻结的绿色通道、MPFA 排列 `[[90,45],[135,0]]`、最近邻/3×3 normalized bilinear 和 `linear_stokes`。可视化中色相表示 AoLP、饱和度为 `clip(4×DoLP)`、亮度为共享尺度的 S₀。三张图只是单场景定性示意；其下 Low/Mid/High 表格为每档 40 场景的平均 AoLP MAE，并同时列出完整四方向带噪声、Nearest MPFA 与 Bilinear MPFA，不能把表中数字解释为 Scene12 单图误差。

## 本项目原创示意图

`11-polar-a.svg`、`11-polar-b.svg`、`11-stokes.svg`、`11-quality.svg`、`11-adaptive.svg`、`11-ocr.svg` 为早期版本根据研究方案绘制并保留的示意资产；当前 10 页主稿未使用，不代表已采集图像或实验结果。

第 2 页的工业反光、去雾、车牌、半反射层、水下增强场景图标，以及 DoFP、Fresnel 和微表面
BRDF 图均为 HTML/CSS/无文字 SVG 的本项目原创机制示意，不是相机照片、光线追踪结果或定量实验。

## 本项目实验数字与结果图

当前 PPT 为 10 页共享偏振表示研究更新版。第 5–6 页数字来自公开数据或合成代理；第 7–9 页是预注册协议与拟执行架构，不是训练结果，也不是自有相机结果。

| 页码 | 内容 | 冻结来源 |
|---|---|---|
| 2 | 五类 RGB 失效场景、彩色偏振相机、Stokes、Fresnel、microfacet BRDF 与 T/R 欠定 | LUCID Phoenix PHX050S-QC 产品资料、Sony IMX250MYR / Polarsens 资料、`05_polarization_camera_physical_models.md`、Born & Wolf *Principles of Optics*、Cook–Torrance / Walter 等 microfacet 模型、Schechner / ReflectNet 的半反射层模型；所有图为机制示意，4×4 单元非芯片实际相位图 |
| 3 | Farid–Schechner–Kong 的传统偏振 T/R 分离演进、共同边界及对学习先验的启发 | 上述三张论文图节选；Farid & Adelson, JOSA A 1999；Schechner et al., ICCV 1999 / JOSA A 2000；Kong et al., TPAMI 2014；方法口径同步见 `polar_representation/LITERATURE.md` |
| 4 | ReflectNet、Lei 2020、Multi-bounce 与 Deng 2026 的偏振/强度恢复层级及采集方案 | 上述三张论文架构图；对应 ECCV 2018、CVPR 2020、ECCV 2020 原文；Deng et al. 2026 仅使用出版元数据与已核实方向，具体输入、监督和采集字段按“待全文核查”处理；完整审计见 `polar_representation/LITERATURE.md` |
| 5 | 从任务读出、仪器响应到 DoFP 重建的三段误差源审计：E0 合成 OCR sanity、E1-a 已知 Stokes 仪器矩阵自检、E1-b PDD MPFA/AoLP 误差 | `e0_clean_code_sanity.json`、`e1_synthetic_instrument_recovery.json`、`e1_pdd_simple_baselines.json`；三段使用不同数据与指标，页面明确禁止直接相加为统一“误差份额” |
| 6 | E2 真实四方向配对增量 → C2 全局亮度/对比度匹配 → C3 噪声选择下限与后端相关剩余信号 → 基础 Selector 和 C1 密集候选控制；由此导向“偏振物理 + 输入质量”联合先验 | 相机为 FLIR BFS-U3-51S5P / Sony IMX250MZR DoFP；公开方向图为作者/SDK 去马赛克后的 8-bit PNG；数字来自 `e0_e2_shdocs_easyocr_scale4.json`、`e0_e2_shdocs_tesseract_scale4.json`、`offline_extension_controls.json` 与 `shdocs_e2_string_length_audit_v1.json`；C1 未训练36路 Selector，只比较固定策略、候选数量与 GT Oracle 上界 |
| 7 | “数据来源—物理处理—共享编码器—证据 Gate”技术闭环：PolaRGB 源任务，合成/PDD/SHDocs 审计，UPLight/ZJU 冻结迁移候选，`S₀/Q/U/q` 与匹配对照，以及 G1–G3 最小主张 | `polargb_release_v1.json`、`polargb_scene_split_v1.json`、`15_shared_polarization_encoder_pretraining_controls.md` A5、§6、§10；UPLight/ZJU 许可与 split 待核查；该页为预注册方案，没有训练或迁移结果 |
| 8 | `S₀/Q/U` 解析 stem、`q_meas/q_pol`、共享编码器与重投影/等变/重组/稳定约束 | `15_shared_polarization_encoder_pretraining_controls.md` §10.2–10.3；`05_polarization_camera_physical_models.md` |
| 9 | PolaRGB 源任务、扰动稳定和 UPLight/ZJU 冻结迁移三阶段实验矩阵 | `polargb_scene_split_v1.json`；`15_shared_polarization_encoder_pretraining_controls.md` §6、§10.4–10.5；UPLight/ZJU 许可与 split 仍待执行前核查 |
| 10 | 路线 1 代理结果、拟议编码器契约与当前未训练状态总结 | 第 5–9 页上述证据与协议；“0 个已训练共享编码器”是当前项目状态，不是性能结果 |

`14-sim-ambiguity.png` 与 `14-sim-reflection.png` 复制自
`polar_representation/evidence/images/`，为本项目基于解析灰度 Stokes 层生成的仿真热图，
不是实拍、光线追踪结果或未来相机性能预测。

SHDocs 平面文档只用于第 6 页说明候选选择与噪声混杂，不作为共享编码器或工业喷码有效性证据。
第 7–9 页全部以 `PRE-REGISTERED / PLAN / NO RESULT` 标注；HAMMER/PPFT 仅作为历史测量与可靠性
资产，不在本版主结果页报告精度。

P0 当前通过的是远端 release/split 冻结；完整 processed 数据仍在仓库外下载，本地全量
size/SHA-256/PNG decode 尚未完成。P1 仅是 release test probe，fixed angle 与 color affine
尚未在 fit 场景冻结。P2 是 processed 诊断，不是 RAW 响应标定；P3 是 96×96 灰度解析层仿真，
只说明条件性趋势和失败边界。它们为后续 Gate 提供背景，但当前 10 页主稿不把它们展开成训练结论。
