# wget https://raw.githubusercontent.com/erdongxin/pipe/refs/heads/main/pipe.py -O pipe.py && screen -dmS pipe bash -c 'python3 pipe.py'

import os
import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta

# 基础配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 时间间隔配置
HEARTBEAT_INTERVAL = 300  # 5分钟发送一次心跳
RETRY_DELAY = 5  # 重试延迟（秒）
MAX_RETRIES = 3  # 最大重试次数

BASE_URL = "https://api.pipecdn.app/api"

# 本地读取pipe.txt中的Token信息
def read_pipe_file():
    """从服务器的pipe.txt中读取Token和邮箱信息"""
    pipe_file_path = "/root/pipe.txt"
    if not os.path.exists(pipe_file_path):
        logging.error(f"未找到 {pipe_file_path} 文件，无法读取Token和邮箱。")
        return None

    with open(pipe_file_path, 'r') as f:
        lines = f.readlines()
    
    email = None
    token = None
    
    for line in lines:
        if line.startswith("email:"):
            email = line.strip().split(":")[1].strip()
        elif line.startswith("token:"):
            token = line.strip().split(":")[1].strip()
    
    if not email or not token:
        logging.error("未从pipe.txt中获取到有效的邮箱和Token信息。")
        return None
    
    return {"email": email, "token": token}

# 获取当前IP地址
async def get_ip():
    """获取当前IP地址"""
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        try:
            async with session.get("https://api64.ipify.org?format=json", timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('ip')
        except Exception as e:
            logging.error(f"获取IP失败: {e}")
            await asyncio.sleep(RETRY_DELAY)
    return None

# 发送心跳信号
async def send_heartbeat(token):
    """发送心跳信号"""
    ip = await get_ip()
    if not ip:
        logging.error(f"无法获取IP，无法发送心跳，Token: {token}")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = {"ip": ip}
    
    retries = 0
    while retries < MAX_RETRIES:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            try:
                async with session.post(f"{BASE_URL}/heartbeat", headers=headers, json=data, timeout=5) as response:
                    if response.status == 200:
                        logging.info(f"成功发送心跳，Token: {token}")
                        return True
                    elif response.status == 429:
                        logging.warning(f"请求过于频繁，Token: {token}")
                        return False
                    else:
                        logging.warning(f"心跳发送失败，状态码: {response.status}, Token: {token}")
            except Exception as e:
                logging.error(f"发送心跳失败: {e}")
        
        retries += 1
        logging.info(f"心跳发送失败，正在重试 {retries}/{MAX_RETRIES}...")
        await asyncio.sleep(RETRY_DELAY)

    logging.error(f"心跳发送失败，达到最大重试次数: {MAX_RETRIES}")
    return False

# 运行节点命令
async def run_node():
    """运行节点并定时发送心跳"""
    server_info = read_pipe_file()
    if not server_info:
        logging.error("无法加载Token和邮箱信息，退出运行。")
        return
    
    token = server_info["token"]
    email = server_info["email"]

    logging.info(f"邮箱: {email}，Token: {token} 已加载，开始运行节点。")

    # 心跳定时任务
    next_heartbeat_time = datetime.now()
    first_heartbeat = True

    last_log_time = datetime.now()  # 用于控制日志输出的时间

    try:
        while True:
            current_time = datetime.now()

            # 每次心跳间隔发送心跳
            if current_time >= next_heartbeat_time:
                if first_heartbeat:
                    logging.info("开始首次心跳...")
                    first_heartbeat = False

                # 发送心跳请求并检查发送是否成功
                heartbeat_sent = await send_heartbeat(token)
                if heartbeat_sent:
                    next_heartbeat_time = current_time + timedelta(seconds=HEARTBEAT_INTERVAL)
                else:
                    # 如果心跳发送失败，则不更新下一次发送时间，等待重试
                    next_heartbeat_time = current_time + timedelta(seconds=RETRY_DELAY)

            # 控制“等待下一次心跳”日志的输出频率
            remaining_time = next_heartbeat_time - current_time
            if remaining_time.total_seconds() > 60 and (current_time - last_log_time).total_seconds() >= 60:
                logging.info(f"等待下一次心跳，剩余时间: {remaining_time}")
                last_log_time = current_time  # 更新日志输出时间

            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logging.info("\n停止节点，返回主菜单...")

# 执行主逻辑
if __name__ == "__main__":
    asyncio.run(run_node())
