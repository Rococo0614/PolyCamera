# 执行记录

## 2026-11-03：开题 PPT 重构为 10 页结果导向版本

### 结构与叙事

- 删除独立目录、基础公式推导、重复方案页和独立参考文献页；
- 理论、工业背景、失效机理和单曝光物理合并为第 2 页，全文仅此一页承担背景介绍；
- 第 3 页统一给出系统、冻结协议和核心可证伪量；
- 第 4–8 页连续报告已完成工作量、E0、E1、E2 跨后端统计和机制/基线；
- 第 9 页集中给出 Gate 与下一轮冻结交付物，第 10 页按“已支持 / 未支持”收束；
- 所有公开代理和 HAMMER/PPFT 数字均保留任务域边界；`all-four-fail` 明确不等于
  系统拒绝率。

### 版式与演示功能

- 页面总数由 20 页压缩为 10 页，正文使用更大的结果数字、铺满式数据行和高密度
  表格，避免依靠缩小字号堆叠；
- speaker notes 与 10 个 `data-slide-id` 一一对应，计划总时长 `11.7 min`；
- 演讲者视图、下一页预览、计时、观众屏同步和批注功能继续保留；
- 重新生成 `slide-01.png`–`slide-10.png`、`overview.png` 和 `grid-all.png`，删除过期的
  `slide-11.png`–`slide-20.png`。

### 验证

- 1600×900 presenter validator 为 `0 errors / 0 warnings`：无页面、内容区或子元素
  越界，5/5 图片资源与字体加载成功；
- 演讲者视图实测可显示第 7 页、下一页预览和对应讲稿；
- 工业识读 `14/14` 项、深度研究 `15/15` 项测试通过，共 `29/29` 项。

## 2026-11-03：PDD Offline E1 首轮公开基准完成

### 数据闭环

- PDD 2025 归档长度 `12,171,672,476` bytes；
- SHA-256 `01f20ebc8b3b8940f1460ebafb981eb0942bcbb5cc4b5af7bf3ab27b46e98008`；
- `unzip -tqq` 全量 CRC 通过；归档共 1,209 entries；
- 只提取 Python 实验需要的 960 个 PNG（约 1.1 GB），不重复提取约 11.1 GB MAT；
- 覆盖 40 场景 × Low/Mid/High 三档噪声，共 120 个条件。

### 简单重建基线

使用绿色通道和公开 MPFA 排列 `[[90,45],[135,0]]`，比较 noisy full-channel
诊断上界、最近邻和项目内可审计的 3×3 normalized bilinear：

| Noise | Method | PSNR dB ↑ | DoLP MAE ↓ | AoLP MAE ° ↓ |
|---|---|---:|---:|---:|
| Low | nearest / bilinear | 32.80 / 38.32 | 0.0313 / 0.0187 | 25.26 / 15.14 |
| Mid | nearest / bilinear | 31.20 / 35.53 | 0.0645 / 0.0424 | 29.77 / 21.24 |
| High | nearest / bilinear | 29.02 / 32.37 | 0.0818 / 0.0564 | 31.81 / 23.69 |

120 个条件产生 360 条记录。双线性在各噪声级均优于最近邻，但 AoLP 对噪声和
空间插值仍明显敏感；后续细字符 OCR 必须把重建方法作为显式消融。该实验不是
官方 PDD 方法复现，也不是未来相机的标定。完整 artifact SHA-256：
`3a4eaa7c71352125f8b39517a24b4ff1305c269611a90a5a26e241c37108bb4f`。

### SHDocs processed 数据与偏振预审计

- processed archive 长度 `1,715,393,730` bytes，SHA-256
  `49457a4afae50fc750328399af708c12570a08c613b1ccfe7f552c6f8acb05c7`，全 ZIP CRC
  通过；
- 50 个 FUNSD 文档、16 种 capture condition，共 800 captures；每个 capture 均有
  `i0/i45/i90/i135/s0_norm/deglared`，共 4,800 图像；
- 对齐标注包含 2,270 个唯一文本区域，跨 16 条件展开为 36,320 个 ROI；
- 发现 17 个 ROI-condition 的标注框轻微超出处理后图像边界，已冻结排除清单，
  避免把截断裁剪误计为反射/OCR 失败；
- 文档级冻结 split 为 train/val/test `35/8/7`，assignment SHA-256
  `3f1868c879df1112ce145eb711e33e7f441c8a5c8f6a31254b5c23419af74343`；
- 800 captures 的平均正交 pair residual `0.02361`，平均 DoLP `0.03387`，计算 S0
  与 SDK `s0_norm` 相关系数 `0.99908`；平均饱和比例仅 `0.000162`。

这些数值来自 8-bit SDK 导出，只允许支持结果级代理实验；不能解释为 FLIR 相机
已经完成物理标定。平均 DoLP 较弱，四方向 OCR 互补性必须由字符串结果直接检验，
不能根据偏振幅值预设成立。完整 audit SHA-256：
`8cfbe0787c055a7db46abfd8151a69b0aa81954d4ccbfc34e1138d5d91563b81`。

SHDocs raw archive 也已完成长度 `10,277,187,768` bytes、SHA-256
`fff85bdb2acb2e4fedf60937f96352f796a6b4b7b3acb5e7e005886b574f746a` 和全 ZIP CRC
校验。其 inventory 为 9,600 training + 4,800 testing 图像文件；该归档级数量与公开
README 的 3,184 scenes 口径仍需核对，因此当前不宣称完成 SHDocs 全数据统计，也不
重复解压 raw archive。

### E0 清晰合成代码 sanity set

使用 100 个唯一字符串、3 种开放等宽字体和 24/32/48 px 三档字号生成 900 张
无反光清晰图；固定 `A–Z/0–9/-/space` allowlist，不使用字典或期望值纠错：

| Backend | Overall exact | Macro CER | EXP exact | SN exact | Mean latency |
|---|---:|---:|---:|---:|---:|
| EasyOCR 1.7.2 | 60.78% | 0.0420 | 95.11% | 36.00% | 3.43 ms |
| Tesseract 5.5.3 PSM7 | 79.44% | 0.0183 | 99.56% | 64.00% | 38.01 ms |

该实验只验证软件/OCR 上限，不代表相机或真实喷码。它证明 E0 必须先锁定主字符
体系：固定日期格式已经可用，而任意字母数字序列号仍需专用 OCR/训练数据，不能
与日期码合并报告。

### SHDocs EasyOCR E0/E2 第一轮

采用文档级 `35/8/7` split，每文档确定性抽取 10 个 region；根据 `camera` 验证集
冻结 `4× bicubic、无 autocontrast`。测试结果：

| Slice | Train-best fixed | Fixed exact | Four-angle oracle | Gap |
|---|---|---:|---:|---:|
| camera E0，全标签 | I90 | 13.04% | 18.84% | +5.80 pp |
| a–o E2，全标签 | I0 | 11.32% | 13.83% | +2.51 pp |
| a–o E2，question/header | I0 | 14.51% | 17.42% | +2.90 pp |

