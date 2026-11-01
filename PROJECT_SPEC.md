# PROJECT_SPEC.md — AI Code Review Assistant (GitHub PR Reviewer)

> Cách dùng: đặt file này ở thư mục gốc repo (có thể đổi tên thành `CLAUDE.md` / `AGENTS.md` / `.cursorrules`).
> Sau đó dán từng "Prompt giai đoạn" ở mục 12 cho AI coding agent (Claude Code, Cursor, Copilot...) theo thứ tự.

---

## 1. Tổng quan

**Tên dự án:** `reviewbot` — Hệ thống hỗ trợ review mã nguồn tự động trên GitHub Pull Request bằng LLM.

**Bài toán:** Khi có PR mới, hệ thống tự động lấy diff, nhờ LLM phát hiện bug/lỗ hổng/code smell, đăng inline comment đúng dòng và sinh mô tả PR.

**Bối cảnh:** Đồ án Chuyên ngành 2 (SE), VKU. Cần có phần AI, phần phân tích thiết kế, mã nguồn chạy được, demo được.

**Người dùng:** Lập trình viên (tác giả PR), reviewer, quản trị viên repo.

---

## 2. Phạm vi

### MVP (bắt buộc)
1. Nhận webhook GitHub (`pull_request`: `opened`, `synchronize`, `reopened`), xác thực chữ ký HMAC SHA-256.
2. Lấy diff PR qua GitHub API, lọc file không review (lock file, ảnh, minified, generated, vendor).
3. Chia diff theo file/hunk, gọi LLM, nhận JSON có cấu trúc.
4. Hậu xử lý: lọc confidence thấp, loại trùng, giới hạn số comment.
5. Đăng **một review** với inline comment đúng dòng + comment tổng kết.
6. Sinh và cập nhật **mô tả PR** (tóm tắt, rủi ro, gợi ý test) trong một comment riêng.
7. Lưu kết quả vào PostgreSQL.

### Mở rộng (làm sau MVP)
- Dashboard (React): số PR, số finding theo severity/category, tỷ lệ comment được chấp nhận.
- File cấu hình `.reviewbot.yml` trong repo đích.
- Tích hợp Semgrep/Ruff/ESLint rồi để LLM tổng hợp.
- Lệnh trong comment: `/review`, `/explain`, `/suggest-test`.
- Thu feedback (👍/👎 reaction) để tính precision thực tế.

### Ngoài phạm vi
Tự động merge, tự sửa code và push commit, hỗ trợ GitLab/Bitbucket.

---

## 3. Công nghệ

| Thành phần | Lựa chọn |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Queue/Worker | Redis + Celery (hoặc RQ/ARQ nếu muốn gọn hơn) |
| CSDL | PostgreSQL + SQLAlchemy 2.0 + Alembic |
| LLM | Anthropic SDK (model đọc từ env, mặc định `claude-sonnet-4-6`); abstraction để thay provider |
| GitHub | GitHub App (JWT → installation token), gọi REST bằng `httpx` |
| Dashboard (mở rộng) | React + Vite + Recharts |
| Test | pytest, pytest-asyncio, respx (mock HTTP) |
| Chất lượng | Ruff, mypy, pre-commit |
| Deploy | Docker Compose; CI bằng GitHub Actions |

---

## 4. Kiến trúc

```
GitHub ──webhook──► FastAPI (Webhook Receiver)
                        │ verify HMAC, ghi job
                        ▼
                     Redis queue
                        │
                        ▼
                  Celery Worker
   ┌────────────────────┼──────────────────────┐
   ▼                    ▼                      ▼
Diff Processor   Context Builder        LLM Reviewer
(parse, filter)  (file, PR meta)     (prompt → JSON findings)
                        │
                        ▼
              Post-processor (dedupe, filter, rank)
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
       GitHub Publisher       PostgreSQL
      (review + comments)    (reviews, findings)
```

**Nguyên tắc:**
- Webhook phải trả `202` trong < 2 giây; mọi việc nặng chạy ở worker.
- Idempotent: cùng `(repo, pr_number, head_sha)` không review hai lần.
- Mỗi module có interface rõ ràng để mock khi test.
- Không bao giờ log token, secret, nội dung code đầy đủ ở mức INFO.

---

## 5. Cấu trúc thư mục

