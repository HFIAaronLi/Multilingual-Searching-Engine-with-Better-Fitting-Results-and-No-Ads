# Multilingual-Searching-Engine-with-Better-Fitting-Results-and-No-Ads[README.md](https://github.com/user-attachments/files/34175343/README.md)
# Terminal Search / 终端搜索

A bilingual terminal search tool with unrestricted-language search by default, ad filtering, result previews, and on-demand paragraph summaries.

一个默认不限搜索语言的中英双语终端搜索工具，支持广告过滤、结果预览，以及按需提取网页段落摘要。

## Improvements / 改进内容

- **Unrestricted language by default / 默认不限语言：** `auto` no longer guesses Chinese or English and does not add a language or region condition to the query. `auto` 不再把查询自动归为中英文，也不会给查询附加语言或地区条件。
- **Optional language setting / 可主动设置语言：** use commands such as `:lang zh`, `:lang en`, `:lang ja`, or `:lang fr`. 可使用 `:lang zh`、`:lang en`、`:lang ja`、`:lang fr` 等命令主动指定搜索语言。
- **Ad and junk filtering / 广告及垃圾内容过滤：** enabled by default; known advertising hosts and explicit ad labels are removed. 默认开启，会过滤已知广告域名和明确的广告标识。
- **Paragraph previews / 段落预览：** results show the beginnings of P1, P2, and Last when those text units are available. 结果会尽量分别显示首段、次段和末段的开头。
- **On-demand page summaries / 按需网页摘要：** `:summary <number>` fetches a selected page and extracts its first, second, and last paragraphs. `:summary <编号>` 会读取指定网页并提取首段、次段和末段。
- **Always bilingual / 始终双语：** the interface displays English first, followed by Chinese; there is no interface-language selection step. 界面固定为英文在前、中文在后，不需要选择界面语言。
- **More built-in engines / 更多内置引擎：** Google, Bing, DuckDuckGo, Yahoo, Baidu, Brave, Ecosia, Yandex, Mojeek, and Sogou are available. 内置 Google、Bing、DuckDuckGo、Yahoo、百度、Brave、Ecosia、Yandex、Mojeek 和搜狗。
- **Custom engine domains / 自定义域名引擎：** enter a domain such as `yahoo.hk`, `yahoo.jp`, or `baidu.com` directly in `:pool`; no provider editing is needed. 可在 `:pool` 中直接输入 `yahoo.hk`、`yahoo.jp`、`baidu.com` 等域名，无需修改程序。
- **More reliable operation / 运行更稳妥：** adds HTTP error checks, safer result numbers, page-bound checks, and clearer error messages. 增加网络错误检查、编号与翻页边界检查，以及更清楚的提示。

## Requirements / 环境要求

- Python 3.9 or newer / Python 3.9 或更新版本。
- macOS or Windows / macOS 或 Windows。
- An internet connection / 可用的网络连接。

No separate compilation step is required. Run the file with Python 3.

不需要单独编译，直接使用 Python 3 运行即可。

## 1. Save the program / 保存程序

Save the supplied file as **`tsearch.py`** on your Desktop. Keep it as a UTF-8 Python file.

将提供的文件以 **`tsearch.py`** 为名保存到桌面，并保持 UTF-8 编码。

Do not rename it to `tsearch.py.txt`, and do not paste Markdown fences such as ```` ```python ```` into the file.

不要把它保存成 `tsearch.py.txt`，也不要把 ```` ```python ```` 等 Markdown 标记复制进文件。

## 2A. macOS installation and launch / macOS 安装与运行

Open **Terminal**. The following commands use a virtual environment, so they do not modify the system Python and do not require activating the environment.

打开“终端”。以下命令使用独立的虚拟环境，不修改系统 Python，也不需要执行环境激活命令。

### Check Python 3 / 检查 Python 3

```bash
python3 --version
```

If Terminal says `python3: command not found`, install Python 3 from <https://www.python.org/downloads/macos/>, then close and reopen Terminal.

