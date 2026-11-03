# industrial_reading

变化反射条件下工业标识可靠识读的离线前置实验目录。当前阶段只运行公开数据
代理实验，不把公开文档结果表述为工业喷码实物结论。

## 当前结果（2026-11-03）

- 14 项单元测试通过；
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
- 互补机制已跨后端重复，但 E0、连续固定角和 deployable selector 仍不足，
  Offline Gate P 保持 open；
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
