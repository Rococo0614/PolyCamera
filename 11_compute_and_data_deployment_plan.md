# 双机器计算与数据部署方案

**更新日期：** 2026-10-26

## 1. 结论

当前机器应作为**控制端、开发端和结果分析端**；另一台 RTX 5080 + 约 1 TB 存储机器应作为**数据端和训练端**。

不建议在当前机器继续下载数据、安装完整 PyTorch/CUDA 依赖或训练模型。当前真正不足的是磁盘，不是系统内存。

## 2. 当前机器实测资源

| 资源 | 实测 | 判断 |
|---|---:|---|
| CPU | Intel Core Ultra 9 285K，24 个在线逻辑 CPU | 文献处理、代码、统计和图片生成充足 |
| RAM | 125 GiB，总可用约 68 GiB | 充足，但 swap 已使用约 9.2/9 GiB，说明机器上有其他负载 |
| GPU | RTX 5090 D，24,455 MiB | 性能强，但检查时已有约 10.7 GiB 占用，只剩约 13 GiB，属于共享资源 |
| 驱动 | 595.58.03 | 很新，旧 PyTorch 1.x/CUDA 11 环境不宜直接安装 |
| 根盘 | 249 GiB，总剩余约 6.6 GiB，使用率 98% | 已低于项目 10 GiB 安全线，禁止新增重依赖和数据 |
| 当前项目 | 约 669 MiB | 本项目不是磁盘占满的主要来源，不删除其他未知文件 |

### 当前机器继续承担

- 文献、产品、课题方案和开题材料；
- 纯 Python/NumPy 数据处理代码与单元测试；
- 4--12 帧选择性样本审计（当前已完成 4 帧，暂停继续下载）；
- PPFT/Depth Prompting 的静态迁移设计；
- 接收远端的小型 CSV、日志、配置和可视化并分析；
- Git 代码管理和实验审查。

### 当前机器停止承担

- HAMMER 全量下载或继续扩展缓存；
- PyTorch、mmcv、Apex、DCN 等大型环境安装；
- 全数据预处理；
- baseline 训练、leave-one-sensor-out 和自动实验；
- 大 checkpoint 长期保存。

## 3. HAMMER 精确存储核算

完整清单见 `depth_research/evidence/hammer_storage_inventory.csv`。

| 内容 | 文件数 | 未压缩 | ZIP 内压缩 |
|---|---:|---:|---:|
| 完整 HAMMER | 432,596 | 171.07 GiB | 158.66 GiB |
| 全部 polarization 坐标数据 | 115,433 | 122.68 GiB | 118.54 GiB |
| 非 naked、项目实际需要的 polarization 数据 | 57,689 | **62.00 GiB** | 59.99 GiB |
| 其中 pol 四角图 | 7,207 | 44.69 GiB | 44.71 GiB |
| RGB | 7,207 | 9.24 GiB | 9.24 GiB |
| 三种 sensor depth 合计 | 21,622 | 6.08 GiB | 5.25 GiB |
| GT + instance + pose | 21,621 | 2.00 GiB | 0.79 GiB |

### 官方 PPFT 预处理为什么浪费空间

公开脚本把每帧完整分辨率 `I/rho/phi` 保存成 float64 `.npy`，7,207 帧预计约 **145.8 GiB**；训练时又只读取 `[::4, ::4]`。

本项目的 `build_ppft_polar_cache.py` 在逐点计算前等价地下采样，并保存 float32：

| cache | 预计容量 |
|---|---:|
| 官方 full-resolution float64 | 145.8 GiB |
| full-resolution float32 | 72.9 GiB |
| downsample=4 float32（推荐） | **4.56 GiB** |
| downsample=4 float16 | 2.28 GiB，但不优先用于首轮复现 |

当前 4 帧测试已确认推荐 cache 的输出为 `208 x 272 x 3 float32`，每帧约 679 KiB。

## 4. 1 TB 训练机推荐目录与预算

已于 2026-10-26 确认：远端为寝室个人电脑，提供约 1 TB 持久磁盘，可通过 SSH 操作，可以联网并长期后台运行。尚待预检确认实际挂载路径、剩余容量、RAM、驱动和准确显存。

```text
/data/poldepth/
├── archives/
│   └── hammer.zip                 # 159 GiB，可在验证后删除
├── datasets/
│   └── hammer_selected/           # 62 GiB，只提取项目所需模态
├── cache/
│   ├── polar_float32_ds4/         # 约 4.6 GiB
│   ├── torch/                     # wheel / extension cache
│   └── models/                    # 预训练权重
├── repos/
│   └── PolyCamera/
├── runs/
│   ├── proxy/
│   ├── baseline/
│   └── full/
└── exports/                       # 小型指标、图、日志，回传当前机器
```

推荐预算：

| 项目 | 预算 |
|---|---:|
| HAMMER ZIP | 160 GiB |
| 选择性提取数据 | 65 GiB |
| 优化 cache | 10 GiB |
| Python/模型/编译缓存 | 40--80 GiB |
| checkpoint 与实验日志 | 150--250 GiB |
| 安全余量 | 至少 300 GiB |

总使用控制在约 450--550 GiB。数据验证后删除 ZIP，可再释放约 159 GiB。不要完整解压 171 GiB 后再运行官方复制脚本，也不要生成 146 GiB 的 float64 偏振 cache。

## 5. 远端部署步骤

### Stage A：机器预检