E2 全标签的文档聚类 bootstrap 95% CI 为 `+1.50–+3.52 pp`；1,034 个测试 ROI 中
36 个只有一个方向成功，且 I0/I45/I90/I135 分别成为唯一成功方向
`21/4/3/8` 次。说明四方向存在可重复互补信号。

但当前结论仍不能通过 Gate P2：camera E0 的绝对 exact 很低，86.17% 的 E2 ROI
四方向均失败；OCR-confidence 选择器 exact `11.03%`，反而低于 train-best I0，
未捕获 oracle 空间。下一步必须用第二 OCR 后端复核，并先解决任务字符体系和
识读器上限，再研究自适应选择器。

### SHDocs Tesseract 独立后端复核与 Gate 判定

根据 camera validation 将 Tesseract 也冻结为 `4× bicubic`。同一 1,034 个 a–o
测试 ROI 上：

- train-best fixed I0：exact `26.31%`，macro CER `0.4005`；
- four-angle oracle：exact `32.88%`，macro CER `0.2768`；
- oracle gap `+6.58 pp`，按 7 个测试文档聚类 bootstrap 95% CI
  `+4.13–+8.86 pp`；
- 117 个样本只有一个方向成功，I0/I45/I90/I135 唯一成功次数分别为
  `74/14/13/16`；
- confidence selector exact `27.56%`，只比 fixed 高 `1.26 pp`，且四次 OCR
  顺序执行均值约 `162.15 ms`；
- question/header 子集 fixed/oracle 为 `31.49%/38.61%`，gap `+7.11 pp`
  （CI `+3.90–+10.83 pp`）。

因此四方向互补性已跨两个 OCR 后端重复，不是 EasyOCR 特例；但 deployable selector
只捕获少量 oracle 空间，SHDocs camera E0 也只有 EasyOCR/Tesseract
`13.04%/33.33%`。Offline Gate P 判定为：P0 条件性、P1 软件代理通过、P2 机制
支持但部署未通过；总状态保持 open，正式工业 Gate 1 关闭。详见
`14_offline_gate_p_results.md`。

### PPT 更新（历史 19 页中间版本）

- 清华风 HTML PPT 从 18 页更新为 19 页；
- 新增 HAMMER/PPFT“前期探索与证据迁移”页，明确深度任务只提供可靠性方法论，
  不作为工业 OCR 增益证据；
- 19 页/19 条 speaker notes 通过 presenter validator，计划时长 16.5 分钟，
  `0 errors / 0 warnings`；逐页 1600×900 截图与总览已重新生成。

### PPT Offline Gate P 结果更新（历史 20 页中间版本，已由本日日志顶部 10 页版替代）

- 以两页结果替换原“新增实验”计划页：第 16 页报告 E0 清晰代码与 PDD E1，
  第 17 页报告 SHDocs 双后端 E2、可靠性边界与 Gate 判定；
- 明确区分 `Offline Gate P = open` 与 `formal industrial Gate 1 = closed`，并在
  正式 Gate 1 页标注“尚未执行”，避免公开代理结果被误读为工业验证；
- E2 页同时报告 fixed / confidence selector / oracle exact、macro CER、worst
  condition、all-four-fail、顺序 OCR 延迟和文档聚类 CI；接受阈值未冻结，因此不把
  all-four-fail 冒充 false-read 或 rejection；
- 更新近期里程碑为“冻结日期/批次码 → 密集虚拟角基线 → 硬件标定与 pilot →
  正式 Gate 1”，并明确在真实 E0/E1/E2 前不训练最终自适应融合；
- 该中间版本为 20 页/20 条 speaker notes，计划时长仍为 16.5 分钟，presenter
  validator 为 `0 errors / 0 warnings`；20 张 1600×900 截图及两张总览已重生成。

## 2026-11-02：Offline E0–E2 前置实验启动

### 决策与边界

- 在偏振相机尚未到位时，先使用 SHDocs、PDD/PIDSR 和现有 HAMMER 资产运行
  Offline Gate P；
- SHDocs 代理结果只用于平面文档高光域的软件/机制验证，不写成工业喷码结论；
- HAMMER 选择集、compact cache、PPFT 结果和历史代码全部保留，不重新下载或删除；
- 开题 PPT 将 HAMMER/PPFT 单列为“前期探索与方法论迁移”，明确不是 OCR 实验。

### 已完成

1. 新增 `industrial_reading/` 独立实验包与 `offline-gate-p-v1` 配置；
2. 实现字符串规范化、raw/normalized exact-read、CER/WER；
3. 实现四方向 Stokes、虚拟检偏角、min/median/mean 表示；
4. 实现仿射仪器矩阵估计、分组 split、train-best、oracle 和分组 bootstrap；
5. 实现 SHDocs 只读 inventory、FUNSD ROI 发现和可续传 EasyOCR JSONL 入口；
6. 14 项新单元测试通过，Python 编译与 JSON 校验通过；
7. 独立 EasyOCR 1.7.2 环境完成 RTX 5080 冒烟；另固定 Tesseract 5.5.3
   作为第二后端，两者均在合成 `LOT A12B9` 上完成执行冒烟；
8. Offline E1 合成实验中，加入角度/增益/偏置误差后，仿射标定将 Stokes RMSE
   从 `0.0114719` 降至 `0.00260309`。该结果只验证软件链；
9. 固定公开仓库版本：SHDocs `5d4e26b`、PolarDenDem `136cc20`、PIDSR
   `ed7e9a3`。

### 数据状态

- SHDocs raw Google Drive 首次连接中断，已保留断点并重试；
- PDD/PIDSR 数据在 SHDocs inventory 后按优先级接入；
- 大数据继续放在 `/home/chocbrownie0524/poldepth/datasets/industrial_reading`，不进入 Git。

## 2026-11-02：主线转向变化反射条件下的工业标识可靠识读

### 决策

将课题叙事和优先实验从“偏振辅助异构深度增强”调整为：

> **面向变化反射条件工业标识可靠识读的单曝光偏振自适应表示方法研究。**

主任务先锁定固定工位工业喷码字符识读。二维码或物流车辆号牌只选择一项作为后续外部验证，不与喷码并列为三个主任务。

### 原因

1. 制造与物流已有清晰的追溯、分拣和出入口识读需求；
2. 光泽、覆膜和姿态变化会移动高光，使固定成像/偏振配置不能始终最优；
3. 调光、调角度和固定偏振已经成熟，真正待验证的是变化条件下的自适应；
4. DoFP 提供单次曝光四方向信息，适合研究无电机切换、低附加机械复杂度的表示选择；
5. 喷码字符串 ground truth 易获得，课题可用 exact-read、误读率、worst-group 和节拍形成可重复评价闭环。

### 证据边界

- 既有 HAMMER 7,207 帧审计、PPFT 复现和深度结果全部保留；
- 它们证明偏振具有场景/质量依赖性，也提供数据处理与可靠性分析基础；
- 它们**不能证明**偏振会提高工业字符识读，不能作为新主线的结果图直接移用；
- 新主线尚未完成喷码工位采集、固定方向基线或自适应方法实验。

### 下一步 Gate 1

