import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔐 Cấu hình token & chat_id ở đây (có thể để trống CHAT_ID)
TELEGRAM_BOT_TOKEN = '7920437249:AAFHucmnlKgeqkd-n19xFoM8aiBP-oR-NYg'
PROMETHEUS_URL = 'http://prometheus:9090'  # Sử dụng tên service trong Docker network

logging.basicConfig(level=logging.INFO)

# Hàm lấy metric từ Prometheus
async def get_metric(query: str) -> str:
    url = f"{PROMETHEUS_URL}/api/v1/query"
    params = {"query": query}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()  # Raise an exception for HTTP errors
        data = resp.json()
        if data["status"] == "success" and data["data"]["result"]:
            return data["data"]["result"][0]["value"][1]
        else:
            return "N/A"
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"
    except (KeyError, IndexError) as e:
        return f"Error parsing Prometheus response: {e}"

# Hàm kiểm tra và trả về báo cáo hệ thống
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cpu_busy = await get_metric("100 - (avg by(instance) (rate(node_cpu_seconds_total{mode='idle'}[1m])) * 100)")
    sys_load = await get_metric("node_load1")
    ram_used = await get_metric("(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100")
    disk_used = await get_metric("100 - (node_filesystem_free_bytes{mountpoint='/'} / node_filesystem_size_bytes{mountpoint='/'}) * 100")
    net_in = await get_metric("rate(node_network_receive_bytes_total[1m])")
    net_out = await get_metric("rate(node_network_transmit_bytes_total[1m])")

    report = (
        f"📊 *System Report*\n"
        f"CPU Busy: {cpu_busy}%\n"
        f"Load (1m): {sys_load}\n"
        f"RAM Used: {ram_used}%\n"
        f"Disk Used (/): {disk_used}%\n"
        f"Network In: {net_in} B/s\n"
        f"Network Out: {net_out} B/s\n"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=report, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("check", check))
    app.run_polling()