```
reviewbot/
├── PROJECT_SPEC.md
├── README.md
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── alembic.ini
├── migrations/
├── src/reviewbot/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Settings (pydantic-settings)
│   ├── api/
│   │   ├── webhook.py          # POST /webhook/github
│   │   ├── health.py           # GET /health
│   │   └── dashboard.py        # GET /api/... (mở rộng)
│   ├── github/
│   │   ├── auth.py             # JWT + installation token (cache)
│   │   ├── client.py           # get PR, get diff, post review, update comment
│   │   └── signature.py        # verify X-Hub-Signature-256
│   ├── core/
│   │   ├── diff_parser.py      # parse unified diff → File/Hunk/Line
│   │   ├── file_filter.py      # ignore patterns
│   │   ├── chunker.py          # chia theo token budget
│   │   ├── secrets_scrubber.py # che API key/secret trước khi gửi LLM
│   │   ├── postprocess.py      # dedupe, threshold, cap
│   │   └── line_mapper.py      # map line → GitHub diff position
│   ├── llm/
│   │   ├── base.py             # LLMClient protocol
│   │   ├── anthropic_client.py
│   │   ├── prompts.py          # system/user prompt templates
│   │   └── schemas.py          # Finding, ReviewResult, PRSummary
│   ├── services/
│   │   ├── review_service.py   # orchestration toàn bộ pipeline
│   │   └── summary_service.py  # sinh mô tả PR
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│   │   └── repositories.py
│   └── worker/
│       ├── celery_app.py
│       └── tasks.py            # review_pull_request(task)
├── tests/
│   ├── fixtures/               # diff mẫu, webhook payload mẫu
│   ├── test_signature.py
│   ├── test_diff_parser.py
│   ├── test_line_mapper.py
│   ├── test_postprocess.py
│   └── test_review_service.py  # mock LLM + GitHub
├── eval/
│   ├── dataset/                # code có bug đã gán nhãn
│   ├── run_eval.py             # tính precision/recall/latency/cost
│   └── README.md
└── dashboard/                  # React (mở rộng)
```

---

## 6. Mô hình dữ liệu (PostgreSQL)

```
repositories(id, github_repo_id UNIQUE, full_name, installation_id, config_json, created_at)

pull_requests(id, repo_id FK, number, title, author, head_sha, base_sha,
              state, created_at, updated_at,
              UNIQUE(repo_id, number))

reviews(id, pr_id FK, head_sha, status ENUM(queued,running,done,failed),
        model, prompt_version, input_tokens, output_tokens, cost_usd,
        duration_ms, error, github_review_id, created_at,
        UNIQUE(pr_id, head_sha))

findings(id, review_id FK, file_path, line_start, line_end,
         severity ENUM(critical,major,minor,info),
         category ENUM(bug,security,performance,maintainability,style,test),
         message, suggestion, confidence FLOAT, evidence,
         posted BOOL, github_comment_id, created_at)

feedback(id, finding_id FK, reaction ENUM(positive,negative,none), source, created_at)

pr_summaries(id, pr_id FK, head_sha, summary_md, risks_md, test_suggestions_md,
             github_comment_id, created_at)
```

---

## 7. API

| Method | Path | Mô tả |
|---|---|---|
| POST | `/webhook/github` | Nhận event; verify chữ ký; enqueue; trả 202 |
| GET | `/health` | Liveness |
| GET | `/api/repos` | Danh sách repo (mở rộng) |
| GET | `/api/repos/{id}/stats` | Thống kê (mở rộng) |
| GET | `/api/reviews/{id}` | Chi tiết review + findings (mở rộng) |

**Webhook xử lý:**
- Header `X-GitHub-Event`, `X-Hub-Signature-256`.
- Chỉ xử lý `pull_request` với action `opened|synchronize|reopened`; bỏ qua PR draft (cấu hình được) và PR do chính bot tạo.
- Sự kiện `issue_comment` (mở rộng) cho lệnh `/review`.

---

## 8. Hợp đồng đầu ra của LLM (schema bắt buộc)

```python
class Finding(BaseModel):
    file: str
    line: int                      # dòng trong file MỚI (right side)
    end_line: int | None = None
    severity: Literal["critical", "major", "minor", "info"]
    category: Literal["bug", "security", "performance", "maintainability", "style", "test"]
    message: str                   # ngắn gọn, nêu vấn đề
    evidence: str                  # trích dòng code làm bằng chứng
    suggestion: str | None = None  # đoạn code đề xuất (nếu có)
    confidence: float              # 0.0 - 1.0

class ReviewResult(BaseModel):
    findings: list[Finding]
    overall_notes: str | None = None

class PRSummary(BaseModel):
    title_suggestion: str
    summary: str
    changes: list[str]
    risks: list[str]
    test_suggestions: list[str]
```

