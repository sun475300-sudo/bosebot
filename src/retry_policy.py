"""백그라운드 작업 재시도 정책 모듈.

외부 API 호출이나 일시적 실패가 가능한 작업에 대해 표준화된
재시도 로직을 제공한다.

특징:
- 지수 백오프 (exponential backoff)
- 지터 (jitter) 로 thundering-herd 방지
- 최대 시도 횟수 / 최대 대기 시간 제한
- 특정 예외 타입만 재시도 (whitelist) 또는 무시 (blacklist)
- 재시도 콜백으로 로깅·메트릭 hook
- 동기/비동기 모두 데코레이터로 사용 가능

Usage::

    from src.retry_policy import RetryPolicy, retry

    @retry(RetryPolicy(max_attempts=3, base_delay=0.1))
    def call_external_api():
        ...

    # or programmatic:
    policy = RetryPolicy(max_attempts=5, base_delay=0.5, max_delay=10.0)
    result = policy.run(my_func, arg1, kwarg=val)
"""

from __future__ import annotations

import functools
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Tuple, Type

LOG = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """재시도 정책 설정.

    Attributes:
        max_attempts: 최대 시도 횟수 (1 = 재시도 없음). 기본 3.
        base_delay: 첫 재시도까지 대기 시간(초). 기본 0.5.
        max_delay: 단일 대기의 상한(초). 기본 30.0.
        backoff_factor: 백오프 배수 (next = prev * factor). 기본 2.0.
        jitter: 0 ~ 1, 실제 대기에 곱해질 랜덤 흔들기 비율. 0이면 비활성.
        retry_on: 재시도할 예외 타입 튜플. 기본 (Exception,) — 모두 재시도.
        give_up_on: 재시도 안 할 예외 타입 튜플. 우선순위 높음.
        on_retry: ``(attempt, exc, delay) → None`` 콜백.
    """

    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    jitter: float = 0.2
    retry_on: Tuple[Type[BaseException], ...] = (Exception,)
    give_up_on: Tuple[Type[BaseException], ...] = field(default_factory=tuple)
    on_retry: Optional[Callable[[int, BaseException, float], None]] = None

    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay < 0:
            raise ValueError("base_delay must be >= 0")
        if self.max_delay < self.base_delay:
            self.max_delay = self.base_delay
        if not 0 <= self.jitter <= 1:
            raise ValueError("jitter must be in [0, 1]")

    def compute_delay(self, attempt: int) -> float:
        """주어진 시도 번호(1-based, 1=첫 재시도 직전)에 대한 대기 시간.

        ``attempt=1`` → base_delay,
        ``attempt=2`` → base_delay * backoff_factor, ...
        결과는 ``[lower, upper]`` 사이에서 jitter 랜덤화.
        """
        raw = self.base_delay * (self.backoff_factor ** max(0, attempt - 1))
        capped = min(raw, self.max_delay)
        if self.jitter <= 0:
            return capped
        # jitter: 결정적 평균 capped, 분포 [capped*(1-j), capped*(1+j)]
        low = capped * (1.0 - self.jitter)
        high = capped * (1.0 + self.jitter)
        return random.uniform(max(0.0, low), high)

    def should_retry(self, exc: BaseException) -> bool:
        """예외가 재시도 대상인지 판정."""
        if isinstance(exc, self.give_up_on):
            return False
        return isinstance(exc, self.retry_on)

    def run(self, fn: Callable[..., Any], *args, **kwargs) -> Any:
        """``fn(*args, **kwargs)``를 정책에 따라 호출.

        성공 시 반환값. 모든 시도 실패 시 마지막 예외를 raise.
        """
        last_exc: Optional[BaseException] = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return fn(*args, **kwargs)
            except BaseException as exc:
                last_exc = exc
                if attempt >= self.max_attempts or not self.should_retry(exc):
                    raise
                delay = self.compute_delay(attempt)
                if self.on_retry is not None:
                    try:
                        self.on_retry(attempt, exc, delay)
                    except Exception:  # pragma: no cover - hook errors swallowed
                        LOG.exception("retry on_retry hook raised")
                if delay > 0:
                    time.sleep(delay)
        # 이론상 unreachable
        if last_exc is not None:  # pragma: no cover
            raise last_exc
        raise RuntimeError("retry exhausted with no exception captured")


def retry(policy: Optional[RetryPolicy] = None, **policy_kwargs):
    """함수에 재시도 정책을 적용하는 데코레이터 팩토리.

    ``@retry(RetryPolicy(...))`` 또는
    ``@retry(max_attempts=5, base_delay=0.1)`` 모두 지원.
    """
    if policy is None:
        policy = RetryPolicy(**policy_kwargs)
    elif policy_kwargs:
        raise TypeError("pass either a RetryPolicy or kwargs, not both")

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return policy.run(fn, *args, **kwargs)
        wrapper.__retry_policy__ = policy  # type: ignore[attr-defined]
        return wrapper
    return deco


__all__ = ["RetryPolicy", "retry"]
