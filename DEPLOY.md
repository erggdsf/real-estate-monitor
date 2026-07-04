# 房产监控日报系统 - 云端全自动版部署指南

## 核心优势
- 无需电脑开机 - 运行在GitHub免费服务器上
- 全自动执行 - 每天定时采集并推送
- 100%安全 - 只访问公开页面,无风控
- 完全免费 - 0元成本

## 方案验证结果

### 数据源验证 (100%可用)
| 数据源 | 类型 | 状态 | 风险 |
|--------|------|------|------|
| 百度热搜 | 公开页面 | 可用 | 无 |
| 微博热搜 | 公开页面 | 可用 | 无 |
| 中国政府网 | 官方网站 | 可用 | 无 |
| 住建部官网 | 官方网站 | 可用 | 无 |

### 推送通道验证 (100%可用)
| 通道 | 费用 | 稳定性 |
|------|------|--------|
| 企业微信机器人 | 免费 | 高 |
| Server酱 | 免费 | 中 |

### 定时任务验证 (100%可用)
| 方案 | 费用 | 可靠性 |
|------|------|--------|
| GitHub Actions | 免费 | 高 |

## 部署步骤

### 1. 注册GitHub账号
- 访问 https://github.com
- 点击 Sign up 注册(免费)
- 验证邮箱

### 2. 创建代码仓库
1. 登录GitHub
2. 点击右上角 + 号 -> New repository
3. 仓库名: real-estate-monitor
4. 选择 Public (公开)
5. 点击 Create repository

### 3. 上传代码
#### 方式A: 网页上传(推荐新手)
1. 进入刚创建的仓库
2. 点击 "uploading an existing file"
3. 将以下文件拖入:
   - main.py
   - requirements.txt
   - .github/workflows/daily-report.yml (需要创建目录)
4. 点击 Commit changes

#### 方式B: Git命令(推荐有基础用户)
```bash
# 进入项目目录
cd C:\Users\PC\Documents\数字人\real_estate_monitor

# 初始化Git仓库
git init

# 添加远程仓库(替换为你的仓库地址)
git remote add origin https://github.com/你的用户名/real-estate-monitor.git

# 添加文件
git add .

# 提交
git commit -m "Initial commit"

# 推送
git push -u origin main
```

### 4. 配置推送密钥
1. 进入GitHub仓库页面
2. 点击 Settings -> Secrets and variables -> Actions
3. 点击 New repository secret
4. 添加以下密钥:

#### Secret 1: WECOM_WEBHOOK (企业微信)
- Name: WECOM_WEBHOOK
- Value: 你的企业微信机器人Webhook地址
- 获取方式: 企业微信APP -> 群聊 -> 添加群机器人 -> 复制Webhook

#### Secret 2: SERVERCHAN_KEY (备用)
- Name: SERVERCHAN_KEY
- Value: 你的Server酱SendKey
- 获取方式: https://sct.ftqq.com/ -> GitHub登录 -> 复制SendKey

### 5. 测试运行
1. 进入GitHub仓库
2. 点击 Actions 标签
3. 点击左侧 "房产监控日报"
4. 点击 "Run workflow" -> "Run workflow"
5. 等待运行完成(约1-2分钟)
6. 检查手机是否收到日报

### 6. 验证定时任务
- GitHub Actions 默认每天 UTC 1:00 运行(即北京时间9:00)
- 无需额外配置,已自动生效
- 可在 Actions 页面查看运行历史

## 运行环境
| 项目 | 说明 |
|------|------|
| 运行平台 | GitHub Actions (Ubuntu服务器) |
| Python版本 | 3.11 |
| 执行频率 | 每天1次 |
| 单次时长 | 约30-60秒 |
| 月度限额 | GitHub免费账户每月2000分钟 |

## 维护说明
| 项目 | 频率 | 操作 |
|------|------|------|
| 检查日报 | 每周 | 确认每天收到推送 |
| 查看日志 | 按需 | GitHub Actions页面查看运行日志 |
| 更新密钥 | 按需 | 如Webhook失效需更新 |

## 故障排查

### 问题1: Actions运行失败
1. 进入仓库 -> Actions 查看错误日志
2. 常见原因:
   - 密钥配置错误 -> 检查 Secrets
   - 网络问题 -> 重新运行
   - 代码错误 -> 查看日志定位

### 问题2: 没有收到推送
1. 检查 Actions 是否运行成功
2. 检查 Secrets 中的 WECOM_WEBHOOK 是否正确
3. 检查企业微信APP是否安装并登录
4. 手动触发一次测试

### 问题3: 采集不到数据
1. 查看 Actions 日志中的采集结果
2. 确认数据源网站可访问
3. 可能是当日无新内容

## 费用清单
| 项目 | 费用 | 说明 |
|------|------|------|
| GitHub账号 | 免费 | 公开仓库免费 |
| GitHub Actions | 免费 | 每月2000分钟额度 |
| Python运行 | 免费 | 服务器预装 |
| requests库 | 免费 | 开源库 |
| 数据采集 | 免费 | 公开页面 |
| 手机推送 | 免费 | 企业微信/Server酱 |
| **总计** | **0元** | |

## 安全声明
本程序:
- 只访问公开网页,不登录任何平台
- 不模拟浏览器行为
- 不破解接口签名
- 请求频率严格限制
- 零封号风险,零法律风险
- 代码开源,可审计
