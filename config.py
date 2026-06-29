"""
配置文件 — 从环境变量读取 Spotify API 凭证。

使用前请先复制 .env.example 为 .env，填入你的 Spotify Developer 应用的
CLIENT_ID 和 CLIENT_SECRET。
"""

import os
import sys
from pathlib import Path

# 自动加载同目录下的 .env 文件
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # 去掉可能存在的引号
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                os.environ.setdefault(key, value)


def get_spotify_credentials():
    """获取 Spotify API 凭证。

    优先从环境变量读取，如果未设置则打印提示信息并退出。

    Returns:
        tuple: (client_id, client_secret)

    Raises:
        SystemExit: 当缺少必要的环境变量时。
    """
    client_id = os.environ.get("SPOTIPY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("=" * 60)
        print("错误：缺少 Spotify API 凭证")
        print("=" * 60)
        print()
        print("请按以下步骤配置：")
        print()
        print("  1. 访问 https://developer.spotify.com/dashboard ，登录你的账号")
        print("  2. 点击 'Create an App' 创建一个新的应用")
        print("  3. 记下页面上的 'Client ID'")
        print("  4. 点击 'Show client secret' 获取 'Client Secret'")
        print("  5. 在项目根目录创建 .env 文件，填入：")
        print()
        print("     SPOTIPY_CLIENT_ID=你的ClientID")
        print("     SPOTIPY_CLIENT_SECRET=你的ClientSecret")
        print()
        print("     或者直接在终端设置环境变量：")
        print()
        print("     export SPOTIPY_CLIENT_ID='你的ClientID'")
        print("     export SPOTIPY_CLIENT_SECRET='你的ClientSecret'")
        print()
        print("=" * 60)
        sys.exit(1)

    return client_id, client_secret


# 模块加载时自动校验凭证
CLIENT_ID, CLIENT_SECRET = get_spotify_credentials()

# 歌单 ID — 从环境变量读取，允许为空（由 main.py 提供默认值）
PLAYLIST_ID = os.environ.get("PLAYLIST_ID", "").strip()
