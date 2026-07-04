#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
房产短视频监控日报系统 - 付费API版
支持平台: 抖音全平台搜索
数据源: 新榜/飞瓜/蝉妈妈 API
特点: 全平台搜索,数据完整,自动化推送
"""

import os
import sys
import json
import time
import sqlite3
import hashlib
import datetime
import hmac
import base64
from urllib.parse import quote, urlencode
from pathlib import Path

# ============ 依赖检查 ============
try:
    import requests
except ImportError:
    print("[ERROR] 缺少依赖: pip install requests")
    sys.exit(1)

# ============ 配置区 ============
CONFIG = {
    # 推送配置(至少填一个)
    "wecom_webhook": os.getenv("WECOM_WEBHOOK", ""),
    "serverchan_key": os.getenv("SERVERCHAN_KEY", ""),
    
    # 数据平台配置（三选一）
    # 方案1: 新榜有数
    "xinbang": {
        "app_key": os.getenv("XINBANG_APP_KEY", ""),
        "app_secret": os.getenv("XINBANG_APP_SECRET", ""),
        "base_url": "https://open.newrank.cn/api",
    },
    
    # 方案2: 飞瓜数据
    "feigua": {
        "app_key": os.getenv("FEIGUA_APP_KEY", ""),
        "app_secret": os.getenv("FEIGUA_APP_SECRET", ""),
        "base_url": "https://open.feigua.cn/api",
    },
    
    # 方案3: 蝉妈妈
    "chanmama": {
        "app_id": os.getenv("CHANMAMA_APP_ID", ""),
        "app_key": os.getenv("CHANMAMA_APP_KEY", ""),
        "base_url": "https://openapi.chanmama.com",
    },
    
    # 选择使用的平台: "xinbang" / "feigua" / "chanmama"
    "platform": os.getenv("DATA_PLATFORM", "chanmama"),
    
    # 数据存储路径
    "db_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db"),
    
    # 搜索关键词
    "keywords": ["房产", "买房", "楼市", "房价", "地产", "楼盘", "二手房", "新房"],
    
    # 优质视频阈值
    "quality_threshold": {
        "min_likes": 1000,
        "min_plays": 10000,
    },
    
    # 每日采集数量
    "max_videos_per_day": 50,
}

# ============ 数据库 ============
def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(CONFIG["db_path"])
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            platform TEXT,
            author TEXT,
            title TEXT,
            url TEXT,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            plays INTEGER DEFAULT 0,
            publish_time TEXT,
            collected_at TEXT,
            is_quality INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            url TEXT,
            summary TEXT,
            collected_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def log(level, message):
    """记录日志"""
    print(f"[{level}] {message}")

# ============ 数据平台API封装 ============
class DataPlatformAPI:
    """统一的数据平台API接口"""
    
    @staticmethod
    def search_videos(keyword, page=1, page_size=20):
        """
        搜索视频
        根据配置的平台调用对应的API
        """
        platform = CONFIG["platform"]
        
        if platform == "xinbang":
            return DataPlatformAPI._search_xinbang(keyword, page, page_size)
        elif platform == "feigua":
            return DataPlatformAPI._search_feigua(keyword, page, page_size)
        elif platform == "chanmama":
            return DataPlatformAPI._search_chanmama(keyword, page, page_size)
        else:
            log("ERROR", f"不支持的平台: {platform}")
            return []
    
    @staticmethod
    def _search_xinbang(keyword, page, page_size):
        """新榜有数API - 搜索抖音视频"""
        cfg = CONFIG["xinbang"]
        if not cfg["app_key"] or not cfg["app_secret"]:
            log("ERROR", "新榜API密钥未配置")
            return []
        
        try:
            # 生成签名
            timestamp = str(int(time.time()))
            params = {
                "app_key": cfg["app_key"],
                "timestamp": timestamp,
                "keyword": keyword,
                "page": page,
                "page_size": page_size,
            }
            
            # 按key排序并拼接
            sorted_params = sorted(params.items())
            sign_str = "&".join([f"{k}={v}" for k, v in sorted_params]) + cfg["app_secret"]
            sign = hashlib.md5(sign_str.encode()).hexdigest()
            params["sign"] = sign
            
            url = f"{cfg['base_url']}/douyin/video/search"
            resp = requests.get(url, params=params, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return DataPlatformAPI._parse_xinbang_videos(data.get("data", {}).get("list", []))
                else:
                    log("ERROR", f"新榜API错误: {data.get('msg')}")
            else:
                log("ERROR", f"新榜HTTP错误: {resp.status_code}")
        
        except Exception as e:
            log("ERROR", f"新榜请求异常: {e}")
        
        return []
    
    @staticmethod
    def _search_feigua(keyword, page, page_size):
        """飞瓜数据API - 搜索抖音视频"""
        cfg = CONFIG["feigua"]
        if not cfg["app_key"] or not cfg["app_secret"]:
            log("ERROR", "飞瓜API密钥未配置")
            return []
        
        try:
            timestamp = str(int(time.time()))
            params = {
                "app_key": cfg["app_key"],
                "timestamp": timestamp,
                "keyword": keyword,
                "page": page,
                "page_size": page_size,
            }
            
            # 生成签名
            sorted_params = sorted(params.items())
            sign_str = "&".join([f"{k}={v}" for k, v in sorted_params]) + cfg["app_secret"]
            sign = hashlib.md5(sign_str.encode()).hexdigest()
            params["sign"] = sign
            
            url = f"{cfg['base_url']}/video/search"
            resp = requests.get(url, params=params, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return DataPlatformAPI._parse_feigua_videos(data.get("data", {}).get("list", []))
                else:
                    log("ERROR", f"飞瓜API错误: {data.get('msg')}")
            else:
                log("ERROR", f"飞瓜HTTP错误: {resp.status_code}")
        
        except Exception as e:
            log("ERROR", f"飞瓜请求异常: {e}")
        
        return []
    
    @staticmethod
    def _search_chanmama(keyword, page, page_size):
        """蝉妈妈API - 搜索抖音视频"""
        cfg = CONFIG["chanmama"]
        if not cfg["app_id"] or not cfg["app_key"]:
            log("ERROR", "蝉妈妈API密钥未配置")
            return []
        
        try:
            timestamp = str(int(time.time()))
            params = {
                "app_id": cfg["app_id"],
                "timestamp": timestamp,
                "keyword": keyword,
                "page": page,
                "page_size": page_size,
            }
            
            # 生成签名
            sign_str = f"app_id={cfg['app_id']}&timestamp={timestamp}{cfg['app_key']}"
            sign = hashlib.md5(sign_str.encode()).hexdigest()
            params["sign"] = sign
            
            url = f"{cfg['base_url']}/v1/douyin/video/search"
            resp = requests.get(url, params=params, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return DataPlatformAPI._parse_chanmama_videos(data.get("data", {}).get("list", []))
                else:
                    log("ERROR", f"蝉妈妈API错误: {data.get('msg')}")
            else:
                log("ERROR", f"蝉妈妈HTTP错误: {resp.status_code}")
        
        except Exception as e:
            log("ERROR", f"蝉妈妈请求异常: {e}")
        
        return []
    
    @staticmethod
    def _parse_xinbang_videos(items):
        """解析新榜视频数据"""
        videos = []
        for item in items:
            video = {
                "id": str(item.get("aweme_id", "")),
                "platform": "抖音",
                "author": item.get("author", {}).get("nickname", ""),
                "title": item.get("title", "")[:200],
                "url": item.get("share_url", ""),
                "likes": item.get("digg_count", 0),
                "comments": item.get("comment_count", 0),
                "shares": item.get("share_count", 0),
                "plays": item.get("play_count", 0),
                "publish_time": item.get("create_time", ""),
            }
            videos.append(video)
        return videos
    
    @staticmethod
    def _parse_feigua_videos(items):
        """解析飞瓜视频数据"""
        videos = []
        for item in items:
            video = {
                "id": str(item.get("aweme_id", "")),
                "platform": "抖音",
                "author": item.get("author_name", ""),
                "title": item.get("title", "")[:200],
                "url": item.get("share_url", ""),
                "likes": item.get("digg_count", 0),
                "comments": item.get("comment_count", 0),
                "shares": item.get("share_count", 0),
                "plays": item.get("play_count", 0),
                "publish_time": item.get("create_time", ""),
            }
            videos.append(video)
        return videos
    
    @staticmethod
    def _parse_chanmama_videos(items):
        """解析蝉妈妈视频数据"""
        videos = []
        for item in items:
            video = {
                "id": str(item.get("aweme_id", "")),
                "platform": "抖音",
                "author": item.get("author_name", ""),
                "title": item.get("title", "")[:200],
                "url": item.get("share_url", ""),
                "likes": item.get("digg_count", 0),
                "comments": item.get("comment_count", 0),
                "shares": item.get("share_count", 0),
                "plays": item.get("play_count", 0),
                "publish_time": item.get("create_time", ""),
            }
            videos.append(video)
        return videos

# ============ 视频采集 ============
class VideoCollector:
    """视频采集器 - 通过付费API"""
    
    @staticmethod
    def collect_all():
        """采集所有关键词的视频"""
        all_videos = []
        
        for keyword in CONFIG["keywords"]:
            log("INFO", f"搜索关键词: {keyword}...")
            videos = DataPlatformAPI.search_videos(keyword, page=1, page_size=20)
            all_videos.extend(videos)
            log("INFO", f"{keyword}: {len(videos)} 条")
            time.sleep(2)
        
        # 去重
        seen = set()
        unique = []
        for v in all_videos:
            if v["id"] and v["id"] not in seen:
                seen.add(v["id"])
                unique.append(v)
        
        # 限制数量
        return unique[:CONFIG["max_videos_per_day"]]

# ============ 数据存储 ============
class DataStore:
    @staticmethod
    def save_videos(videos):
        if not videos:
            return 0
        
        conn = sqlite3.connect(CONFIG["db_path"])
        cursor = conn.cursor()
        added = 0
        
        for v in videos:
            is_quality = 1 if (v.get("likes", 0) >= CONFIG["quality_threshold"]["min_likes"] or
                              v.get("plays", 0) >= CONFIG["quality_threshold"]["min_plays"]) else 0
            
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO videos 
                    (id, platform, author, title, url, likes, comments, shares, plays, publish_time, collected_at, is_quality)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    v["id"], v["platform"], v["author"], v["title"], v["url"],
                    v.get("likes", 0), v.get("comments", 0), v.get("shares", 0), v.get("plays", 0),
                    v.get("publish_time", ""), datetime.datetime.now().isoformat(), is_quality
                ))
                if cursor.rowcount > 0:
                    added += 1
            except Exception as e:
                log("ERROR", f"保存视频失败: {e}")
        
        conn.commit()
        conn.close()
        return added
    
    @staticmethod
    def get_today_data():
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(CONFIG["db_path"])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT platform, author, title, url, likes, comments, shares, plays
            FROM videos 
            WHERE collected_at LIKE ?
            ORDER BY likes DESC
            LIMIT 20
        ''', (f"{today}%",))
        videos = cursor.fetchall()
        
        conn.close()
        return videos

# ============ 推送模块 ============
class PushNotifier:
    @staticmethod
    def send(message, title="房产监控日报"):
        success = False
        
        if CONFIG["wecom_webhook"]:
            if PushNotifier._send_wecom(message):
                success = True
        
        if CONFIG["serverchan_key"]:
            if PushNotifier._send_serverchan(title, message):
                success = True
        
        return success
    
    @staticmethod
    def _send_wecom(message):
        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {"content": message}
            }
            resp = requests.post(CONFIG["wecom_webhook"], json=payload, timeout=15)
            result = resp.json()
            if result.get("errcode") == 0:
                log("INFO", "企业微信推送成功")
                return True
            else:
                log("ERROR", f"企业微信推送失败: {result}")
                return False
        except Exception as e:
            log("ERROR", f"企业微信请求异常: {e}")
            return False
    
    @staticmethod
    def _send_serverchan(title, message):
        try:
            url = f"https://sctapi.ftqq.com/{CONFIG['serverchan_key']}.send"
            resp = requests.post(url, data={"title": title, "desp": message}, timeout=15)
            result = resp.json()
            if result.get("code") == 0:
                log("INFO", "Server酱推送成功")
                return True
            else:
                log("ERROR", f"Server酱推送失败: {result}")
                return False
        except Exception as e:
            log("ERROR", f"Server酱请求异常: {e}")
            return False
    
    @staticmethod
    def send_daily_report():
        today = datetime.datetime.now().strftime("%Y年%m月%d日")
        videos = DataStore.get_today_data()
        
        lines = [f"# 抖音房产监控日报 ({today})\n"]
        
        lines.append("## 今日优质房产短视频\n")
        if videos:
            for v in videos[:15]:
                platform, author, title, url, likes, comments, shares, plays = v
                quality_mark = "🔥" if likes >= CONFIG["quality_threshold"]["min_likes"] else ""
                lines.append(f"{quality_mark} **{author}**")
                lines.append(f"   {title}")
                lines.append(f"   [点击观看]({url})")
                lines.append(f"   ▶️{plays} 👍{likes} 💬{comments} 📤{shares}")
                lines.append("")
        else:
            lines.append("> 今日暂无新视频\n")
        
        lines.append("---")
        lines.append("*自动发送*")
        
        message = "\n".join(lines)
        return PushNotifier.send(message, f"抖音房产监控日报 {today}")

# ============ 主程序 ============
def main():
    start_time = datetime.datetime.now()
    log("INFO", "=" * 40)
    log("INFO", "抖音房产监控日报系统启动")
    log("INFO", f"使用平台: {CONFIG['platform']}")
    log("INFO", f"开始时间: {start_time.isoformat()}")
    log("INFO", "=" * 40)
    
    init_db()
    
    log("INFO", "[1/2] 开始采集视频数据...")
    videos = VideoCollector.collect_all()
    video_added = DataStore.save_videos(videos)
    log("INFO", f"[1/2] 视频采集完成,新增: {video_added} 条")
    
    log("INFO", "[2/2] 发送日报...")
    if PushNotifier.send_daily_report():
        log("INFO", "[2/2] 日报发送成功")
    else:
        log("ERROR", "[2/2] 日报发送失败,请检查推送配置")
    
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    log("INFO", "=" * 40)
    log("INFO", f"执行完成,耗时: {duration:.1f} 秒")
    log("INFO", "=" * 40)

if __name__ == "__main__":
    main()