在至少两类光泽/覆膜材质、多个姿态与光照条件下采集 `RGB/S0/I0/I45/I90/I135`，固定成熟 OCR，比较四个固定方向与训练集最佳固定方向。只有观察到最优方向随条件稳定切换且四方向存在识读互补性，才进入自适应表示方法开发。

完整故事与实验边界见 `12_industrial_reading_research_story.md`；实验编号与 Gate 见 `13_industrial_reading_experiment_plan.md`。

### 文档与实验协议更新

- 重写 `01_topic_and_research_questions.md`：RQ1–RQ6、否证条件和停止 Gate；
- 重写 `02_datasets_and_prior_work.md`：SHDocs、DocHR14K、HAFNet、Polarized RR、PolarFree、DoFP virtual polarizer 与工业实践；
- 重写 `03_one_month_plan.md`：首月从清晰 OCR 上限、标定、pilot 到 Gate 1/2；
- 重写 `04_hardware_and_data_collection.md`：相机/镜头/照明/工位/标定/manifest/划分/成本；
- 更新 `05_polarization_camera_physical_models.md` 的工业识读链路；
- 新增 `13_industrial_reading_experiment_plan.md`：E0–E13、B0–B7、U0–U2、M1–M6 以及统计协议；
- 新增采集 manifest 和实验结果 TSV 模板。

## 2026-10-23：Phase 0 完成，Phase 1/2 启动

### 已完成

1. 将“偏振辅助异构深度传感器增强”设为当前主线；
2. 保留原有透明分割路线作为兜底，不删除既有成果；
3. 固化研究问题、可证伪假设、评价指标和决策门槛；
4. 建立文献/产品证据矩阵；
5. 建立 `poldepth` 分析包：
   - Stokes、DoLP、AoLP 与周期编码；
   - 通道对一致性残差和启发式质量图；
   - 深度 MAE/RMSE/AbsRel/delta/coverage/P95/P99；
   - 2x2 偏振 composite 显式排列解析；
6. 当前 13 个单元测试通过，覆盖偏振公式、饱和检测、象限配对、深度指标、边界/腐蚀 mask、FoV/support 诊断和 silent-error 排序指标；
7. 核查本机资源：RTX 5090 D 24 GB，根分区仅约 14--17 GB；
8. 核查 HAMMER 完整 ZIP 大小：170,457,339,555 bytes（约 159 GiB）；
9. 实现 HTTP Range ZIP 读取工具，成功远程列出 434,911 个归档条目中的目标条目；
10. 从 159 GiB 归档中只下载了 `scene13_traj1_1/000000` 的约 7.6 MiB 必要数据，而非整包：
    - rendered GT；
    - instance label；
    - D435/L515/I-ToF warped depth；
    - polarization 2x2 composite。
11. 核对 HAMMER 官方数据页：数据采用 MIT license，并明确允许商业使用。
12. 下载并阅读 PPFT 补充材料：作者测试了未见的合成 8/16 线 LiDAR 稀疏 pattern，但没有给出“留出一种真实传感器训练、在该真实传感器上测试”的协议。当前跨真实传感器假设仍成立为待验证问题，但后续必须把合成 pattern 基线纳入比较。
13. 阅读 Depth Prompting：其已覆盖稀疏度、采样 pattern、量程和商业传感器 zero/few-shot。后续不能把普通 sparse-pattern 泛化作为本课题创新，必须进一步针对透明/反光的系统错误以及偏振带来的增量价值。
14. 核对 LUCID 官方 pixel-format 文档，并对实际四象限做正交 pair-sum 检验。PPFT 对边配对残差为 `0.055`，明显小于另两种配对的 `0.118/0.149`。DoLP 幅值分析可暂时继续，但 AoLP 绝对方向仍未完全核实。
15. 克隆并静态审计 PPFT/Depth Prompting：两者都依赖 PyTorch 1.x、旧 CUDA、旧 mmcv；PPFT 测试脚本还引用仓库中不存在的 `main_refactored.py`。已形成 `depth_research/evidence/reproduction_audit.md`，后续采用现代 PyTorch 单 GPU 迁移，不在当前机器盲装旧环境。
16. 第一版证据矩阵已扩展到 22 篇核心工作、12 个产品/产品族，覆盖偏振 SfP、多视图、商品深度增强、sensor-agnostic completion、透明/反光深度以及 2026 最新工作。条目数量达到 Phase 1 门槛，但 ReCAP2、PTOD 等开放性与实验细节仍待核查。
17. 阅读 GAA-TSO：RGB-D 透明/高反深度补全已经使用点云分支、深度 confidence、自适应邻域和 gated 融合，并验证机器人抓取。因此这些组件本身不能作为创新；后续必须突出偏振增量、真实跨传感器和双模态质量校准。
18. 已将 autoresearch 思路改写为本项目专用 `depth_research/program.md`：冻结数据/评测、单假设实验、代理/完整两阶段预算、多指标准入、测试集保护和停止条件。协议在 Gate 3 前明确禁用，避免在问题尚未确认时自动堆网络。
19. 核查 PolarDepth/PTOD 开放性：论文已公开，但 GitHub 当前仅 README，并声明代码/数据稍后开放；PTOD 需要申请且项目页入口不完整。当前实验不能依赖 PTOD，只将其作为后续外部验证候选。
20. 已为当前三个几何场景、四个视角的 28 个 PNG 生成 SHA-256 清单 `depth_research/evidence/hammer_sample_checksums.sha256`，用于后续结果复核。
21. 深读 PolarDepth 补充材料：PTOD 有 2,878 场景，用透明物体的不透明复制品 + D435i + Depth Anything refinement 构造稠密真值；作者还人工标注 HAMMER 子集做跨域 fine-tune，但模型输入不含三类 raw sensor depth。其明确限制是弱偏振材料。由此确认本课题不能泛称“偏振透明深度”或“低偏振鲁棒性”，差异必须落在商品 raw depth、真实传感器错误迁移和双模态可靠性。
22. 阅读 TPAMI 2026 PolFusion+：低照、过曝、模糊偏振快照恢复已有专门框架，且能改善下游任务。其需要短/长曝光对且不处理 raw depth。本课题的退化方向需限定为“偏振质量对深度融合的风险与单帧回退/校准”，不再把一般偏振恢复当创新。
23. 解析 PPFT 数据列表：其使用 scene2--10 训练、scene11--12 验证、scene13--14 测试，与 HAMMER 官方划分不同；scene13/14 又是同轨迹不同光照。后续报告必须明确 split 名称，并按几何场景分组统计，禁止把视频帧或光照复制视为独立样本。

### 文件与对齐核查

选择性下载的文件均通过 PNG 完整性检查：

| 模态 | 尺寸 | 类型 |
|---|---:|---|
| GT depth | 1088 x 832 | 16-bit PNG |
| D435 depth | 1088 x 832 | 16-bit PNG |
| L515 depth | 1088 x 832 | 16-bit PNG |
| I-ToF depth | 1088 x 832 | 16-bit PNG |
| instance label | 1088 x 832 | 8-bit PNG |
| polarization composite | 2176 x 1664 | RGB PNG，四象限拆分后 1088 x 832 |

