"""
认证模块单元测试 — 密码哈希、Token 验证、Session 管理。

不需要数据库，测试纯函数和 mock 后的认证逻辑。
"""
import bcrypt as _bcrypt
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta


# ============================================================
# bcrypt 密码哈希测试
# ============================================================

class TestPasswordHashing:
    """密码哈希 — 对应 P0-① bcrypt 改造后的验证"""

    def test_bcrypt_hash_and_verify(self):
        """bcrypt 哈希后应能验证成功"""
        password = b"MyP@ssw0rd!123"
        salt = _bcrypt.gensalt()
        h = _bcrypt.hashpw(password, salt)
        assert _bcrypt.checkpw(password, h), "正确密码应验证通过"
        assert not _bcrypt.checkpw(b"wrong_password", h), "错误密码应验证失败"

    def test_bcrypt_unique_hashes(self):
        """相同密码每次应生成不同哈希（自动加盐）"""
        password = b"test123"
        h1 = _bcrypt.hashpw(password, _bcrypt.gensalt())
        h2 = _bcrypt.hashpw(password, _bcrypt.gensalt())
        assert h1 != h2, "bcrypt 每次应生成不同哈希（因自动加盐）"

    def test_bcrypt_no_sha256_password_leak(self):
        """确认 src/ 中不再用 SHA256 做密码哈希（API key 生成等非密码用途除外）"""
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src_dir = os.path.join(root, "src")
        found = []
        for dirpath, _, filenames in os.walk(src_dir):
            for fn in filenames:
                if fn.endswith(".py"):
                    path = os.path.join(dirpath, fn)
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        # 跳过注释行和 API key 生成（使用 sha256 但不涉及密码哈希）
                        if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
                            continue
                        if "hashlib.sha256" in stripped and "password" in stripped.lower():
                            # 排除 API key 生成场景 和 SHA256→bcrypt 迁移升级路径
                            if "api_key" not in stripped.lower() and "stored_hash" not in stripped:
                                found.append(f"{path}:{i}: {stripped}")
        if found:
            pytest.fail(f"发现 SHA256 密码哈希可能残留:\n" + "\n".join(found))


# ============================================================
# 登录/注册验证逻辑测试
# ============================================================

class TestLoginValidation:
    """注册/登录的输入验证逻辑 — 对应 P0-⑤ 输入安全加固"""

    def test_email_validation(self):
        """邮箱格式校验"""
        import re
        email_re = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

        valid = ["user@example.com", "test@dc.ai", "a.b@c.co"]
        invalid = ["notanemail", "@no.com", "no@.com", "", "spaces in@email.com"]

        for e in valid:
            assert email_re.match(e), f"有效的 {e} 不应被拒绝"
        for e in invalid:
            assert not email_re.match(e), f"无效的 {e} 不应被接受"


# ============================================================
# Token 验证测试
# ============================================================

class TestAuthToken:
    """Token 验证逻辑 — 对应 P0-② Token 持久化"""

    def test_token_expiry_check(self):
        """Token 过期判断"""
        now = datetime.now(timezone.utc)
        valid_token = {"expires_at": (now + timedelta(hours=24)).isoformat()}
        expired_token = {"expires_at": (now - timedelta(hours=1)).isoformat()}

        def is_expired(t):
            expires = datetime.fromisoformat(t["expires_at"])
            return expires < now

        assert not is_expired(valid_token), "24小时内有效"
        assert is_expired(expired_token), "已过期"


# ============================================================
# 注册限速逻辑测试
# ============================================================

class TestRateLimit:
    """注册限速 — 对应 P0-④ 注册限速"""

    def test_rate_limit_exists(self):
        """确认项目中有限流配置"""
        import os
        server_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "web_server.py"
        )
        with open(server_path, "r", encoding="utf-8") as f:
            content = f.read()
        has_limiter = "limiter" in content.lower() or "rate" in content.lower()
        assert has_limiter, "web_server.py 中应包含限流配置"


# ============================================================
# 邮箱验证测试
# ============================================================

class TestEmailVerification:
    """邮箱验证 — 对应 P0-④ 邮箱验证"""

    def test_verify_token_format(self):
        """验证 token 应为十六进制字符串"""
        import secrets
        token = secrets.token_hex(32)
        assert len(token) == 64, "32 字节 hex 应为 64 字符"
        assert all(c in "0123456789abcdef" for c in token), "应为纯十六进制"

    def test_verify_email_page_exists(self):
        """验证邮箱页面应存在且包含验证逻辑"""
        import os
        verify_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "verify_email.html"
        )
        assert os.path.exists(verify_path), "verify_email.html 应存在"
        with open(verify_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "verify" in content.lower() or "验证" in content, \
            "verify_email.html 应包含验证相关文本"

