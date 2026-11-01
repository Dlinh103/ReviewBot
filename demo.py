"""Interactive demo of ReviewBot: Automated AI Code Review Assistant."""

import asyncio
import json
import sys
from typing import Any

if sys.platform == "win32":
    try:
        reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure_fn):
            reconfigure_fn(encoding="utf-8", errors="replace")
    except Exception:
        pass

from reviewbot.config import get_settings
from reviewbot.core.file_filter import FileFilter
from reviewbot.core.secrets_scrubber import scrub_secrets
from reviewbot.db.repositories import ReviewRepository
from reviewbot.db.session import create_all_tables, get_db_session
from reviewbot.github.client import GitHubClient
from reviewbot.github.signature import compute_github_signature, verify_github_signature
from reviewbot.llm.anthropic_client import AnthropicClient
from reviewbot.llm.base import LLMClient, LLMResponse
from reviewbot.llm.schemas import Finding
from reviewbot.services.review_service import ReviewService

# Simulated Pull Request Changes
MOCK_PR_FILES = [
    {
        "filename": "src/auth/database.py",
        "status": "modified",
        "changes": 12,
        "patch": """@@ -15,7 +15,10 @@ def authenticate_user(username, password):
-    # TODO: verify user
-    return None
+    AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
+    # Querying user with raw SQL string formatting
+    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
+    cursor.execute(query)
+    return cursor.fetchone()
""",
    },
    {
        "filename": "src/payment/processor.py",
        "status": "modified",
        "changes": 10,
        "patch": """@@ -22,5 +22,7 @@ def calculate_discount_ratio(total_amount, coupon_count):
-    return total_amount * 0.95
+    # Potential division by zero bug if coupon_count is 0
+    discount_ratio = total_amount / coupon_count
+    return discount_ratio
""",
    },
    {
        "filename": "package-lock.json",
        "status": "modified",
        "changes": 450,
        "patch": "@@ -1,500 +1,500 @@ Lockfile changes",
    },
]


class DemoIntelligentLLM(LLMClient):
    """Fallback LLM simulating Claude Sonnet responses for offline demonstrations."""

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        _max_tokens: int | None = None,
    ) -> LLMResponse:
        await asyncio.sleep(0.3)  # Simulate API latency

        if "tóm tắt" in system_prompt.lower() or "summary" in system_prompt.lower():
            content = json.dumps(
                {
                    "title_suggestion": (
                        "feat(auth/payment): add user authentication query and discount calculator"
                    ),
                    "summary": (
                        "Pull Request bổ sung logic xác thực người dùng trong database "
                        "và hàm tính toán tỷ lệ giảm giá theo mã coupon."
                    ),
                    "changes": [
                        "Bổ sung hàm authenticate_user truy vấn trực tiếp bảng users",
                        "Thêm cấu hình kết nối AWS",
                        "Cập nhật hàm tính tỷ lệ chiết khấu calculate_discount_ratio",
                    ],
                    "risks": [
                        "Lỗ hổng bảo mật: Nguy cơ SQL Injection khi nối chuỗi trực tiếp",
                        "Lỗi Crash ứng dụng: Nguy cơ ZeroDivisionError khi coupon_count = 0",
                        "Lộ lọt thông tin nhạy cảm: Hardcoded AWS Access Key trong mã nguồn",
                    ],
                    "test_suggestions": [
                        "Thực hiện kiểm thử bảo mật SQL Injection với username: ' OR '1'='1",
                        "Bổ sung unit test cho trường hợp coupon_count = 0",
                        "Chuyển AWS credentials sang biến môi trường (.env)",
                    ],
                }
            )
        elif "database.py" in user_prompt:
            content = json.dumps(
                {
                    "findings": [
                        {
                            "file": "src/auth/database.py",
                            "line": 18,
                            "end_line": 19,
                            "severity": "critical",
                            "category": "security",
                            "message": (
                                "Phát hiện lỗ hổng SQL Injection nghiêm trọng do nối chuỗi trực tiếp "
                                "tham số username và password vào câu lệnh SQL."
                            ),
                            "evidence": (
                                'query = f"SELECT * FROM users WHERE username = '
                                "'{username}' AND password = '{password}'\""
                            ),
                            "suggestion": (
                                'query = "SELECT * FROM users WHERE username = %s AND password = %s"\n'
                                "    cursor.execute(query, (username, password))"
                            ),
                            "confidence": 0.98,
                        },
                        {
                            "file": "src/auth/database.py",
                            "line": 15,
                            "end_line": None,
                            "severity": "critical",
                            "category": "security",
                            "message": (
                                "Không được lưu cứng khóa truy cập AWS trong mã nguồn. "
                                "Cần chuyển sang sử dụng biến môi trường."
                            ),
                            "evidence": 'AWS_ACCESS_KEY_ID = "[REDACTED_AWS_KEY_ID]"',
                            "suggestion": (
                                "import os\n"
                                "    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')"
                            ),
                            "confidence": 0.95,
                        },
                    ],
                    "overall_notes": "Phát hiện 2 lỗ hổng bảo mật mức độ Critical cần xử lý khẩn cấp.",
                }
            )
        else:
            content = json.dumps(
                {
                    "findings": [
                        {
                            "file": "src/payment/processor.py",
                            "line": 23,
                            "end_line": None,
                            "severity": "major",
                            "category": "bug",
                            "message": (
                                "Nguy cơ lỗi ZeroDivisionError nếu tham số coupon_count bằng 0, "
                                "có thể gây crash luồng thanh toán."
                            ),
                            "evidence": "discount_ratio = total_amount / coupon_count",
                            "suggestion": (
                                "if not coupon_count:\n"
                                "        return 0.0\n"
                                "    discount_ratio = total_amount / coupon_count"
                            ),
                            "confidence": 0.92,
                        }
                    ],
                    "overall_notes": "Cần bổ sung kiểm tra biên cho phép chia.",
                }
            )

        return LLMResponse(
            content=content,
            input_tokens=420,
            output_tokens=180,
            estimated_cost_usd=0.0039,
            model="claude-sonnet-4-6",
            duration_ms=300,
        )


