# industrial_reading

变化反射条件下工业标识可靠识读的离线前置实验目录。当前阶段只运行公开数据
代理实验，不把公开文档结果表述为工业喷码实物结论。

## 当前结果（2026-11-09 更新；其余条目为 2026-11-03 首轮）

- 2026-11-09 增补三项不需要硬件的对照（密集固定虚拟角、强度匹配、噪声零对照），详见
  `14_offline_gate_p_results.md` 第 8 节与 `evidence/offline_extension_controls.json`：
  连续固定角没有优于 raw I0；强度匹配没有消除 oracle gap；**同内容噪声零对照复现了 gap 的
  相当大一部分**，因此 oracle gap 不能单独作为偏振互补内容的证据，P2 改为"未成立也未被否定"；
- 14 项单元测试通过（首轮；增补后的总数见 `09_execution_log.md` 2026-11-09 条目）；
- EasyOCR 1.7.2 与 Tesseract 5.5.3 两个独立后端已完成执行冒烟；
- E1 合成仿射仪器矩阵恢复将 Stokes RMSE 从 `0.01147` 降至 `0.00260`；
- PDD 40 场景 × 3 噪声级首轮简单基线完成：双线性 MPFA 的 AoLP MAE 为
  `15.14° / 21.24° / 23.69°`（低/中/高噪声）；
- SHDocs processed 50 文档/800 captures 已通过 SHA-256、全 CRC 与偏振一致性审计；
  平均 pair residual `0.02361`、平均 DoLP `0.03387`；
- 清晰合成 E0 中，Tesseract 对固定 `EXP YYYY-MM-DD` 达到 `99.56%` exact，
  但随机字母数字 `SN` 仅 `64%`，证明主字符集/格式是硬件前置决策；
- SHDocs EasyOCR 4× 代理中，a–o 测试的 train-best fixed 为 `11.32%`，四方向
  oracle 为 `13.83%`，差 `+2.51 pp`（文档聚类 95% CI `+1.50–+3.52 pp`）；
  Tesseract 对应为 `26.31% → 32.88%`，差 `+6.58 pp`（CI
  `+4.13–+8.86 pp`）；
- oracle gap 已跨后端重复，但 E0 和 deployable selector 仍不足，且噪声零对照复现了其中
  一大部分；Offline Gate P 保持 open；
- 这些数字只验证公开数据代理链和预处理敏感性，不是自有相机标定结果。

## 当前目标

```text
Offline E0  OCR 后端、字符串规范化与 exact/CER/WER 评测
Offline E1  Stokes/虚拟角、仪器矩阵和公开去马赛克基准
Offline E2  SHDocs 四固定方向、train-best、简单融合与 oracle
```

正式 Gate 1 仍需自采工业喷码、材质、姿态、光照和固定交叉偏振数据。

## 推荐公开数据

| 数据 | 用途 | 不能证明 |
|---|---|---|
| SHDocs | E0/E2；同曝光四方向、`S0`、SDK deglared 与 OCR 标注 | 工业喷码、曲面、动态节拍 |
| PDD 2025 | E1；noisy mosaic 与 noise-free 四方向 GT | 未来相机的真实标定参数 |
| PIDSR | E1；偏振去马赛克/超分强基线 | 工业识读收益 |
| HAMMER | 已完成的偏振质量与任务可靠性探索 | 工业 OCR 增益 |

大数据放在仓库外：

```text
/home/chocbrownie0524/poldepth/datasets/industrial_reading/
/home/chocbrownie0524/poldepth/runs/industrial_reading/
```

## 安装与测试

```bash
/home/chocbrownie0524/miniconda3/envs/depthbench/bin/python -m pip install -e ./industrial_reading
/home/chocbrownie0524/miniconda3/envs/depthbench/bin/python -m unittest discover -s industrial_reading/tests -v
```

## 不依赖数据的 E1 冒烟实验

```bash
/home/chocbrownie0524/miniconda3/envs/depthbench/bin/python \
  industrial_reading/scripts/run_e1_synthetic.py \
  --output /home/chocbrownie0524/poldepth/runs/industrial_reading/e1_synthetic.json
```

## E0 清晰代码软件 sanity set

```bash
python industrial_reading/scripts/generate_clean_code_set.py \
  --output-root /home/chocbrownie0524/poldepth/datasets/industrial_reading/synthetic_clean_codes

python industrial_reading/scripts/run_clean_code_ocr.py \
  --manifest /home/chocbrownie0524/poldepth/datasets/industrial_reading/synthetic_clean_codes/manifest.csv \
  --backend tesseract \
  --allowlist 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- ' \
  --output /home/chocbrownie0524/poldepth/runs/industrial_reading/clean_codes_tesseract_allowlist.jsonl
```

该集合只检查 OCR 软件和字符体系，不替代真实镜头、相机、喷码字体与工作距离下的
正式 E0。

PDD PNG 子集到齐后运行公开重建代理：

```bash
/home/chocbrownie0524/poldepth/envs/industrial-reading/bin/python \
  industrial_reading/scripts/run_pdd_baselines.py \
  --root /home/chocbrownie0524/poldepth/datasets/industrial_reading/pdd_2025/DatasetPDD/ImagePNG \
  --archive-sha256 01f20ebc8b3b8940f1460ebafb981eb0942bcbb5cc4b5af7bf3ab27b46e98008 \
  --output /home/chocbrownie0524/poldepth/runs/industrial_reading/pdd_simple_baselines.json
```

