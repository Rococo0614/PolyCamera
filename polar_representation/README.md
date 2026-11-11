# polar_representation

共享偏振表示新主线的训练前 P0–P3 实验包。当前只做数据冻结、无学习基线、物理一致性和
解析仿真，不训练编码器，不把仿真或公开数据表述为自有相机结果。

相关物理、反光分离、偏振恢复和跨任务论文分层见 `LITERATURE.md`。
通用预训练模型的偏振能力、2026 年直接竞争工作、底座选型与公平评测方案见
[`FOUNDATION_MODELS.md`](FOUNDATION_MODELS.md)（文献调研，不是本项目训练结果）。

## 环境

根分区空间不足，数据、缓存、临时文件和完整运行结果均放：

```text
/mnt/ssd/polycamera_offline/
```

运行时使用：

```bash
export PYTHONPATH=/home/jiangrui/PolyCamera/polar_representation/src
PY=/mnt/ssd/polycamera_offline/envs/industrial-reading/bin/python
```

## P0：冻结 release 与场景 split

```bash
$PY polar_representation/scripts/freeze_polargb_release.py \
  --metadata /mnt/ssd/polycamera_offline/cache/polargb/hf_dataset_metadata.json \
  --summary polar_representation/evidence/polargb_release_v1.json \
  --manifest /mnt/ssd/polycamera_offline/manifests/polargb_processed_v1.tsv.gz \
  --split polar_representation/evidence/polargb_scene_split_v1.json
```

完整 processed release 下载并逐文件校验：

```bash
$PY polar_representation/scripts/download_polargb.py \
  --metadata /mnt/ssd/polycamera_offline/cache/polargb/hf_dataset_metadata.json \
  --root /mnt/ssd/polycamera_offline/datasets/polargb \
  --workers 12 --verify-existing
```

## P1：无学习基线

需要完整 train/test：

```bash
$PY polar_representation/scripts/run_polargb_baselines.py \
  --metadata /mnt/ssd/polycamera_offline/cache/polargb/hf_dataset_metadata.json \
  --root /mnt/ssd/polycamera_offline/datasets/polargb \
  --split polar_representation/evidence/polargb_scene_split_v1.json \
  --output polar_representation/evidence/polargb_no_learning_baselines_v1.json
```

固定方向选择和颜色 affine 只使用 fit 场景；release test 只用于最终汇总。

## P2：辐射/偏振一致性

```bash
$PY polar_representation/scripts/audit_polargb_physics.py \
  --metadata /mnt/ssd/polycamera_offline/cache/polargb/hf_dataset_metadata.json \
  --root /mnt/ssd/polycamera_offline/datasets/polargb \
  --subset test --side input \
  --output polar_representation/evidence/polargb_test_physics_audit_v1.json
```

## P3：解析前向仿真

```bash
$PY polar_representation/scripts/run_forward_simulation.py \
  --output polar_representation/evidence/p3_forward_simulation_v1.json \
  --image-dir polar_representation/evidence/images
```

## 测试

```bash
$PY -m unittest discover -s polar_representation/tests
```

## 可选 RAW 对照

下载约 1 GB 的 raw test 后，可核对 2×2 偏振排列、Bayer 去马赛克与 processed release 的关系：

```bash
$PY polar_representation/scripts/audit_polargb_raw.py \
  --raw-root /mnt/ssd/polycamera_offline/datasets/polargb_raw \
  --processed-root /mnt/ssd/polycamera_offline/datasets/polargb \
  --output polar_representation/evidence/polargb_raw_test_audit_v1.json
```