将仓库中的 `depth_research/tools/remote_preflight.sh` 复制到训练机执行，把输出发回。需要确认：

- Linux 发行版；
- RTX 5080 的准确显存（通常为 16 GiB，但以 `nvidia-smi` 为准）；
- 驱动和可安装的 PyTorch/CUDA 版本；
- CPU、RAM、磁盘挂载路径与可用空间；
- 是否可以访问 GitHub、Google Drive、HAMMER 数据服务器和 PyPI；
- 是否允许 `tmux`/长时间后台任务；
- 1 TB 是否为持久磁盘而非临时盘。

### Stage B：代码和目录

1. 当前仓库先提交一个可复现 checkpoint；
2. 远端通过 Git clone/pull 获取代码，不手工复制散落文件；
3. 数据和 checkpoint 放 `/data/poldepth`，不放 Git 仓库；
4. 每次实验记录 Git commit 和 `study.json` 协议版本。

### Stage C：数据准备

推荐顺序：

1. 用可续传工具顺序下载 159 GiB ZIP；
2. 校验文件长度为 `170457339555` bytes，并运行 ZIP 完整性检查；
3. 用 `inventory_hammer.py --archive` 生成本地清单，与仓库清单核对；
4. 先运行选择性提取 dry-run；
5. 用 `prepare_hammer_selected.py` 只提取非 naked 的 polarization 坐标数据，约 62 GiB；
6. 生成 float32/downsample=4 偏振 cache，约 4.6 GiB；
7. 随机抽查 PNG、CRC、shape、depth 单位和 cache 数值；
8. 通过后可选择删除 ZIP。

不推荐在远端直接通过 HTTP Range 抽取 57,689 个文件：当前样本实验表明随机 Range 请求较慢。训练机空间足够时，顺序下载一次再本地选择性解压更稳定。

### Stage D：模型环境

RTX 5080 属于新架构，不使用论文原始 PyTorch 1.9/1.10 + CUDA 11.x 环境。流程为：

1. 根据远端驱动选择支持 5080 的现代 PyTorch；
2. Python 优先 3.10/3.11；
3. 单独环境，不污染系统 Python；
4. 先移除 PPFT 推理路径对 Apex/DDP 的强制依赖；
5. 用 `torch.amp` 代替 Apex AMP；
6. 处理旧 mmcv checkpoint loader 和 deformable convolution；
7. 先加载作者 checkpoint 跑 1 帧、1 batch；
8. 再运行 4 帧审计子集；
9. 最后才运行完整 test/train。

### Stage E：5080 显存策略

按常见 RTX 5080 16 GiB 显存保守设计，实际以预检为准：

- 推理 batch size 从 1 开始；
- 训练 batch size 从 2 开始；
- BF16/FP16 AMP；
- gradient accumulation 模拟较大 batch；
- 固定 208 x 272 或论文实际网络输入，不先提分辨率；
- 必要时 gradient checkpointing；
- 每个配置记录 peak VRAM；
- 先短预算 proxy，再批准完整训练。

不应为了复现作者的 batch size 14 而发生 OOM；有效 batch 可以通过梯度累积保持。

## 6. 实验调度

### 第一批：不训练

- 全 7,207 帧 raw sensor 统计；
- 固定 FoV/support mask；
- material interior/boundary；
- 25/50/100 mm silent-error 标签；
- DoLP/material/RGB/depth heuristic 对照。

这些任务主要吃 CPU、磁盘和读取带宽，可在模型环境迁移时并行完成。

### 第二批：baseline inference

1. raw depth；
2. 简单 RGB-D / material error detector；
3. CompletionFormer；
4. PPFT 作者 checkpoint；
5. Depth Prompting 或可复现的 sensor-agnostic baseline。

### 第三批：baseline training

- 先复现 PPFT split；
- 再建立严格 leave-one-real-sensor-out；
- 被留出传感器不得参与 early stopping；
- 每个传感器先跑一个短预算 proxy；
- 只有稳定缺口才开始新模型。

### 第四批：方法与自动实验

达到 Gate 3 后才启用 `depth_research/program.md`。单张 5080 不适合无边界“整夜无限循环”；采用固定 GPU 小时预算、代理实验和人工批准的 full run。

## 7. 两台机器之间同步什么

### Git 同步

- 源码、配置、manifest schema、文档和小型证据表；
- 不提交 dataset、环境目录、模型缓存和大 checkpoint。

### 从训练机回传

```text
results.tsv
配置 JSON/YAML
环境清单
stdout/stderr 摘要
逐场景/逐传感器 CSV
少量代表图
最佳 checkpoint 的路径和 SHA-256（checkpoint 本体留远端）
```

当前机器负责汇总和审查，训练机保留大文件。可以使用 `rsync --partial`，具体命令需知道 SSH 地址和远端目录后生成。

## 8. 开始远端工作前需要用户确认

已确认：1 TB 为磁盘、可 SSH、可联网、可后台长时间运行。

仍需确认：

1. SSH 主机名/IP、用户名和端口（不要发送密码）；
2. 训练机操作系统；
3. `nvidia-smi` 完整输出；
4. CPU/RAM/1 TB 磁盘的实际挂载路径与空闲空间；
5. 希望使用的项目根目录；
6. 是否可以通过当前 GitHub 仓库同步代码，或改用 `rsync`。

拿到预检信息后，再生成精确的 PyTorch 安装命令、下载命令、远端目录初始化脚本和第一个 baseline 作业。