async def run_demo() -> None:
    settings = get_settings()

    print("=" * 80)
    print("🤖 REVIEWBOT — HỆ THỐNG TRỢ LÝ REVIEW MÃ NGUỒN TỰ ĐỘNG BẰNG LLM")
    print("   Đề tài Chuyên ngành 2 (SE) — VKU")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # BƯỚC 1: TIẾP NHẬN WEBHOOK GITHUB & XÁC THỰC HMAC
    # -------------------------------------------------------------------------
    print("\n[BƯỚC 1] TIẾP NHẬN SỰ KIỆN GITHUB WEBHOOK (HMAC SHA-256)")
    print("-" * 80)
    webhook_secret = settings.GITHUB_WEBHOOK_SECRET or "demo-secret-key-12345"
    sample_payload: dict[str, Any] = {
        "action": "opened",
        "repository": {"full_name": "vku-se/student-management-app", "id": 987654321},
        "pull_request": {
            "number": 101,
            "title": "feat(auth/payment): add user authentication query and discount calculator",
            "body": "This PR implements user auth and coupon discount calculations.",
            "head": {"sha": "9f8e7d6c5b4a3210fedcba987654321012345678"},
        },
    }
    raw_payload_bytes = json.dumps(sample_payload).encode("utf-8")
    signature = compute_github_signature(raw_payload_bytes, webhook_secret)

    print("  • Event           : pull_request (action: opened)")
    print(f"  • Repository      : {sample_payload['repository']['full_name']}")
    print(f"  • PR Number       : #{sample_payload['pull_request']['number']}")
    print(f"  • Commit Head SHA : {sample_payload['pull_request']['head']['sha'][:10]}...")
    print(f"  • Signature Header: {signature[:25]}...")

    is_valid = verify_github_signature(raw_payload_bytes, signature, webhook_secret)
    status_label = "✅ HỢP LỆ (202 Accepted)" if is_valid else "❌ TỪ CHỐI (401 Unauthorized)"
    print(f"  -> Xác thực chữ ký HMAC SHA-256: {status_label}")

    # -------------------------------------------------------------------------
    # BƯỚC 2: LỌC FILE KHÔNG REVIEW & KHỬ DỮ LIỆU NHẠY CẢM
    # -------------------------------------------------------------------------
    print("\n[BƯỚC 2] LỌC TỆP TIN & KHỬ THÔNG TIN NHẠY CẢM (SECRETS SCRUBBING)")
    print("-" * 80)
    file_filter = FileFilter()
    retained_files, skipped_files = file_filter.filter_files(MOCK_PR_FILES)

    print(f"  • Tổng số files trong PR : {len(MOCK_PR_FILES)}")
    print(f"  • Files giữ lại review   : {len(retained_files)}")
    for f in retained_files:
        print(f"    [+] {f['filename']} (status: {f['status']}, changes: {f['changes']})")
    print(f"  • Files bị loại trừ      : {len(skipped_files)}")
    for filename, reason in skipped_files:
        print(f"    [-] {filename} -> Lý do: {reason}")

    print("\n  • Kiểm tra che giấu Secrets (Secrets Scrubber):")
    for f in retained_files:
        _clean_patch, count = scrub_secrets(f["patch"])
        if count > 0:
            print(f"    🛡️ Phát hiện {count} secret(s) trong '{f['filename']}' -> Đã che an toàn")

    # -------------------------------------------------------------------------
    # BƯỚC 3: PHÂN TÍCH DIFF & GỌI LLM REVIEW CHUNKS
    # -------------------------------------------------------------------------
    print("\n[BƯỚC 3] TIẾN HÀNH PHÂN TÍCH DIFF & GỌI LLM REVIEW")
    print("-" * 80)
    if settings.ANTHROPIC_API_KEY:
        print("  • Sử dụng Live Anthropic Client (Claude Sonnet)...")
        llm_client: LLMClient = AnthropicClient(settings=settings)
    else:
        print("  • Chưa có ANTHROPIC_API_KEY trong .env -> Sử dụng Intelligent Demo Reviewer")
        llm_client = DemoIntelligentLLM()

    # Create SQLite tables for persistence
    create_all_tables()

    # Setup mock GitHubClient
    class MockGitHubClient(GitHubClient):
        async def get_pr_files(
            self,
            repo_full_name: str,
            pr_number: int,
            per_page: int = 100,
        ) -> list[dict[str, Any]]:
            _ = (repo_full_name, pr_number, per_page)
            return MOCK_PR_FILES

        async def create_review(
            self,
            repo_full_name: str,
            pr_number: int,
            commit_id: str,
            body: str,
            comments: list[dict[str, Any]],
            event: str = "COMMENT",
        ) -> dict[str, Any]:
            _ = (repo_full_name, pr_number, commit_id, body, comments, event)
            return {"id": 123456, "state": "COMMENTED"}

        async def upsert_issue_comment(
            self,
            repo_full_name: str,
            pr_number: int,
            body: str,
            marker: str = GitHubClient.SUMMARY_MARKER,
        ) -> dict[str, Any]:
            _ = (repo_full_name, pr_number, body, marker)
            return {"id": 789012}

    mock_github = MockGitHubClient()
    review_service = ReviewService(llm_client=llm_client, settings=settings)

    print("  • Đang phân tích mã nguồn và gọi LLM...")
    result = await review_service.review_pull_request(
        github_client=mock_github,
        repo_full_name="vku-se/student-management-app",
        pr_number=101,
        head_sha="9f8e7d6c5b4a3210fedcba987654321012345678",
        pr_title=sample_payload["pull_request"]["title"],
        pr_body=sample_payload["pull_request"]["body"],
    )

    # -------------------------------------------------------------------------
    # BƯỚC 4: KẾT QUẢ GITHUB REVIEW (INLINE COMMENTS)
    # -------------------------------------------------------------------------
    print("\n[BƯỚC 4] KẾT QUẢ GITHUB REVIEW — INLINE COMMENTS ĐÚNG DÒNG")
    print("=" * 80)
    findings = result.get("findings", [])
    print(f"Tổng số phát hiện: {len(findings)} issues")
    print("=" * 80)

    for i, finding_dict in enumerate(findings, start=1):
        print(f"\n👉 Comment #{i} trên file: {finding_dict['file']}:{finding_dict['line']}")
        print("   " + "-" * 70)
        sev = finding_dict["severity"].upper()
        cat = finding_dict["category"].upper()
        conf = int(finding_dict["confidence"] * 100)
        print(f"   Mức độ: [{sev}] | Danh mục: [{cat}] | Độ tin cậy: {conf}%")
        print(f"   Thông báo: {finding_dict['message']}")
        print(f"   Bằng chứng: {finding_dict['evidence']}")
        if finding_dict.get("suggestion"):
            print("   Đề xuất sửa đổi (GitHub Suggested Changes):")
            print("   ```suggestion")
            for line in finding_dict["suggestion"].splitlines():
                print(f"   {line}")
            print("   ```")

    # -------------------------------------------------------------------------
    # BƯỚC 5: COMMENT TÓM TẮT PULL REQUEST (PR SUMMARY)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("[BƯỚC 5] COMMENT TÓM TẮT PR TỰ ĐỘNG (MARKER: <!-- reviewbot:summary -->)")
    print("=" * 80)
    summary_dict = result.get("summary", {})
    if summary_dict:
        print(f"💡 Gợi ý tiêu đề: {summary_dict.get('title_suggestion')}")
        print("\n📌 Tóm tắt mục tiêu:")
        print(f"   {summary_dict.get('summary')}")
        print("\n🛠️ Thay đổi chính:")
        for ch in summary_dict.get("changes", []):
            print(f"   • {ch}")
        print("\n⚠️ Rủi ro tiềm ẩn:")
        for rk in summary_dict.get("risks", []):
            print(f"   • {rk}")
        print("\n🧪 Gợi ý kiểm thử:")
        for ts in summary_dict.get("test_suggestions", []):
            print(f"   • {ts}")

    # -------------------------------------------------------------------------
    # BƯỚC 6: BỀN VỮNG HÓA VÀ TRUY VẤN CƠ SỞ DỮ LIỆU
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("[BƯỚC 6] KIỂM TRA LƯU TRỮ VÀO CƠ SỞ DỮ LIỆU (DATABASE AUDIT LOG)")
    print("=" * 80)

    # Save to SQLite db
    with get_db_session() as session:
        repo_layer = ReviewRepository(session)
        repo_obj = repo_layer.get_or_create_repo(
            github_repo_id=987654321,
            full_name="vku-se/student-management-app",
        )
        pr_obj = repo_layer.get_or_create_pr(
            repo_id=repo_obj.id,
            number=101,
            title=sample_payload["pull_request"]["title"],
            author="student_dev",
            head_sha=sample_payload["pull_request"]["head"]["sha"],
        )
        review_obj = repo_layer.create_or_get_review(
            pr_id=pr_obj.id,
            head_sha=sample_payload["pull_request"]["head"]["sha"],
            model=result.get("model", "claude-sonnet-4-6"),
        )
        findings_models = [Finding.model_validate(f) for f in findings]
        repo_layer.complete_review(
            review_id=review_obj.id,
            github_review_id=result.get("github_review_id", 123456),
            input_tokens=result.get("input_tokens", 840),
            output_tokens=result.get("output_tokens", 360),
            cost_usd=result.get("total_cost_usd", 0.0078),
            duration_ms=result.get("duration_ms", 650),
            findings=findings_models,
        )

        # Query back from DB
        db_review = repo_layer.get_review_with_findings(review_obj.id)
        assert db_review is not None
        status_name = db_review.status.value.upper()
        total_toks = db_review.input_tokens + db_review.output_tokens
        print(f"  • Database Record ID : #{db_review.id} (Status: {status_name})")
        print(f"  • GitHub Review ID   : {db_review.github_review_id}")
        print(
            f"  • Tokens đã dùng     : {total_toks} "
            f"(In: {db_review.input_tokens}, Out: {db_review.output_tokens})"
        )
        print(f"  • Chi phí ước lượng  : ${db_review.cost_usd:.4f} USD")
        print(f"  • Thời gian xử lý    : {db_review.duration_ms} ms")
        print(f"  • Số findings lưu DB : {len(db_review.findings)} bản ghi")

    print("\n" + "=" * 80)
    print("🎉 DEMO HOÀN THÀNH XUẤT SẮC TOÀN BỘ 6 BƯỚC CỦA HỆ THỐNG REVIEWBOT!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_demo())
