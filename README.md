# 每天一条：天气 + 科技要闻 → 微信 / 邮箱

一个零依赖（只用 Python 标准库）的小脚本，每天定时把「当天天气 + 前一天科技要闻」推到你的微信。

- **数据免费、不用注册 API key**：天气用 [Open-Meteo](https://open-meteo.com/)，新闻抓 IT之家 / 爱范儿 / 少数派 / Solidot / 极客公园 / 钛媒体的 RSS
- **推送渠道可插拔**：微信公众号模板消息、邮件、Server酱、PushPlus、企业微信机器人，可同时发多个
- **跑在 GitHub Actions 上**，电脑关机也照发，一天三次（09:00 / 12:00 / 18:00）

## 效果长这样

```
## 11月5日 周四 · 晚间科技速递

**北京** 🌫 有雾　4~16℃　降水 0%
现在 8℃（体感 4℃）· 湿度 33% · 风 10km/h

今天 🌫有雾 4~16℃ 降水0%　明天 ⛅多云 3~13℃ 降水0%　后天 ❄️大雪 1~6℃ 降水100%

### 📰 近 30 小时要闻
1. 反对声浪下 OpenAI 重申将承担数据中心供电成本，承诺征求社区意见、公开建设规划 — IT之家 · 2小时前
   https://www.ithome.com/1/022/958.htm
2. 比亚迪腾势 Z9S 首次 OTA：AI 超级智能体迪迪虾上车，新增代言人王力宏场景播报 — IT之家 · 3小时前
   https://www.ithome.com/1/022/911.htm
3. AI安全背后的哲学思想，有效利他主义如何影响硅谷？（上篇） — 钛媒体 · 3小时前
   https://www.tmtpost.com/8194754.html
...

### 🧥 出门提示
- 早晚温差 12℃，分层穿衣最稳
- 早晚偏凉，出门加件外套
- 穿搭建议：厚外套 / 棉服 + 毛衣
```

在微信公众号里收到的是**紧凑版**（公众号模板消息有字数限制，放不了长链接）：

```
11月5日 晚间科技速递
🌤 天气：北京 🌫有雾 4~16℃ 降水0%
📰 要闻：1. 反对声浪下 OpenAI 重申将承担数据…
        2. 比亚迪腾势 Z9S 首次 OTA：AI 超级…
        3. AI安全背后的哲学思想，有效利他主义…
🧥 提示：早晚温差 12℃，分层穿衣最稳；早晚偏凉，出门加件外套
现在8℃ 体感4℃ · 明天⛅多云 3~13℃
```

---

## 一、先本地跑通（3 分钟）

**Windows 上最简单：双击 `运行.cmd`，选 `1. 预览`。**

它会自动找到可用的 Python（包括跳过系统里那个用不了的假 `python`），跑完停住不闪退。

命令行方式：

```bash
cd daily-push
copy .env.example .env      # macOS/Linux 用 cp
.\运行.cmd 预览             # 等价于 python main.py --dry-run
```

打印出来的就是消息内容，同时会在 `out/latest.md` 留一份。**没有配任何密钥时这是唯一可用的命令**（不会报错，只会提示「渠道参数不全」）。

`运行.cmd` 支持的快捷参数：`预览` / `测试` / `发送`；不带参数则是交互式菜单。

---

## 二、微信公众号怎么配

先说结论，因为这决定你走哪条路：

| 你的公众号 | 能用模板消息吗 | 怎么办 |
|---|---|---|
| **订阅号**（个人注册默认就是这种） | ❌ 不行 | 用下面的**路线 A：接口测试号** |
| **认证服务号**（企业主体，年审过） | ✅ 可以 | 路线 B，但模板字段有 20 字限制，详见下文 |
| **接口测试号**（谁都能申请） | ✅ 可以 | **路线 A，最省事，推荐** |

> 关键事实：`模板消息` 是服务号能力，**订阅号没有**，所以「拿自己的订阅号给粉丝推送」这条路根本不通。「接口测试号」是微信官方提供的沙箱，能力等同认证服务号、但不用认证，自用完全够。

### 30 秒自检：你那个号到底是哪种

登录 <https://mp.weixin.qq.com> 后看左侧菜单：

| 你看到的 | 结论 |
|---|---|
| 有「**模板消息**」（一般在「功能」下面） | 服务号，可以直接用 |
| 只有「内容管理 / 互动管理 / 数据分析 / 收入变现 / 账号成长」，创作台是「文章 / 贴图 / 播客 / 直播」 | **订阅号**，不能用模板消息 |
| 连「设置与开发」都找不到 | 这个号没开放 API 权限，更只能用测试号 |

两条硬规则，能省掉很多纠结：

1. **个人主体注册的公众号一律是订阅号**，而个人主体又不支持微信认证，所以个人号永远拿不到模板消息权限。
2. **订阅号和服务号注册后不能互转**，只能另注册一个企业主体的服务号（要营业执照 + 300 元/年认证费）。

所以：自用推送走**路线 A 测试号**，你那个订阅号留着写文章就行，两者不冲突。总用户数只有 1 也是完全正常的——测试号的推送发给你自己的微信号，跟公众号粉丝数无关。

### 路线 A：接口测试号（推荐，不需要任何认证）

1. 打开 <https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login>，微信扫码登录
2. 页面上直接能看到 **appID** 和 **appsecret** → 填到 `.env` 的 `WX_APPID` / `WX_APPSECRET`
3. 用微信扫页面上的**测试号二维码**关注它（关注后才能在下面的「用户列表」里看到自己）
4. 「用户列表」里那一串 `oXXXXX...` 就是你的 **openid** → 填到 `WX_OPENID`
5. 在「模板消息」区域点 **新增测试模板**：
   - 标题：`每日速递`
   - 内容（直接复制，注意保留 `{{ }}`）：

     ```
     {{title.DATA}}
     🌤 天气：{{weather.DATA}}
     📰 要闻：{{news.DATA}}
     🧥 提示：{{tip.DATA}}
     {{remark.DATA}}
     ```

     如果配了 AI（见第五节），再加一行 `💡 一句：{{ai.DATA}}` 放在 `{{remark.DATA}}` 前面。
   - 提交后会得到一个**模板 ID** → 填到 `WX_TEMPLATE_ID`
6. 验证：

   ```bash
   python main.py --test
   ```

   微信里应该立刻收到一条「daily-push 测试」。

### 路线 B：你自己的认证服务号

流程一样（基本配置拿 AppID/AppSecret，用户管理拿 openid），只有两点不同：

1. **模板不能自由写**。认证服务号的模板要从「类目模板库」里选，字段类型是固定的（`thing` 最多 20 字、`phrase` 最多 5 字…）。
2. 所以长内容塞不进去。这时用 `n1`~`n5` 这五个字段，每个是一条标题（程序已限制在 20 字内）：

   ```
   {{title.DATA}}
   {{weather.DATA}}
   要闻1：{{n1.DATA}}
   要闻2：{{n2.DATA}}
   要闻3：{{n3.DATA}}
   {{remark.DATA}}
   ```

   并在 `.env` 里显式指定：

   ```dotenv
   WX_FIELDS=title,weather,n1,n2,n3,remark
   ```

> ⚠️ **海外 IP 白名单**：认证服务号如果在「基本配置」里开启了 IP 白名单，GitHub Actions 的 IP 每次都不一样，会直接调用失败。要么关掉白名单，要么改成本地跑。测试号没有这个问题。

---

## 三、部署到 GitHub Actions（电脑关机也能收）

这台机器上没装 git，最省事的是用 **GitHub Desktop**（图形界面，帮你搞定登录和认证）：

### 3.1 把代码传上去

1. 下载安装 <https://desktop.github.com/>，用你的 GitHub 账号登录
2. 菜单 **File → Add local repository** → 选 `daily-push` 这个文件夹
3. 它提示"不是 Git 仓库，要不要创建一个？"→ 点 **create a repository**
4. 左下角 Summary 随便填 `init`，点 **Commit to main**
5. 右上角 **Publish repository** → 勾上/不勾 *Keep this code private* 都行 → 发布

> 用 GitHub Desktop 或 git 命令上传时，`.gitignore` 会生效，`.env`（你的 AppSecret）不会被传上去。
> **千万不要用网页「拖拽上传」**——网页上传不认 `.gitignore`，会把 `.env` 里的密钥一起传出去。

### 3.2 配置密钥

仓库页 → **Settings → Secrets and variables → Actions**

**Secrets** 标签，4 个（New repository secret）：

| Name | Secret |
|---|---|
| `WX_APPID` | 测试号的 appID |
| `WX_APPSECRET` | 测试号的 appsecret |
| `WX_TEMPLATE_ID` | 模板 ID |
| `WX_OPENID` | 你的 openid |

**Variables** 标签，2 个（New repository variable）：

| Name | Value |
|---|---|
| `CITY` | `岳阳` |
| `PUSH_CHANNELS` | `wechat_mp` |

### 3.3 跑一次验证

仓库页 → **Actions** → 左边选「每日推送」→ 右边 **Run workflow** → 绿色按钮。
等半分钟，微信应该收到；日志里能看到完整内容。

之后每天 09:00 / 12:00 / 18:00（北京时间）自动发，不用再管。

### 3.4 推荐：改用 Server酱，点开就能看全文

公众号模板消息**只是一张通知卡片，不是网页**，微信也没有「展开全文」。而且每个字段只显示**一行**（约 26 字），6 条新闻根本塞不进去，系统会用「…」硬截断——所以你只能看到摘要。

要「点开看全文」，最省事的是换成 **Server酱（方糖）**：微信里收到一条「方糖」服务号消息，点开就是一个渲染好的网页，6 条新闻齐全、链接可点。

1. 打开 <https://sct.ftqq.com>，微信扫码登录
2. 进「SendKey」页面，复制那串 `SCT` 开头的密钥
3. 仓库 → Settings → Secrets and variables → Actions：
   - **Secrets** 加 `SERVERCHAN_SENDKEY` = 刚才的密钥
   - **Variables** 把 `PUSH_CHANNELS` 改成 `serverchan`
4. 重跑一次 workflow

> **额度**：免费会员每天 5 条。你要 3 条/天，够用但没多少余量——同一天手动重跑两三次就会超，超出后当天不再发。新用户有 7 天全功能试用。
>
> 想要零额度顾虑就换 PushPlus（约 200 条/天），改 `PUSH_CHANNELS=pushplus` + 加 `PUSHPLUS_TOKEN` 即可。

**如果你更希望消息来自自己的公众号卡片**，那必须自建网页给 `WX_LINK_URL` 用。免费方案是 GitHub Pages，但它要求仓库**公开**：Settings → 最下面 Danger Zone → Change visibility → Make public，然后 Settings → Pages → Source 选 `Deploy from a branch`、目录 `/docs`，再把 `WX_LINK_URL` 设成 `https://你的用户名.github.io/daily-push/`。

几个必须知道的坑：

| 现象 | 原因 | 处理 |
|---|---|---|
| 时间不准，晚了几分钟到二十分钟 | GitHub 免费 runner 的定时任务排队延迟 | 正常，无法根治 |
| 隔了两个月突然不发了 | 仓库 60 天无提交，定时任务被自动停用 | 已带 `keepalive.yml` 每月自动提交一次；万一还是停了，去 Actions 页面点一下「Enable workflow」 |
| 私有仓库额度不够 | 私有仓库的 Actions 分钟数有免费上限（每月 2000 分钟） | 这套一天三次、每次约 40 秒，一个月只用 60 分钟左右，够用 |
| 想改时间 | 改 `.github/workflows/daily.yml` 里的 cron | cron 是 UTC，北京时间减去 8 小时（09:00 → `0 1 * * *`） |

---

## 四、想在 QQ 上收 / 用别的渠道

个人 QQ 没有官方机器人接口，最稳的两条路：

- **邮件 → QQ 邮箱**：配 `PUSH_CHANNELS=mail`，`MAIL_TO=你的QQ号@qq.com`，手机 QQ 会弹邮件提醒。这是最省事、最不会挂的方式。
- **Qmsg酱**（<https://qmsg.zendee.cn/>）：加一个机器人 QQ 好友，它给你发私聊。本项目没内置（它的接口常变），需要的话按它的文档加个 20 行的渠道模块即可。

其他已内置渠道：

```dotenv
# 邮件
PUSH_CHANNELS=mail
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=you@qq.com
SMTP_PASS=授权码          # QQ 邮箱：设置 → 账号 → 开启 SMTP → 生成授权码
MAIL_TO=you@qq.com

# Server酱（微信「方糖」服务号收）  https://sct.ftqq.com/
SERVERCHAN_SENDKEY=SCT...
PUSH_CHANNELS=wechat_mp,serverchan

# PushPlus（微信「pushplus」公众号收）  https://www.pushplus.plus/
PUSHPLUS_TOKEN=...

# 企业微信群机器人（个人也能注册企业微信）
WECOM_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...
```

多个渠道用逗号分隔，程序会**逐个发**，某个渠道挂了不影响其他渠道。

---

## 五、加一句 AI 总结（可选）

配好任意 OpenAI 兼容接口即可，不配就不发这一段：

```dotenv
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com/v1   # 也可换成通义/Moonshot/本地 Ollama
LLM_MODEL=deepseek-chat
```

它会把当天选出的标题丢给模型，让它写一句不超过 55 字的概括。成本约每次几厘钱。

---

## 六、配置项全表

| 变量 | 默认 | 说明 |
|---|---|---|
| `CITY` | `北京` | 中文地名，自动地理编码；同名地多时可改用 `LATITUDE`/`LONGITUDE` |
| `PUSH_CHANNELS` | 自动 | 逗号分隔：`wechat_mp` `mail` `serverchan` `pushplus` `wecom`。**留空则按已配好的凭据自动选一个**（优先 serverchan → pushplus → wecom → wechat_mp → mail） |
| `SLOT` | `auto` | `morning`(09点) / `noon`(12点) / `evening`(18点)，`auto` 按当前时间判断 |
| `NEWS_SOURCES` | 6 个源 | 可选：`ithome` `ifanr` `sspai` `solidot` `geekpark` `tmtpost` |
| `NEWS_COUNT` | `6` | 选几条，建议 4~8 |
| `NEWS_LOOKBACK_HOURS` | `30` | 只取最近多少小时的新闻（30 小时 ≈ 昨天全天 + 今早） |
| `EXTRAS` | 空 | 逗号分隔：`quote`(每日一句) `countdown`(倒数日) `fx`(汇率) |
| `COUNTDOWN` | 空 | 形如 `2027-01-01\|元旦`，多个用逗号分隔 |
| `FX_PAIRS` | 空 | 形如 `USD:CNY,EUR:CNY` |
| `WX_FIELDS` | 见上文 | 模板消息里依次填哪些字段，**必须和模板里的 `{{xxx.DATA}}` 一一对应** |
| `WX_LINK_URL` | 空 | 点开模板消息时跳转的地址 |

命令行：

```bash
python main.py              # 抓数据并推送
python main.py --dry-run    # 只生成预览
python main.py --test       # 发一条测试消息
python main.py --only mail  # 只发某个渠道
python main.py --show       # 顺带把完整 markdown 打到日志里
```

---

## 七、常见问题

**CMD 里敲 `python` 一点反应都没有 / 提示"不是内部或外部命令"**
Windows 10/11 自带一个 **0 字节的 `python.exe` 占位符**（在 `%LOCALAPPDATA%\Microsoft\WindowsApps\`），敲它什么都不输出、直接返回错误码 9009——看起来就是"没反应"。这不是本项目的问题，任何 Python 程序都一样。

两个解决办法：

1. **双击 `运行.cmd`**（推荐）。它逐个试探系统里的候选，实测能跑通 `--version` 的才用，会自动跳过那个 0 字节占位符。
2. 装一个真 Python：`winget install Python.Python.3.12`，装完**关掉 CMD 重开**，`python` 就能用了。

排查命令：`where python` 如果指向 `WindowsApps` 且文件大小是 0，就是上面这个情况。

**发送失败返回 40001 / 40013**
AppID 或 AppSecret 不对。AppSecret 只显示一次，忘了就点「重置」再复制。

**返回 40003 或 43004**
`openid` 不对，或者那个微信号根本没关注这个公众号。测试号要扫码关注后才会出现在用户列表里。

**返回 47003 / 模板参数不合法**
`WX_FIELDS` 里的字段名和模板里的 `{{xxx.DATA}}` 对不上，或者某字段超长。测试号每个字段上限约 120 字，程序已经按 100 字截断。

**40164 / invalid ip**
认证服务号开了 IP 白名单，而 GitHub runner 的 IP 是变的。关掉白名单，或改成本地计划任务跑。

**订阅号能不能直接用？**
不能。订阅号没有模板消息权限，只能群发图文（每天 1 次，且有内容审核）。要么用测试号，要么走邮件/Server酱。

**抓不到新闻**
免费 RSS 偶尔会抽风或改地址。`NEWS_SOURCES` 换几个源即可；日志里会打印哪个源失败。

---

## 八、想改内容？

- 想加数据源：在 `pusher/news.py` 的 `SOURCES` 里加一行 `key: (显示名, RSS 地址)`，然后写进 `NEWS_SOURCES`。注意 `feed` 必须是合法 XML（36氪、品玩的 feed 实测会返回坏数据，已排除）。
- 想改版式：`pusher/render.py`，三个函数分别管 markdown / 纯文本 / 公众号紧凑版。
- 想改排序：`pusher/news.py` 的 `INTEREST`（关键词加权）和 `_quality_penalty`（压「日报/盘点」类大杂烩）。

## 目录结构

```
daily-push/
├── main.py                     入口 / CLI
├── pusher/
│   ├── config.py               环境变量 → 配置对象
│   ├── http.py                 urllib 封装（超时、重试）
│   ├── weather.py              Open-Meteo + WMO 天气码 + 穿衣提示
│   ├── news.py                 RSS 抓取 / 去重 / 打分 / 选稿
│   ├── extras.py               每日一句、倒数日、汇率
│   ├── llm.py                  可选的一句话总结
│   ├── render.py               三种版式输出
│   └── channels/               各推送渠道，一个渠道一个文件
├── .github/workflows/
│   ├── daily.yml               一天三次
│   └── keepalive.yml           防止 60 天不活跃被停
└── .env.example
```

## 合规提醒

微信公众号模板消息的官方定位是「重要服务通知」，不支持营销内容。给自己的号推送属于自用，一般没人管；但如果你的公众号有真实粉丝、把模板消息当成资讯推送来用，有被限制模板权限的风险——那种场景请用邮件或 Server酱。
