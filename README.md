# SAF original website

这是用户指定的费托合成催化剂材料数据平台原始网站，可独立本地运行，不含新增的模型预测或训练模块。

项目位置：`D:\Codex\10-projects\SAF`。Windows 不区分 `SAF` 和 `saf`，因此新项目使用独立目录，原 `D:\Codex\saf` 保留。

## 运行

当前电脑已配置项目独立的 `.venv` 环境。双击 `run_site.bat`，访问 http://127.0.0.1:8502/ 。如该地址已经可用，无需重复启动。

新机器先安装 Python 3.12，复制整个文件夹（包括 `outputs/` 中的初始数据库），运行 `setup_site.bat` 安装依赖，再运行 `run_site.bat`。虚拟环境应在目标机器重新创建，不依赖旧 `saf` 的环境。

## 原有功能

1. 平台数据总览：文献统计、数据库筛选、散点图、云雨图。
2. 论文自动下载：DOI 分类、下载队列、PDF 校验和结果导出。
3. 数据自动提取：PDF 提取、预览、确认入库。
4. 数据可视化分析：自动读取数据库，按性能、反应条件、论文信息及材料维度绘图。
5. 使用说明。

源代码来自 https://github.com/z72882743-arch/saf-data-platform 的固定提交 `43336612e47b499653bfa74bb2edc11dcdd9d432`，对应用户给出的 https://z72882743-arch-saf-data-platform-app27-ynhtbs.streamlit.app/ 。应用和配套模块保留上游原始字节，文件哈希见 `docs/upstream-manifest.json`。线上页面当前访问失败、GitHub API 限流，因此未重新确认云端实时部署提交号。

数据库为上游初始副本 `outputs/FT_SAF_catalyst_extraction_wide_table.parquet`，4068 行、438 列。后续入库只影响本项目副本。没有复制旧网站的研究 PDF、凭据或模型文件。页面显示的文献/PDF统计来自数据库元数据，并不表示本文件夹保存了所有原始 PDF。

外部论文下载需要网络及相应访问权限；WebVPN 模式沿用原有浏览器登录和调试端口要求；LLM 提取需在页面配置自己的 API 条件。原仓库的个人批处理文件、日志和凭据未复制。上述外部操作未在离线验收中发起。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c constraints-verified.txt
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m compileall -q app27.py saf_common.py ingest_extraction.py
.\.venv\Scripts\python.exe -m pip check
```

没有配置额外的 lint、格式或类型检查器。原始源文件保持上游格式，避免改变既有逻辑。验收结果见 `docs/verification.md`。
