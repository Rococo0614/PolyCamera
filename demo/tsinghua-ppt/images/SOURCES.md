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

当前 PPT 为 10 页结果导向版本，各页数字来源如下：

| 页码 | 内容 | 冻结来源 |
|---|---|---|
| 4 | SHDocs / PDD / HAMMER 工作量与可复现资产 | `shdocs_processed_inventory.json`、`e1_pdd_simple_baselines.json`、`ppft_hammer_full_evaluation.json`、`ppft_hammer_test_reproduction.json` |
| 5 | 900 张清晰合成字符 E0 | `industrial_reading/evidence/e0_clean_code_sanity.json` |
| 6 | 合成仪器恢复与 PDD 120 条件 E1 | `e1_synthetic_instrument_recovery.json`、`e1_pdd_simple_baselines.json` |
| 7 | SHDocs 双 OCR 后端 E2 汇总 | `e0_e2_shdocs_easyocr_scale4.json`、`e0_e2_shdocs_tesseract_scale4.json` |
| 8 | 四方向独占成功样本与全部简单基线 | 同上两份 E2 证据及下述冻结结果图 |
| 9–10 | Gate 状态与总结数字 | `offline_gate_p_status.json` 及上述证据文件 |

第 4 页未使用 HAMMER 图像。HAMMER/PPFT 数字被明确标注为偏振辅助深度任务的
前期探索与工程工作量，只支撑可靠性方法论和可复现能力，不作为工业 OCR 增益证据。

`17-shdocs-four-direction-examples.png` 是本项目从冻结的 SHDocs EasyOCR 测试记录生成
的结果图，原始 artifact 位于仓库外
`/home/chocbrownie0524/poldepth/runs/industrial_reading/shdocs_easyocr_unique_direction_examples.png`，
复制时未修改；SHA-256 为
`7f040a7e65b7183f121e2c11c70d40bbe899128bc4c308fffebda1fe44edf18f`。

第 5–8 页均在页面内或页脚明确标注公开数据/合成数据代理边界：SHDocs 平面文档
结果不作为工业喷码 Gate 1 结果；PDD 重建和合成仪器恢复也不作为未来相机的物理
标定结果。第 7 页的 `all-four-fail` 仅表示四个原始方向均未 exact-read；在未冻结
接受阈值时，不将其命名为系统拒绝率。
