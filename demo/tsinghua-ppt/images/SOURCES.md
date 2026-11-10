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

## 本项目原创示意图

`11-polar-a.svg`、`11-polar-b.svg`、`11-stokes.svg`、`11-quality.svg`、`11-adaptive.svg`、`11-ocr.svg` 为本项目根据研究方案绘制的数据结构示意，不代表已采集的偏振图或实验结果。

第 2 页的工业反光、去雾、车牌、半反射层、水下增强场景图标，以及 DoFP、Fresnel 和微表面
BRDF 图均为 HTML/CSS/无文字 SVG 的本项目原创机制示意，不是相机照片、光线追踪结果或定量实验。

## 本项目实验数字与结果图

当前 PPT 为 18 页共享偏振表示研究更新版。所有新主线数字均来自公开数据或解析仿真，不是自有相机结果。

| 页码 | 内容 | 冻结来源 |
|---|---|---|
| 2 | 五类 RGB 失效场景、彩色偏振相机、Stokes、Fresnel、microfacet BRDF 与 T/R 欠定 | LUCID Phoenix PHX050S-QC 产品资料、Sony IMX250MYR / Polarsens 资料、`05_polarization_camera_physical_models.md`、Born & Wolf *Principles of Optics*、Cook–Torrance / Walter 等 microfacet 模型、Schechner / ReflectNet 的半反射层模型；所有图为机制示意，4×4 单元非芯片实际相位图 |
| 3 | Farid–Schechner–Kong 的传统偏振 T/R 分离演进、共同边界及对学习先验的启发 | 上述三张论文图节选；Farid & Adelson, JOSA A 1999；Schechner et al., ICCV 1999 / JOSA A 2000；Kong et al., TPAMI 2014；方法口径同步见 `polar_representation/LITERATURE.md` |
| 4 | ReflectNet、Lei 2020、Multi-bounce 与 Deng 2026 的偏振/强度恢复层级及采集方案 | 上述三张论文架构图；对应 ECCV 2018、CVPR 2020、ECCV 2020 原文；Deng et al. 2026 仅使用出版元数据与已核实方向，具体输入、监督和采集字段按“待全文核查”处理；完整审计见 `polar_representation/LITERATURE.md` |
| 5 | 物理 stem、共享编码器、负对照与 Gate A0 | `15_shared_polarization_encoder_pretraining_controls.md` 第 10 节 |
| 6 | PolaRGB 与 P0–P3 工作量 | `polar_representation/evidence/polargb_release_v1.json`、`p0_p3_evidence_index_v1.json`、`polar_representation/RESULTS.md` |
| 7 | 前期代理 E0：900 张清晰合成字符 | `industrial_reading/evidence/e0_clean_code_sanity.json` |
| 8 | 前期代理 E1：合成仪器恢复与 PDD | `e1_synthetic_instrument_recovery.json`、`e1_pdd_simple_baselines.json` |
| 9 | 前期代理 E2：SHDocs 双 OCR 后端 | `e0_e2_shdocs_easyocr_scale4.json`、`e0_e2_shdocs_tesseract_scale4.json` |
| 10 | 密集固定角、强度匹配与噪声零对照 | `industrial_reading/evidence/offline_extension_controls.json` |
| 11 | P0：PolaRGB revision、manifest 与 59/8 release 口径 | `polargb_release_v1.json`、`polargb_scene_split_v1.json` |
| 12 | P1 test-only 无学习基线 | `polargb_test_probe_v1.json`；GT affine 和 per-sample angle 明确标为 ceiling |
| 13 | P2 processed test 偏振一致性与饱和 | `polargb_test_physics_audit_v1.json`、`polargb_test_gt_physics_audit_v1.json` |
| 14 | P3 Fresnel、透射偏振失败区与 MPFA 反例 | `p3_forward_simulation_v1.json`；`14-sim-ambiguity.png` 为本项目解析仿真图 |
| 15 | 冻结编码器跨任务验证矩阵 | `15_shared_polarization_encoder_pretraining_controls.md` 第 10 节 |
| 16 | Gate A0 状态与正式采集前顺序 | `polar_representation/RESULTS.md`；尚未训练和试采的条目明确标注 |
| 17 | 代表参考文献 | `polar_representation/LITERATURE.md` |
| 18 | 总结数字 | 上述 P0–P3 compact evidence |

`14-sim-ambiguity.png` 与 `14-sim-reflection.png` 复制自
`polar_representation/evidence/images/`，为本项目基于解析灰度 Stokes 层生成的仿真热图，
不是实拍、光线追踪结果或未来相机性能预测。

第 7–10 页保留旧工业识读代理实验，只用于说明任务定义、去马赛克和选择效应；SHDocs 平面文档
不作为共享编码器或工业喷码有效性证据。HAMMER/PPFT 仅作为历史测量与可靠性资产，不在本版
主结果页报告精度。

P0 当前通过的是远端 release/split 冻结；完整 processed 数据仍在仓库外下载，本地全量
size/SHA-256/PNG decode 尚未完成。P1 仅是 release test probe，fixed angle 与 color affine
尚未在 fit 场景冻结，因此页面明确写为“P1 final 未完成”。P2 是 processed 诊断，不是 RAW 响应
标定。P3 是 96×96 灰度解析层仿真，只说明条件性趋势和失败边界。
