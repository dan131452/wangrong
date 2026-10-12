# AIGC 数字绘本 · 三国故事系列

用 AIGC 工作流做的儿童数字绘本合集，目前两本（共 27 页）：

- **《草船借箭》**（15 页，封面 + 13 故事 + 封底）：改编自《三国演义》第四十六回，讲诸葛亮的智慧——观察、了解、提前准备
- **《三顾茅庐》**（12 页，封面 + 10 故事 + 封底）：改编自第三十七、三十八回，讲刘备的诚意——以礼待人、坚持不解

两本书共享诸葛亮形象设定（青纶巾、白袍、羽扇），跨书角色一致。

## AIGC 工作流

```
GLM（文案+提示词） → 生图 API / 豆包等工具（插画） → 本项目（自动排版） → 成品
data/books/*.json        assets/images/           uv run build      dist/
```

## 快速开始

> **换了一台新电脑？** 见下方[新电脑从零启动](#新电脑从零启动)。

```bash
uv sync                                  # 安装依赖
uv run picture-book serve                # ★ 启动 AIGC 生成器网页（真实生图模式）
uv run picture-book serve --demo         # ★ 演示模式：不调 API，占位图模拟生成（课堂演示稳）
uv run picture-book check                # 查看两本书哪些插画还没就位
uv run picture-book gen                  # 命令行批量生成缺失插画（配置见 .env）
uv run picture-book build                # 生成所有成品：每本书 PDF + PPTX + 静态网页阅读器
uv run picture-book build --book san-gu-mao-lu            # 只构建《三顾茅庐》
uv run picture-book prompts              # 从 books JSON 重新生成 data/prompts.md
```

## 新电脑从零启动

### 1. 装 uv（唯一的系统级依赖）

本项目用 [uv](https://docs.astral.sh/uv/) 管理 Python 与依赖，**不需要自己装 Python**（uv 会按 `pyproject.toml` 里的 `requires-python = ">=3.10"` 自动准备）。

```powershell
# Windows（PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

装完**重开一个终端**，运行 `uv --version` 能打印版本号即成功。

### 2. 拿代码并装依赖

```bash
git clone https://github.com/dan131452/wangrong.git
cd wangrong
uv sync
```

### 3. 配置生图 API Key ← 关键一步

**Key 配置在项目根目录的 `.env` 文件里**（和 `pyproject.toml` 同级）。仓库里只有模板 `.env.example`，真实的 `.env` 被 `.gitignore` 忽略，**不会上传、也不在仓库里**，需要你自己创建：

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

然后编辑 `.env`，把 key 填进 `IMAGE_API_KEY=`：

```ini
IMAGE_API_KEY=sk-你的真实key
IMAGE_API_BASE=https://api.ipc.wiki/v1
IMAGE_MODEL=gpt-image-2.5
IMAGE_SIZE=1536x1024
```

| 变量 | 必填 | 说明 |
|---|---|---|
| `IMAGE_API_KEY` | **是** | 生图服务 key。留空时 `gen` / `serve` 会直接报错提示 |
| `IMAGE_API_BASE` | 否 | API 根地址，任何 OpenAI 兼容的 `/v1` 端点都行，默认 `https://api.ipc.wiki/v1` |
| `IMAGE_MODEL` | 否 | 模型名，默认 `gpt-image-2.5` |
| `IMAGE_SIZE` | 否 | 出图尺寸，默认 `1536x1024`（管道会自动居中裁剪） |

`.env` 由 `src/picture_book/gen.py` 的 `_load_dotenv()` 读取；**已存在的系统环境变量优先于 `.env`**，所以也可以用 `$env:IMAGE_API_KEY="sk-..."` 临时覆盖。

> 没有 key 也能跑：`uv run picture-book serve --demo` 和 `uv run picture-book build` 完全不调 API。

### 4. 启动

```bash
uv run picture-book serve --demo     # 先跑演示模式，确认环境没问题
uv run picture-book serve            # 真实生图模式，浏览器开 http://127.0.0.1:8765
```

`serve` 是**常驻进程**，保持这个终端开着，`Ctrl+C` 退出。

### 5. 常见问题

| 现象 | 原因与处理 |
|---|---|
| `uv: command not found` | 装完 uv 后没重开终端 |
| `错误：.env 里没有 IMAGE_API_KEY` | 没建 `.env`，或 `IMAGE_API_KEY=` 后面是空的 |
| 端口 8765 被占用 | 换端口：`uv run picture-book serve --port 8766` |
| 页面全是"插画占位"图 | 正常现象——还没有真插画。跑 `gen` 生成，或忽略它先看版式 |
| `gen` 单页失败 | 改用 `gen --book 书目id --page 页码` 单独重试，加 `--force` 覆盖重生成 |

## AIGC 生成器（serve）

浏览器打开 `http://127.0.0.1:8765`：**选择故事 → 点击「✦ 生成绘本」→ 逐页观察生成进度（缩略图网格 + 进度条，失败的页可单独重试）→ 开始阅读**（图文左右分栏版式，键盘/按钮翻页）。

- 真实模式调用 `.env` 配置的生图 API，已生成的页面自动跳过（再点生成秒完成）；
- 演示模式完全不调 API，适合课堂展示流程、或 API 不稳时的兜底；
- 生成的插画落盘到 `assets/images/`，之后 `build` 出的 PDF/PPTX/静态阅读器自动就是真图版。

没有插画时也能 build：缺图页自动使用山水云鸟场景的占位图，方便先预览版式。

## 成品（dist/）

| 文件 | 说明 |
|---|---|
| `绘本阅读器.html` | **单文件静态阅读器**：双击直接看，双书切换、键盘/按钮/触屏翻页，图已内嵌可单发 |
| `草船借箭.pdf / .pptx` | A4 横版 / 16:9 幻灯片 |
| `三顾茅庐.pdf / .pptx` | 同上 |

`serve` 启动的生成器网页（选故事→生成→阅读）在 http://127.0.0.1:8765，不入 dist。

## 加一本新绘本

1. 在 `data/books/` 新建一个 JSON（文件名即书目 id，格式参考现有两本）；
2. `uv run picture-book prompts` 重新生成提示词清单；
3. 出图（gen 或手动）后 `uv run picture-book build`——PDF/PPTX/网页自动全部包含新书。

## 生图 API 配置（.env，已 gitignore）

```
IMAGE_API_KEY=sk-...            # 必填
IMAGE_API_BASE=https://api.ipc.wiki/v1   # OpenAI 兼容中转
IMAGE_MODEL=gpt-image-2.5       # 该平台可用：gpt-image-2 / 2.5 / 2.5-flare / 2.5-sunburst
IMAGE_SIZE=1536x1024            # gpt-image 系列合法横版尺寸，管道会自动裁剪
```

`gen` 失败的页面可单独重试：`uv run picture-book gen --book 书目id --page 3`；想覆盖重生成加 `--force`。
gpt-image 单张生成较慢（1~5 分钟），命令内置重试。

## 放入插画（手动路线）

1. 打开 `data/prompts.md`，把提示词复制到**豆包**（免费、参考图一致性最好）或即梦/通义万相；
2. 每页生成 2~4 张挑最好的一张，按清单里的文件名（如 `sg-06-waiting.png`）存进 `assets/images/`；
3. 重新 `uv run picture-book build`。

> 角色一致性：把《草船借箭》P3 的诸葛亮图发进豆包当参考（“参考这张图里的角色”），两本书共用；张飞形象以《三顾茅庐》P5 为锚点。

## 目录结构

```
data/books/*.json       # 每本绘本一个 JSON（唯一数据源：文案+提示词+文件名）
data/prompts.md         # 自动生成的出图提示词清单
assets/images/          # AI 生成的插画（两本书共用，文件名不冲突）
src/picture_book/       # story(数据) / build(排版) / web(网页) / gen(生图) / placeholders(占位图) / fonts
scripts/render_png.py   # PDF 渲染成 PNG 预览（uv run --group preview）
dist/                   # 成品输出
```

## 技术

- Python ≥3.10（uv 管理），依赖：reportlab（PDF）、python-pptx（PPTX）、Pillow（裁剪/占位图）
- 版式：插画满铺 + 双线装饰边框 + 带投影的奶油色圆角文字卡片（橙色强调条）；自动居中裁剪适配任意比例原图
- 网页阅读器：零依赖单文件 HTML，页面图 base64 内嵌（1280 宽 JPEG），file:// 直读
- 中文字体自动探测系统字体（微软雅黑 → 黑体 → 宋体 → 内置 CID 字体兜底）
