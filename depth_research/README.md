# depth_research

偏振辅助商品级深度传感器增强的可复现实验目录。当前只实现数据审计和固定评测基础，不包含尚未被证据支持的“最终网络”。

## 目录

```text
configs/                 固定研究协议和实验配置
evidence/                文献与产品证据矩阵
evidence/ppft_hammer_test_reproduction.json  官方 946 帧复现摘要与指纹
evidence/ppft_hammer_full_evaluation.json     7,207 帧全量评测摘要与指纹
src/poldepth/            偏振表示、质量图和深度指标
scripts/                 数据审计入口
tools/remote_zip.py      HTTP Range 选择性读取大型 ZIP
tools/inventory_hammer.py  不解压统计完整归档容量
tools/prepare_hammer_selected.py  训练机选择性提取约 62 GiB 所需数据
tools/build_ppft_polar_cache.py   构建约 4.6 GiB 的紧凑偏振 cache
tools/remote_preflight.sh         训练机只读资源/联网预检
tests/                   物理公式和指标单元测试
data/                    数据（忽略，不提交）
results/                 生成结果（忽略，不提交）
program.md               基线稳定后才能启用的自动实验协议
results_template.tsv     实验登记表模板
```

## 当前执行顺序

1. HAMMER 7,207 帧选择集、compact cache、固定 support 和全量 raw audit 已完成；
2. PPFT 官方 Table 2 与 train/val/test 共 21,621 条推理已完成；
3. 下一步运行 CompletionFormer/其他 baseline、输入消融和偏振/深度压力测试；
4. 复现训练 backward 后再执行严格 leave-one-real-sensor-out；
5. 继续联系作者核实偏振四象限的绝对角度；该问题不阻塞 checkpoint 推理，
   但阻塞绝对 AoLP 物理方向结论；
6. Gate 3 通过前不启动方法网络和自动实验。

## 安装分析环境

```bash
python -m venv .venv
.venv/bin/pip install -e ./depth_research
```

## 测试

```bash
.venv/bin/python -m unittest discover -s depth_research/tests -v
```

## 选择性查看 HAMMER 归档

```bash
.venv/bin/python depth_research/tools/remote_zip.py \
  --url https://www.campar.in.tum.de/public_datasets/2022_arxiv_jung/_dataset_processed.zip \
  list --pattern '*scene13*000000*' --limit 100
```

`--pattern` 可以重复传入，从而只解析一次中央目录并同时选择多个帧。

## 训练机数据准备

完整步骤与容量预算见 `../11_compute_and_data_deployment_plan.md`。核心 dry-run 命令：

```bash
.venv/bin/python depth_research/tools/inventory_hammer.py \
  --archive /data/poldepth/archives/hammer.zip \
  --output depth_research/results/hammer_inventory_remote.csv

.venv/bin/python depth_research/tools/prepare_hammer_selected.py \
  --archive /data/poldepth/archives/hammer.zip \
  --output /data/poldepth/datasets/hammer_selected \
  --manifest /data/poldepth/manifests/hammer_selected.csv \
  --dry-run
```

确认 dry-run 后去掉 `--dry-run`。随后构建紧凑 cache：

```bash
.venv/bin/python depth_research/tools/build_ppft_polar_cache.py \
  --data-root /data/poldepth/datasets/hammer_selected \
  --output-root /data/poldepth/cache/polar_float32_ds4 \
  --downsample 4 --dtype float32 --grayscale opencv --workers 8
```

公开 PPFT loader 必须相应设置为不再二次 `[::4]`。
该 cache 保留相同空间采样，但会在 AoLP 周期编码前把 `[I, rho, phi]` 量化为
float32；这是约 4.6 GiB 存储方案的显式取舍。论文数值交叉验证应另跑少量 raw
路径，确认这种浮点舍入不改变结论。

下载前先用 `list` 确认真实归档路径；完整文件约 159 GiB，禁止在当前根分区直接整包下载。

## 样本审计

样本文件准备好后：

```bash
.venv/bin/python depth_research/scripts/analyze_sample.py \
  --gt path/to/_gt/000000.png \
  --depth d435=path/to/depth_d435/000000.png \
  --depth l515=path/to/depth_l515/000000.png \
  --depth itof=path/to/depth_tof/000000.png \
  --polar path/to/pol/000000.png \
  --label path/to/_instance/000000.png \
  --output depth_research/results/sample_audit/000000.json
```

`--polar-order` 必须在角度定义核实后填写；默认值只是常见四象限假设，不作为物理真值。

生成单帧审计图：

```bash
.venv/bin/python depth_research/scripts/visualize_sample.py \
  --rgb path/to/rgb/000000.png \
  --gt path/to/_gt/000000.png \
  --depth d435=path/to/depth_d435/000000.png \
  --depth l515=path/to/depth_l515/000000.png \
  --depth itof=path/to/depth_tof/000000.png \
  --polar path/to/pol/000000.png \
  --label path/to/_instance/000000.png \
  --output depth_research/results/sample_audit/000000_overview.png
```

批量汇总少量样本：

```bash
.venv/bin/python depth_research/scripts/batch_audit.py \
  --root depth_research/data/hammer_sample \
  --output depth_research/results/batch_audit
```

输出包括逐帧、逐标签、深度边界、FoV/support、DoLP 分箱、silent-error 检测和偏振质量 CSV。相邻视频帧不应被当作独立样本计算统计显著性。

完整选择集可先从跨帧观测频率建立固定 support mask，再传给批量审计，避免
把 I-ToF 的视场外区域计作随机空洞：

