# 数据、前人工作与候选缺口

**更新日期：** 2026-11-02
**检索状态：** 工业标识识读新主线第一轮；以下区分论文证据、公开数据、工业实践和待验证判断

## 1. 工业实践已经解决了什么

### 固定照明与偏振是成熟方案

工业视觉通常先通过光源几何和滤光提高对比度：同轴光、穹顶光、暗场、漫射罩、带通滤光和交叉偏振都已广泛使用。IDS 的偏振相机技术说明明确把反光抑制、细结构对比增强和单帧偏振获取列为工业用途，同时指出金属表面仅靠接收端偏振片未必能消除反射，往往还需要在照明端加偏振片。

来源：

- IDS, *Polarisation camera / Using a polarisation filter*：<https://en.ids-imaging.com/techtipp-details/items/techtip-on-camera-polarization.html>
- Vision Systems Design, *Uses for polarization imaging in machine and computer vision*：<https://www.vision-systems.com/home/article/14068739/uses-for-polarization-imaging-in-machine-and-computer-vision>

因此，本课题不能把“偏振片可以压反光”写成创新，必须比较固定交叉偏振强基线。

### 工业 OCR/OCV 的核心是过程窗口

KEYENCE、Cognex 等工业产品资料均强调：生产日期、批次号、条码和包装标识识读依赖稳定成像、触发、预处理、格式验证和拒绝策略。光泽、褶皱、曲面和 SKU 变化是明确的工程困难。

来源：

- KEYENCE OCR/1D/2D verification：<https://www.keyence.com/products/vision/applications/ocr-verification-and-character-inspection.jsp>
- Cognex flexible packaging OCR：<https://www.cognex.com/en/applications/optical-character-recognition/ocr-text-verification-on-flexible-packaging>

这些资料能证明需求存在，但属于产品/应用证据，不能代替学术方法对比。

### 车牌不是天然适合偏振的同一任务

Axis 2024 的车牌采集白皮书指出，正确对齐的偏振片可减弱挡风玻璃或道路反射，但会阻挡约 50% 入射光，对车牌可见度改善有限，因此不推荐将偏振片作为车牌采集的通用方案。车牌还涉及逆反射材料、红外补光、车灯、速度和户外环境。

来源：<https://whitepapers.axis.com/en-us/license-plate-capture>

因此，车辆号牌只能作为后期外部验证，不能直接把工业喷码结论泛化到车牌。

## 2. 与本课题最接近的公开数据与工作

### 2.1 SHDocs（NeurIPS 2024 Datasets and Benchmarks）

- 任务：真实文档高光去除与 OCR 下游评价；
- 数据：基于 FUNSD 文档，公开仓库说明包含 3,184 个场景、19,104 张图像；
- 采集：打印文档放入不同透明文件袋，构造多种高光条件和对齐的去高光反事实；
- 评价：同时报告图像增强和 OCR；
- 代码/数据：公开，仓库标注 MIT；OpenReview 页面标注 CC BY 4.0 论文许可；
- 价值：直接证明“高光去除应以 OCR 结果评价”，并提供数据构建参考；
- 局限：对象是平面文档/文件袋，不是工业喷码、曲面和 DoFP 自适应表示。

链接：

- 论文：<https://proceedings.neurips.cc/paper_files/paper/2024/hash/af9199ef7d5ff267451a667170124c04-Abstract-Datasets_and_Benchmarks_Track.html>
- 代码与数据：<https://github.com/JovinLeong/SHDocs>

### 2.2 DocHR14K / L2HRNet（2025）

- 任务：单幅文档图像高光去除；
- 数据：14,902 对高分辨率真实图像，覆盖 6 类文档和 9 种照明条件；平均分辨率约 2319×1553；
- 方法：Highlight Location Prior + Laplacian pyramid + diffusion detail restoration；
- 报告：在 DocHR14K 上相对既有方法提高 PSNR、降低 RMSE；
- 价值：说明高分辨率文本和多光照需要专门数据；其交叉偏振采集方案可借鉴为干净参考；
- 局限：核心是单图恢复，不以四方向偏振作为部署输入，也不是工业 exact-read 任务。

