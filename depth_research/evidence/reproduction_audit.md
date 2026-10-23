# 基线代码复现审计

**日期：** 2026-10-23
**目的：** 在安装大型依赖前，通过源码核查判断“能否直接运行”以及迁移成本。

## 1. PPFT

- 仓库：<https://github.com/lastbasket/Polarization-Prompt-Fusion-Tuning>；
- 核查 commit：`9b1145d87e50895fd17068fad9cec1199092f67a`（2024-08-20）；
- 代码许可证：MIT；
- checkpoint：仓库不直接包含，通过 Google Drive 脚本下载；
- 数据：需要完整 HAMMER 或按其目录构造的子集。

### 1.1 已发现的直接复现问题

1. `scripts/runs/test.sh` 调用 `main_refactored.py`，但该文件不在仓库中；训练脚本调用的是现有 `main.py`。测试入口需人工核对和修正。
2. README 指定 PyTorch 1.10、torchvision 0.11、CUDA 11.3，并依赖：
   - NVIDIA Apex；
   - `mmcv-full==1.4.4`；
   - 本地编译 deformable convolution；
   - Pillow 9.5。
3. `main.py` 无条件导入 Apex，并使用 Apex SyncBN/DDP；即使只推理也不能简单忽略。
4. 当前机器是 RTX 5090 D、驱动 595/CUDA 13.2。PyTorch 1.10/CUDA 11.3 发布时不存在该 GPU 架构，不能假设旧二进制可直接运行。
5. `process_hammer.py` 对四象限角度映射留有作者自己的 `by guess, not sure` 注释。
6. README 的 TODO 虽然后来补充了部分说明，但整体仓库提交次数少，测试脚本与主文件不一致，必须把“论文可复现”作为待验证事项而不是既定事实。

### 1.2 推荐迁移顺序

1. 不先装旧 CUDA 环境；
2. 下载作者 checkpoint，先检查 state dict 结构和模型参数名；
3. 建立 Python 3.10/3.11 + 支持 RTX 5090 的现代 PyTorch 独立环境；
4. 将 Apex AMP 替换为 `torch.amp`，单 GPU 推理先移除分布式和 SyncBN 依赖；
5. 处理 `mmcv.runner.load_checkpoint` 的替代或兼容层；
6. 单独验证 deformable convolution 编译/替代实现；
7. 先在一帧/一个 batch 上加载权重和推理；
8. 再接入选择性下载的 HAMMER 审计子集；
9. 最后才考虑完整数据训练。

不建议为了“原样环境”在当前根分区同时安装多套 CUDA/PyTorch；应使用独立数据盘或容器缓存。

## 2. Depth Prompting

- 仓库：<https://github.com/JinhwiPark/DepthPrompting>；
- 核查 commit：`a7b08ffff77cd037f9830c88cbf615b1c058eb19`（2024-07-29）；
- 仓库根目录未发现 LICENSE 文件，正式复用源码前需向作者或项目页确认许可；
- checkpoint 和 split 通过 Google Drive 提供；
- 公开代码没有 HAMMER loader，需要单独适配。

### 2.1 环境风险

README 指定 Python 3.8.18、PyTorch 1.9/CUDA 11.1、torchvision 0.10、`mmcv-full==1.3.13`。这比 PPFT 环境更旧，同样不能直接用于 RTX 5090。

### 2.2 在本课题中的合理用法

- 作为“没有偏振的 sensor-agnostic depth”竞争基线；
- 比较它对 sparsity/pattern/range 的适应与本项目对透明/反光 silent error 的处理；
- 若完整迁移成本过高，可以先复现论文的简单 bias protocol，并把模型复现作为后续阶段；
- 不应直接把它的随机稀疏输入协议等同于 HAMMER 的真实 ToF/主动双目系统误差。

## 3. 当前结论

两套关键基线都有公开代码，但都不是“clone 后立即运行”。当前最合理顺序仍是：

```text
原始数据统计与小样本协议
→ checkpoint/代码静态审计
→ 现代环境单帧推理迁移
→ 固定子集基线
→ 完整训练
```

这也是为什么选题阶段不能只根据论文表格承诺最终精度或时间表。
