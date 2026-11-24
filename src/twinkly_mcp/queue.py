"""Thread-safe command queue for Twinkly MCP."""

import threading
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Command(BaseModel):
    """A command queued for the Raspberry Pi."""

    id: str
    type: Literal["twinklysay", "run_card"]
    payload: dict
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CommandQueue:
    """Thread-safe in-memory command queue.

    Commands are stored with monotonically increasing IDs for efficient
    polling. Old commands are automatically pruned after max_size is reached.
    """

    def __init__(self, max_size: int = 100):
        self._commands: list[Command] = []
        self._lock = threading.Lock()
        self._max_size = max_size
        self._counter = 0

    def add(self, cmd_type: Literal["twinklysay", "run_card"], payload: dict) -> Command:
        """Add a command to the queue.

        Args:
            cmd_type: "twinklysay" or "run_card"
            payload: Command-specific data

        Returns:
            The created Command
        """
        with self._lock:
            self._counter += 1
            cmd = Command(
                id=f"cmd_{self._counter:06d}",
                type=cmd_type,
                payload=payload,
            )
            self._commands.append(cmd)

            # Prune old commands if over max size
            if len(self._commands) > self._max_size:
                self._commands = self._commands[-self._max_size :]

            return cmd

    def get_after(self, last_id: str | None = None) -> list[Command]:
        """Get all commands after a given ID.

        Args:
            last_id: The last command ID the client has seen.
                     If None or empty, returns all commands.

        Returns:
            List of commands newer than last_id
        """
        with self._lock:
            if not last_id:
                return list(self._commands)

            # Find index of last_id
            for i, cmd in enumerate(self._commands):
                if cmd.id == last_id:
                    return list(self._commands[i + 1 :])

            # If last_id not found, return all (client may have missed some)
            return list(self._commands)

    def clear(self) -> None:
        """Clear all commands (for testing)."""
        with self._lock:
            self._commands.clear()
            self._counter = 0

    def __len__(self) -> int:
        """Return number of commands in queue."""
        with self._lock:
            return len(self._commands)


# Singleton queue instance
command_queue = CommandQueue()


class CardRegistry:
    """Thread-safe registry of available display cards.

    The Raspberry Pi can register its available cards on startup,
    which then become available for the run_card MCP tool.
    """

    # Default cards (fallback if Pi hasn't registered yet)
    DEFAULT_CARDS = [
        "beer",
        "calendar",
        "carlsberg_lab",
        "clock",
        "coffee",
        "confetti",
        "countdown",
        "fire",
        "fireworks",
        "friday",
        "image",
        "lava",
        "leaderboard",
        "matrix",
        "menorah",
        "news",
        "ocean",
        "pacman",
        "pacman_chase",
        "pong",
        "pomodoro",
        "quote",
        "rainbow",
        "santa",
        "snake",
        "snow",
        "space_invaders",
        "starfield",
        "test_pattern",
        "tetris",
        "text",
        "tuborg_julebryg",
        "twinklysay",
        "weather",
    ]

    def __init__(self):
        self._cards: set[str] = set(self.DEFAULT_CARDS)
        self._wall_registered = False
        self._lock = threading.Lock()

    def register(self, cards: list[str]) -> None:
        """Register available cards from the Raspberry Pi.

        This replaces the current card list with the new one.

        Args:
            cards: List of card type IDs
        """
        with self._lock:
            self._cards = set(card.lower().strip() for card in cards)
            self._wall_registered = True

    def add(self, card_id: str) -> None:
        """Add a single card to the registry.

        Args:
            card_id: Card type ID to add
        """
        with self._lock:
            self._cards.add(card_id.lower().strip())

    def remove(self, card_id: str) -> None:
        """Remove a card from the registry.

        Args:
            card_id: Card type ID to remove
        """
        with self._lock:
            self._cards.discard(card_id.lower().strip())

    def is_known(self, card_id: str) -> bool:
        """Check if a card is registered.

        Args:
            card_id: Card type ID to check

        Returns:
            True if the card is registered
        """
        with self._lock:
            return card_id.lower().strip() in self._cards

    def list_cards(self) -> list[str]:
        """Get list of all registered cards.

        Returns:
            Sorted list of card IDs
        """
        with self._lock:
            return sorted(self._cards)

    def list_wall_cards(self) -> list[str]:
        """List cards only after the wall has registered its catalog."""
        with self._lock:
            return sorted(self._cards) if self._wall_registered else []

    def clear(self) -> None:
        """Clear all cards (for testing)."""
        with self._lock:
            self._cards.clear()
            self._wall_registered = False


# Singleton card registry instance
card_registry = CardRegistry()