**Quy tắc xử lý:**
- Yêu cầu model chỉ trả JSON; parse bằng Pydantic; nếu lỗi → retry tối đa 2 lần kèm thông báo lỗi parse.
- Loại finding có `line` không nằm trong các dòng thay đổi của diff.
- Giữ finding có `confidence >= 0.6` (cấu hình được).
- Tối đa `MAX_COMMENTS_PER_PR` (mặc định 15), ưu tiên theo severity rồi confidence.
- Loại trùng theo `(file, line, category)` hoặc message tương tự.

---

## 9. Prompt (phiên bản 1 — lưu trong `llm/prompts.py`, có biến `PROMPT_VERSION`)

**System prompt (review):**
```
You are a senior software engineer performing a code review on a GitHub pull request.
Review ONLY the lines that were added or modified (marked with '+' in the diff).
Report only issues you are confident about, with concrete evidence from the code.
Focus on: correctness bugs, security vulnerabilities, error handling, performance
problems, and significant maintainability issues. Do NOT comment on trivial style,
formatting, or personal preference. Do NOT invent issues. If there is nothing
significant, return an empty findings list.
Return ONLY valid JSON matching the provided schema. No markdown, no prose.
```

**User prompt (template):**
```
PR title: {title}
PR description: {description}
Language: {language}
File: {path}

Surrounding context (unchanged code, for reference only):
{context}

Diff (line numbers refer to the NEW file):
{numbered_diff}

Schema:
{json_schema}
```

**System prompt (tóm tắt PR):** yêu cầu tóm tắt thay đổi, rủi ro, gợi ý test, trả JSON theo `PRSummary`, văn phong ngắn gọn; ngôn ngữ đầu ra cấu hình được (`vi`/`en`).

**Lưu ý:** đánh số dòng sẵn trong diff gửi cho LLM (ví dụ `L42: + code`) để model trả đúng số dòng.

---

## 10. Cấu hình & biến môi trường (`.env.example`)

```
APP_ENV=dev
LOG_LEVEL=INFO

GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY_PATH=./secrets/github-app.pem
GITHUB_WEBHOOK_SECRET=

ANTHROPIC_API_KEY=
LLM_MODEL=claude-sonnet-4-6
LLM_MAX_TOKENS=2000
LLM_TIMEOUT_SECONDS=60

DATABASE_URL=postgresql+psycopg://reviewbot:reviewbot@db:5432/reviewbot
REDIS_URL=redis://redis:6379/0

MAX_FILES_PER_PR=40
MAX_DIFF_TOKENS_PER_CHUNK=6000
MAX_COMMENTS_PER_PR=15
MIN_CONFIDENCE=0.6
REVIEW_DRAFT_PRS=false
OUTPUT_LANGUAGE=vi
```

**Cấu hình theo repo (`.reviewbot.yml`, mở rộng):**
```yaml
language: vi
min_confidence: 0.7
max_comments: 10
ignore:
  - "**/*.lock"
  - "dist/**"
  - "**/*.min.js"
focus: [bug, security]
```

---

## 11. Bảo mật & chất lượng

- Verify HMAC bằng `hmac.compare_digest`; từ chối nếu sai chữ ký (401).
- Scrub secret (AWS key, `ghp_`, private key, JWT, `password=`...) trước khi gửi LLM.
- Không commit `.env`, file `.pem`; có `.gitignore` đầy đủ.
- Token installation cache theo thời hạn (hết hạn sau ~1 giờ), tự làm mới.
- Xử lý rate limit GitHub (đọc `Retry-After`/`X-RateLimit-Reset`) và rate limit LLM (exponential backoff).
- Giới hạn kích thước PR; nếu quá lớn thì review các file ưu tiên và ghi chú đã bỏ qua.
- Mọi lỗi pipeline phải cập nhật `reviews.status = failed` kèm `error`; không làm worker crash.

---

## 12. Kế hoạch triển khai bằng prompt (copy theo thứ tự)

