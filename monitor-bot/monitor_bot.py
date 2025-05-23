import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_BOT_TOKEN = '7920437249:AAFHucmnlKgeqkd-n19xFoM8aiBP-oR-NYg'
PROMETHEUS_URL = 'http://prometheus:9090' 
ALERTMANAGER_URL = "http://alertmanager:9093" 
LOKI_URL = "http://loki:3100"  


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

#/alerts Kiểm tra lịch sử alert gần nhất từ Prometheus Alertmanager
async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.get(f"{ALERTMANAGER_URL}/api/v2/alerts", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            await update.message.reply_text("✅ Không có cảnh báo nào hiện tại.")
            return
        messages = []
        for alert in data:
            status = alert.get("status", {}).get("state", "unknown")
            name = alert.get("labels", {}).get("alertname", "unknown")
            starts_at = alert.get("startsAt", "N/A")
            messages.append(f"⚠️ {name} - {status.upper()} (since {starts_at})")
        await update.message.reply_text("\n".join(messages))
    except Exception as e:
        await update.message.reply_text(f"Lỗi lấy cảnh báo: {e}")


#/uptime – Kiểm tra thời gian uptime của DVWA (hoặc bất kỳ container nào)
async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        result = await get_metric("time() - node_boot_time_seconds")
        uptime_seconds = float(result)
        uptime_hours = uptime_seconds / 3600
        await update.message.reply_text(f"🕒 Máy chủ đã khởi động lại cách đây {uptime_hours:.2f} giờ.")
    except Exception as e:
        await update.message.reply_text(f"Lỗi: {e}")


#/status – Kiểm tra container DVWA có đang chạy không (ping từ Blackbox Exporter)
probe_query = 'probe_success{instance="http://dvwa:80"}'

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        status = await get_metric(probe_query)
        if status == "1":
            await update.message.reply_text("✅ DVWA hiện đang hoạt động bình thường.")
        else:
            await update.message.reply_text("❌ DVWA hiện đang _ngưng hoạt động_.")
    except Exception as e:
        await update.message.reply_text(f"Lỗi kiểm tra trạng thái DVWA: {e}")


#/help – Gợi ý các lệnh có thể dùng
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Các lệnh hỗ trợ:*\n"
        "/check - Báo cáo hệ thống\n"
        "/alerts - Xem cảnh báo hiện tại\n"
        "/uptime - Kiểm tra thời gian uptime của server\n"
        "/status - Kiểm tra DVWA có hoạt động không\n"
        "/help - Danh sách các lệnh"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


#sqlmap attack
async def sqlmap_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        now = datetime.datetime.utcnow()
        # ISO timestamp cho log gần nhất (1 phút trước)
        start = (now - datetime.timedelta(minutes=1)).isoformat("T") + "Z"
        end = now.isoformat("T") + "Z"

        # LogQL query tìm các dòng có "sqlmap"
        query = '{job="apache_access"} |= "sqlmap"'
        params = {
            "query": query,
            "start": start,
            "end": end,
            "limit": 5
        }

        # Gửi request đến Loki
        resp = requests.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params)
        data = resp.json()

        if not data["data"]["result"]:
            await update.message.reply_text("✅ Không phát hiện truy cập nghi ngờ từ sqlmap trong 1 phút qua.")
            return

        # Trích xuất IP từ dòng log (ví dụ IP đứng đầu)
        log_lines = data["data"]["result"][0]["values"]
        detected_ips = set()

        for _, line in log_lines:
            # Giả sử IP là chuỗi đầu tiên trước dấu cách
            ip = line.split(" ")[0]
            detected_ips.add(ip)

        ip_list = "\n".join(detected_ips)
        await update.message.reply_text(
            f"🚨 *Phát hiện tấn công SQLMap!*\nCác IP nghi ngờ:\n`{ip_list}`",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"Lỗi kiểm tra sqlmap: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("check", check))

    app.add_handler(CommandHandler("alerts", alerts))
    app.add_handler(CommandHandler("uptime", uptime))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("sqlmap", sqlmap_check))

    app.run_polling()
