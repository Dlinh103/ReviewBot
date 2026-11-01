<<<<<<< HEAD
# ReviewBot — AI Code Review Assistant for GitHub Pull Requests

Hệ thống hỗ trợ review mã nguồn tự động trên GitHub Pull Request bằng LLM.

## Tính năng chính
- 🚀 **GitHub Webhook Receiver**: Tự động nhận diện sự kiện `pull_request` (`opened`, `synchronize`, `reopened`), bảo mật xác thực HMAC SHA-256.
- 🔍 **Diff Processing**: Phân tích patch, định vị số dòng (new side), lọc các file không cần thiết (.lock, vendor, minified).
- 🤖 **LLM Review Engine**: Phát hiện lỗi sai, lỗ hổng bảo mật, lỗi hiệu năng và sinh gợi ý code (`suggestion`).
- 💬 **GitHub Publisher**: Gửi inline review comments và tự động cập nhật PR summary.
- 📊 **Database Logging**: Lưu trữ toàn bộ lịch sử review, findings, token usage và cost vào PostgreSQL.

## Cài đặt & Chạy ứng dụng

### 1. Yêu cầu
- Python 3.11+
- Docker & Docker Compose
- GitHub App (Private Key, App ID, Webhook Secret)
- Anthropic API Key (hoặc provider LLM tương thích)

### 2. Cấu hình môi trường
Sao chép `.env.example` thành `.env` và điền các thông tin:
```bash
cp .env.example .env
```

### 3. Chạy bằng Docker Compose
```bash
docker compose up --build
```
Kiểm tra endpoint health:
```bash
curl http://localhost:8000/health
```
=======
# ReviewBot
>>>>>>> 53a4dd31b443c17c575df290709a948820b4aab8