### Giai đoạn 0 — Khởi tạo
```
Đọc PROJECT_SPEC.md. Khởi tạo project theo mục 5: pyproject.toml (FastAPI, uvicorn,
pydantic-settings, SQLAlchemy 2, alembic, psycopg, celery, redis, httpx, PyJWT,
anthropic, pytest, respx, ruff, mypy), cấu trúc thư mục, config.py đọc env theo mục 10,
Dockerfile, docker-compose.yml (api, worker, db postgres, redis), .env.example,
.gitignore, GET /health. Chạy được bằng `docker compose up`.
```

### Giai đoạn 1 — Webhook + xác thực
```
Cài github/signature.py (verify HMAC SHA-256) và api/webhook.py theo mục 7.
Chỉ nhận pull_request opened/synchronize/reopened, bỏ qua draft và PR của bot.
Enqueue task Celery review_pull_request với payload tối thiểu (installation_id,
repo full_name, pr number, head_sha). Viết test cho chữ ký đúng/sai và lọc event.
```

### Giai đoạn 2 — GitHub client
```
Cài github/auth.py (tạo JWT từ App ID + private key, đổi sang installation token,
cache đến khi sắp hết hạn) và github/client.py: get_pull_request, get_pr_files
(có phân trang), get_file_content, create_review (comments inline), upsert_issue_comment
(tìm comment của bot theo marker ẩn <!-- reviewbot:summary --> để cập nhật thay vì tạo mới).
Dùng httpx.AsyncClient, retry/backoff cho 5xx và rate limit. Test bằng respx.
```

### Giai đoạn 3 — Xử lý diff
```
Cài core/diff_parser.py: parse patch của từng file thành File → Hunk → Line với
số dòng cũ/mới và loại dòng (added/removed/context). Cài core/file_filter.py
(glob ignore + file nhị phân + file quá lớn), core/line_mapper.py (xác định dòng
mới có nằm trong diff không để comment hợp lệ), core/chunker.py (chia theo token
budget, ước lượng token = len(text)/4), core/secrets_scrubber.py. Viết test với
các diff mẫu trong tests/fixtures, gồm cả file thêm mới, xóa, đổi tên.
```

### Giai đoạn 4 — LLM reviewer
```
Cài llm/schemas.py (mục 8), llm/base.py (Protocol LLMClient.generate_json),
llm/anthropic_client.py (timeout, retry, đếm token, tính chi phí ước lượng),
llm/prompts.py (mục 9, có PROMPT_VERSION). Dựng hàm review_chunk() trả
ReviewResult đã validate bằng Pydantic, retry khi JSON lỗi. Test bằng fake LLMClient.
```

