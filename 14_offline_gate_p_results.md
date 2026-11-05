# 工业偏振识读 Offline Gate P：公开数据前置实验结果

**版本：** v0.1  
**日期：** 2026-11-03  
**状态：** 公开数据代理完成第一轮；正式工业 Gate 1 仍关闭

## 1. 结论摘要

当前证据同时支持两个判断：

1. **四方向确实存在可重复的 OCR 互补性。** 在 SHDocs `a–o` 高光条件中，
   per-image four-angle oracle 相对训练集最佳固定方向的增量，在 EasyOCR 和
   Tesseract 两个后端上均为正，且文档聚类置信区间不跨 0；
2. **现在还不能进入学习式自适应方法。** SHDocs camera 条件的绝对 OCR 上限仍低，
   简单 OCR-confidence 选择器只兑现少量 oracle 空间，而且尚未完成连续固定虚拟角
   强基线。

因此 Offline Gate P 总状态为 **open**：候选问题得到支持，但部署方法和正式工业
有效性均未成立。

## 2. 数据与可复现边界

### SHDocs

- processed archive：`1,715,393,730` bytes；
- SHA-256：`49457a4afae50fc750328399af708c12570a08c613b1ccfe7f552c6f8acb05c7`；
- 全 ZIP CRC 通过；50 文档、800 captures、4,800 图像；
- 每个 capture 包含 `i0/i45/i90/i135/s0_norm/deglared`；
- 2,270 个唯一文本区域，跨 16 条件共 36,320 ROI；
- 17 个轻微越界 ROI-condition 使用冻结清单排除；
- 文档级 split：train/val/test = `35/8/7`。

名为 `raw_captures` 的归档也已通过长度、SHA-256 和 CRC，但内容仍是六种重建
PNG，不是传感器 mosaic、暗场或平场。

### PDD 2025

- archive：`12,171,672,476` bytes；全 CRC 通过；
- SHA-256：`01f20ebc8b3b8940f1460ebafb981eb0942bcbb5cc4b5af7bf3ab27b46e98008`；
- 40 场景 × 3 噪声等级；首轮使用 960 个 PNG，不重复提取 MAT。

## 3. E0：OCR 上限首先取决于字符体系

使用 100 个唯一字符串、3 种开放等宽字体和 24/32/48 px 三档字号，生成 900 张
无反光清晰图。只使用字符 allowlist，不做字典或 OCV 纠错：

| Backend | Overall exact | EXP 日期格式 | LOT | BATCH | 随机 SN | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
| EasyOCR 1.7.2 | 60.78% | 95.11% | 57.78% | 54.22% | 36.00% | 3.43 ms |
| Tesseract 5.5.3 | 79.44% | **99.56%** | 80.00% | 74.22% | 64.00% | 38.01 ms |

结论不是“Tesseract 已解决工业 OCR”，而是：固定日期格式的软件上限可用，任意
字母数字序列仍不可用。正式 E0 前必须选择一种喷码工艺、字符集和格式。

SHDocs camera 条件包含混合印刷/手写表单字段，4× 预处理后的 train-best exact
分别只有 EasyOCR `13.04%`、Tesseract `33.33%`，不能作为工业清晰上限通过值。

## 4. E1：去马赛克不是中性预处理

PDD 的绿色通道 MPFA 简单基线：

| Noise | Nearest AoLP MAE | Bilinear AoLP MAE | Bilinear DoLP MAE |
|---|---:|---:|---:|
| Low | 25.26° | 15.14° | 0.0187 |
| Mid | 29.77° | 21.24° | 0.0424 |
| High | 31.81° | 23.69° | 0.0564 |

双线性明显优于最近邻，但在低噪声下仍有约 15° 的 AoLP 误差。后续细字符 OCR
必须把超像素/去马赛克方法作为显式消融，不能把 SDK 输出当作无误差事实。

## 5. E2：四方向互补性跨 OCR 后端重复

预处理倍率只由 camera validation 选择，两个后端均冻结为 `4× bicubic`。测试仅
用于一次最终汇总：

| Backend | Test ROI | Train-best fixed | Fixed exact | Oracle exact | Gap | Cluster 95% CI |
|---|---:|---|---:|---:|---:|---:|
| EasyOCR | 1,034 | I0 | 11.32% | 13.83% | **+2.51 pp** | +1.50–+3.52 pp |
| Tesseract | 1,034 | I0 | 26.31% | 32.88% | **+6.58 pp** | +4.13–+8.86 pp |

在 question/header 印刷字段子集中：

| Backend | Fixed exact | Oracle exact | Gap | Cluster 95% CI |
|---|---:|---:|---:|---:|
| EasyOCR | 14.51% | 17.42% | +2.90 pp | +1.43–+4.41 pp |
| Tesseract | 31.49% | 38.61% | +7.11 pp | +3.90–+10.83 pp |

两个后端中，I0/I45/I90/I135 都出现“仅该方向读对”的样本，因此增量并非只来自
一个全局固定方向。但简单方法仍不足：

- EasyOCR confidence selector：`11.03%`，低于 fixed I0 `11.32%`；
- Tesseract confidence selector：`27.56%`，只比 fixed I0 高 `1.26 pp`，远低于
  oracle `32.88%`；
- SDK `deglared`、min、median 和 `S0` 均未消除 oracle gap；
- Tesseract 四方向全部失败率仍为 `67.12%`，EasyOCR 为 `86.17%`。

## 6. Gate 判定

| Gate | 状态 | 判定 |
|---|---|---|
| P0 OCR 软件上限 | 条件性通过 | 固定日期格式可用；任意序列号和真实喷码未通过 |
| P1 测量/重建软件链 | 通过（代理） | 合成标定、PDD 与 SHDocs 一致性链可运行 |
| P2 固定方向必要性 | 机制支持，部署未通过 | 双后端 oracle gap 成立，但选择器与 E0 不足 |
| 正式工业 Gate 1 | 关闭 | 无自采工业喷码、光学强基线、动态与实物标定 |

## 7. 下一步

1. 优先将主任务收窄为固定格式日期/批次码，或另行准备专用序列号 OCR；
2. 在同一冻结子集补充密集固定虚拟角基线，避免只与四个离散方向比较；
3. 在不训练生成网络的前提下分析 oracle-only 案例，建立可解释的角度选择特征；
4. 获得硬件后重新执行真实 E0/E1/E2，包括固定交叉偏振和曝光公平协议；
5. 在正式 E0 和 Gate 1 前，不训练最终自适应融合网络。

HAMMER/PPFT 结果继续作为偏振可靠性、工程工作量与反例方法论的前期探索，已在
12 页结果导向开题 PPT 的工作量页单独标注；不与上述 OCR 数字混报。
