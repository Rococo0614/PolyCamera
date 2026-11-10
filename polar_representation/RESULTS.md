# P0–P3 训练前实验结果

**日期：** 2026-11-10

**状态：** P0 远端 release 与 split 已冻结；P1 test-only probe、P2 test 审计和 P3 解析仿真已完成；
P0 本地全量完整性与 P1 train-fitted 对照等待 processed train 下载完成

## 1. P0：release 与场景划分

- Hugging Face revision：`ea2829b16b02a25183708702b73592577ae9c313`；
- 数据许可：CC BY-NC 4.0；
- 33,055 个 processed LFS 文件，合计 `64,846,736,102` bytes；
- 6,500 个输入 captures；所有组均包含 `000/045/090/135/rgb`；
- 发布版实际为 59 个 train 场景、8 个 test 场景，不是论文所写的 56/11；
- train/test GT 五文件哈希签名完全相同的场景数为 0；
- easy/hard 重叠的 44 个 train GT 已确认逐表示相同；
- 冻结 split：fit/validation/test = `49/10/8` 场景；
- 远端 manifest 33,055 条，gzip SHA-256：
  `7a0a833919a24b94d120dc378584a5ca50425724533e0722731f0ecb57c01bc4`。

证据：

- `evidence/polargb_release_v1.json`
- `evidence/polargb_scene_split_v1.json`
- 仓库外 `/mnt/ssd/polycamera_offline/manifests/polargb_processed_v1.tsv.gz`

当前完整 processed release 正在下载到 `/mnt/ssd`。下载器对每个新文件核对 size 和 SHA-256；
完成后还会独立执行一次全量 hash + PNG decode 审计。

## 2. P1：test-only 无学习 probe

当前仅使用 release test 的 188 captures / 8 场景。固定方向和 GT affine 均未作为可部署方法；
最终 P1 仍需等待 fit 场景，完成 train-selected fixed angle 与 train-fitted affine。

| 方法 | PSNR micro | PSNR scene-macro | 相对 RGB | SSIM |
|---|---:|---:|---:|---:|
| RGB identity | 15.68 | 17.24 | — | 0.7839 |
| mean4 / S0 强度 | 15.66 | 17.20 | −0.03 dB | 0.7841 |
| median4 | 15.26 | 16.88 | −0.42 dB | 0.7730 |
| min4 | 18.76 | 19.64 | **+3.08 dB** [1.22, 4.95] | **0.8178** |
| virtual_min | 18.38 | 19.38 | **+2.70 dB** [1.19, 4.25] | 0.8169 |
| 单方向 90°（test diagnostic） | 17.40 | 18.31 | +1.72 dB [−1.27, 4.75] | 0.7861 |
| RGB + 逐图 GT affine ceiling | 18.30 | 20.06 | +2.62 dB [1.47, 3.79] | 0.8032 |
| min4 + 逐图 GT affine ceiling | 20.21 | 21.29 | +4.53 dB [2.43, 6.47] | 0.8185 |
| per-sample 最佳角 ceiling | 19.06 | 19.70 | +3.38 dB [1.41, 5.11] | — |

解读：

1. `min4/virtual_min` 的 PSNR 和 SSIM 同时提高，不能只用“整体变暗”解释；
2. 但 RGB 的 GT 色彩 affine ceiling 已能增加 2.62 dB，颜色/曝光混杂很强；
3. 90° 的区间跨 0，不能在 test 上把它宣布为固定最佳方向；
4. `min4` 在无玻璃 GT 上只有 31.47 dB / SSIM 0.9614，而 mean4 为 53.40 dB /
   SSIM 0.9985。简单最暗方向会改变本来干净的图像，必须有质量门控。

证据：`evidence/polargb_test_probe_v1.json`。

## 3. P2：processed test 偏振一致性

### Mixed input（188 captures）

| 量 | sample mean | sample p95 |
|---|---:|---:|
| stored 正交对相对残差 | 0.0481 | 0.1293 |
| 强制 sRGB inverse 后残差 | 0.0946 | 0.2318 |
| 四方向重投影 RMSE | 0.0189 | 0.0560 |
| RGB 与 mean4 MAE | 0.00166 | 0.00171 |
| median DoLP | 0.1272 | 0.2835 |
| 饱和比例 | **6.92%** | **19.92%** |

### Transmission-only GT（8 场景）