这证明公开数据可以在不占用 159 GiB 本地空间的情况下进行小样本审计。

### 第一帧原始深度结果

单位为 mm；RMSE/MAE 只在 GT 和传感器深度同时有效的像素上计算，因此必须与 coverage 一起阅读。

| 传感器 | Coverage | MAE | RMSE | P95 abs error | P99 abs error |
|---|---:|---:|---:|---:|---:|
| D435 主动双目 | 74.86% | 20.20 | 41.25 | 71 | 205 |
| L515 D-ToF | 81.53% | 41.55 | 103.98 | 266 | 486 |
| Helios I-ToF | 43.07% | 45.59 | 106.03 | 191 | 292 |

### 当前能说什么

- 同一真实场景、同一目标相机坐标下，三种商品深度表现出明显不同的“覆盖率—误差”组合；
- D435 在有效像素上的误差最低，但约四分之一 GT 像素无有效深度；
- L515 覆盖率较高，但尾部错误明显更大；
- 当前帧的 I-ToF 覆盖率最低，且有效区域 RMSE 仍较大；
- 实例 ID 分层后差异进一步增大，例如部分实例上 ToF RMSE 超过 150 mm，而另一些实例只有 20--50 mm。

这与 H1 的方向一致，但**只有一帧，不能作为论文结论或统计显著证据**。

将标签 mask 叠加到 RGB 后，当前帧中 `label=140` 视觉上覆盖金属支架、金属勺等反光对象，`label=160` 覆盖透明水瓶和玻璃容器。按该暂定映射：

| 暂定材质标签 | D435 Coverage / RMSE | L515 Coverage / RMSE | I-ToF Coverage / RMSE |
|---|---:|---:|---:|
| 140，反光 | 87.3% / 52.2 mm | 98.5% / 28.8 mm | 100.0% / 45.9 mm |
| 160，透明 | 70.8% / 52.5 mm | 94.9% / 153.9 mm | 99.1% / 150.7 mm |

透明区域呈现了非常典型的差异：主动双目更多表现为缺失，而两类 ToF 几乎都有数值，却存在约 150 mm RMSE，即“silent wrong depth”。这比单纯研究随机空洞更有实际意义。不过标签 ID 到材质的映射目前来自可视化核对，正式统计前必须从作者说明或多场景一致性中进一步确认。

已生成审计总览图：

`depth_research/results/sample_audit/scene13_traj1_1_000000_overview.png`

图中可直接看到：D435 存在大量散点状和边界空洞；L515 视场较完整但在复杂物体、桌边及局部区域出现明显误差；I-ToF 的有效视场显著小于目标相机，视场外区域全部缺失。这些现象与论文对三种测量机理的描述一致。

### 偏振审计结果与限制

在暂用 `左上/右上/左下/右下 = 0/45/90/135` 的假设下：

- 物理有效率：98.16%（任一 RGB 分量到达 255 均按饱和无效处理）；
- 饱和比例：1.84%；
- 平均 DoLP（有效区域）：0.151；
- 两组正交强度和的平均相对残差：0.055；
- 启发式平均 confidence：0.375。

但 HAMMER 补充材料的角度文字和 PPFT 代码的映射存在疑点，且 PPFT 源码明确标注该映射为猜测。因此当前结果只能证明“数据可解析”，不能证明 AoLP 的绝对物理方向正确。

### 第一帧的偏振条件统计

在上述未核实的四象限假设下，按 DoLP 分箱后出现了值得继续验证、但尚不能作结论的趋势：

| DoLP 区间 | D435 RMSE | L515 RMSE | I-ToF RMSE |
|---|---:|---:|---:|
| [0, 0.05) | 33.2 mm | 39.2 mm | 54.8 mm |
| [0.05, 0.10) | 38.6 mm | 53.4 mm | 69.6 mm |
| [0.10, 0.20) | 32.2 mm | 85.2 mm | 82.5 mm |
| [0.20, 0.40) | 44.3 mm | 156.8 mm | 176.9 mm |
| [0.40, 1.00] | 92.1 mm | 184.5 mm | 96.2 mm |

DoLP 与绝对深度误差的单帧 Pearson 相关系数为：D435 `0.087`、L515 `0.373`、I-ToF `0.227`。这说明偏振变化可能与部分传感器失效区域共现，尤其是 L515，但它也可能只是物体、距离、材质或错误象限映射的混杂结果。必须在多场景、材质 mask 和正确偏振约定下复验，不能写成“DoLP 导致/预测深度误差”。

当前启发式偏振 confidence 与绝对误差的相关方向在 D435（约 `+0.139`）和两类 ToF（约 `-0.163/-0.149`）并不一致。这说明仅用 `S0 + 饱和 + pair residual` 得到的单一质量图不能直接充当“所有深度传感器通用的融合权重”；可靠性还必须结合传感器深度状态和任务损失进行校准。

### 第二帧复核（同场景相隔 120 帧）

第二帧保留了相同的基本趋势：D435 全图 RMSE `36.9 mm`，L515 `57.0 mm`，I-ToF `78.5 mm`；I-ToF coverage 仍只有约 `42.9%`。更重要的是，暂定透明标签 160 上：

```text
D435: coverage 81.7%, RMSE 59.3 mm
L515: coverage 94.1%, RMSE 157.5 mm
I-ToF: coverage 81.5%, RMSE 143.8 mm
```

这复现了第一帧中的“主动双目更多缺失、ToF 更完整但透明区域出现大幅 silent error”现象。标签 140/160 的 RGB overlay 在两个视角中也分别持续覆盖反光/透明对象。它提高了问题存在的可信度，但两个样本仍属于同一场景和轨迹，不能当成独立场景统计。

两帧的正交配对残差也高度稳定：PPFT 配对均约 `0.055`，另两种约为 `0.118--0.149`，进一步支持当前 DoLP 配对方式。

第二帧偏振有效率约 `97.86%`、饱和比例约 `2.14%`，说明即使公开数据经过相机处理，过曝区域仍不应直接参与 DoLP/AoLP 物理约束。

需要修正对 I-ToF coverage 的解释：它映射到偏振相机后只覆盖约 `47.5%` 的整幅视场。使用非零深度外接框作为临时 support 诊断，两帧 support 内 coverage 均约 `90.3--90.5%`；L515 support 内 coverage 约 `90.7--91.7%`，D435 仍为 `74.9--80.0%`。因此最终协议必须同时报告 FoV/support 和 support 内 coverage，不能把视场外区域当作传感器随机失效。该外接框只是临时估计，正式实验需由标定/warp 有效域生成静态 support mask。

在暂定透明标签 160 与 I-ToF support 的交集内，两帧 coverage 实际为 `99.6%` 和 `98.1%`，但 RMSE 仍为 `150.7 mm` 和 `143.8 mm`。这进一步说明这里不是单纯的 FoV/空洞问题，而是“几乎处处返回深度但深度系统性错误”。

