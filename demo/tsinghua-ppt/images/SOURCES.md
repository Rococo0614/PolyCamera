# PPT 图片来源与许可

以下图片均下载自 Wikimedia Commons，用于本项目学术汇报中的工业场景示意。它们不是本项目实验数据。本文档记录原文件、作者和许可；本地 WebP 仅做尺寸压缩和格式转换。

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

## 本项目原创示意图

`11-polar-a.svg`、`11-polar-b.svg`、`11-stokes.svg`、`11-quality.svg`、`11-adaptive.svg`、`11-ocr.svg` 为本项目根据研究方案绘制的数据结构示意，不代表已采集的偏振图或实验结果。

## 本项目实验数字与结果图

当前 PPT 为 12 页结果导向版本，各页数字来源如下：

| 页码 | 内容 | 冻结来源 |
|---|---|---|
| 2 | 方向调整与前期工作：时间线、深度线复现与审计数字、H1–H5 状态 | `depth_research/evidence/ppft_hammer_test_reproduction.json`（官方 test 946 帧：RMSE 28.63 mm、论文值、最大差）、`ppft_hammer_full_evaluation.json`（`raw_audit.frames` 7,207、`raw_audit.sensor_frame_rows` 21,621、`dolp.mean_auroc` 0.641）；H1–H5 状态见 `07_depth_enhancement_execution_plan.md` 当前进度与 `09_execution_log.md`；时间线见 `git log` 与 `09_execution_log.md` 各节标题；其余口径见下 |
| 5 | SHDocs / PDD / HAMMER 工作量与可复现资产 | `shdocs_processed_inventory.json`、`e1_pdd_simple_baselines.json`、`ppft_hammer_full_evaluation.json`、`ppft_hammer_test_reproduction.json` |
| 6 | 900 张清晰合成字符 E0 | `industrial_reading/evidence/e0_clean_code_sanity.json` |
| 7 | 合成仪器恢复与 PDD 120 条件 E1 | `e1_synthetic_instrument_recovery.json`、`e1_pdd_simple_baselines.json` |
| 8 | SHDocs 双 OCR 后端 E2 汇总 | `e0_e2_shdocs_easyocr_scale4.json`、`e0_e2_shdocs_tesseract_scale4.json` |
| 9 | 四方向独占成功样本与全部简单基线 | 同上两份 E2 证据及下述冻结结果图 |
| 10 | Gate 状态与下一轮实验 | `offline_gate_p_status.json` |
| 11 | 设备条件与一年计划（无实验数字） | 无冻结证据；各条目的来源与「口头 / 推断 / 拟定 / 未定」标签见下 |
| 12 | 总结数字 | `offline_gate_p_status.json` 及上述证据文件 |

第 2、5 页未使用 HAMMER 图像。HAMMER/PPFT 数字被明确标注为偏振辅助深度任务的
前期探索与工程工作量，只支撑可靠性方法论和可复现能力，不作为工业 OCR 增益证据。

第 2 页的数字口径不同：7,207 帧、21,621 条记录与 DoLP AUROC 0.641 来自全量
审计；「弱偏振反例」（scene12 平均 DoLP 约 0.071，scene10/13 约 0.14–0.15）来自
更早的 4 帧诊断（3 个几何场景：scene10 第 0 帧、scene12 第 0 帧、scene13 第 0 与
第 120 帧，见 `depth_research/evidence/sample_manifest.csv` 中 `status=downloaded`
的 4 行，以及 `09_execution_log.md` 中从「第一帧原始深度结果」到「第二个测试场景
复核」的各节）。该日志自己写明「不把四帧诊断当作统计论文结果」。转向原因（只有
1 台偏振相机、设备预算上限约 1000 元、深度线自采验证需要受控偏振照明与深度参考）
为本人口述，仓库内没有对应的书面材料；原计划对「无法及时获得设备」的处理见
`07_depth_enhancement_execution_plan.md` 风险表。`depth_research/evidence/hypothesis_status.csv`
仍停留在 2026-10-23 的状态（H1/H5 为「初步支持」），与第 2 页的 H1/H5「全量支持」
不一致时，以 `07`、`09` 为准。

`17-shdocs-four-direction-examples.png` 是本项目从冻结的 SHDocs EasyOCR 测试记录生成
的结果图，原始 artifact 位于仓库外
`/home/chocbrownie0524/poldepth/runs/industrial_reading/shdocs_easyocr_unique_direction_examples.png`，
复制时未修改；SHA-256 为
`7f040a7e65b7183f121e2c11c70d40bbe899128bc4c308fffebda1fe44edf18f`。

第 6–9 页均在页面内或页脚明确标注公开数据/合成数据代理边界：SHDocs 平面文档
结果不作为工业喷码 Gate 1 结果；PDD 重建和合成仪器恢复也不作为未来相机的物理
标定结果。第 8 页的 `all-four-fail` 仅表示四个原始方向均未 exact-read；在未冻结
接受阈值时，不将其命名为系统拒绝率。

第 11 页没有实验数字，条目标签「口头 / 推断 / 拟定 / 未定」为本人标注。相机型号
`PHX050S1-QC` 在仓库里只记录为 HAMMER 所用型号（`depth_research/evidence/product_matrix.csv`），
自有设备为本人口述，设备读数尚未做。「镜头：推断有」的依据是前人论文装置图
（`demo/前人巨作/` 中论文 PDF 第 30 页，图 2.5，近景可见镜头），焦距、接口与可用性均未
核实；预算上限约 1000 元为口述。「普通 LED 为默认、入射偏振片为后备」是本人决定，
`04_hardware_and_data_collection.md` 第 4 节与 `13_industrial_reading_experiment_plan.md`
的 E4 仍按「LED + 可拆入射偏振片」描述，尚未同步。一年计划为本人拟定，月份自设备读数
完成日起算。该页只文字引用前人论文，未复制其中任何图像（该材料著作权归原作者，见
`demo/前人巨作/README.md`）。已用的公开代理数据的读取方式：SHDocs 为 SDK 导出的 8-bit
图并转灰度（`industrial_reading/src/polread/shdocs_rois.py`）；PDD 用逐方向 PNG 取绿色
通道，再由代码合成 MPFA 马赛克（`industrial_reading/src/polread/pdd.py`、
`industrial_reading/scripts/run_pdd_baselines.py`）；二者都不是传感器 RAW（见
`02_datasets_and_prior_work.md`、`09_execution_log.md`）。
