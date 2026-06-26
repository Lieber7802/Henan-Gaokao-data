# 河南高考录取统计 OCR 项目

本项目用于把《2025年理科录取统计》这类图片式 PDF 中的招生录取表格，经过 PP-StructureV3 识别和专用后处理，整理成可统计的 Excel。

当前仓库只保存代码、配置、测试、说明文档和小体积参考表。原始 PDF、OCR 输出、渲染图片、虚拟环境和中间产物不进入 Git；原始 PDF 请单独传到项目根目录。

## 目录说明

- `configs/`：试点页和章节配置。
- `scripts/`：OCR 运行、PP-Structure 输出解析、最终 Excel 构建、质量扫描脚本。
- `tests/`：解析规则和试点契约测试。
- `docs/chapter3_major_admission_reuse_notes.md`：本科一批经验沉淀，本科二批复用说明。
- `requirements/paddleocr-pilot.txt`：PaddleOCR/PaddleX 及数据处理依赖，不包含 `paddlepaddle` 本体。
- `河南高考物理类录取统计.xlsx`：目标统计表结构参考。

## 不上传的内容

- `2025年理科录取统计.pdf`
- `tmp_input_2025_science_stats.pdf`
- `output/`
- `tmp/`
- `.venv-paddleocr/`
- `workbook_build/node_modules/`

这些内容要么体积过大，要么可以重新生成。换机器后，把 PDF 放回项目根目录即可继续跑。

## 新机器初始化

```powershell
git clone <你的仓库地址>
cd gaokao_data

python -m venv .venv-paddleocr
.\.venv-paddleocr\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

先按目标机器安装 PaddlePaddle。GPU 版命令和 CUDA/Python/显卡有关，不要直接照搬公司电脑的 CPU 环境。官方入口：

- PaddlePaddle 安装指南：https://www.paddlepaddle.org.cn/documentation/docs/zh/install/index_cn.html
- PaddleX 50 系显卡说明：https://paddlepaddle.github.io/PaddleX/3.4/installation/paddlepaddle_install.html

安装好 PaddlePaddle 后，再安装本项目依赖：

```powershell
python -m pip install -r requirements\paddleocr-pilot.txt
python -c "import paddle; print(paddle.__version__); print(paddle.device.get_device()); paddle.utils.run_check()"
```

如果家里是 Windows + NVIDIA 50 系显卡，优先看 PaddleX 文档里的 50 系专用 wheel 说明。

## 运行本科二批

把 `2025年理科录取统计.pdf` 放到项目根目录后运行：

```powershell
.\.venv-paddleocr\Scripts\python.exe scripts\run_chapter3_batch2_full_pipeline.py
```

输出位置：

- 原始 PP-Structure 结果：`output/ppstructure_full/chapter3_batch2/raw/`
- 宽表 JSON：`output/ppstructure_full/chapter3_batch2/review/major_history_chapter3_batch2_data.json`
- 最终 Excel：`output/ppstructure_full/chapter3_batch2/preview/本科二批分数线.xlsx`
- 进度状态：`output/ppstructure_full/chapter3_batch2/review/pipeline_status.json`

## 质量检查

```powershell
.\.venv-paddleocr\Scripts\python.exe -m pytest tests

.\.venv-paddleocr\Scripts\python.exe scripts\check_major_history_workbook.py output\ppstructure_full\chapter3_batch2\preview\本科二批分数线.xlsx --batch 本科二批 --output-json output\ppstructure_full\chapter3_batch2\review\workbook_quality_check.json
```

本科二批跑完后，先看 `workbook_quality_check.json` 和 `major_history_chapter3_batch2_data.json` 里的 `review_rows`，再决定是否需要改解析规则。