链接：<https://arxiv.org/abs/2504.14238>

### 2.3 HAFNet / LSH（CVPR 2025）

- 任务：大面积文本图像镜面高光去除；
- 数据：使用 Unity3D/PBR 构造包含卡片、证件和海报的 LSH 文本高光数据；
- 方法：在深层特征和重建层进行自适应过滤；
- 主要指标：PSNR、SSIM；
- 价值：证明文本图像的大面积高光与自然图像小高光不同，需保留字符语义和细节；
- 局限：以合成恢复为主，没有单曝光四方向偏振输入，也未把工业字符串 exact-read 设为主目标。

链接：<https://openaccess.thecvf.com/content/CVPR2025/papers/Jiang_Hierarchical_Adaptive_Filtering_Network_for_Text_Image_Specular_Highlight_Removal_CVPR_2025_paper.pdf>

### 2.4 Polarized Reflection Removal（CVPR 2020）

- 任务：使用偏振图像进行玻璃反射层去除；
- 数据：公开仓库说明为 807 对，覆盖 100 多种玻璃；
- 方法：两阶段偏振反射去除，强调训练对的完美对齐；
- 价值：证明多方向偏振对反射/透射分离有明显价值，并提供公开代码；
- 局限：主要处理隔着玻璃的反射层，不是表面喷码和工业 OCR；旧 TensorFlow 环境复现成本较高。

链接：

- 论文：<https://openaccess.thecvf.com/content_CVPR_2020/html/Lei_Polarized_Reflection_Removal_With_Perfect_Alignment_in_the_Wild_CVPR_2020_paper.html>
- 代码：<https://github.com/ChenyangLEI/polarization-reflection-removal>

### 2.5 Polarization Guided Specular Reflection Separation（TIP 2021）

- 任务：RGB + 偏振引导的镜面/漫反射分离；
- 方法：偏振色度和 ADMM 优化，缓解照明颜色接近表面颜色时的不稳定；
- 价值：可作为物理/优化类反光分离基线；
- 局限：优化目标是反射分离质量，不是识读任务，也未针对 DoFP 速度与字符高频边缘。

DOI：<https://doi.org/10.1109/TIP.2021.3104188>

### 2.6 PolarFree / PolaRGB（CVPR 2025）

- 任务：偏振引导的真实场景反射去除；
- 数据：论文报告 6,500 组对齐样本，覆盖室内外和多种照明；项目提供代码与 Hugging Face 数据；
- 方法：使用 diffusion 生成 reflection-free cues；
- 价值：是当前偏振反射去除的强学习基线和数据来源；
- 局限：模型重、目标是一般反射层去除，不是工业单曝光低延迟识读；公开数据规模/命名在项目页与托管页面间需下载后再核对 inventory。

链接：

- 论文/项目：<https://mdyao.github.io/PolarFree>
- 代码：<https://github.com/mdyao/PolarFree>
- 数据：<https://huggingface.co/datasets/Mingde/PolaRGB>

### 2.7 DoFP 去马赛克与虚拟偏振片

Qiu 等在 *Linear Polarization Demosaicking for Monochrome and Colour Polarization Focal Plane Arrays*（Computer Graphics Forum 2021）中明确讨论 DoFP 去马赛克和 virtual polarizer，可由完整线偏振信息合成任意分析角度图像。

价值：直接支持本课题“采集后虚拟选角”的物理实现；同时提醒 DoLP/AoLP 和虚拟角度精度受 DoFP 空间采样与去马赛克影响。

链接：<https://onlinelibrary.wiley.com/doi/full/10.1111/cgf.14204>

## 3. 当前候选缺口

第一轮检索已经找到三类强邻近工作：

