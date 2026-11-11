from katiu.core.security import LoginRateLimiter, hash_password, verify_password


def test_hash_y_verificacion() -> None:
    h = hash_password("secreto-largo")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "secreto-largo")
    assert not verify_password(h, "otro")
    assert not verify_password("basura", "secreto-largo")


def test_rate_limiter() -> None:
    rl = LoginRateLimiter(max_attempts=2, window_seconds=60)
    assert not rl.is_blocked("ip")
    rl.register_failure("ip")
    rl.register_failure("ip")
    assert rl.is_blocked("ip")
    assert not rl.is_blocked("otra-ip")
    rl.reset("ip")
    assert not rl.is_blocked("ip")