透明标签上的 signed error 也主要为正：L515 两帧平均约 `+111 mm`，I-ToF 约 `+118/+104 mm`，正误差像素约占 `74--84%`。这与透明表面透射/折射后测到更远背景或多路径距离的解释一致，但仍需更多场景确认，不能仅凭两帧断言具体光路。

将透明 mask 向内腐蚀 5 像素后，L515 两帧内部 RMSE 仍为 `152.8/163.6 mm`，I-ToF 为 `151.4/141.4 mm`；因此大误差并非只来自透明轮廓配准或边界混合。D435 内部 RMSE 为 `46.4/49.0 mm`，但 coverage 只有 `70.2/82.4%`。

按 GT 中大于 20 mm 的深度跳变构造两像素边界带后，三类传感器两帧 RMSE 均约 `90--115 mm`，显著高于全图的 D435 误差。这表明深度边界需要作为固定评价切片，不能只报告全图平均值。

### 跨场景复核：scene10 / frame 000000

训练场景 scene10 提供了不同物体布局，label 140 在该场景中覆盖金属叉，label 160 覆盖透明杯，支持这两个 ID 跨场景分别对应反光/透明组的判断。

| 区域 | 传感器 | Coverage | RMSE |
|---|---|---:|---:|
| 全图 | D435 / L515 / I-ToF | 87.1% / 80.5% / 42.7% | 36.6 / 111.7 / 72.9 mm |
| 反光 label 140 | D435 / L515 / I-ToF | 95.3% / 58.1% / 95.7% | 16.1 / 291.2 / 193.3 mm |
| 透明 label 160 | D435 / L515 / I-ToF | 81.9% / 91.9% / 99.8% | 67.3 / 175.5 / 163.0 mm |

与 scene13 相比，具体数值会变，但关键现象跨场景重复：两类 ToF 在透明区域高覆盖但大误差；本帧的金属叉对 ToF 同样形成显著 silent error，而主动双目较准确。材质内部腐蚀后该趋势仍然存在。

以 `|raw-GT| >= 50 mm` 定义有效但错误的深度，DoLP 单特征在 scene10 上的 AUROC 为 D435 `0.673`、L515 `0.914`、I-ToF `0.912`；scene13 两帧对应约 `0.66--0.79`。这只是诊断基线，可能包含材质和位置混杂，但已经证明偏振与深度异常之间存在值得建模的非随机关系。

阈值敏感性不能忽略：在 25/50/100 mm 阈值下，DoLP 对两类 ToF 的 AUROC 多数保持约 `0.68--0.92`，但 D435 在 scene10 的 25 mm 阈值只有 `0.374`，到 100 mm 才升至 `0.803`。这说明 DoLP 更像“大幅材料诱导错误”的线索，而不是通用小误差质量分数，也进一步反对把同一个偏振门控规则硬套到所有传感器。

进一步只在同一暂定材质标签内部计算后，DoLP AUROC 明显下降：透明 label 160 内，两类 ToF 三个视角约为 `0.60--0.64`；反光 label 140 内多数约为 `0.47--0.63`。因此全图 `0.7--0.91` 的高 AUROC 有相当部分来自“DoLP 区分了材质/区域”，而不是直接精确预测每个像素的深度误差。这个结果否定了“DoLP 阈值就够了”的简单方案，也规定了后续必须加入 material-mask-only 对照并证明偏振在材质内部仍有增量。

使用暂定 label 140/160 构造二值 material-oracle 分数后，在 scene10/13 上其 ToF AUROC 只有约 `0.54--0.58`，明显低于 DoLP 的 `0.78--0.91`；但在弱偏振 scene12 上二者都约为 `0.64--0.69`。所以 DoLP 的全图收益不完全等价于这两个材质 mask，却强烈依赖场景偏振强度。合理目标应是学习“何时使用偏振”，而不是固定阈值或固定材质规则。

scene10 的正确正交配对残差仍最低：`0.054`，另两种为 `0.115/0.137`，四象限配对结论也完成了跨场景复核。

### 第二个测试场景复核：scene12 / frame 000000

scene12 中 label 140 继续覆盖金属餐具，label 160 覆盖透明瓶，标签语义完成第三个几何场景的视觉复核。该场景也说明“某类传感器永远最好”并不成立：

- 全图 RMSE：D435 `59.5 mm`、L515 `36.0 mm`、I-ToF `99.8 mm`；
- 反光 label 140 RMSE：D435 `209.4 mm`、L515 `69.5 mm`、I-ToF `257.8 mm`；
- 透明 label 160 RMSE：D435 `84.0 mm`、L515 `74.7 mm`、I-ToF `90.4 mm`。

其中反光 D435/L515 的大误差有明显边界成分：mask 腐蚀后 RMSE 分别降至 `100.7/17.0 mm`，而 I-ToF 仍为 `297.4 mm`。这进一步说明必须同时报告 material interior 和 boundary，而不能用一个材质平均值概括传感器机理。

scene12 平均 DoLP 只有约 `0.071`，显著低于 scene10/13 的约 `0.14--0.15`。对应地，DoLP 检测 50 mm silent error 的全图 AUROC 降至 D435 `0.526`、L515 `0.692`、I-ToF `0.640`，材质内部接近随机。这个反例很重要：偏振有价值，但在弱偏振场景不能被强制使用，模型必须具备可靠回退机制。

scene12 的 PPFT 象限配对残差仍最低（`0.0556`），但与其他配对（`0.0619/0.0654`）差距较小；因此 pair-sum 是支持证据而非绝对角度标定。

## 本次 checkpoint 决策

### 当前保留的方向

> **面向透明与反光场景的偏振引导深度异常检测与跨传感器增强**

它比泛化的“偏振辅助三维重建”更具体，也比“再做一个融合模块”更容易被证伪和量化。

### 假设状态

- H1 不同传感器存在不同系统错误：跨 3 个几何场景初步支持；
- H2 偏振有非冗余价值：混合证据，强偏振场景支持、弱偏振和材质内部存在反例；
- H3 未见真实传感器泛化缺口：尚未运行模型，不能宣称；
- H4 双可靠性融合有效：尚未运行模型，不能宣称；
- H5 silent-error 检测有价值：跨场景初步支持。

### 尚未允许做的事

- 不启用自动改网络循环；
- 不宣称 DoLP 可以直接检测所有错误；
- 不把四帧诊断当作统计论文结果；
- 不下载 159 GiB 整包；
- 不在 RTX 5090 上盲装 PyTorch 1.9/1.10 + CUDA 11.x。

### 下一执行批次

1. 将选择性审计扩展到 12 帧，并按几何场景而非视频帧统计区间；
2. 从标定/跨帧并集建立固定 sensor support mask；
3. 发送 `depth_research/evidence/author_questions.md` 中的数据约定问题；
4. 准备约 400 GiB 独立数据盘；
5. 在现代 PyTorch 单 GPU 环境迁移 PPFT 作者权重，先做一帧推理；
6. 固定基线后执行 leave-one-real-sensor-out，只有缺口复现才进入方法阶段。

## 2026-10-26：双机器部署规划

### 当前机资源复核