| 量 | scene mean | scene p95 |
|---|---:|---:|
| stored 正交对相对残差 | 0.0280 | 0.0316 |
| 强制 sRGB inverse 后残差 | 0.0531 | 0.0587 |
| 四方向重投影 RMSE | 0.00677 | 0.00851 |
| median DoLP | 0.0729 | 0.1949 |
| 饱和比例 | 1.84% | 5.24% |

解读：

- stored 值域比 sRGB inverse 更符合正交对约束，因此当前主分析保留 stored 域；这不是 RAW
  响应标定，仍需 raw audit；
- `_rgb` 几乎等于四方向均值，适合作为同一观测的强度基线；
- mixed 中平均约 6.9% 的方向/颜色样本达到 255，个别 capture 接近 20%，饱和不是边缘问题；
- mixed 的残差、DoLP 和饱和均高于 transmission GT，但这些量同时包含真实反射、插值和裁剪。

证据：

- `evidence/polargb_test_physics_audit_v1.json`
- `evidence/polargb_test_gt_physics_audit_v1.json`

## 4. P3：解析层仿真

当前为 96×96 灰度 Stokes 层仿真，包含 T/R 纹理、DoLP/AoLP、分析器、噪声、增益/偏置、
角度误差和单色 MPFA 双线性重建。它只验证趋势，不代表真实相机。

### 4.1 透射不偏振时

- reflection DoLP = 0：`virtual_min` 相对 mean4 为 0 dB，偏振没有可用分离信号；
- reflection DoLP 从 0.1 增至 1.0，增益随之增加；
- 在当前纹理和强度网格中，30 个组合有 25 个增益超过 0.1 dB；
- 最高增益约 +35.2 dB，出现在高偏振、较弱且未严重裁剪的反射条件。

### 4.2 透射本身偏振时

固定 reflection DoLP = 0.75、AoLP 差 45°：

- 36 个 `transmission DoLP × reflection ratio` 组合中，仅 50% 的增益超过 0.1 dB；
- 增益范围从 **−19.37 dB 到 +12.04 dB**；
- 反射较弱而 transmission DoLP 较高时，`virtual_min` 会把目标自身的偏振成分误删；
- 随反射变强，最暗角重新可能成为有利表示。

### 4.3 噪声、仪器和 MPFA

- 在不饱和的理想四通道条件下 Stokes 可数值精确恢复；
- 噪声 sigma 从 0 增至 0.04 时，`virtual_min` 增益由约 +12.0 dB 降至 +1.8 dB；
- 当前高频纹理上，四张完整图的 +12.0 dB 在单色 MPFA 双线性后变成 **−0.78 dB**；
- 这不是对真实彩色 DoFP 的数值预测，但证明去马赛克不能被视为中性预处理。

### 4.4 Fresnel 入射角依据

空气到折射率 1.5 的无吸收介质，固定观测反射强度比为 0.25、只让 reflected DoLP 按 Fresnel
变化：法向入射 DoLP 为 0，`virtual_min` 增益为 0 dB；30° 为 +4.16 dB，45° 为 +14.18 dB；
在 Brewster 角约 56.31°，反射 DoLP 达 1，增益峰值约 +23.51 dB；继续增大入射角后 DoLP 与增益
再次下降。该扫描把“偏振帮助反光分离”限定为与入射角相关的条件性结论，而不是普遍结论。

证据：

- `evidence/p3_forward_simulation_v1.json`
- `evidence/images/virtual_min_gain_reflection_sweep.png`
- `evidence/images/virtual_min_gain_ambiguity_sweep.png`

## 5. 当前 Gate 判断

| Gate | 状态 | 判断 |
|---|---|---|
| P0 远端 release/split | 通过 | revision、manifest、59/8 和 49/10/8 已冻结 |
| P0 本地完整性 | 进行中 | processed train 下载完成后做独立全量校验 |
| P1 test probe | 通过（只作诊断） | 简单偏振有增量，但颜色混杂和 clean damage 明显 |
| P1 final | 等待数据 | 需要 train-best fixed 与 train-fitted affine |
| P2 processed test | 条件性通过 | stored 域更自洽；饱和比例高，RAW 口径未核实 |
| P3 解析仿真 | 通过（趋势） | 可用区与明确失败区同时存在，质量门控是必需模块 |

当前结果支持继续完成 P1，而不支持直接开始大模型训练。最重要的待验证问题是：

> 使用 fit 场景冻结颜色校正和固定方向后，`min4/virtual_min` 的独立测试增量还剩多少？
