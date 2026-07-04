#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
房产短视频监控日报系统 - 房产大V版
功能：监控指定房产大V账号的最新视频（抖音/快手/视频号）
      采集各平台房产相关政策
      每日定点推送到手机微信
"""

import os
import sys
import json
import time
import sqlite3
import hashlib
import datetime
import re
from urllib.parse import quote
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
    
    # 数据存储路径
    "db_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db"),
    
    # 请求间隔（秒）
    "request_delay": 5,
    
    # 每日最大请求数
    "max_requests_per_day": 50,
    
    # 优质视频判定阈值
    "quality_threshold": {
        "min_likes": 1000,
        "min_comments": 100,
    },
    
    # 监控的房产大V账号列表
    # 格式: {"platform": "抖音/快手/视频号", "name": "显示名称", "user_id": "用户ID"}
    "accounts": [
        # 抖音房产大V示例（请替换为真实账号ID）
        {"platform": "抖音", "name": "房产大V-示例1", "user_id": ""},
        {"platform": "抖音", "name": "房产大V-示例2", "user_id": ""},
        
        # 快手房产大V示例（请替换为真实账号ID）
        {"platform": "快手", "name": "房产大V-示例3", "user_id": ""},
        
        # 视频号房产大V示例（请替换为真实账号ID）
        {"platform": "视频号", "name": "房产大V-示例4", "user_id": ""},
    ],
    
    # 政策公告页面监控
    "policy_sources": [
        {"name": "抖音创作者中心公告", "url": "https://creator.douyin.com/announcement"},
        {"name": "快手创作者服务中心", "url": "https://cp.kuaishou.com/article"},
        {"name": "微信视频号助手公告", "url": "https://channels.weixin.qq.com/announcement"},
    ],
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            message TEXT,
            created_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def log(level, message):
    """记录日志"""
    print(f"[{level}] {message}")
    try:
        conn = sqlite3.connect(CONFIG["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (level, message, created_at) VALUES (?, ?, ?)",
            (level, message, datetime.datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except:
        pass

# ============ 请求计数器 ============
class RequestCounter:
    """控制请求频率"""
    
    @staticmethod
    def can_request():
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(CONFIG["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM logs WHERE level='REQUEST' AND created_at LIKE ?",
            (f"{today}%",)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count < CONFIG["max_requests_per_day"]
    
    @staticmethod
    def record(url):
        log("REQUEST", url[:100])

# ============ 安全请求工具 ============
class SafeRequest:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }
    
    @classmethod
    def get(cls, url, retries=2, timeout=15):
        if not RequestCounter.can_request():
            log("WARN", "今日请求已达上限,跳过")
            return None
        
        for i in range(retries):
            try:
                time.sleep(CONFIG["request_delay"])
                resp = requests.get(url, headers=cls.HEADERS, timeout=timeout)
                RequestCounter.record(url)
                
                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 429:
                    log("WARN", "请求过于频繁,暂停60秒")
                    time.sleep(60)
                else:
                    log("WARN", f"HTTP {resp.status_code}: {url}")
            except Exception as e:
                log("WARN", f"请求失败 ({i+1}/{retries}): {e}")
                if i < retries - 1:
                    time.sleep(10)
        return None

# ============ 视频采集 - 房产大V版 ============
class VideoCollector:
    """
    通过RSSHub采集房产大V账号视频
    安全、免费、无封号风险
    """
    
    # RSSHub实例列表（多个备用）
    RSSHUB_INSTANCES = [
        "https://rsshub.app",
        "https://rsshub.rssforever.com",
        "https://rss.shab.fun",
    ]
    
    @staticmethod
    def collect_all():
        """采集所有配置的账号"""
        all_videos = []
        
        for account in CONFIG["accounts"]:
            if not account.get("user_id"):
                log("INFO", f"跳过未配置账号: {account['name']}")
                continue
            
            log("INFO", f"采集[{account['platform']}] {account['name']}...")
            videos = VideoCollector.collect_from_rsshub(account)
            all_videos.extend(videos)
            log("INFO", f"{account['name']}: {len(videos)} 条")
            time.sleep(3)
        
        # 去重
        seen = set()
        unique = []
        for v in all_videos:
            if v["url"] and v["url"] not in seen:
                seen.add(v["url"])
                unique.append(v)
        
        return unique
    
    @staticmethod
    def collect_from_rsshub(account):
        """通过RSSHub采集单个账号"""
        videos = []
        
        # 构建RSSHub URL
        if account["platform"] == "抖音":
            rss_path = f"/douyin/user/{account['user_id']}"
        elif account["platform"] == "快手":
            rss_path = f"/kuaishou/user/{account['user_id']}"
        elif account["platform"] == "视频号":
            # 视频号可能需要其他方式
            log("WARN", f"视频号暂不支持RSSHub采集: {account['name']}")
            return videos
        else:
            return videos
        
        # 尝试多个RSSHub实例
        for instance in VideoCollector.RSSHUB_INSTANCES:
            rss_url = instance + rss_path
            resp = SafeRequest.get(rss_url)
            
            if resp:
                videos = VideoCollector.parse_rss(resp.text, account)
                if videos:
                    break
            
            time.sleep(2)
        
        return videos
    
    @staticmethod
    def parse_rss(rss_content, account):
        """解析RSS内容"""
        videos = []
        
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(rss_content)
            
            for item in root.findall('.//item'):
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                description = item.find('description')
                
                title_text = title.text if title is not None else ""
                link_text = link.text if link is not None else ""
                
                # 过滤房产相关内容
                keywords = ["房", "楼", "地产", "楼盘", "房价", "买房", "卖房", "租房", "楼市"]
                if not any(kw in title_text for kw in keywords):
                    continue
                
                video_id = hashlib.md5((account["platform"] + link_text + title_text).encode()).hexdigest()[:16]
                
                # 提取互动数据（如果有）
                likes = 0
                comments = 0
                if description is not None and description.text:
                    # 尝试从描述中提取点赞/评论数
                    like_match = re.search(r'点赞[:：]s*(d+)', description.text)
                    comment_match = re.search(r'评论[:：]s*(d+)', description.text)
                    if like_match:
                        likes = int(like_match.group(1))
                    if comment_match:
                        comments = int(comment_match.group(1))
                
                videos.append({
                    "id": video_id,
                    "platform": account["platform"],
                    "author": account["name"],
                    "title": title_text[:200],
                    "url": link_text,
                    "likes": likes,
                    "comments": comments,
                    "plays": 0,
                    "publish_time": pub_date.text if pub_date is not None else datetime.datetime.now().isoformat(),
                    "collected_at": datetime.datetime.now().isoformat(),
                })
        
        except Exception as e:
            log("ERROR", f"RSS解析失败 [{account['name']}]: {e}")
        
        return videos

# ============ 政策采集 ============
class PolicyCollector:
    """平台政策公告采集器"""
    
    @staticmethod
    def collect_all():
        all_policies = []
        for source in CONFIG["policy_sources"]:
            log("INFO", f"采集政策: {source['name']}...")
            policies = PolicyCollector.collect_from_page(source["name"], source["url"])
            all_policies.extend(policies)
            log("INFO", f"{source['name']}: {len(policies)} 条")
            time.sleep(3)
        return all_policies
    
    @staticmethod
    def collect_from_page(source_name, url):
        resp = SafeRequest.get(url)
        if not resp:
            return []
        
        policies = []
        try:
            import re
            text = resp.text.lower()
            keywords = ["房产", "地产", "房屋", "楼市", "直播", "账号", "规范", "治理", "公告", "政策"]
            
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) < 10 or len(line) > 300:
                    continue
                
                if any(kw in line for kw in keywords):
                    policy_id = hashlib.md5((source_name + line).encode()).hexdigest()[:16]
                    policies.append({
                        "id": policy_id,
                        "source": source_name,
                        "title": line[:200],
                        "url": url,
                        "summary": line[:300],
                        "collected_at": datetime.datetime.now().isoformat(),
                    })
            
            seen = set()
            unique = []
            for p in policies:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    unique.append(p)
            
            return unique[:10]
        
        except Exception as e:
            log("ERROR", f"政策采集失败 [{source_name}]: {e}")
            return []

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
                              v.get("comments", 0) >= CONFIG["quality_threshold"]["min_comments"]) else 0
            
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO videos 
                    (id, platform, author, title, url, likes, comments, plays, publish_time, collected_at, is_quality)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    v["id"], v.get("platform", ""), v.get("author", ""),
                    v["title"], v["url"], v.get("likes", 0),
                    v.get("comments", 0), v.get("plays", 0),
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
    def save_policies(policies):
        if not policies:
            return 0
        
        conn = sqlite3.connect(CONFIG["db_path"])
        cursor = conn.cursor()
        added = 0
        
        for p in policies:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO policies 
                    (id, source, title, url, summary, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (p["id"], p["source"], p["title"], p["url"], p["summary"], p["collected_at"]))
                if cursor.rowcount > 0:
                    added += 1
            except Exception as e:
                log("ERROR", f"保存政策失败: {e}")
        
        conn.commit()
        conn.close()
        return added
    
    @staticmethod
    def get_today_data():
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(CONFIG["db_path"])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT platform, author, title, url, likes, comments, plays 
            FROM videos 
            WHERE collected_at LIKE ?
            ORDER BY likes DESC
            LIMIT 15
        ''', (f"{today}%",))
        videos = cursor.fetchall()
        
        cursor.execute('''
            SELECT source, title, url, summary 
            FROM policies 
            WHERE collected_at LIKE ?
            ORDER BY collected_at DESC
            LIMIT 10
        ''', (f"{today}%",))
        policies = cursor.fetchall()
        
        conn.close()
        return videos, policies

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
        videos, policies = DataStore.get_today_data()
        
        lines = [f"# 房产监控日报 ({today})\n"]
        
        lines.append("## 今日优质房产短视频\n")
        if videos:
            for v in videos[:10]:
                platform, author, title, url, likes, comments, plays = v
                quality_mark = "🔥" if likes >= CONFIG["quality_threshold"]["min_likes"] else ""
                lines.append(f"{quality_mark} **[{platform}]** {author}")
                lines.append(f"   {title}")
                lines.append(f"   [点击观看]({url})")
                if likes > 0 or comments > 0:
                    lines.append(f"   👍{likes} 💬{comments}")
                lines.append("")
        else:
            lines.append("> 今日暂无新视频\n")
        
        lines.append("## 平台政策动态\n")
        if policies:
            for p in policies[:8]:
                source, title, url, summary = p
                lines.append(f"**[{source}]** {title}")
                lines.append(f"[查看详情]({url})")
                lines.append("")
        else:
            lines.append("> 今日暂无新政策\n")
        
        lines.append("---")
        lines.append("*自动发送*")
        
        message = "\n".join(lines)
        return PushNotifier.send(message, f"房产监控日报 {today}")

# ============ 主程序 ============
def main():
    start_time = datetime.datetime.now()
    log("INFO", "=" * 40)
    log("INFO", "房产监控日报系统启动(大V版)")
    log("INFO", f"开始时间: {start_time.isoformat()}")
    log("INFO", "=" * 40)
    
    init_db()
    
    log("INFO", "[1/3] 开始采集视频数据...")
    videos = VideoCollector.collect_all()
    video_added = DataStore.save_videos(videos)
    log("INFO", f"[1/3] 视频采集完成,新增: {video_added} 条")
    
    log("INFO", "[2/3] 开始采集政策信息...")
    policies = PolicyCollector.collect_all()
    policy_added = DataStore.save_policies(policies)
    log("INFO", f"[2/3] 政策采集完成,新增: {policy_added} 条")
    
    log("INFO", "[3/3] 发送日报...")
    if PushNotifier.send_daily_report():
        log("INFO", "[3/3] 日报发送成功")
    else:
        log("ERROR", "[3/3] 日报发送失败,请检查推送配置")
    
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    log("INFO", "=" * 40)
    log("INFO", f"执行完成,耗时: {duration:.1f} 秒")
    log("INFO", "=" * 40)

if __name__ == "__main__":
    main()
