# FolioQueue

**可重复执行、逐文件保存进度的本地文档转 Markdown 工具。**

[English](README.md) · [设计](docs/design.md) · [验证记录](docs/validation.md)

适合维护本地文档集合和知识库：文件变化后重新转换，未变化的文件跳过，失败文件下次重试。PDF、DOCX、HTML 的底层提取使用 Microsoft MarkItDown；TXT、Markdown、CSV 使用 Python 标准库。

**当前为 0.1.0 alpha。** 项目刚开始，没有成熟用户规模或生产可靠性承诺。它是独立的工作流工具，与 Microsoft、OpenAI 没有隶属关系。

## 安装和使用

需要 Python 3.11 或以上，建议在虚拟环境安装。Windows 的 Python 命令可能是 `py`。

```bash
git clone https://github.com/GokouRuri43/folioqueue.git
cd folioqueue
python -m pip install ".[documents]"
folioqueue plan examples/documents -o demo-output --json
folioqueue convert examples/documents -o demo-output
folioqueue convert examples/documents -o demo-output
```

第一次转换三个示例文件并忽略一个不支持的文件；第二次应跳过三个未变化文件。打开 `demo-output/report.html` 查看结果。

仅需要 TXT、Markdown、CSV 时，执行 `python -m pip install .`，核心没有第三方运行依赖。GitHub Releases 提供 wheel 和源码包；**目前没有发布到 PyPI**。

转换自己的文件夹：

```powershell
folioqueue convert 'C:\My Documents' -o 'C:\Markdown Output' --workers 2 --timeout 60
```

输入和输出目录必须互不包含。默认递归扫描，跳过以点开头的文件/目录、符号链接和 Windows junction。支持 `.txt .md .csv .html .htm .docx .pdf`，不支持 OCR、旧版 `.doc`、表格文件、演示文稿、音视频、压缩包或 URL。

## 行为约定

- 每个文件在独立进程中转换，有超时与大小检查；一个文件失败不会让其他文件一起失败。
- 每完成一个文件保存一次检查点；中断后重新运行原命令即可继续。
- SHA-256 同时检查源文件和输出；修改时间不变也能检测到内容变化。
- 手动修改的输出或工具未记录的同名文件会报冲突，`--force` 也不会覆盖。请将冲突文件另存，或使用新输出目录。
- 保留原扩展名，例如 `报告.pdf` 输出为 `documents/报告.pdf.md`，避免与 `报告.docx` 冲突。
- 源文件被删除后，旧输出会保留并标记为 stale；更新失败也可能保留上次成功结果。导入知识库前需要检查报告。
- 报告包含相对文件名和状态，不包含提取正文或转换库的原始异常。文件名仍可能敏感。
- 转换流程不配置云服务或 LLM，不启用 MarkItDown 第三方插件。依赖需要预先安装。

## 常用选项

```bash
folioqueue convert ./documents -o ./out --types txt,csv,docx
folioqueue convert ./documents -o ./out --encoding gb18030
folioqueue convert ./documents -o ./out --max-input-mb 64 --max-output-mb 32
folioqueue convert ./documents -o ./out --force --json
```

并发默认 2，范围 1–16；转换子进程默认超时 60 秒。超时不包含扫描、校验和计算、复制和写入。CSV 为逗号分隔，第一行作为表头；文本默认严格按 UTF-8（兼容 BOM）解码。

退出码：`0` 无失败，`1` 有文件失败/计划冲突，`2` 参数或运行环境错误，`130` 被中断。`report.html` 和 `report.json` 是最近一次完成的运行报告，不代表目录中每个 Markdown 都一定是最新内容。

`.folioqueue/state.json` 包含绝对源目录和校验记录，不应手动修改或公开分享。源目录迁移时请使用新输出目录。强制终止后可能在 `.folioqueue/work` 留下源文件快照，确认没有运行中的任务后可手动删除该目录。

独立进程用于隔离普通故障，**不是安全沙箱**。处理不可信文件需要额外沙箱；大小检查也不是操作系统级内存限制。详见 [安全边界](SECURITY.md)。

欢迎提交可复现问题和脱敏样例。AI 辅助开发记录不等于真实用户反馈；项目的使用效果需要实际使用来验证。
