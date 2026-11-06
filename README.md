# 每天一条：技术早报 + 天气，推到微信

一个零依赖（只用 Python 标准库）的小脚本。每天 09:00 / 12:00 / 18:00 自动抓取科技新闻和天气，整理成一份**分板块**的简报，通过 **Server酱（方糖）** 推到微信——点开就是完整网页，每条标题都能点。

- **数据免费、不用注册 API key**：天气用 [Open-Meteo](https://open-meteo.com/)，新闻抓 IT之家 / 爱范儿 / 少数派 / Solidot / 极客公园 / 钛媒体 / 界面新闻的 RSS
- **推送渠道可插拔**：Server酱、公众号模板消息、邮件、PushPlus、企业微信机器人
- **跑在 GitHub Actions 上**，电脑关机也照发。一天三次，每次覆盖不同时段，内容不重复
- **按行业分板块**：AI 前线 / 半导体芯片 / 手机 / 汽车 / 新能源，各占固定配额；Epic 喜加一有保底

## 效果长这样

微信里收到「方糖」服务号的一条消息，点开是这个页面（这是真实抓取的一期）：

```markdown
### 🌤 天气 · 岳阳（湖南）

- 今天 ☁️ 阴　15~22℃　降水 29%
- 明天 🌧 强阵雨　14~16℃　降水 100%
- 后天 🌧 强阵雨　14~17℃　降水 100%
- 现在 16℃（体感 16℃）· 湿度 89% · 风 6km/h
- 日出 06:43 · 日落 17:37 · 紫外线 1（低） · AQI 92（良）

### 🤖 AI 前线

1. [OpenAI CEO 奥尔特曼警示：未来人类可能无法从 AI 手中夺回控制权](链接)（IT之家 · 2小时前）
2. [Claude Code 华人一姐跳槽到 OpenAI](链接)（钛媒体 · 7小时前）
3. [欧洲央行考虑审查银行对数据中心的贷款](链接)（界面新闻 · 2小时前）

### 🔬 半导体芯片

1. [台积电据悉考虑进军先进存储芯片领域，为英伟达生产 3D DRAM](链接)（界面新闻 · 2小时前）
2. [Brightspeed 与英伟达洽谈，将老旧电信建筑改造为小型数据中心](链接)（IT之家 · 4小时前）

### 📱 手机

1. [苹果 Action Button 将在明年的新款 iPhone 上退场](链接)（IT之家 · 4小时前）
2. [iQOO 7 英寸中端机已开模：超万级电池](链接)（IT之家 · 3小时前）

### 🚗 汽车

1. [特斯拉将停产 Cybertruck](链接)（Solidot · 2小时前）
2. [斯巴鲁召回部分进口汽车，共 196494 辆](链接)（IT之家 · 7小时前）

### ⚡ 新能源

1. [吉利星愿 10 月全球销量突破 7 万辆](链接)（IT之家 · 5小时前）

### 🧥 出门提示

- 降水概率 100%，记得带伞
- 穿搭建议：长袖衬衫或薄外套即可
```

每条标题在页面上都是可点的链接，点一下直接跳到原文。**哪个板块当天没货，就整个不输出**，不会留空标题。

---

## 一、先本地跑通（3 分钟）

**Windows 上最简单：双击 `运行.cmd`，选 `1. 预览`。**

它会自动找到可用的 Python（包括跳过系统里那个用不了的假 `python`），跑完停住不闪退。

命令行方式：

```powershell
cd daily-push
copy .env.example .env      # macOS/Linux 用 cp
.\运行.cmd 预览             # 等价于 python main.py --dry-run
```

打印出来的就是消息内容，同时会在 `out/latest.md` 留一份。**没有配任何密钥时这是唯一可用的命令**（不会报错，只会提示「渠道参数不全」）。

`运行.cmd` 支持的快捷参数：`预览` / `测试` / `发送`；不带参数则是交互式菜单。

> PowerShell 里必须写 `.\运行.cmd`（前面带 `.\`），CMD 里可以直接写 `运行.cmd`。

---

## 二、配置推送渠道

### 2.1 Server酱（推荐，也是默认主路径）

微信里收到一条「方糖」服务号消息，点开就是完整网页，链接可点。

1. 打开 <https://sct.ftqq.com>，微信扫码登录
2. 进「SendKey」页面，复制那串 `SCT` 开头的密钥
3. 填进 `.env`：

   ```dotenv
   PUSH_CHANNELS=serverchan
   SERVERCHAN_SENDKEY=SCT你的密钥
   ```

4. 验证：

   ```powershell
   .\运行.cmd 测试        # 微信「方糖」应立刻收到一条「daily-push 测试消息」
   ```

> **额度**：免费会员每天 5 条。一天三次用掉 3 条，剩下 2 条余量——手动重跑两三次就会超，超出后当天不再发。新用户有 7 天全功能试用。
>
> 想要零额度顾虑就换 PushPlus（约 200 条/天），见 2.3。

### 2.2 备用：公众号模板消息（默认不启用）

> **这一节默认用不上。** 项目按方糖（2.1）设计，`.env` 里所有 `WX_*` 配置**已注释停用**，代码只是把渠道留在那里备用。
> 想让消息显示成「你自己的公众号卡片」时再回来看这一节。

如果你已经有**接口测试号**或**认证服务号**，也能推到公众号卡片。但要知道它的天花板：

- 每张卡片只能显示 **3~4 行**，每个字段只显示 **一行**（约 26 字）
- 没有「展开全文」，点它也不会打开网页（除非你另配 `WX_LINK_URL`）

所以它适合「一眼摘要」，不适合十几条分板块的新闻。这也是本项目默认改用方糖的原因。

| 你的公众号 | 能用模板消息吗 | 怎么办 |
|---|---|---|
| 订阅号（个人注册默认） | ❌ 不行 | 用接口测试号 |
| 认证服务号（企业主体） | ✅ 可以 | 但模板字段有 20 字限制 |
| 接口测试号（谁都能申请） | ✅ 可以 | 最省事 |

> 关键事实：模板消息是**服务号**能力，订阅号没有。而个人主体注册的公众号一律是订阅号、又不能做微信认证，所以个人号永远拿不到这个权限。订阅号和服务号注册后也不能互转。

**用接口测试号的流程**（要启用时才做）：

1. 打开 <https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login> 扫码登录
2. 页面上的 **appID** / **appsecret** → 填 `.env` 的 `WX_APPID` / `WX_APPSECRET`（先把行首的 `# [已停用]` 去掉）
3. 扫页面上的**测试号二维码**关注它，然后在「用户列表」里找到你的 `openid` → 填 `WX_OPENID`
4. 「新增测试模板」，标题写 `每日速递`，内容：

   ```
   {{title.DATA}}
   🌤 天气：{{weather.DATA}}
   📰 要闻：{{news.DATA}}
   🧥 提示：{{tip.DATA}}
   {{remark.DATA}}
   ```

   保存后得到**模板 ID** → 填 `WX_TEMPLATE_ID`
5. `PUSH_CHANNELS` 改成 `wechat_mp`（想两个都收就写 `serverchan,wechat_mp`）
6. 如果跑在 GitHub Actions 上，还要把这 4 个值加回 Secrets

> ⚠️ **IP 白名单**：认证服务号如果开了 IP 白名单，GitHub Actions 的 IP 每次都不一样，会直接失败。测试号没这个问题。

### 2.3 其他渠道

```dotenv
# PushPlus（额度宽裕，免费约 200 条/天）
PUSH_CHANNELS=pushplus
PUSHPLUS_TOKEN=...

# 邮件（完整 HTML，链接可点）
PUSH_CHANNELS=mail
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=you@qq.com
SMTP_PASS=授权码          # QQ 邮箱：设置 → 账号 → 开启 SMTP → 生成授权码
MAIL_TO=you@qq.com

# 企业微信群机器人（个人也能注册企业微信）
WECOM_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...
```

多个渠道用逗号分隔（如 `serverchan,pushplus`），程序会**逐个发**，某个挂了不影响其他。

---

## 三、部署到 GitHub Actions（电脑关机也能收）

### 3.1 把代码传上去

```powershell
cd D:\dsh-work\dsh-wenjian\daily-push
git init -b main
git add .
git commit -m "init: 每日科技早报"
git remote add origin https://github.com/你的用户名/daily-push.git
git push -u origin main
```

第一次推会弹浏览器登录，选 **Sign in with your browser** 授权即可。

> `git add` 前用 `git status` 确认 **`.env` 不在列表里**（里面是密钥）。`.gitignore` 已经把它排除了。
> **千万不要用网页「拖拽上传」**——网页上传不认 `.gitignore`，会把 `.env` 一起传出去。

### 3.2 配置密钥

仓库页 → **Settings → Secrets and variables → Actions**

**Secrets**（New repository secret）：

| Name | 值 |
|---|---|
| `SERVERCHAN_SENDKEY` | `SCT...` 你的方糖密钥 |

**Variables**（New repository variable）：

| Name | 值 |
|---|---|
| `CITY` | `岳阳` |
| `PUSH_CHANNELS` | `serverchan` |
| `NEWS_COUNT` | `15` |
| `NEWS_MIX` | `ai:3,chip:3,phone:2,auto:2,energy:2` |

### 3.3 跑一次验证

仓库页 → **Actions** → 左边选「每日推送」→ 右边 **Run workflow** → 绿色按钮。

半分钟后微信应该收到；日志里能看到完整内容。之后每天 09:00 / 12:00 / 18:00 自动发。

### 3.4 必须知道的坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 晚几分钟到二十分钟 | GitHub 免费 runner 的定时任务排队延迟 | 正常，无法根治 |
| 两个月后突然不发了 | 仓库 60 天无提交，定时任务被自动停用 | 已带 `keepalive.yml` 每月自动提交一次；真停了去 Actions 页点「Enable workflow」 |
| Actions 分钟数不够 | 私有仓库每月 2000 分钟免费额度 | 一天三次、每次约 40 秒，一个月只用 60 分钟，够用 |
| 想改时间 | 改 `.github/workflows/daily.yml` 的 cron | cron 走 UTC，北京时间减 8 小时（09:00 → `0 1 * * *`） |

---

## 四、想在 QQ 上收

个人 QQ 没有官方机器人接口，最稳的两条路：

- **邮件 → QQ 邮箱**：配 `PUSH_CHANNELS=mail`，`MAIL_TO=你的QQ号@qq.com`，手机 QQ 会弹邮件提醒
- **Qmsg酱**（<https://qmsg.zendee.cn/>）：加一个机器人 QQ 好友。本项目没内置（接口常变），按它的文档加 20 行渠道模块即可

---

## 五、加一句 AI 总结（可选）

配好任意 OpenAI 兼容接口即可，不配就不发这一段：

```dotenv
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com/v1   # 也可换通义 / Moonshot / 本地 Ollama
LLM_MODEL=deepseek-chat
```

它会把当天选出的标题丢给模型，写一句不超过 55 字的概括。成本约每次几厘钱。

---

## 六、配置项全表

| 变量 | 默认 | 说明 |
|---|---|---|
| `CITY` | `北京` | 中文地名，自动地理编码；同名地多时可改用 `LATITUDE`/`LONGITUDE` |
| `PUSH_CHANNELS` | 自动 | 逗号分隔：`serverchan` `pushplus` `wechat_mp` `mail` `wecom`。**留空则按已配好的凭据自动选**（优先 serverchan → pushplus → wecom → wechat_mp → mail） |
| `SLOT` | `auto` | `morning` / `noon` / `evening`，`auto` 按当前时间判断 |
| `NEWS_SOURCES` | 7 个源 | `ithome` `ifanr` `sspai` `solidot` `geekpark` `tmtpost` `jiemian` |
| `NEWS_COUNT` | `6` | 选几条。**设了 `NEWS_MIX` 后此项被忽略**（总数 = 各板块配额之和） |
| `NEWS_MIX` | 空 | 板块配额，如 `ai:3,chip:3,phone:2,auto:2,energy:2`。留空则纯按分数选 |
| `NEWS_LOOKBACK_HOURS` | 自动 | 回看多少小时。留空=跟着时段走（早 12h / 午 4h / 晚 6h）；填数字则固定 |
| `EXTRAS` | 空 | `quote`(每日一句) `countdown`(倒数日) `fx`(汇率) |
| `COUNTDOWN` | 空 | 形如 `2027-01-01\|元旦` |
| `FX_PAIRS` | 空 | 形如 `USD:CNY,EUR:CNY` |
| `WX_FIELDS` | 空 | ⚠️ 仅在启用公众号时生效。模板消息里依次填哪些字段，必须和模板里的 `{{xxx.DATA}}` 一一对应 |
| `WX_LINK_URL` | 空 | ⚠️ 仅在启用公众号时生效。点开模板消息时跳转的地址 |

命令行：

```bash
python main.py              # 抓数据并推送
python main.py --dry-run    # 只生成预览，不发送
python main.py --explain    # 打印选稿明细和各类前 4 名，不发送
python main.py --test       # 发一条测试消息
python main.py --only mail  # 只发某个渠道
python main.py --show       # 顺带把完整 markdown 打到日志里
```

> `--dry-run` / `--show` 默认只打正文。只有 `PUSH_CHANNELS` 里包含 `wechat_mp` 时，才会额外打印公众号模板字段。

### 6.1 三次推送为什么不会重复

一天发三次，如果每次都回看 24 小时，第二、三次基本就是第一份的复制。所以回看窗口跟着时段走：

| 时段 | 回看 | 覆盖范围 | 实测候选 |
|---|---|---|---|
| 09:00 早 | 12 小时 | 昨晚 21:00 → 今早 | 103 条 |
| 12:00 午 | 4 小时 | 08:00 → 12:00 | 42 条 |
| 18:00 晚 | 6 小时 | 12:00 → 18:00 | 58 条 |

货不够时（比如午间只有 20 条候选）会自动放宽到 12 小时、再放宽到 24 小时，不会因为窗口太窄而发不满。想固定窗口就设 `NEWS_LOOKBACK_HOURS=24`。

### 6.2 行业板块与配额（NEWS_MIX）

消息按行业分板块，每块固定条数：

```dotenv
NEWS_MIX=ai:3,chip:3,phone:2,auto:2,energy:2
```

| 板块 | key | 收什么 | 不收什么 |
|---|---|---|---|
| 🤖 AI 前线 | `ai` | 大模型、智能体、OpenAI/DeepSeek、AI 应用与监管 | 纯股价行情 |
| 🔬 半导体芯片 | `chip` | 制程、晶圆、光刻、台积电、英伟达、存储、GPU、代工 | 手机 SoC（归手机） |
| 📱 手机 | `phone` | 手机/平板/Mac 的新品、开售、参数 | 机器人、汽车、公关人事 |
| 🚗 汽车 | `auto` | 整车、智驾、座舱、车企动态 | 电池与光伏（归新能源） |
| ⚡ 新能源 | `energy` | 光伏、储能、电池、电网、氢能 | 整车 |

规则：

- 一条新闻**只归一个板块**，判定优先级：`游戏 → AI → 手机 → 芯片 → 汽车 → 新能源 → 国际 → 其他`
- **哪个板块当天没货，就整个不输出**，不会留空标题、也不会硬凑
- 某个板块缺货时，空出来的位置由其他板块补位，但**每个板块最多补到「配额 + 1」**，不会一家独大
- **Epic / Steam 喜加一有保底**：当天只要有，就额外多一条（不挤占上面 12 条的配额），排在最前面
- 股市行情（涨跌、指数、中概股）会被直接过滤掉；活动预告、人事任命、辟谣声明会大幅降权
- 用 `--explain` 可以看每个板块的真实库存和前 4 名，核对分类准不准

不写 `NEWS_MIX` 就退回纯分数排序（不分板块）。

---

## 七、常见问题

**CMD 里敲 `python` 一点反应都没有**
Windows 10/11 自带一个 **0 字节的 `python.exe` 占位符**（在 `%LOCALAPPDATA%\Microsoft\WindowsApps\`），敲它什么都不输出、直接返回 9009——看起来就是"没反应"。任何 Python 程序都一样。

1. **双击 `运行.cmd`**（推荐），它会逐个试探候选、自动跳过那个占位符
2. 或装个真 Python：`winget install Python.Python.3.12`，装完**关掉 CMD 重开**

排查：`where python` 指向 `WindowsApps` 且文件大小是 0，就是这个问题。

**方糖返回 code 非 0**
密钥不对或额度用完了。免费会员每天 5 条，超了当天就不再发。

**方糖消息里点标题跳不过去**
标题链接是原文地址，部分站点（如爱范儿）的 RSS 带 utm 参数，跳转正常，只是地址较长。

**推送成功了但我没看到**
「方糖」提醒可能在微信的服务号通知里被折叠，或者你手机通知被静音了。打开微信搜「方糖」服务号能翻到历史消息。

**抓不到新闻**
免费 RSS 偶尔抽风或改地址。`NEWS_SOURCES` 换几个源；日志会打印哪个源失败。

**公众号报错（40001 / 40013 / 40003 / 47003）——只在启用了公众号时才会遇到**
`40001`/`40013` 是 AppID/AppSecret 错；`40003` 是 openid 错或没关注；`47003` 是 `WX_FIELDS` 和模板字段对不上。

---

## 八、想改内容？

- **加数据源**：在 `pusher/news.py` 的 `SOURCES` 里加一行 `key: (显示名, RSS 地址)`，再写进 `NEWS_SOURCES`。feed 必须是合法 XML（36氪、品玩、观察者网实测会返回坏数据，已排除）
- **改版式**：`pusher/render.py`，`render_markdown` / `render_plain` / `compact_fields` 各管一种输出
- **改排序**：`pusher/news.py` 的 `INTEREST`（关键词加权）、`_quality_penalty`（压日报/股闻/活动预告）、`categorize`（品类判定）
- **改配额**：`NEWS_MIX` 环境变量，不用动代码

## 目录结构

```
daily-push/
├── main.py                     入口 / CLI / 选稿编排
├── 运行.cmd / run.ps1          Windows 启动器（自动找可用的 Python）
├── pusher/
│   ├── config.py               环境变量 → 配置对象
│   ├── http.py                 urllib 封装（超时、重试）
│   ├── weather.py              Open-Meteo 天气 + 空气质量 + WMO 码 + 穿衣提示
│   ├── news.py                 RSS 抓取 / 去重 / 打分 / 分类 / 配额选稿
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

公众号模板消息的官方定位是「重要服务通知」，不支持营销内容。给自己的号推送属于自用，一般没人管；但如果公众号有真实粉丝、把模板消息当资讯推送来用，有被限制模板权限的风险——那种场景请用方糖、PushPlus 或邮件。