### Giai đoạn 5 — Pipeline và đăng review
```
Cài core/postprocess.py (lọc confidence, bỏ dòng không thuộc diff, dedupe, ranking,
cap số comment) và services/review_service.py điều phối: lấy PR → lọc file → chia chunk
→ gọi LLM song song có giới hạn concurrency → hậu xử lý → đăng một review với inline
comment (định dạng: badge severity + category, message, suggestion trong khối
```suggestion nếu hợp lệ) → lưu DB. Cài services/summary_service.py sinh PRSummary và
upsert comment tóm tắt. Đảm bảo idempotent theo (pr_id, head_sha). Test end-to-end
với LLM và GitHub được mock.
```

### Giai đoạn 6 — CSDL
```
Cài db/models.py theo mục 6, session, repositories, migration Alembic đầu tiên.
Lưu reviews/findings/pr_summaries kèm token, chi phí, thời gian. Cập nhật status
queued → running → done/failed.
```

### Giai đoạn 7 — Mở rộng (chọn theo thời gian)
```
(a) Đọc .reviewbot.yml từ repo đích và áp dụng cấu hình.
(b) Xử lý issue_comment với lệnh /review, /explain.
(c) Chạy Ruff/Semgrep trên file thay đổi, đưa kết quả vào prompt để LLM tổng hợp và giải thích.
(d) Webhook pull_request_review_comment / reaction để lưu feedback.
```

### Giai đoạn 8 — Dashboard
```
Tạo api/dashboard.py (stats theo repo: số PR, finding theo severity/category,
tỷ lệ positive feedback, chi phí và thời gian trung bình) và dashboard/ bằng
React + Vite + Recharts hiển thị các biểu đồ và danh sách review gần đây.
```

### Giai đoạn 9 — Đánh giá (cho báo cáo)
```
Tạo eval/dataset gồm 50-100 mẫu code Python/JS có bug đã gán nhãn (file, dòng,
loại bug) cùng một số mẫu code sạch. Viết eval/run_eval.py chạy pipeline trên dataset
và xuất: precision, recall, F1, tỷ lệ false positive trên code sạch, độ trễ trung bình,
chi phí trung bình mỗi PR; xuất CSV + bảng Markdown. Hỗ trợ so sánh nhiều model và
so sánh "LLM thuần" với "LLM + phân tích tĩnh".
```

### Giai đoạn 10 — CI/CD & tài liệu
```
Thêm .github/workflows/ci.yml (ruff, mypy, pytest) và workflow build Docker image.
Viết README.md: giới thiệu, cách tạo GitHub App (quyền Pull requests: read & write,
Contents: read, Issues: write; subscribe event Pull request, Issue comment), cách chạy
local bằng ngrok/smee.io, cách cấu hình env, cách chạy test và eval.
```

---

## 13. Hướng dẫn tạo GitHub App (làm tay một lần)

1. GitHub → Settings → Developer settings → GitHub Apps → New GitHub App.
2. **Webhook URL:** URL công khai trỏ tới `/webhook/github` (dev: dùng smee.io hoặc ngrok). **Webhook secret:** chuỗi ngẫu nhiên, ghi vào `GITHUB_WEBHOOK_SECRET`.
3. **Permissions (Repository):** Pull requests: Read & write; Contents: Read-only; Issues: Read & write; Metadata: Read-only.
4. **Subscribe to events:** Pull request, Issue comment (mở rộng), Pull request review comment (mở rộng).
5. Generate private key (.pem) → lưu vào `secrets/`, ghi `GITHUB_APP_ID`.
6. Install App vào một repo test và mở PR thử.

---

## 14. Tiêu chí hoàn thành (Definition of Done)

**MVP:**
- [ ] Mở PR trên repo test → trong vòng 1-2 phút xuất hiện review với inline comment đúng dòng.
- [ ] Có comment tóm tắt PR; push commit mới thì comment được cập nhật, không tạo trùng.
- [ ] Gửi webhook sai chữ ký bị từ chối.
- [ ] PR chứa file lock/ảnh không bị gửi LLM.
- [ ] Secret trong diff được che trước khi gửi LLM (có test).
- [ ] Lỗi LLM/GitHub không làm sập worker, `reviews.status = failed` có lý do.
- [ ] `docker compose up` chạy toàn bộ hệ thống; `pytest` pass.

**Đồ án:**
- [ ] Có bộ eval và bảng kết quả (precision/recall/latency/cost).
- [ ] Có sơ đồ: kiến trúc, use case, sequence (luồng xử lý PR), ERD.
- [ ] Demo được với PR thật cho vòng bán kết "AI for Life".

---

## 15. Quy tắc cho AI coding agent

- Làm **từng giai đoạn một**, chạy test sau mỗi giai đoạn, dừng lại báo cáo trước khi sang giai đoạn kế.
- Type hint đầy đủ, hàm nhỏ, có docstring ngắn; dùng `async` cho I/O.
- Không hard-code secret/URL; mọi cấu hình qua `config.py`.
- Mọi gọi mạng ngoài (GitHub, LLM) phải đi qua interface để mock được trong test.
- Không thêm thư viện ngoài danh sách nếu chưa cần; nếu cần, nêu lý do.
- Khi không chắc về hành vi API GitHub (ví dụ `position` vs `line`/`side` của review comment), ưu tiên dùng `line` + `side=RIGHT` và ghi chú giả định.
- Mỗi tính năng mới kèm test; không sửa test cho pass nếu logic sai.
- Commit nhỏ, message rõ ràng theo Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`).

---

## 16. Gợi ý cấu trúc báo cáo (ánh xạ từ dự án)

1. Giới thiệu → mục 1-2
2. Cơ sở lý thuyết → code review, LLM, prompt engineering, GitHub App/Webhook
3. Khảo sát công cụ hiện có (CodeRabbit, Copilot code review, SonarQube) và khoảng trống
4. Phân tích yêu cầu → mục 2, 14
5. Thiết kế hệ thống → mục 4, 6, 7, 8
6. Triển khai → mục 3, 5, 9, 11
7. Kiểm thử và đánh giá → mục 12 (giai đoạn 9)
8. Kết luận và hướng phát triển