如果提示 `python3: command not found`，请先从上述 Python 官网安装 Python 3，然后关闭并重新打开终端。

### Go to Desktop / 进入桌面目录

```bash
cd ~/Desktop
```

### Create an isolated environment / 创建独立环境

```bash
python3 -m venv .tsearch-venv
```

### Install dependencies / 安装依赖

```bash
.tsearch-venv/bin/python -m pip install requests beautifulsoup4 rich
```

PyYAML is no longer required.

新版不再需要 PyYAML。

### Launch / 启动

```bash
.tsearch-venv/bin/python tsearch.py
```

For later runs, only these two commands are needed:

以后再次运行时，只需执行：

```bash
cd ~/Desktop
.tsearch-venv/bin/python tsearch.py
```

## 2B. Windows installation and launch / Windows 安装与运行

Open **Windows Terminal** or **PowerShell**. These commands also use an isolated environment and do not require changing PowerShell's execution policy.

打开“Windows 终端”或 PowerShell。以下命令同样使用独立环境，不需要修改 PowerShell 执行策略。

### Check Python / 检查 Python

```powershell
py --version
```

If `py` is unavailable, try `python --version`; in the next command, replace `py` with `python`.

如果 `py` 不可用，请尝试 `python --version`，并在下一条创建环境的命令中用 `python` 替代 `py`。

### Go to Desktop / 进入桌面目录

```powershell
cd "$env:USERPROFILE\Desktop"
```

### Create an isolated environment / 创建独立环境

```powershell
py -m venv .tsearch-venv
```

### Install dependencies / 安装依赖

```powershell
.tsearch-venv\Scripts\python.exe -m pip install requests beautifulsoup4 rich
```

### Launch / 启动

```powershell
.tsearch-venv\Scripts\python.exe tsearch.py
```

For later runs, only these two commands are needed:

以后再次运行时，只需执行：

```powershell
cd "$env:USERPROFILE\Desktop"
.tsearch-venv\Scripts\python.exe tsearch.py
```

## 3. Basic use / 基本使用

When you see the following prompt, enter a query in any language:

看到以下提示后，可以用任意语言输入搜索内容：

```text
Search 搜索 >
```

Examples / 示例：

```text
Python decorators
巴黎 旅游
東京 ラーメン
inteligencia artificial
```

Type `:help` to see all commands, and `:exit` or `q` after a colon (`:q`) to quit.

输入 `:help` 查看全部命令；输入 `:exit` 或 `:q` 退出。

## 4. Commands / 命令

| Command / 命令 | Function / 功能 |
| --- | --- |
| `:new` | Start a new topic / 开始新话题 |
| `:next` or `n` / `:next` 或 `n` | Next page / 下一页 |
| `:prev` or `p` / `:prev` 或 `p` | Previous page / 上一页 |
| `:open 1` | Open result 1 in the browser / 在浏览器中打开第 1 条结果 |
| `:summary 1` | Extract a paragraph summary from result 1 / 提取第 1 条结果网页的段落摘要 |
| `:pool` | Show available engines and the current pool / 查看可用引擎和当前搜索池 |
| `:pool bing,baidu` | Use Bing and Baidu / 使用 Bing 和百度 |
| `:pool google,yahoo.jp,baidu.com` | Mix built-in engines and custom domains / 混合使用内置引擎与自定义域名 |
| `:pool reset` | Restore the expanded default pool / 恢复扩展后的默认搜索池 |
| `:lang auto` | Remove the explicit language setting / 取消主动语言设置 |
| `:lang ja` | Request Japanese results / 请求日文搜索结果 |
| `:lang zh-CN` | Request Simplified Chinese results / 请求简体中文搜索结果 |
| `:filter on` | Enable ad and junk filtering / 开启广告及垃圾内容过滤 |
| `:filter off` | Disable filtering / 关闭过滤 |
| `:exit` or `:q` | Quit / 退出 |

