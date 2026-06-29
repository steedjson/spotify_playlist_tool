"""
Spotify 歌单自动化工具 — 批量搜索歌曲并添加到指定歌单。

使用 Authorization Code Flow 认证，需要用户首次授权。
Token 会自动缓存到 .spotify_tokens.json，后续可直接使用。

用法:
    python main.py auth                          # 首次授权
    python main.py                               # 搜索并添加到默认歌单
    python main.py --force-auth                  # 强制重新授权
"""

import csv
import json
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

import spotipy
from spotipy.oauth2 import SpotifyOAuth

# 将当前目录加入路径，以便导入 config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CLIENT_ID, CLIENT_SECRET, PLAYLIST_ID  # noqa: E402

# ---------- 常量 ----------

SCRIPT_DIR = Path(__file__).resolve().parent
SONGS_CSV = SCRIPT_DIR / "songs.csv"
TOKEN_FILE = SCRIPT_DIR / ".spotify_tokens.json"
MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_DELAY = 0.5

SCOPES = "playlist-modify-public playlist-modify-private"
REDIRECT_URI = "http://127.0.0.1:8080/callback"

# 目标歌单 ID — 优先级: CLI 参数 > 环境变量 > 硬编码默认值
_DEFAULT_PLAYLIST_ID = "3iTS9MK0wnrUFqpKb5NBLo"


def get_auth_manager():
    """创建 SpotifyOAuth 管理器（带文件缓存）。"""
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        cache_handler=spotipy.cache_handler.CacheFileHandler(cache_path=str(TOKEN_FILE)),
        open_browser=False,
    )


def load_cached_token():
    """加载缓存的 token，如果存在且未过期则返回。"""
    handler = spotipy.cache_handler.CacheFileHandler(cache_path=str(TOKEN_FILE))
    token_info = handler.get_cached_token()
    if token_info is not None:
        auth = get_auth_manager()
        validated = auth.validate_token(token_info)
        if validated is not None:
            return validated
    return None


def get_sp():
    """获取已认证的 spotipy 客户端。"""
    print("[认证] 正在连接 Spotify API ...")

    # 尝试使用缓存 token
    token_info = load_cached_token()
    if token_info:
        auth = get_auth_manager()
        auth.cache_handler.save_token_to_cache(token_info)
        sp = spotipy.Spotify(auth_manager=auth)
        try:
            sp.current_user()
            print("[认证] 使用缓存 token 认证成功！")
            return sp
        except spotipy.exceptions.SpotifyException:
            pass

    # 没有有效缓存，需要重新授权
    print("[认证] 没有找到有效的 token，需要先授权 ...")
    print()
    token_info = do_authorize()

    # 授权后创建客户端
    auth = get_auth_manager()
    auth.cache_handler.save_token(token_info)
    sp = spotipy.Spotify(auth_manager=auth)

    try:
        sp.current_user()
        print("[认证] 认证成功！")
    except spotipy.exceptions.SpotifyException as e:
        print(f"[错误] 认证失败: {e}")
        sys.exit(1)

    return sp


def do_authorize():
    """执行完整的授权流程，返回 token_info dict。"""
    print("=" * 60)
    print("Spotify 授权")
    print("=" * 60)
    print()

    auth = get_auth_manager()
    auth_url = auth.get_authorize_url()

    print("1. 打开以下链接，登录 Spotify 并授权:")
    print()
    print(f"   {auth_url}")
    print()
    print("2. 授权后浏览器会跳转到 http://127.0.0.1:8080/callback")
    print("3. 等待回调接收授权码 ...")
    print()

    # 启动本地 HTTP 服务器接收回调
    received_code = {"code": None, "done": False}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/callback":
                params = parse_qs(parsed.query)
                received_code["code"] = params.get("code", [None])[0]
                received_code["done"] = True

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                msg = "✅ 授权成功！<p>你可以关闭此窗口，回到终端继续。</p>"
                self.wfile.write(msg.encode("utf-8"))

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 8080), CallbackHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # 自动打开浏览器
    import webbrowser
    webbrowser.open(auth_url)

    # 等待授权完成（最多 120 秒）
    for _ in range(120):
        if received_code["done"]:
            break
        time.sleep(1)

    server.shutdown()

    if not received_code["code"]:
        print("[错误] 授权超时（120 秒），请重试。")
        print("提示: 你也可以手动复制上面的授权 URL 到浏览器完成授权，")
        print("      然后从回调 URL 中复制 code 参数。")
        sys.exit(1)

    print(f"[回调] 收到授权码 (长度={len(received_code['code'])})")
    print("[认证] 正在换取 access token ...")

    # 用 code 换取 token
    token_info = auth.get_access_token(code=received_code["code"])

    if not token_info:
        print("[错误] 未能获取 token，请重试。")
        sys.exit(1)

    print(f"[认证] Token 已缓存到 {TOKEN_FILE}")
    print()
    print("[授权] 完成！现在可以直接运行:")
    print("  python main.py")
    print()
    return token_info