- CPU：Core Ultra 9 285K，24 个在线逻辑 CPU；
- RAM：125 GiB、约 68 GiB available；
- swap：约 9.2/9 GiB 已使用，存在其他负载；
- GPU：RTX 5090 D 24 GiB，但检查时只剩约 13 GiB，属于共享资源；
- 根盘：仅剩约 6.6 GiB、98% 使用率，已低于 10 GiB 安全线；
- 本项目约 669 MiB，不擅自删除其他用户/系统文件。

决定：当前机停止继续下载、重环境安装和训练，只承担代码、文档、轻量测试及远端结果分析。

### HAMMER 容量核算

通过远程 ZIP 中央目录统计，而非估算：

- 完整 ZIP：158.66 GiB；完整解压：171.07 GiB；
- 项目实际需要的非 naked polarization 视角数据：62.00 GiB；
- 公开 PPFT full-resolution float64 cache 预计 145.8 GiB；
- 本项目 downsample=4 float32 cache 预计 4.56 GiB。

因此 1 TB 训练盘足够，但不应采用“完整解压 + 再复制 + 官方 float64 cache”的浪费路径。

### 已增加并验证的远端工具

- `remote_preflight.sh`：只读机器/网络预检，shell 语法检查通过；
- `inventory_hammer.py`：生成精确存储清单；
- `prepare_hammer_selected.py`：本地 ZIP 中选择性、原子、可续提取 62 GiB 数据，并生成 CRC manifest；已用微型 ZIP 验证路径过滤、naked 排除和 PPFT 目录转换；
- `build_ppft_polar_cache.py`：紧凑偏振 cache；已在 4 个真实 HAMMER 样本上验证，输出 `208x272x3 float32`，约 679 KiB/帧。

完整分工和远端步骤见 `11_compute_and_data_deployment_plan.md`。下一步必须先取得 RTX 5080 机器的预检输出，再决定精确 PyTorch 安装命令。

### 用户确认的训练端条件

2026-10-26 已确认远端为寝室个人电脑：RTX 5080、约 1 TB 持久磁盘、可 SSH、可联网、允许长期后台任务。训练端基本条件满足；待提供 SSH 入口后执行只读预检。

### 本轮发现的工程问题

1. 完整 HAMMER 无法存入当前磁盘；
2. 远程 ZIP 中央目录约数十 MiB、条目超过 43 万，重复远程解析较慢；
3. 已为 Range reader 增加持久块缓存，后续重复查询不应重新下载中央目录；
4. PPFT 老版本依赖与 RTX 5090 D 的兼容性尚未测试；
5. 当前 Python 3.14 适合统计脚本，但不应直接作为旧版深度模型环境。
6. 驱动为 595.58.03、系统报告 CUDA 13.2；检查时其他进程占用约 10--11 GiB 显存，实际空闲约 12--13 GiB。PPFT 完整训练不能默认独占 24 GiB，需要另行安排 GPU 时段。

### 下一步

1. 利用已缓存中央目录选择训练/测试场景中相隔较远的 20--50 帧；
2. 查明实例 ID 到对象类别/材质的映射；
3. 生成按实例、边界、距离和缺失类型分层的统计；
4. 联系/核查 HAMMER 偏振角度约定；
5. 单独创建兼容 PyTorch 的模型环境，优先跑 PPFT 作者权重而不是直接全量训练；
6. 在获得额外数据盘之前不下载完整 HAMMER。

## 2026-10-26：RTX 5080 训练端启动并完成 PPFT 真实小样本推理

### 训练端实测与部署修正

- 本节记录的是另一台训练端，不覆盖上文 5090 控制端的历史预检；
- CPU：AMD Ryzen 9 9950X3D，32 个逻辑 CPU；RAM：44 GiB；
- GPU：RTX 5080 16 GiB；复用 `depthbench` 的 Python 3.10、PyTorch
  2.11.0+cu128、torchvision 0.26.0+cu128，已确认包含 `sm_120` 并能实际执行
  CUDA FP16 矩阵乘；
- ext4 根分区开始时约有 343 GiB 可用。大容量 NTFS 分区首次写入长时间阻塞，
  因而完整 ZIP、选择集和 cache 均先放 ext4；ZIP 校验提取后再释放；
- 完整 HAMMER ZIP 已在 tmux 中可续传下载，记录本节时约为
  `16 GiB / 158 GiB`；完整结果尚未产生。

### PPFT 现代推理兼容层

1. 固定上游 commit `9b1145d87e50895fd17068fad9cec1199092f67a`；
2. 保留作者模型定义和 checkpoint，以 `torchvision.ops.deform_conv2d` 替代旧
   DCN 前向，并只声明单卡推理兼容，不声明 Apex/DDP 训练已复现；
3. 新增零 offset/mask=1 时与标准卷积一致的测试；当前共 14 项测试通过；
4. checkpoint 必须 `strict=True` 加载，且运行参数会与 checkpoint 中的
   `prop_time/prop_kernel/affinity/conf_prop/pol_rep` 等行为参数核对；
5. 新增 batch=1、模型只加载一次、每个 frame-sensor 原子落盘的可续传 split
   评测入口。四帧重跑时 12 个 record 全部跳过，文件 mtime 未改变；
6. raw 偏振路径已逐值对照作者 `process_hammer.py`：保持 float64 至最终七通道
   tensor 转 float32，`I==0`、`Q==0` 的替换和输出完全一致；
7. 指标同时输出本项目 coverage-aware 协议和作者 `cfmetric.py` 协议，后者保留
   zero prediction，并按每帧算术平均，以便直接比较论文 Table 2。

### 作者 checkpoint 与样本完整性

- checkpoint 最终大小：`1,083,919,501` bytes；
- SHA-256：`551ee4fcdbb17f11f6ff3a886ad28469abce52f68cfbca9c0ed0108e3f7512fa`；
- 内容：epoch 24，`net` 共 1663 keys；同时包含 optimizer、scheduler、Apex
  AMP state 和训练参数；
- 本机 PPFT 构造后严格加载 1663/1663 keys 成功；模型唯一参数量
  90,823,661（checkpoint 因共享模块别名共保存 174,380,721 tensor elements）；
- 四帧样本共 28 个文件全部逐项通过
  `depth_research/evidence/hammer_sample_checksums.sha256`；
- 四帧 raw audit 完成：4 frame × 3 sensor，共 12 条 frame 记录，无缺失模态。

### 数值精度决策

全模型 FP16 autocast 在真实作者权重上产生整幅 NaN（3 个传感器均为
56,576/56,576 NaN），因此不得用于指标。FP32 输出全部有限，单帧三传感器
峰值仅约 541.2 MiB，远低于 16 GiB；论文交叉验证改用 FP32。FP16 选项只保留
作诊断，并在首个非有限输出处停止。

### 真实帧结果（scene13_traj1_1/000000，作者指标口径，FP32）