The search language, pool, custom engines, and filtering setting are saved in `.tsearch.json` in your home directory.

搜索语言、搜索池、自定义引擎和过滤设置会保存在用户主目录下的 `.tsearch.json` 中。

### Language behavior / 语言行为说明

`auto` means no additional language restriction. Other language codes are passed to engines that support language or regional preferences. Search engines can still occasionally return pages in other languages; Baidu does not provide a general language-control parameter in this tool.

`auto` 表示不附加语言限制。其他语言代码会传递给支持语言或地区设置的引擎。搜索引擎仍可能偶尔返回其他语言的网页；本工具中的百度搜索没有通用的语言控制参数。

This setting never changes the bilingual interface.

该设置不会改变中英双语界面。

### Filtering and summaries / 过滤与摘要说明

Filtering is enabled by default. If you are researching advertising itself and believe a useful result was removed, use `:filter off`.

广告过滤默认开启。如果你正在研究广告相关内容，并认为有用结果被误过滤，可使用 `:filter off`。

The search table builds its short preview from search-result text. Use `:summary <number>` to read the selected public page and show the beginnings of its first, second, and last available paragraphs. Sites that require login, block automated access, use only JavaScript-rendered text, or return non-HTML content may not be summarizable.

结果表格中的简短预览来自搜索结果文本。使用 `:summary <编号>` 可读取对应的公开网页，并显示首段、次段和末段的开头。需要登录、阻止自动访问、仅通过 JavaScript 生成正文，或返回非 HTML 内容的网站可能无法生成摘要。

## 5. Search engines / 搜索引擎

### Start with no setup / 无需设置，直接使用

The default pool now searches Google, Bing, DuckDuckGo, Yahoo, Baidu, and Brave at the same time. You do not need to configure an engine before typing a query.

默认搜索池现在会同时使用 Google、Bing、DuckDuckGo、Yahoo、百度和 Brave。输入搜索内容前不需要配置引擎。

To see every available engine and your current pool:

查看全部引擎和当前搜索池：

```text
:pool
```

To restore the default pool at any time:

随时可用以下命令恢复默认搜索池：

```text
:pool reset
```

### Choose built-in engines / 选择内置引擎

Available names are:

可用名称如下：

```text
google, bing, duckduckgo, yahoo, baidu, brave,
ecosia, yandex, mojeek, sogou
```

Examples / 示例：

```text
:pool google
:pool google,bing,yahoo
:pool bing,baidu,sogou
:pool google,ecosia,mojeek
```

Setting `:pool` replaces the current pool, so include every engine you want to use. If you normally use Google, Yahoo, Bing, DuckDuckGo, or Ecosia through Safari, choose the same engine name here; Safari itself is the browser rather than a separate search provider in this tool.

设置 `:pool` 会替换当前搜索池，因此需要列出所有想使用的引擎。如果你平时通过 Safari 使用 Google、Yahoo、Bing、DuckDuckGo 或 Ecosia，在这里选择对应名称即可；Safari 本身是浏览器，不是本工具中的独立搜索提供方。

### Add your own engine by domain / 通过域名添加自己的引擎

Type the domain directly after `:pool`. Do not edit the source code.

把域名直接写在 `:pool` 后面即可，不需要修改源代码。

```text
:pool yahoo.hk
:pool yahoo.jp
:pool google,yahoo.jp,baidu.com
:pool https://search.yahoo.co.jp
```

Custom engines are saved automatically and appear under `Custom engines / 自定义引擎` the next time you run `:pool`.

自定义引擎会自动保存；下次输入 `:pool` 时，会显示在“Custom engines / 自定义引擎”一栏。

Enter a domain only, with an optional `http://` or `https://` prefix. The program recognizes several common search sites and otherwise tries a standard search address plus a general result parser. It follows redirects returned by the website and does not substitute a different regional engine on your behalf.

只需输入域名，也可以加上 `http://` 或 `https://` 前缀。程序会识别多个常见搜索网站；对于其他网站，会尝试常见的搜索地址和通用结果解析。网站自身返回跳转时，程序会跟随跳转，不会擅自替你换成其他地区的引擎。