def load_songs(csv_path):
    """从 CSV 文件加载歌曲列表。"""
    if not csv_path.exists():
        print(f"[错误] 找不到歌曲列表文件: {csv_path}")
        sys.exit(1)

    songs = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["song", "artist"]:
            print(f"[错误] CSV 格式不正确，期望列名: song,artist，实际: {reader.fieldnames}")
            sys.exit(1)

        for row in reader:
            song_name = row["song"].strip()
            artist_name = row["artist"].strip()
            if song_name and artist_name:
                songs.append({"song": song_name, "artist": artist_name})

    print(f"[加载] 共加载 {len(songs)} 首歌")
    return songs


def search_track(sp, song_name, artist_name):
    """搜索一首歌，返回最佳匹配的 track URI。"""
    query = f"{song_name} {artist_name}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            results = sp.search(q=query, type="track", limit=1)
            items = results.get("tracks", {}).get("items", [])
            if items:
                return items[0]["uri"]

            # 降级搜索：只用歌曲名
            if attempt == 1:
                results = sp.search(q=song_name, type="track", limit=5)
                items = results.get("tracks", {}).get("items", [])
                for item in items:
                    artist_match = any(
                        artist_name in a["name"] or a["name"] in artist_name
                        for a in item["artists"]
                    )
                    if artist_match:
                        return item["uri"]

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        except spotipy.exceptions.SpotifyException as e:
            error_msg = e.get("body", {}).get("error", {}).get("message", "未知错误")
            if attempt < MAX_RETRIES:
                print(f"  [警告] 搜索失败 ({error_msg})，第 {attempt}/{MAX_RETRIES} 次重试 ...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  [错误] 搜索最终失败: {error_msg}")
                return None

    return None


def get_existing_track_uris(sp, playlist_id):
    """获取歌单中已有的所有 track URI。"""
    existing = set()
    # 先获取总数
    items = sp.playlist_items(playlist_id=playlist_id)
    total = items.get("total", 0)

    # 逐页获取 URI（数据在 item 字段中，不是 track）
    limit = 100
    offset = 0
    while offset < total:
        items = sp.playlist_items(
            playlist_id=playlist_id,
            offset=offset,
            limit=limit,
        )
        for it in items.get("items", []):
            obj = it.get("item")
            if obj and obj.get("type") == "track" and obj.get("uri"):
                existing.add(obj["uri"])
        offset += limit
    return existing


def add_tracks_to_playlist(sp, playlist_id, track_uris):
    """将一批 track URI 添加到指定歌单。"""
    BATCH_SIZE = 100

    for i in range(0, len(track_uris), BATCH_SIZE):
        batch = track_uris[i:i + BATCH_SIZE]
        try:
            sp.playlist_add_items(playlist_id, batch)
            print(f"  [添加] 本批 {len(batch)} 首，累计已添加 {i + len(batch)} 首")
        except spotipy.exceptions.SpotifyException as e:
            error_msg = e.get("body", {}).get("error", {}).get("message", "未知错误")
            print(f"  [错误] 添加失败: {error_msg}")

    print(f"\n[完成] 共向歌单 '{playlist_id}' 添加了 {len(track_uris)} 首歌曲")