## SHDocs 到齐后的顺序

```bash
# 1. 只读 inventory，不修改源数据
python industrial_reading/scripts/inventory_shdocs.py \
  --root /path/to/shdocs \
  --output /path/to/shdocs_manifest.csv

# 2. OCR 推理结果统一写成 JSONL
# 3. 从 JSONL 计算逐方法指标、train-best、oracle 和配对区间
python industrial_reading/scripts/summarize_ocr_records.py \
  --records /path/to/ocr_records.jsonl \
  --conditions a,b,c,d,e,f,g,h,i,j,k,l,m,n,o \
  --output /path/to/e2_summary.json
```

`camera` 清晰条件和 `a–o` 高光条件必须分开汇总；E2 的 train-best 和 oracle 不得
混入 `camera` 条件。

首轮 GT-ROI EasyOCR 冒烟建议只取少量文档，确认目录、方向图与标注对齐后再放大：

```bash
/home/chocbrownie0524/poldepth/envs/industrial-reading/bin/python \
  industrial_reading/scripts/run_shdocs_ocr.py \
  --images-root /path/to/processed_captures/testing_data/images \
  --annotations-root /path/to/processed_captures/testing_data/annotations \
  --output /home/chocbrownie0524/poldepth/runs/industrial_reading/shdocs_easyocr.jsonl \
  --backend easyocr \
  --methods i0,i45,i90,i135,s0_norm,deglared \
  --limit-documents 3 \
  --limit-regions-per-document 2
```

第二后端使用固定的 Tesseract 5.5.3，本地二进制与语言包位于
`/home/chocbrownie0524/poldepth/tools/`；输出使用独立 JSONL，禁止与 EasyOCR
记录混合后再按方法直接平均。

所有正式结果必须记录数据清单、split、OCR 版本、归一化规则、代码 commit 和配置
哈希。相同文档的不同高光条件不得跨 split。

## 补充对照：密集固定角、强度匹配、噪声零对照

这些实验在"计算视图"上运行 OCR：每个视图由同一 ROI 的四个 SDK 通道裁剪计算
（`polread.views`），并沿用首轮的 split、ROI 抽样、排除清单与 `4× bicubic`。

| 模块 / 脚本 | 作用 |
|---|---|
| `polread.views` | 原始、虚拟角 `virtual_<deg>`、直方图/均值方差匹配 `hm_*`/`ms_*`、噪声零对照 `null_<mean\|i0>_m<m>_k<k>` |
| `polread.noise` | PDD 噪声标定（`var = a·x + b`）与 SHDocs 盲估计 |
| `polread.protocol` | 冻结 split、每文档 ROI 抽样、排除清单、分片 |
| `polread.headroom` | 成功矩阵、train-best、oracle、文档聚类 bootstrap |
| `polread.analysis` | 每样本增益（固定/可交换/干净基线）、配对对比、剂量锚点 |
| `scripts/run_shdocs_views_ocr.py` | 可分片、可断点续跑的 GT-ROI OCR |
| `scripts/measure_view_differences.py` | 视图间像素 RMS，用来**在看 OCR 结果前**锚定噪声剂量 |
| `scripts/summarize_dense_sweep.py`, `analyze_dense_decomposition.py` | 密集扫角、间距对照、逐条件最优角 |
| `scripts/summarize_e3_matching.py` | 强度匹配 vs raw 的 gap 变化 |
| `scripts/summarize_noise_null.py` | 噪声零对照与真实 gap 的配对对比 |
| `scripts/build_extension_evidence.py` | 汇总为 `evidence/offline_extension_controls.json`（含各 JSONL/源码 SHA-256） |

最小复现（路径按本机 `/mnt/ssd/polycamera_offline` 布局，大数据不入库）：

```bash
python industrial_reading/scripts/run_shdocs_views_ocr.py \
  --images-root .../testing_data/images --annotations-root .../testing_data/annotations \
  --backend tesseract --views hm_i0,hm_i45,hm_i90,hm_i135,ms_i0,ms_i45,ms_i90,ms_i135 \
  --conditions a,b,c,d,e,f,g,h,i,j,k,l,m,n,o --shard-index 0 --shards 8 --output e3_tess_shard0.jsonl \
  --tesseract-executable .../tesseract --tessdata-directory .../tessdata
python industrial_reading/scripts/summarize_e3_matching.py --raw 'raw4_shard*.jsonl' \
  --matched 'e3_tess_shard*.jsonl' --backend-label 'Tesseract 5.5.3 PSM7, 4x bicubic' --output e3.json
```

噪声零对照需要 `--noise-model-json`（PDD-High 标定结果）；`summarize_noise_null.py` 默认只评测
测试集（`--eval-split test`），`--eval-split all` 合并 50 篇文档，仅用作稳健性检查（固定方法
仍只在 train 上选，因此对 train 文档偏乐观）。OCR 引擎崩溃（`status != ok`）默认计为读错
（`--error-policy fail`），`drop` 为丢弃含崩溃样本的敏感性分析。

**解读边界：** 噪声零对照是注入的 iid 高斯噪声，不是真实重复曝光；它只能界定同量级扰动能制造
多少"挑最优"增益。剂量按像素距离锚定，而不是按传感器噪声。
