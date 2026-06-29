# Spotify 歌单自动化工具

将一份华语老歌列表批量搜索并添加到 Spotify 歌单。

## 功能

- 从 `songs.csv` 读取歌曲列表
- 使用 Spotify Web API 逐首搜索最佳匹配
- 一次性将所有找到的歌曲添加到指定歌单
- 详细的进度输出和未匹配歌曲汇总
- Token 缓存，首次授权后可重复使用

## 前置要求

- Python 3.8+
- [Spotify Developer 账号](https://developer.spotify.com/)

## 安装

```bash
pip install spotipy
```

## 配置

### 1. 创建 Spotify Developer 应用

1. 访问 [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. 登录你的 Spotify 账号
3. 点击 **"Create App"**
4. 填写应用名称和描述（任意填即可）
5. 勾选 **"Web API"** 权限
6. 点击 **"Show client secret"** 获取凭证

### 2. 设置凭证

凭证已通过 `.env` 文件配置。如需修改：

```bash
cp .env.example .env
# 编辑 .env，填入你的 CLIENT_ID 和 CLIENT_SECRET
```

或直接设置环境变量：

```bash
export SPOTIPY_CLIENT_ID="你的ClientID"
export SPOTIPY_CLIENT_SECRET="你的ClientSecret"
export PLAYLIST_ID="你的歌单ID"
```

## 使用方法

### 第一步：授权（只需执行一次）

```bash
python main.py auth
```

这会打开浏览器，让你登录 Spotify 并授权应用。授权成功后 token 会自动缓存到 `.spotify_tokens.json`。

### 第二步：运行添加

```bash
python main.py                              # 使用 .env 中的 PLAYLIST_ID
python main.py <歌单ID>                     # 命令行指定歌单 ID
python main.py --force-auth                 # 强制重新授权
```

示例：

```bash
python main.py 3iTS9MK0wnrUFqpKb5NBLo --use-token
```

### 获取歌单 ID

在 Spotify 中打开目标歌单，点击 **"分享" → "复制 Spotify 链接"**：

```
https://open.spotify.com/playlist/3iTS9MK0wnrUFqpKb5NBLo
                                        ^^^^^^^^^^^^^^^^^^
                                        这就是歌单 ID
```

## 数据格式

歌曲列表保存在 `songs.csv` 文件中，格式为：

```csv
song,artist
秋天不回来,王强
求佛,誓言
```

- `song`: 歌曲名称
- `artist`: 歌手名称

修改此文件即可自定义要添加的歌曲列表。

## 工作流程

```
读取 songs.csv
    ↓
Authorization Code 认证（首次）/ 缓存 Token（后续）
    ↓
逐首搜索 (歌曲名 + 歌手名)
    ↓
收集匹配的 track URI
    ↓
确认添加
    ↓
批量添加到歌单
```

## 搜索策略

1. **精确搜索**：同时使用歌曲名和歌手名搜索（如 `"秋天不回来 王强"`），提高匹配准确率
2. **降级搜索**：如果精确搜索未找到，尝试只用歌曲名在前 5 个结果中模糊匹配歌手名
3. **重试机制**：每次搜索最多重试 3 次，应对网络波动
4. **请求限速**：每次搜索之间间隔 0.5 秒，避免触发 API 限流

## 输出示例

```
[认证] 正在连接 Spotify API ...
[认证] 认证成功！
[加载] 共加载 51 首歌

============================================================
开始搜索 51 首歌 ...
============================================================

  [1/51] [OK] 秋天不回来 - 王强
  [2/51] [OK] 求佛 - 誓言
  [3/51] [未找到] 一万个理由 - 郑源
  ...

============================================================
搜索完成: 找到 48 首, 未找到 3 首
============================================================

以下歌曲未找到匹配结果，请检查:
  - 一万个理由 - 郑源
  - ...

是否将 48 首歌曲添加到歌单 '3iTS9MK0wnrUFqpKb5NBLo'? [y/N] y

正在添加到歌单 ...
  [添加] 本批 48 首，累计已添加 48 首

全部完成！请在 Spotify 中查看歌单。
```

## 故障排查

| 问题 | 解决方法 |
|------|----------|
| 认证失败 | 检查 CLIENT_ID 和 CLIENT_SECRET 是否正确 |
| 需要重新授权 | 删除 `.spotify_tokens.json`，重新运行 `python main.py auth` |
| 大量歌曲未找到 | Spotify 曲库因地区而异，某些歌曲可能在你的地区不可用 |
| API 限流 | 脚本已内置限速，如遇 429 错误请等待后重试 |
| 浏览器未自动打开 | 手动复制终端显示的授权 URL 到浏览器完成授权 |
