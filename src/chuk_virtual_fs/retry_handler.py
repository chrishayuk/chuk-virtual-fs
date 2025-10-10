"""
chuk_virtual_fs/retry_handler.py - Retry mechanism with exponential backoff
"""

import asyncio
import logging
import random
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryError(Exception):
    """Exception raised when all retry attempts fail"""

    def __init__(self, message: str, last_exception: Exception = None):
        super().__init__(message)
        self.last_exception = last_exception


class RetryHandler:
    """
    Handles retry logic with exponential backoff and jitter
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on: tuple[type[Exception], ...] = (Exception,),
        logger: logging.Logger | None = None,
    ):
        """
        Initialize retry handler

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
            retry_on: Tuple of exception types to retry on
            logger: Optional logger instance
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on = retry_on
        self.logger = logger or logging.getLogger(__name__)

        # Statistics
        self.stats = {
            "total_attempts": 0,
            "successful_attempts": 0,
            "failed_attempts": 0,
            "total_retries": 0,
        }

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt number

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = min(self.base_delay * (self.exponential_base**attempt), self.max_delay)

        # Add jitter
        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay

    async def execute_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute async function with retry logic

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from successful function execution

        Raises:
            RetryError: When all retry attempts fail
        """
        last_exception = None
        attempt = 0

        self.stats["total_attempts"] += 1

        while attempt <= self.max_retries:
            try:
                # Log attempt
                if attempt > 0:
                    self.logger.debug(
                        f"Retry attempt {attempt}/{self.max_retries} for {func.__name__}"
                    )
                    self.stats["total_retries"] += 1

                # Execute function
                result = await func(*args, **kwargs)

                # Success
                if attempt > 0:
                    self.logger.info(
                        f"Successfully executed {func.__name__} after {attempt} retries"
                    )

                self.stats["successful_attempts"] += 1
                return result

            except self.retry_on as e:
                last_exception = e

                # Check if we should retry
                if attempt >= self.max_retries:
                    self.logger.error(
                        f"All {self.max_retries} retry attempts failed for {func.__name__}: {e}"
                    )
                    break

                # Calculate delay
                delay = self.calculate_delay(attempt)

                self.logger.warning(
                    f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                    f"Retrying in {delay:.2f} seconds..."
                )

                # Wait before retry
                await asyncio.sleep(delay)
                attempt += 1

            except Exception as e:
                # Don't retry on unexpected exceptions
                self.logger.error(
                    f"Unexpected exception in {func.__name__} (not retrying): {e}"
                )
                self.stats["failed_attempts"] += 1
                raise

        # All retries failed
        self.stats["failed_attempts"] += 1
        raise RetryError(
            f"Failed to execute {func.__name__} after {self.max_retries} retries",
            last_exception,
        )

    def execute_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute synchronous function with retry logic

        Args:
            func: Synchronous function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from successful function execution

        Raises:
            RetryError: When all retry attempts fail
        """
        last_exception = None
        attempt = 0

        self.stats["total_attempts"] += 1

        while attempt <= self.max_retries:
            try:
                # Log attempt
                if attempt > 0:
                    self.logger.debug(
                        f"Retry attempt {attempt}/{self.max_retries} for {func.__name__}"
                    )
                    self.stats["total_retries"] += 1

                # Execute function
                result = func(*args, **kwargs)

                # Success
                if attempt > 0:
                    self.logger.info(
                        f"Successfully executed {func.__name__} after {attempt} retries"
                    )

                self.stats["successful_attempts"] += 1
                return result

            except self.retry_on as e:
                last_exception = e

                # Check if we should retry
                if attempt >= self.max_retries:
                    self.logger.error(
                        f"All {self.max_retries} retry attempts failed for {func.__name__}: {e}"
                    )
                    break

                # Calculate delay
                delay = self.calculate_delay(attempt)

                self.logger.warning(
                    f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                    f"Retrying in {delay:.2f} seconds..."
                )

                # Wait before retry
                import time

                time.sleep(delay)
                attempt += 1

            except Exception as e:
                # Don't retry on unexpected exceptions
                self.logger.error(
                    f"Unexpected exception in {func.__name__} (not retrying): {e}"
                )
                self.stats["failed_attempts"] += 1
                raise

        # All retries failed
        self.stats["failed_attempts"] += 1
        raise RetryError(
            f"Failed to execute {func.__name__} after {self.max_retries} retries",
            last_exception,
        )

    def get_stats(self) -> dict:
        """Get retry statistics"""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics"""
        self.stats = {
            "total_attempts": 0,
            "successful_attempts": 0,
            "failed_attempts": 0,
            "total_retries": 0,
        }


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: tuple[type[Exception], ...] = (Exception,),
):
    """
    Decorator for adding retry logic to functions

    Usage:
        @with_retry(max_retries=3, base_delay=1.0)
        async def my_function():
            # Function that might fail
            pass
    """

    def decorator(func):
        handler = RetryHandler(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            retry_on=retry_on,
        )

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await handler.execute_async(func, *args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return handler.execute_sync(func, *args, **kwargs)

            return sync_wrapper

    return decorator


# Global retry handler instance
default_retry_handler = RetryHandler()
