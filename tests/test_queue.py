"""Tests for the command queue."""

import threading

import pytest

from twinkly_mcp.queue import Command, CommandQueue


class TestCommandQueue:
    """Tests for CommandQueue."""

    def test_add_command(self):
        """Test adding a command to the queue."""
        queue = CommandQueue()
        cmd = queue.add("twinklysay", {"text": "Hello"})

        assert cmd.id == "cmd_000001"
        assert cmd.type == "twinklysay"
        assert cmd.payload == {"text": "Hello"}
        assert len(queue) == 1

    def test_add_multiple_commands(self):
        """Test adding multiple commands."""
        queue = CommandQueue()
        cmd1 = queue.add("twinklysay", {"text": "First"})
        cmd2 = queue.add("run_card", {"card_id": "clock"})
        cmd3 = queue.add("twinklysay", {"text": "Third"})

        assert cmd1.id == "cmd_000001"
        assert cmd2.id == "cmd_000002"
        assert cmd3.id == "cmd_000003"
        assert len(queue) == 3

    def test_get_after_none(self):
        """Test getting all commands when no last_id provided."""
        queue = CommandQueue()
        queue.add("twinklysay", {"text": "First"})
        queue.add("twinklysay", {"text": "Second"})

        commands = queue.get_after(None)
        assert len(commands) == 2

    def test_get_after_empty_string(self):
        """Test getting all commands when empty string provided."""
        queue = CommandQueue()
        queue.add("twinklysay", {"text": "First"})
        queue.add("twinklysay", {"text": "Second"})

        commands = queue.get_after("")
        assert len(commands) == 2

    def test_get_after_specific_id(self):
        """Test getting commands after a specific ID."""
        queue = CommandQueue()
        queue.add("twinklysay", {"text": "First"})
        cmd2 = queue.add("twinklysay", {"text": "Second"})
        queue.add("twinklysay", {"text": "Third"})

        commands = queue.get_after(cmd2.id)
        assert len(commands) == 1
        assert commands[0].payload["text"] == "Third"

    def test_get_after_last_id(self):
        """Test getting commands after the last command (empty result)."""
        queue = CommandQueue()
        queue.add("twinklysay", {"text": "First"})
        cmd2 = queue.add("twinklysay", {"text": "Second"})

        commands = queue.get_after(cmd2.id)
        assert len(commands) == 0

    def test_get_after_unknown_id(self):
        """Test getting commands with unknown ID returns all."""
        queue = CommandQueue()
        queue.add("twinklysay", {"text": "First"})
        queue.add("twinklysay", {"text": "Second"})

        commands = queue.get_after("cmd_unknown")
        assert len(commands) == 2

    def test_clear(self):
        """Test clearing the queue."""
        queue = CommandQueue()
        queue.add("twinklysay", {"text": "First"})
        queue.add("twinklysay", {"text": "Second"})

        queue.clear()
        assert len(queue) == 0

        # Counter should reset
        cmd = queue.add("twinklysay", {"text": "New"})
        assert cmd.id == "cmd_000001"

    def test_max_size_pruning(self):
        """Test that old commands are pruned when max_size is exceeded."""
        queue = CommandQueue(max_size=3)

        queue.add("twinklysay", {"text": "1"})
        queue.add("twinklysay", {"text": "2"})
        queue.add("twinklysay", {"text": "3"})
        queue.add("twinklysay", {"text": "4"})  # This should prune first one

        assert len(queue) == 3
        commands = queue.get_after(None)
        texts = [cmd.payload["text"] for cmd in commands]
        assert texts == ["2", "3", "4"]

    def test_thread_safety(self):
        """Test that the queue is thread-safe."""
        queue = CommandQueue()
        errors = []

        def add_commands(prefix: str, count: int):
            try:
                for i in range(count):
                    queue.add("twinklysay", {"text": f"{prefix}-{i}"})
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_commands, args=("A", 100)),
            threading.Thread(target=add_commands, args=("B", 100)),
            threading.Thread(target=add_commands, args=("C", 100)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(queue) == 300


class TestCommand:
    """Tests for Command model."""

    def test_command_creation(self):
        """Test creating a command."""
        cmd = Command(id="test_001", type="twinklysay", payload={"text": "Hello"})

        assert cmd.id == "test_001"
        assert cmd.type == "twinklysay"
        assert cmd.payload == {"text": "Hello"}
        assert cmd.created_at is not None

    def test_command_type_validation(self):
        """Test that command type is validated."""
        with pytest.raises(ValueError):
            Command(id="test", type="invalid_type", payload={})
