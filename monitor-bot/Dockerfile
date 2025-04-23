# Dùng image python phiên bản 3.11-slim làm base image
FROM python:3.11-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# Copy file requirements.txt vào thư mục làm việc của container
COPY requirements.txt .

# Cài đặt các dependencies từ file requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy file monitor_bot.py vào thư mục làm việc của container
COPY monitor_bot.py .

# Lệnh mặc định để chạy ứng dụng khi container khởi động
CMD ["python", "monitor_bot.py"]