1. 工业照明与固定偏振；
2. 文本/文档高光去除并用 OCR 评价；
3. 偏振反射去除与虚拟偏振片。

但尚未找到一个被广泛采用的公开基准同时满足：

```text
单曝光 DoFP 原始四方向
+ 工业喷码/标识字符串 ground truth
+ 系统变化的材质、姿态与光照
+ 最佳固定方向强基线
+ 自适应偏振表示
+ exact-read / worst-group / latency
```

因此当前候选缺口不是“首次用偏振去高光”，而是：

> **将单曝光多方向偏振从一般图像恢复线索，转化为面向工业识读的任务驱动、自适应且可拒绝的表示，并以最佳固定光学配置和跨条件可靠性为主要对照。**

这仍是待进一步检索和实验验证的候选缺口，开题前不能使用“首次”表述。

## 4. 公共数据如何使用

| 数据/工作 | 可承担 | 不能承担 |
|---|---|---|
| SHDocs | 高光影响 OCR 的公开证据；OCR 评价代码；数据构建参考 | 工业喷码主结果、DoFP 自适应结论 |
| DocHR14K | 高分辨率文本恢复预训练/压力测试 | 单曝光偏振部署评价 |
| LSH/HAFNet | 大面积文字高光恢复基线 | 真实工业跨材质结论 |
| Polarized RR / PolarFree | 偏振反射去除预训练或强基线 | 工业 exact-read 和低延迟证明 |
| 自采数据 | 主实验、固定方向必要性、跨条件与节拍 | 大规模通用场景结论（除非规模足够） |

公开文档数据只能做辅助预训练、方法 sanity check 或相关工作对照。论文主结论必须来自自采工业工位，因为研究问题包含材质、姿态、照明、触发和节拍。

## 5. 新数据集最小设计

### 必备输入

```text
raw mosaic
I0 / I45 / I90 / I135（注明重建方式）
S0 / S1 / S2 / DoLP / AoLP
曝光、增益、光圈、光源和触发元数据
字符 ROI 与真实字符串
材质、姿态、光照、SKU、批次标签
```

### 建议参考

- 每个条件保存普通 RGB/灰度或 `S0`；
- 静态子集保存旋转偏振片密集角度扫描，作为角度插值与 DoFP 误差上界；
- 可行时保存固定交叉偏振和 HDR/多曝光结果；
- 记录每次是否可读、OCR 输出和置信度，而不只保存图片。

### 划分原则

- 同一物理喷码实例和相邻帧不得跨 split；
- 按材质、SKU/批次和采集日期分组；
- 最终保留未见光照或姿态区间；
- 外部二维码/车牌数据完全独立，不用于主模型选择。

## 6. 复现与阅读优先级

1. **SHDocs：** 先跑数据与 OCR benchmark，验证 exact-read/CER 管线；
2. **DoFP virtual polarizer：** 实现标定后任意角度合成和角度扫描；
3. **简单高光基线：** `S0`、固定方向、min/median、交叉偏振；
4. **Polarization-guided separation：** 选择轻量可复现方法，不一开始迁移 diffusion；
5. **HAFNet/DocHR14K/PolarFree：** 作为强恢复基线或预训练候选，在主工位成立后再投入。

## 7. 仍需补检索

- 直接面向工业 OCR/OCV 的偏振学术论文；
- 工业 DPM（laser/inkjet/dot-peen）在光泽表面的公开数据；
- 任务驱动图像增强与 recognizer-aware restoration；
- 动态场景 DoFP 偏振去马赛克及瞬时视场误差；
- 固定/可调交叉偏振照明的工业对照；
- 多帧 HDR、多光源与偏振在相同节拍下的公平比较；
- 识读置信度校准与 selective OCR。

旧的透明分割、偏振深度与 HAMMER 文献继续保留在 `08_depth_landscape_and_gap.md` 和 `depth_research/evidence/`，但不再作为新主线的主要 related work。