| Sensor | RMSE (mm) | MAE (mm) | delta1 | 推理时间（首个/稳态） |
|---|---:|---:|---:|---:|
| D435 | 22.0843 | 9.1008 | 0.995740 | 0.197 s（首个 CUDA 调用） |
| L515 | 21.8089 | 10.5472 | 0.995263 | 0.0158 s |
| I-ToF | 31.2048 | 19.7119 | 0.990172 | 0.0148 s |

这些是单帧结果，只证明 checkpoint、数据预处理和现代推理链路可运行，不能和
论文 946 帧汇总值直接等同。

该帧的 provisional material slice 也保留了反例，而非只报告总体改善：三个
传感器在透明 label 160 上 RMSE 均明显下降；但 L515 的反光 label 140 MAE 从
`14.58 mm` 上升到 `16.72 mm`，腐蚀后内部区域也从 `12.11 mm` 上升到
`13.32 mm`。这仍是单帧、临时 label 语义，提示后续必须汇总材质内部与边界，
不能用全图均值替代 H2/H4 验证。

### 四帧可续传冒烟结果（混合 train/val/test，非论文结果）

| Sensor | mean RMSE (mm) | mean MAE (mm) | mean delta1 |
|---|---:|---:|---:|
| D435 | 24.7628 | 10.6326 | 0.996437 |
| L515 | 22.0537 | 9.7565 | 0.996597 |
| I-ToF | 31.9806 | 17.0341 | 0.991351 |
| 三传感器平均 | 26.2657 | 12.4744 | 0.994795 |

紧凑 downsample=4 float32 `[I, rho, phi]` cache 与 raw float64 作者路径在这 12
条记录上的最大差异为 RMSE `0.002901 mm`、MAE `0.001597 mm`。该差异当前远小于
论文报告精度，但全量报告仍须注明 cache 在 AoLP 周期编码前发生 float32 量化。

### 当时尚未完成与下一步（后续状态见下一节）

1. 等待完整 ZIP 下载完成，核对长度 `170,457,339,555`、ZIP CRC 和 inventory；
2. 选择性提取约 62 GiB，构建约 4.6 GiB compact cache 和跨帧固定 support；
3. 运行 946 帧官方 test split，并对照论文 Table 2：D435 `24.78/10.66`、
   L515 `23.84/10.47`、I-ToF `37.27/21.37`、All `28.63/14.17`
   （RMSE/MAE，mm）；
4. 在 full split 结果交叉验证通过前，不把 torchvision DCN 迁移称为数值等价；
5. AoLP 绝对角度仍待作者确认；DoLP 和 checkpoint 推理可以继续，但不宣称绝对
   物理方向结论；
6. Gate 3 仍未通过，不启动自动改网络和方法训练。

## 2026-10-26：PPFT 官方 946 帧 test split 独立复现完成

### 数据完整性与固定 support

- 按作者 `data_paths/hammer_test.txt` 提取 scene13/14 的 946 帧、7 个模态，最终
  恰好 `6,622` 个 PNG；每模态 946 个，无缺失、无额外文件、无 `.part`；
- 逐文件 SHA-256 清单：
  `/home/chocbrownie0524/poldepth/manifests/hammer_test_remote.sha256`，清单自身
  SHA-256 为 `ac6d119afac6d84ffdf8d3c17068f2264af92437c3fc5e157f7c74d513f2a16b`；
- inventory 共 `8,449,894,843` bytes；RGB/depth/GT/instance 均为
  `1088x832`，polar composite 均为 `2176x1664`，格式和 bit depth 全部一致；
- 946 帧 compact cache 完成：`208x272x3 float32`，946 个 NPY，合计
  `642,371,840` bytes，无临时文件；
- 以“至少 1% 帧出现正深度”构建固定 support：D435 `0.996572`、L515
  `0.882963`、I-ToF `0.456698`。这是 test 数据驱动的诊断近似，不冒充标定 FoV。

### Table 2 主结果：raw float64 作者预处理、FP32、batch=1

作者 test loader 将 946 帧扩展为 2,838 条 sensor-frame 记录。全部记录均原子
落盘且输出有限；峰值显存 `541.21 MiB`，本次评测循环约 `122.6 s`。作者指标
按源码对每条记录先算指标、再做算术平均：

| Sensor | 本次 RMSE (mm) | 论文 | 差值 | 本次 MAE (mm) | 论文 | 差值 |
|---|---:|---:|---:|---:|---:|---:|
| D435 | 24.78884 | 24.78 | +0.00884 | 10.65956 | 10.66 | -0.00044 |
| L515 | 23.84283 | 23.84 | +0.00283 | 10.46670 | 10.47 | -0.00330 |
| I-ToF | 37.27167 | 37.27 | +0.00167 | 21.37325 | 21.37 | +0.00325 |
| All | 28.63444 | 28.63 | +0.00444 | 14.16650 | 14.17 | -0.00350 |

delta1 同样一致：D435 `0.995036`、L515 `0.994976`、I-ToF `0.987296`、All
`0.992436`。所有 RMSE/MAE 与论文表值的绝对差分别不超过 `0.0089 mm` 和
`0.0035 mm`。因此，**现代 torchvision DCN 推理路径已通过 Table 2 结果级
交叉验证**；这不等同于证明新旧 DCN 对任意输入逐算子/逐 bit 等价。

主报告：
`/home/chocbrownie0524/poldepth/runs/ppft_hammer_test_fp32_raw/report.json`，
SHA-256 `e536bab6e48e7c73b1c05cf6f8d1b73fe57591144a870051158c6d4a4f0bc5ca`。
报告同时固化 checkpoint、数据清单、split、view direction 和三个本地执行模块的
SHA-256，防止续传时混用不同代码或数据。
可提交的小型复现摘要见
`depth_research/evidence/ppft_hammer_test_reproduction.json`。

### compact cache 全量交叉验证

相同 2,838 条记录用 compact float32 cache 重跑完成，循环约 `85.4 s`。与 raw
作者路径相比：

- All mean RMSE 差 `+0.0000143 mm`，mean MAE 差 `+0.00000036 mm`；
- 单条记录最大 RMSE 差 `0.010543 mm`，最大 MAE 差 `0.004088 mm`；
- 论文两位小数结论完全不变。

因此 compact cache 可用于后续大规模实验，但主复现数字仍引用 raw 路径。
对照文件：
`/home/chocbrownie0524/poldepth/runs/ppft_hammer_test_raw_vs_cache.json`。

### coverage-aware pooled 诊断（不同于论文算术平均口径）

按有效预测像素池化后，raw sensor 到 PPFT 的全图结果为：

| Sensor | raw coverage | raw RMSE/MAE (mm) | PPFT coverage | PPFT RMSE/MAE (mm) |
|---|---:|---:|---:|---:|
| D435 | 0.7322 | 48.31 / 23.61 | 1.0000 | 25.57 / 10.65 |
| L515 | 0.8210 | 80.79 / 32.74 | 1.0000 | 24.35 / 10.46 |
| I-ToF | 0.4243 | 77.48 / 35.35 | 1.0000 | 39.33 / 21.36 |
| All | 0.6591 | 69.73 / 29.92 | 1.0000 | 30.52 / 14.16 |