```bash
.venv/bin/python depth_research/scripts/build_support_masks.py \
  --root /data/poldepth/datasets/hammer_selected \
  --output /data/poldepth/cache/support_masks

.venv/bin/python depth_research/scripts/run_batch_audit_sharded.py \
  --root /data/poldepth/datasets/hammer_selected \
  --data-manifest /data/poldepth/manifests/hammer_selected.csv \
  --support-root /data/poldepth/cache/support_masks \
  --output depth_research/results/full_raw_audit \
  --workers 24
```

默认 support 要求一个像素在至少 1% 帧中有正深度；输出同时记录跨帧 union
和阈值化 support 的比例及外接框。它仍是数据驱动近似，最终实物实验应优先
使用标定/warp 的精确有效域。

分片入口按 trajectory 原子落盘并可续传，最后合并 CSV。silent-error 的多个误差
阈值共享一次 score 排序；四帧回归测试与旧实现的全部 CSV 逐字节一致。7,207
帧、32 trajectory、24 workers 实测约 62 分钟。

核查 label ID 对应的物体/材质：

```bash
.venv/bin/python depth_research/scripts/visualize_labels.py \
  --rgb path/to/rgb/000000.png \
  --label path/to/_instance/000000.png \
  --output depth_research/results/sample_audit/000000_labels.png
```

## 自动实验

`program.md` 借鉴 `karpathy/autoresearch` 的“冻结评测—单变量实验—保留/丢弃—完整记录”思想，但增加了多指标约束、真实传感器留出、测试集保护和 GPU 预算。当前尚未达到启用条件，不能让代理直接循环改网络。

## 现代 PyTorch 上的 PPFT 单帧推理

`scripts/run_ppft_sample.py` 保留作者模型与 checkpoint，使用
`torchvision.ops.deform_conv2d` 替代旧 CUDA DCN 的推理前向，并绕过仅用于
初始化的旧 PVT/ResNet 权重。checkpoint 以 `strict=True` 加载；任何参数缺失
都会停止，而不是静默忽略。该兼容路径当前只声明支持推理，不声明已复现
Apex/DDP 训练。

```bash
PYTHONPATH=depth_research/src python depth_research/scripts/run_ppft_sample.py \
  --upstream-root /path/to/Polarization-Prompt-Fusion-Tuning \
  --checkpoint /path/to/ppft_fin.pt \
  --rgb /path/to/rgb/000000.png \
  --polar /path/to/pol/000000.png \
  --view-directions /path/to/PPFT/utils/vd.npy \
  --gt /path/to/_gt/000000.png \
  --label /path/to/_instance/000000.png \
  --depth d435=/path/to/depth_d435/000000.png \
  --depth l515=/path/to/depth_l515/000000.png \
  --depth itof=/path/to/depth_tof/000000.png \
  --output-dir depth_research/results/ppft_smoke/scene13_000000
```

脚本显式复现作者 loader 的 BGR/归一化行为、四象限假设和 4 倍下采样，
并记录 checkpoint SHA-256、环境、耗时、峰值显存、raw/PPFT 全图及材质切片
指标。torchvision DCN 路径已用官方 946 帧结果完成论文汇总值交叉验证；这只
证明当前 checkpoint/test 路径的结果级兼容，不宣称新旧 DCN 对任意输入逐算子
或逐 bit 等价。

官方 946 帧 test split 使用模型只加载一次的可续传入口；固定 batch=1，且每个
frame-sensor 结果先以临时文件写入、再原子改名，机器重启后重复同一命令即可
跳过已完成记录：

```bash
PYTHONPATH=depth_research/src python depth_research/scripts/run_ppft_split.py \
  --upstream-root /path/to/Polarization-Prompt-Fusion-Tuning \
  --checkpoint /path/to/ppft_fin.pt \
  --data-root /data/poldepth/datasets/hammer_selected \
  --data-manifest /data/poldepth/manifests/hammer_selected.csv \
  --split-file /path/to/PPFT/data_paths/hammer_test.txt \
  --view-directions /path/to/PPFT/utils/vd.npy \
  --output-dir depth_research/results/ppft_test_fp32 \
  --amp none
```

最终 `report.json` 按作者代码对每帧指标做算术平均，并逐项对照论文 Table 2；
同时保留本项目 coverage-aware 全图、材质和边界切片。可先加 `--limit 4` 做
冒烟测试，默认不保存约 0.6 GiB 的逐帧预测；需要时使用
`--save-predictions`。

使用 compact cache 做全 split 评测时增加：

```bash
  --polar-cache-root /data/poldepth/cache/polar_float32_ds4 \
  --polar-cache-manifest /data/poldepth/manifests/polar_float32_ds4.sha256
```

run config 同时固化 runner、共享预处理、兼容层、指标模块、数据清单和 cache
清单的 SHA-256；配置变化时拒绝混用已有原子记录。

官方 raw float64 预处理结果（946 帧、2,838 条 sensor-frame）为：D435
`24.78884/10.65956`、L515 `23.84283/10.46670`、I-ToF
`37.27167/21.37325`、All `28.63444/14.16650`（RMSE/MAE，mm）；与论文各项
绝对差不超过 `0.0089/0.0035 mm`。需要使用紧凑 cache 时增加
`--polar-cache-root`；完整 test split 上 cache 相对 raw 的 All mean RMSE 差仅
`0.0000143 mm`，但主复现数字仍应引用 raw 路径。

作者 checkpoint 在当前 PyTorch 2.11/torchvision DCN 路径下对**全模型 FP16
autocast 会产生 NaN**，因此默认和论文交叉验证均使用 FP32；实测单帧峰值约
541 MiB，16 GB 显卡没有显存压力。`--amp fp16` 仅保留作诊断选项，并会在
首个非有限输出处停止，不能把其结果用于评测。
