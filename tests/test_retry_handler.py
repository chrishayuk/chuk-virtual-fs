"""
Test module for retry_handler module
"""

import pytest

from chuk_virtual_fs.retry_handler import (
    RetryError,
    RetryHandler,
    default_retry_handler,
    with_retry,
)


class TestRetryError:
    """Test RetryError exception"""

    def test_retry_error_creation(self):
        """Test creating a RetryError"""
        error = RetryError("Test error")
        assert str(error) == "Test error"
        assert error.last_exception is None

    def test_retry_error_with_exception(self):
        """Test creating a RetryError with last exception"""
        last_exc = ValueError("Original error")
        error = RetryError("Test error", last_exc)
        assert str(error) == "Test error"
        assert error.last_exception == last_exc


class TestRetryHandler:
    """Test RetryHandler class"""

    def test_initialization_defaults(self):
        """Test default initialization"""
        handler = RetryHandler()
        assert handler.max_retries == 3
        assert handler.base_delay == 1.0
        assert handler.max_delay == 60.0
        assert handler.exponential_base == 2.0
        assert handler.jitter is True
        assert handler.retry_on == (Exception,)
        assert handler.stats["total_attempts"] == 0

    def test_initialization_custom(self):
        """Test custom initialization"""
        handler = RetryHandler(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False,
            retry_on=(ValueError, KeyError),
        )
        assert handler.max_retries == 5
        assert handler.base_delay == 2.0
        assert handler.max_delay == 120.0
        assert handler.exponential_base == 3.0
        assert handler.jitter is False
        assert handler.retry_on == (ValueError, KeyError)

    def test_calculate_delay_no_jitter(self):
        """Test delay calculation without jitter"""
        handler = RetryHandler(base_delay=1.0, exponential_base=2.0, jitter=False)

        # Test exponential backoff
        assert handler.calculate_delay(0) == 1.0  # 1.0 * 2^0
        assert handler.calculate_delay(1) == 2.0  # 1.0 * 2^1
        assert handler.calculate_delay(2) == 4.0  # 1.0 * 2^2

    def test_calculate_delay_with_max(self):
        """Test delay calculation with max delay"""
        handler = RetryHandler(
            base_delay=1.0, exponential_base=2.0, max_delay=3.0, jitter=False
        )

        # Should cap at max_delay
        assert handler.calculate_delay(10) == 3.0

    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter"""
        handler = RetryHandler(base_delay=2.0, exponential_base=2.0, jitter=True)

        # With jitter, delay should be in range [base * 0.5, base * 1.5]
        delay = handler.calculate_delay(0)
        assert 1.0 <= delay <= 3.0

    @pytest.mark.asyncio
    async def test_execute_async_success_first_try(self):
        """Test successful async execution on first try"""
        handler = RetryHandler()

        async def successful_func():
            return "success"

        result = await handler.execute_async(successful_func)
        assert result == "success"
        assert handler.stats["total_attempts"] == 1
        assert handler.stats["successful_attempts"] == 1
        assert handler.stats["total_retries"] == 0

    @pytest.mark.asyncio
    async def test_execute_async_success_after_retries(self):
        """Test successful async execution after retries"""
        handler = RetryHandler(max_retries=3, base_delay=0.01, jitter=False)

        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = await handler.execute_async(flaky_func)
        assert result == "success"
        assert call_count == 3
        assert handler.stats["total_attempts"] == 1
        assert handler.stats["successful_attempts"] == 1
        assert handler.stats["total_retries"] == 2

    @pytest.mark.asyncio
    async def test_execute_async_all_retries_fail(self):
        """Test async execution when all retries fail"""
        handler = RetryHandler(max_retries=2, base_delay=0.01, jitter=False)

        async def always_fails():
            raise ValueError("Permanent error")

        with pytest.raises(RetryError) as exc_info:
            await handler.execute_async(always_fails)

        assert "Failed to execute always_fails after 2 retries" in str(exc_info.value)
        assert isinstance(exc_info.value.last_exception, ValueError)
        assert handler.stats["failed_attempts"] == 1

    @pytest.mark.asyncio
    async def test_execute_async_unexpected_exception(self):
        """Test async execution with unexpected exception"""
        handler = RetryHandler(retry_on=(ValueError,), base_delay=0.01)

        async def raises_runtime_error():
            raise RuntimeError("Unexpected error")

        with pytest.raises(RuntimeError):
            await handler.execute_async(raises_runtime_error)

        assert handler.stats["failed_attempts"] == 1

    def test_execute_sync_success_first_try(self):
        """Test successful sync execution on first try"""
        handler = RetryHandler()

        def successful_func():
            return "success"

        result = handler.execute_sync(successful_func)
        assert result == "success"
        assert handler.stats["total_attempts"] == 1
        assert handler.stats["successful_attempts"] == 1
        assert handler.stats["total_retries"] == 0

    def test_execute_sync_success_after_retries(self):
        """Test successful sync execution after retries"""
        handler = RetryHandler(max_retries=3, base_delay=0.01, jitter=False)

        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = handler.execute_sync(flaky_func)
        assert result == "success"
        assert call_count == 3
        assert handler.stats["total_attempts"] == 1
        assert handler.stats["successful_attempts"] == 1
        assert handler.stats["total_retries"] == 2

    def test_execute_sync_all_retries_fail(self):
        """Test sync execution when all retries fail"""
        handler = RetryHandler(max_retries=2, base_delay=0.01, jitter=False)

        def always_fails():
            raise ValueError("Permanent error")

        with pytest.raises(RetryError) as exc_info:
            handler.execute_sync(always_fails)

        assert "Failed to execute always_fails after 2 retries" in str(exc_info.value)
        assert isinstance(exc_info.value.last_exception, ValueError)
        assert handler.stats["failed_attempts"] == 1

    def test_execute_sync_unexpected_exception(self):
        """Test sync execution with unexpected exception"""
        handler = RetryHandler(retry_on=(ValueError,), base_delay=0.01)

        def raises_runtime_error():
            raise RuntimeError("Unexpected error")

        with pytest.raises(RuntimeError):
            handler.execute_sync(raises_runtime_error)

        assert handler.stats["failed_attempts"] == 1

    def test_get_stats(self):
        """Test getting statistics"""
        handler = RetryHandler()

        def successful_func():
            return "success"

        handler.execute_sync(successful_func)

        stats = handler.get_stats()
        assert stats["total_attempts"] == 1
        assert stats["successful_attempts"] == 1
        assert isinstance(stats, dict)

        # Verify it's a copy
        stats["total_attempts"] = 999
        assert handler.stats["total_attempts"] == 1

    def test_reset_stats(self):
        """Test resetting statistics"""
        handler = RetryHandler()

        def successful_func():
            return "success"

        handler.execute_sync(successful_func)
        assert handler.stats["total_attempts"] == 1

        handler.reset_stats()
        assert handler.stats["total_attempts"] == 0
        assert handler.stats["successful_attempts"] == 0
        assert handler.stats["failed_attempts"] == 0
        assert handler.stats["total_retries"] == 0

    @pytest.mark.asyncio
    async def test_execute_async_with_args_kwargs(self):
        """Test async execution with arguments"""
        handler = RetryHandler()

        async def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = await handler.execute_async(func_with_args, 1, 2, c=3)
        assert result == "1-2-3"


class TestWithRetryDecorator:
    """Test with_retry decorator"""

    @pytest.mark.asyncio
    async def test_decorator_async_function(self):
        """Test decorator with async function"""
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01, jitter=False)
        async def flaky_async_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"

        result = await flaky_async_func()
        assert result == "success"
        assert call_count == 2

    def test_decorator_sync_function(self):
        """Test decorator with sync function"""
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01, jitter=False)
        def flaky_sync_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"

        result = flaky_sync_func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_async_all_fail(self):
        """Test decorator when all retries fail"""

        @with_retry(max_retries=1, base_delay=0.01)
        async def always_fails():
            raise ValueError("Error")

        with pytest.raises(RetryError):
            await always_fails()

    def test_decorator_sync_all_fail(self):
        """Test decorator when all retries fail"""

        @with_retry(max_retries=1, base_delay=0.01)
        def always_fails():
            raise ValueError("Error")

        with pytest.raises(RetryError):
            always_fails()

    @pytest.mark.asyncio
    async def test_decorator_with_args(self):
        """Test decorator with function arguments"""

        @with_retry(max_retries=2, base_delay=0.01)
        async def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = await func_with_args(1, 2, c=3)
        assert result == "1-2-3"

    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves function name"""

        @with_retry()
        async def my_function():
            pass

        assert my_function.__name__ == "my_function"

    @pytest.mark.asyncio
    async def test_decorator_with_specific_exceptions(self):
        """Test decorator with specific retry exceptions"""
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01, retry_on=(ValueError,))
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Should retry")
            elif call_count == 2:
                raise RuntimeError("Should not retry")
            return "success"

        with pytest.raises(RuntimeError):
            await func()

        assert call_count == 2


class TestDefaultRetryHandler:
    """Test default retry handler instance"""

    def test_default_handler_exists(self):
        """Test that default handler instance exists"""
        assert isinstance(default_retry_handler, RetryHandler)
        assert default_retry_handler.max_retries == 3

    def test_default_handler_can_execute(self):
        """Test that default handler can execute functions"""

        def successful_func():
            return "success"

        result = default_retry_handler.execute_sync(successful_func)
        assert result == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