这里的 pooled RMSE 不能和论文“每帧 RMSE 的算术平均”混用。provisional label
140/160 和 20 mm GT boundary 的全量切片也已汇总。单帧 L515 label 140 反例在
全量池化后不再是整体退化（MAE `25.19 -> 15.42 mm`，内部
`21.65 -> 12.61 mm`），但仍证明逐帧收益不保证单调，后续应报告退化帧比例，
而不只报告 pooled 均值。汇总文件：
`/home/chocbrownie0524/poldepth/runs/ppft_hammer_test_coverage_slices.json`。

### 当前状态与下一步

1. PPFT 作者 checkpoint 的官方 test split 复现已完成；Phase 3 中该项通过；
2. 完整 `158 GiB` ZIP 已从约 `19 GiB` 断点恢复下载；代理 TLS 出错后改为直连，
   aria2 继续读取原 `.aria2` 位图，不重复已有块；
3. 完整 ZIP 到齐后仍须验证长度 `170,457,339,555`、ZIP CRC、inventory，并提取
   7,207 帧约 62 GiB 选择集；
4. 继续运行全部 raw audit、CompletionFormer/其他 baseline、输入消融、偏振/深度
   压力测试和 leave-one-real-sensor-out；这些未完成前 Gate 3 仍不通过；
5. AoLP 绝对角度约定仍待作者确认，不宣称绝对物理方向已验证；
6. 旧 Apex/DDP 训练与 DCN backward 尚未迁移，不把推理复现外推成训练复现。

## 2026-11-01：完整 HAMMER 数据与全量评测完成

### 完整归档闭环

- 完整 ZIP 长度严格等于 `170,457,339,555` bytes；
- SHA-256：`af57d2d51e6308e501e40bb6f5909b58c60bc708662ba73c23bdf4de096615af`；
- `unzip -tqq` 对 432,596 个文件完成全量解压/CRC 检查，退出码 0；
- 本地 inventory 与仓库 `hammer_storage_inventory.csv` 逐字节一致；
- 选择性提取 57,689 文件、`66,574,983,990` bytes，共 32 trajectories；manifest
  中所有 size 与磁盘文件一致，无缺失、额外文件或 `.part`；
- 作者 train/val/test 列表合计 7,207 个唯一帧，7 个核心模态共 50,449 文件全部
  存在；先前 6,622 个 test PNG 的 SHA-256 也与本地提取逐项一致；
- 归档通过以上验证后已删除，释放约 159 GiB；当前选择集约 63 GiB。

### 全数据 cache 与固定 support

- 7,207 个 compact NPY 全部为 `208x272x3 float32`，总计
  `4,893,841,280` bytes，无临时文件；cache manifest SHA-256 为
  `a3cb0c5780bcadfe3728aebc0a1b02737ee29e5e0047ec2af73698440aed0cfd`；
- 全数据固定 support：D435 `0.998790`、L515 `0.925798`、I-ToF `0.468031`；
- HAMMER 含一个无配对 GT/RGB 的字面文件
  `scene2_traj2_1/depth_d435/{06d}.png`。support builder 现以 GT 帧为锚，明确记录
  并排除该归档伪影；三种传感器分母统一为 7,207 帧。

### 7,207 帧 full-resolution raw audit

将 silent-error 的三个阈值改为共享一次 score 排序，并按 32 trajectory 分片、
24 workers 原子执行；四帧回归的六类 CSV 与旧实现逐字节一致。全量耗时约
`1:01:50`，输出：

- 21,621 frame rows；
- 193,233 label rows；
- 7,207 polarization rows；
- 108,105 DoLP-bin rows；
- 21,621 depth-boundary rows；
- 302,694 silent-error detection rows。

全分辨率、coverage-aware、按像素池化结果：

| Split | Sensor | Coverage | RMSE / MAE (mm) |
|---|---|---:|---:|
| All | D435 | 0.8268 | 70.33 / 33.58 |
| All | L515 | 0.8213 | 68.12 / 22.26 |
| All | I-ToF | 0.4207 | 80.76 / 33.59 |
| All | 三传感器 | 0.6896 | 71.73 / 29.09 |
| Test | D435 | 0.7331 | 49.71 / 23.58 |
| Test | L515 | 0.8214 | 80.74 / 32.72 |
| Test | I-ToF | 0.4243 | 77.66 / 35.35 |

固定 support 内 I-ToF coverage 从全图 `0.4207` 提升到 `0.8969`，确认其大量零值
来自较小 FoV；但 support 内 RMSE 仍为 `79.73 mm`，说明视场差异不能解释全部
误差。20 mm GT boundary 上三传感器 pooled RMSE 均很高（D435 `150.90`、
L515 `129.46`、I-ToF `147.10 mm`）。provisional label 160 的总体 RMSE/MAE
为 `197.34/130.76 mm`，明显高于 label 140 的 `89.03/40.91 mm`。

50 mm silent-error 的逐帧平均 AUROC/AP：DoLP `0.641/0.266`，
one-minus-confidence `0.599/0.220`，pair residual `0.531/0.172`，临时材质 oracle
`0.611/0.274`。因此 H5 获得全量支持，但 DoLP 只能提供中等、场景依赖的排序
信号，不能单独作为通用错误检测器。

### PPFT 全 7,207 帧推理

compact cache、FP32、batch=1 共完成 21,621 条有限输出，无 `.part`：

| Split | Frames / records | D435 RMSE/MAE | L515 RMSE/MAE | I-ToF RMSE/MAE | All RMSE/MAE |
|---|---:|---:|---:|---:|---:|
| Train | 5,253 / 15,759 | 11.04/4.15 | 10.02/2.83 | 12.45/5.64 | 11.17/4.21 |
| Val | 1,008 / 3,024 | 50.29/22.56 | 38.67/13.84 | 56.30/27.54 | 48.42/21.31 |
| Test | 946 / 2,838 | 24.79/10.66 | 23.84/10.47 | 37.27/21.37 | 28.63/14.17 |

这里仍采用作者“逐 sensor-frame 指标算术平均”的口径；train 是训练内描述，不能
当泛化结果。另按同一 4x 网格池化 coverage-aware 指标后，PPFT 在三 split 均给出
1.0 coverage。Val 的 L515 在 raw 有效像素上的 RMSE/MAE 为 `37.65/12.29 mm`，
PPFT 全域为 `41.12/13.85 mm`；由于 coverage 从 `0.833` 增至 `1.0`，两者不是
同一像素集合，但这是后续 common-support/paired-pixel 消融必须保留的潜在反例。

### 复现状态

作者 checkpoint 的数据准备、严格加载、官方 Table 2、完整 train/val/test 推理、
全量 raw/material/boundary/DoLP/silent-error 评测均已完成。可提交摘要见
`depth_research/evidence/ppft_hammer_full_evaluation.json`。

仍不纳入“已复现”的部分：旧 DCN 逐算子等价、Apex/DDP 训练 backward、绝对
AoLP 角度约定，以及 CompletionFormer/其他 baseline 与 leave-one-sensor-out。
这些属于下一阶段对照和方法缺口验证，不影响本次作者 checkpoint 推理复现结论。
