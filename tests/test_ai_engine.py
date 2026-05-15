"""Tests for JARVIS AI engine module"""
import pytest
import hashlib
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestCacheKey:
    def test_deterministic_cache_key(self):
        """Cache key should be deterministic across calls"""
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        key1 = ai._get_cache_key("test message")
        key2 = ai._get_cache_key("test message")
        assert key1 == key2

    def test_different_messages_different_keys(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        key1 = ai._get_cache_key("hello")
        key2 = ai._get_cache_key("world")
        assert key1 != key2

    def test_cache_key_is_sha256(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        key = ai._get_cache_key("test")
        expected = hashlib.sha256("test".encode()).hexdigest()
        assert key == expected


class TestLocationExtraction:
    def test_extract_location_with_in(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        assert ai._extract_location("weather in london") == "london"

    def test_extract_location_with_for(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        assert ai._extract_location("weather for paris") == "paris"

    def test_extract_location_default_auto(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        result = ai._extract_location("what's the weather")
        assert result == "auto"

    def test_extract_location_strips_noise(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        result = ai._extract_location("weather in tokyo today please")
        assert "tokyo" in result
        assert "today" not in result
        assert "please" not in result


class TestDirectQueries:
    def test_time_query(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        result = ai._handle_direct_queries("what time is it")
        assert result is not None
        assert "time" in result.lower() or ":" in result

    def test_non_direct_query_returns_none(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        result = ai._handle_direct_queries("tell me a joke")
        assert result is None


class TestFallbackResponses:
    def test_greeting_response(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        response = ai._fallback_response("hello")
        assert response  # Should return non-empty string
        assert "help" in response.lower() or "assist" in response.lower()

    def test_help_response(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        response = ai._fallback_response("help")
        assert "task" in response.lower()

    def test_thank_you_response(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        response = ai._fallback_response("thanks")
        assert "welcome" in response.lower()

    def test_time_response(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        response = ai._fallback_response("what time is it")
        assert "time" in response.lower() or ":" in response

    def test_unknown_message_response(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        response = ai._fallback_response("xyzzy random gibberish")
        assert response  # Should still return something

    def test_empty_message_categorized(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        category = ai._categorize_message("random stuff")
        assert category == "general"

    def test_task_message_categorized(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        category = ai._categorize_message("add a task for tomorrow")
        assert category == "task_management"

    def test_weather_message_categorized(self):
        from core.ai_engine import JarvisAI

        ai = JarvisAI()
        category = ai._categorize_message("what's the weather")
        assert category == "weather_query"