A custom engine can still fail because of network access, regional availability, CAPTCHA checks, login requirements, or an unsupported page layout. This is reported as an engine failure; it does not stop the other engines.

自定义引擎仍可能因网络连接、地区可用性、验证码、登录要求或网页结构不受支持而失败。程序会显示该引擎失败，但不会影响其他引擎。

### SearXNG: optional; most people can skip it / SearXNG：可选项，大多数人可跳过

**You do not need SearXNG. If you do not already use it, ignore this subsection and no address configuration is needed.**

**你不需要安装或配置 SearXNG。如果你本来就没有使用它，直接跳过本小节即可，也不需要填写任何地址。**

Only if you already have a running SearXNG service, you can add it like any other engine:

只有已经运行 SearXNG 服务的人，才需要像下面这样把它加入搜索池：

```text
:pool searxng
:pool bing,searxng
```

If it does not connect, use `:pool reset` and continue with the normal engines.

如果无法连接，输入 `:pool reset`，继续使用普通搜索引擎即可。

### Network availability / 网络可用性

Any search engine may be unreachable on a particular network. A failed, timed-out, CAPTCHA-blocked, or unreadable engine is listed in a warning while the remaining engines can still return results.

任何搜索引擎都可能在特定网络下无法连接。失败、超时、被验证码拦截或无法解析的引擎会显示在警告中，其他引擎仍可正常返回结果。

## 6. Troubleshooting / 故障排查

### Why did the original fail in macOS Terminal? / 原版为什么在苹果终端中失败？

The pasted original source passes a Python 3 syntax check, so a definite cause cannot be identified without the actual Terminal error. The most common causes are using `python` instead of `python3`, missing packages, running from the wrong directory, a `.txt` suffix, or accidentally saving Markdown fences with the code.

你贴出的原版代码可以通过 Python 3 语法检查，因此没有实际报错信息时，无法断定唯一原因。常见原因包括：误用 `python` 而不是 `python3`、缺少依赖、运行目录不正确、文件带有 `.txt` 后缀，或把 Markdown 代码标记一起保存了进去。

The installation commands above avoid these issues by using an explicit Python 3 environment and its full interpreter path.

上述安装命令通过明确的 Python 3 环境和完整解释器路径来避开这些问题。

### `No module named requests`, `bs4`, or `rich` / 提示缺少模块

Install dependencies with the same interpreter that launches the program. The commands in sections 2A and 2B already do this.

请使用启动程序的同一个 Python 解释器安装依赖。2A 和 2B 中的命令已经按此方式处理。

### `externally-managed-environment` on macOS / macOS 提示环境受系统管理

Use the virtual-environment commands in section 2A instead of installing packages into Homebrew or system Python.

请使用 2A 中的虚拟环境命令，不要直接向 Homebrew 或系统 Python 安装软件包。

### `can't open file` or `No such file or directory` / 找不到文件

Check that Terminal is in the folder containing `tsearch.py`:

请确认终端当前目录中存在 `tsearch.py`：

- macOS: run `ls` / macOS：执行 `ls`。
- Windows: run `dir` / Windows：执行 `dir`。

Then use `cd` to enter the actual folder where the file is saved.

如果文件不在当前目录，请用 `cd` 进入实际保存位置。

### `Permission denied` on macOS / macOS 提示权限不足

Do not run `./tsearch.py`. Launch it through Python as shown:

不要直接执行 `./tsearch.py`，请按以下方式通过 Python 启动：

```bash
.tsearch-venv/bin/python tsearch.py
```

### A `SyntaxError` appears / 出现语法错误

Use the supplied `tsearch.py` directly, make sure the file contains Python code only, and launch it with Python 3 rather than Python 2.

请直接使用提供的 `tsearch.py`，确保文件中只有 Python 代码，并使用 Python 3 而不是 Python 2 启动。
