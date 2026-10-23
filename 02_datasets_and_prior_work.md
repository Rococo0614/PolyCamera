# 数据集与前人工作

> **状态说明（2026-10-23）：** 本文是早期分割/位姿数据调研。当前偏振辅助深度主线及 HAMMER、PPFT、Depth Prompting、ReCAP2、CDPR、Poppy、PolarDepth 的调研见 `08_depth_landscape_and_gap.md`。

## 1. 偏振透明目标分割

### RGBP-Glass / PGSNet

- 项目页：<https://mhaiyang.github.io/CVPR2022_PGSNet/index.html>
- 代码：<https://github.com/Mhaiyang/CVPR2022_PGSNet>
- 论文：*Glass Segmentation using Intensity and Spectral Polarization Cues*, CVPR 2022。
- 规模：4511 张图像。
- 输入：RGB、三色 AoLP、三色 DoLP。
- 标注：像素级玻璃 mask、bounding box；部分训练辅助数据含 reflection 和 edge map。
- 传感器：LUCID PHX050S 三色偏振阵列相机。
- 代表方法：PGSNet，使用多分支和动态多模态融合。
- 适用性：当前最适合作为第一条复现主线。
- 注意：数据下载入口可能需要申请，需先确认实际下载可用性和许可证。

### Deep Polarization Cues

- 论文：*Deep Polarization Cues for Transparent Object Segmentation*, CVPR 2020。
- 任务：偏振辅助透明物体分割。
- 意义：较早系统验证偏振信息对透明目标分割的价值。
- 适用性：适合作为早期 baseline 和相关工作起点。
- 注意：代码和数据获取路径相对分散，复现优先级低于 RGBP-Glass。

### ZJU-RGB-P / EAFNet

- 论文：*Polarization-driven Semantic Segmentation via Efficient Attention-bridged Fusion*。
- 数据：394 张像素对齐 RGB-Polarization 图像，9 类语义分割。
- 训练/验证：论文中使用 344/50 的划分。
- 特点：面向户外场景和轻量实时语义分割；讨论 AoLP、DoLP 和 RGB 融合。
- 适用性：适合研究轻量模型、端侧部署和户外场景。
- 注意：数据量较小，不适合作为唯一数据集。

## 2. 偏振三维重建与法向估计

### DeepSfP

- 项目页：<https://visual.ee.ucla.edu/deepsfp.htm/>
- 代码：<https://github.com/UCLA-VMG/DeepSfP>
- 论文：*Deep Shape from Polarization*, ECCV 2020。
- 数据：338 个样本，27 个物体、4 个方向、3 种光照；包含四方向偏振图、mask、surface normal 和物理先验。
- 方法：将 Fresnel 物理先验与深度网络结合。
- 适用性：适合偏振三维/表面法向方向；物理含义强，但风险高。

### P2D

- 论文：*P2D: A Self-Supervised Method for Depth Estimation from Polarimetry*。
- 方向：使用偏振信息进行自监督单目深度估计。
- 适用性：可作为偏振深度方向的补充文献，不建议作为第一个复现项目。

## 3. 偏振 6D 位姿估计

### Polarimetric Pose Prediction / PPP

- 项目页：<https://daoyig.github.io/PPPNet/>
- 代码：<https://github.com/DaoyiG/polarimetric-pose-prediction>
- 数据说明：<https://www.campar.in.tum.de/public_datasets/2022_eccv_ruhkamp/README.html>
- 论文：*Polarimetric Pose Prediction*, ECCV 2022。
- 任务：instance-level 6D object pose。
- 特点：结合偏振物理先验和数据驱动模型，关注高反光、透明物体。
- 数据许可证：项目页说明为 CC-BY-NC，需注意非商业限制。
- 适用性：如果后续确定要做偏振 6D pose，可以作为专门 baseline。

## 4. 透明物体 RGB-D 三维感知

### ClearPose

- 代码：<https://github.com/opipari/ClearPose>
- 论文：*ClearPose: Large-scale Transparent Object Dataset and Benchmark*, ECCV 2022。
- 规模：约 35 万 RGB-D 帧，63 个透明物体，超过 500 万 instance 标注。
- 标注：raw depth、ground-truth depth、surface normal、mask、6D object pose。
- 困难场景：重遮挡、半透明遮挡物、不透明干扰物、液体、非平面摆放。
- 局限：没有偏振数据，不能直接用于偏振联合训练。
- 适用性：适合研究透明物体的 depth completion、RGB-D pose 和下游三维基线。

### ClearGrasp

- 数据页：<https://sites.google.com/view/cleargrasp/data>
- 代码：<https://github.com/Shreeyak/cleargrasp>
- 数据：5 万多张合成图像，286 张真实测试图像。
- 标注：透明物体 mask、边缘、surface normal、depth。
- 适用性：适合透明深度补全和三维感知 baseline。

### Trans10K

- 项目页：<https://xieenze.github.io/projects/TransLAB/TransLAB.html>
- 规模：10,428 张真实 RGB 图像。
- 标注：透明目标像素级 mask。
- 局限：没有偏振、深度和 6D pose。
- 适用性：适合普通 RGB 透明分割对照。

## 5. 当前数据集之间的关系

```text
RGBP-Glass：有偏振 + 透明分割，没有深度/位姿
PPP：有偏振 + 6D pose，场景和物体更专用
DeepSfP：有偏振 + 表面法向，偏物理三维
ClearPose：有 RGB-D + 透明物体 pose，没有偏振
ClearGrasp：有 RGB-D/深度补全，没有偏振
Trans10K：有 RGB + 透明 mask，没有偏振和三维
```

本轮检索暂未发现一个大规模、同时包含以下全部信息的公开数据集：

```text
偏振原始数据 + RGB + RGB-D + 透明物体 mask + 6D pose
```

因此，如果论文要做偏振-RGB-D 三维感知，需要自己采集小规模配对验证集。

## 6. 推荐复现顺序

1. RGBP-Glass + PGSNet：确认偏振分割主线可运行。
2. RGB-only / AoLP / DoLP / AoLP+DoLP 消融。
3. EAFNet 或轻量分割 baseline：确认端侧/实时方向。
4. PPP：如果确定做偏振 6D pose，再单独复现。
5. ClearPose：作为透明 RGB-D 三维感知和 pose 的对照，不强求完整训练。
6. DeepSfP：如果导师明确支持偏振三维物理，再深入。

## 7. 可能的改进点

- AoLP 使用 `sin(2*AoLP)` 和 `cos(2*AoLP)` 周期编码；
- 使用 `S0`、DoLP、饱和度和噪声构造偏振可靠性图；
- reliability-aware RGB/偏振自适应融合；
- 透明边界 head 和 boundary-aware loss；
- 公开相机到自购相机的少样本 domain adaptation；
- 偏振提升的分割 mask 是否改善 RGB-D 三维中心、尺寸和 pose；
- 端侧模型轻量化、量化和实时性评测。
