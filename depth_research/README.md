# depth_research

偏振辅助商品级深度传感器增强的可复现实验目录。当前只实现数据审计和固定评测基础，不包含尚未被证据支持的“最终网络”。

## 目录

```text
configs/                 固定研究协议和实验配置
evidence/                文献与产品证据矩阵
src/poldepth/            偏振表示、质量图和深度指标
scripts/                 数据审计入口
tools/remote_zip.py      HTTP Range 选择性读取大型 ZIP
tests/                   物理公式和指标单元测试
data/                    数据（忽略，不提交）
results/                 生成结果（忽略，不提交）
program.md               基线稳定后才能启用的自动实验协议
results_template.tsv     实验登记表模板
```

## 当前执行顺序

1. 远程列出 HAMMER ZIP 中与目标帧相关的文件；
2. 选择性下载少量 RGB、polar、三种 depth 和 GT；
3. 运行原始深度审计；
4. 核实偏振四象限的角度定义；
5. 再开始 baseline 推理。

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

批量汇总所有已选择性下载的样本：

```bash
.venv/bin/python depth_research/scripts/batch_audit.py \
  --root depth_research/data/hammer_sample \
  --output depth_research/results/batch_audit
```

输出包括逐帧、逐标签、深度边界、FoV/support、DoLP 分箱、silent-error 检测和偏振质量 CSV。相邻视频帧不应被当作独立样本计算统计显著性。

核查 label ID 对应的物体/材质：

```bash
.venv/bin/python depth_research/scripts/visualize_labels.py \
  --rgb path/to/rgb/000000.png \
  --label path/to/_instance/000000.png \
  --output depth_research/results/sample_audit/000000_labels.png
```

## 自动实验

`program.md` 借鉴 `karpathy/autoresearch` 的“冻结评测—单变量实验—保留/丢弃—完整记录”思想，但增加了多指标约束、真实传感器留出、测试集保护和 GPU 预算。当前尚未达到启用条件，不能让代理直接循环改网络。
