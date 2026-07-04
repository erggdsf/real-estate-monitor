#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Playwright浏览器自动化采集模块（备用方案）
当直接请求被封时，使用此模块模拟真实浏览器访问
需要安装: pip install playwright
然后执行: playwright install chromium
"""

import asyncio
import datetime
from playwright.async_api import async_playwright

async def collect_douyin_with_playwright(user_url):
    """使用Playwright采集抖音用户视频"""
    videos = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        try:
            await page.goto(user_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)  # 等待页面渲染
            
            # 提取视频列表
            video_elements = await page.query_selector_all('[data-e2e="user-post-item"]')
            
            for elem in video_elements[:10]:
                try:
                    title_elem = await elem.query_selector('[data-e2e="user-post-item-desc"]')
                    title = await title_elem.inner_text() if title_elem else ""
                    
                    link_elem = await elem.query_selector('a')
                    href = await link_elem.get_attribute('href') if link_elem else ""
                    
                    # 提取点赞数
                    like_elem = await elem.query_selector('[data-e2e="user-post-item-stats"]')
                    likes_text = await like_elem.inner_text() if like_elem else "0"
                    
                    videos.append({
                        "title": title,
                        "url": "https://www.douyin.com" + href if href else "",
                        "likes_text": likes_text,
                        "platform": "抖音",
                    })
                except Exception as e:
                    print(f"解析单条视频失败: {e}")
                    
        except Exception as e:
            print(f"Playwright采集失败: {e}")
        finally:
            await browser.close()
    
    return videos

if __name__ == "__main__":
    # 测试
    result = asyncio.run(collect_douyin_with_playwright("https://www.douyin.com/user/xxx"))
    print(result)
