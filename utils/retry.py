"""
ReelRecon - Retry Logic with Exponential Backoff
Robust retry mechanism for network operations
"""

import time
import functools
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Type, Any, List
from .logger import get_logger


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    on_retry: Optional[Callable[[Exception, int], None]] = None


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay with exponential backoff and optional jitter"""
    delay = min(
        config.initial_delay * (config.exponential_base ** attempt),
        config.max_delay
    )

    if config.jitter:
        import random
        delay = delay * (0.5 + random.random())

    return delay


def retry_with_backoff(
    func: Optional[Callable] = None,
    *,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    category: str = "RETRY"
):
    """
    Decorator for retrying functions with exponential backoff.

    Usage:
        @retry_with_backoff(max_attempts=3)
        def fetch_data():
            ...

        # Or with config object:
        @retry_with_backoff(max_attempts=5, retryable_exceptions=(ConnectionError, TimeoutError))
        def network_call():
            ...
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
        on_retry=on_retry
    )

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            logger = get_logger()
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return fn(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = calculate_delay(attempt, config)
                        logger.warning(category, f"Attempt {attempt + 1}/{config.max_attempts} failed, retrying in {delay:.1f}s", {
                            "function": fn.__name__,
                            "error": str(e),
                            "attempt": attempt + 1
                        })

                        if config.on_retry:
                            config.on_retry(e, attempt + 1)

                        time.sleep(delay)
                    else:
                        logger.error(category, f"All {config.max_attempts} attempts failed", {
                            "function": fn.__name__,
                            "final_error": str(e)
                        }, exception=e)

            raise last_exception

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


class RetryContext:
    """
    Context manager for retry logic.

    Usage:
        with RetryContext(max_attempts=3) as retry:
            while retry.should_continue():
                try:
                    result = risky_operation()
                    break
                except SomeError as e:
                    retry.handle_error(e)
    """

    def __init__(self, config: Optional[RetryConfig] = None, **kwargs):
        self.config = config or RetryConfig(**kwargs)
        self.attempt = 0
        self.last_error: Optional[Exception] = None
        self.logger = get_logger()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def should_continue(self) -> bool:
        """Check if we should continue retrying"""
        return self.attempt < self.config.max_attempts

    def handle_error(self, error: Exception, category: str = "RETRY") -> bool:
        """
        Handle an error and decide whether to retry.
        Returns True if retry will happen, False if max attempts reached.
        """
        self.last_error = error
        self.attempt += 1

        if not isinstance(error, self.config.retryable_exceptions):
            raise error

        if self.attempt >= self.config.max_attempts:
            self.logger.error(category, f"Max attempts ({self.config.max_attempts}) reached", {
                "error": str(error)
            }, exception=error)
            return False

        delay = calculate_delay(self.attempt - 1, self.config)
        self.logger.warning(category, f"Attempt {self.attempt}/{self.config.max_attempts} failed, retrying in {delay:.1f}s", {
            "error": str(error)
        })

        if self.config.on_retry:
            self.config.on_retry(error, self.attempt)

        time.sleep(delay)
        return True

    def success(self):
        """Mark operation as successful"""
        self.last_error = None


def retry_operation(
    operation: Callable,
    *args,
    config: Optional[RetryConfig] = None,
    category: str = "RETRY",
    **kwargs
) -> Any:
    """
    Retry an operation with the given configuration.

    Usage:
        result = retry_operation(
            fetch_url,
            "https://example.com",
            config=RetryConfig(max_attempts=5),
            category="HTTP"
        )
    """
    config = config or RetryConfig()
    logger = get_logger()
    last_error = None

    for attempt in range(config.max_attempts):
        try:
            return operation(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_error = e

            if attempt < config.max_attempts - 1:
                delay = calculate_delay(attempt, config)
                logger.warning(category, f"Attempt {attempt + 1}/{config.max_attempts} failed", {
                    "error": str(e),
                    "retry_delay": delay
                })

                if config.on_retry:
                    config.on_retry(e, attempt + 1)

                time.sleep(delay)
            else:
                logger.error(category, f"All {config.max_attempts} attempts failed", {
                    "final_error": str(e)
                }, exception=e)

    raise last_error


# Pre-configured retry decorators for common use cases
network_retry = functools.partial(
    retry_with_backoff,
    max_attempts=3,
    initial_delay=1.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
    category="NETWORK"
)

api_retry = functools.partial(
    retry_with_backoff,
    max_attempts=3,
    initial_delay=2.0,
    max_delay=60.0,
    category="API"
)

download_retry = functools.partial(
    retry_with_backoff,
    max_attempts=3,
    initial_delay=2.0,
    max_delay=30.0,
    category="DOWNLOAD"
)
