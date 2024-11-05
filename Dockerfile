# Sử dụng Python base image phiên bản mới
FROM python:3.7
# Thiết lập biến môi trường để không tạo file .pyc và ghi log trực tiếp
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cài đặt các thư viện hệ thống cần thiết (libproj-dev và gdal-bin chỉ cần nếu ứng dụng của bạn sử dụng)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libproj-dev gdal-bin && \
    rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc cho ứng dụng
WORKDIR /opt/services/app/src

# Sao chép file requirements.txt và cài đặt các thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn ứng dụng
COPY . .

# Thu thập static files (nếu cần cho Django)
RUN python manage.py collectstatic --no-input

# Khai báo cổng mặc định cho ứng dụng Django
EXPOSE 8000

# Khởi chạy ứng dụng Django bằng gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "myapp.wsgi:application"]