def main():
    """主函数。"""
    force_auth = "--force-auth" in sys.argv
    argv = [a for a in sys.argv if a != "--force-auth"]

    # 解析歌单 ID: CLI 参数 > 环境变量 > 硬编码默认值
    playlist_id = _DEFAULT_PLAYLIST_ID
    if len(argv) >= 2 and argv[1] != "auth":
        playlist_id = argv[1]
    elif PLAYLIST_ID:
        playlist_id = PLAYLIST_ID

    if len(argv) < 1:
        print("用法:")
        print()
        print("  首次授权:")
        print("    python main.py auth")
        print()
        print("  搜索并添加到歌单:")
        print("    python main.py                  # 使用 .env 中的 PLAYLIST_ID")
        print("    python main.py <歌单ID>          # 命令行指定歌单 ID")
        print("    python main.py --force-auth      # 强制重新授权")
        print()
        print(f"当前歌单: {playlist_id}")
        sys.exit(1)

    if len(argv) >= 2 and argv[1] == "auth":
        do_authorize()
        return

    # 认证
    if force_auth:
        do_authorize()
    sp = get_sp()

    # 加载歌曲列表
    songs = load_songs(SONGS_CSV)
    if not songs:
        print("[错误] 歌曲列表为空，请检查 songs.csv")
        sys.exit(1)

    # 获取歌单已有歌曲
    print()
    print("检查歌单已有歌曲 ...")
    existing_uris = get_existing_track_uris(sp, playlist_id)
    print(f"[检查] 歌单中已有 {len(existing_uris)} 首歌曲")

    # 逐首搜索
    print()
    print("=" * 60)
    print(f"开始搜索 {len(songs)} 首歌 ...")
    print("=" * 60)
    print()

    found_uris = []
    already_exists = []
    not_found = []
    total = len(songs)

    for idx, song in enumerate(songs, 1):
        uri = search_track(sp, song["song"], song["artist"])

        if uri:
            if uri in existing_uris:
                already_exists.append(song)
                print(f"  [{idx}/{total}] [已有] {song['song']} - {song['artist']}")
            else:
                found_uris.append(uri)
                print(f"  [{idx}/{total}] [OK] {song['song']} - {song['artist']}")
        else:
            not_found.append(song)
            print(f"  [{idx}/{total}] [未找到] {song['song']} - {song['artist']}")

        if idx < total:
            time.sleep(REQUEST_DELAY)

    # 汇总
    print()
    print("=" * 60)
    print(f"搜索完成: 新增 {len(found_uris)} 首, 已有 {len(already_exists)} 首, 未找到 {len(not_found)} 首")
    print("=" * 60)

    if already_exists:
        print()
        print("以下歌曲已在歌单中，不会重复添加:")
        for song in already_exists:
            print(f"  - {song['song']} - {song['artist']}")

    if not_found:
        print()
        print("以下歌曲未找到匹配结果，请检查:")
        for song in not_found:
            print(f"  - {song['song']} - {song['artist']}")

    if not found_uris and not already_exists:
        print("\n[提示] 所有歌曲都已存在于歌单中，无需操作。")
        sys.exit(0)

    # 确认
    print()
    try:
        confirm = input(f"是否将 {len(found_uris)} 首歌曲添加到歌单 '{playlist_id}'? [y/N] ").strip().lower()
        confirmed = confirm in ("y", "yes")
    except EOFError:
        print(f"[自动] 检测到非交互式环境，自动确认添加 {len(found_uris)} 首歌曲 ...")
        confirmed = True

    if not confirmed:
        print("[取消] 操作已取消。")
        sys.exit(0)

    # 添加到歌单
    print()
    print("=" * 60)
    print("正在添加到歌单 ...")
    print("=" * 60)
    add_tracks_to_playlist(sp, playlist_id, found_uris)

    print()
    print("全部完成！请在 Spotify 中查看歌单。")


if __name__ == "__main__":
    main()
