import json
import random
from pathlib import Path

from faker import Faker

from .models import ClientProfile


class ClientPool:
    def __init__(
        self,
        size: int = 5,
        custom_pool_path: str | None = None,
        faker_instance: Faker | None = None,
    ):
        self.fake = faker_instance or Faker()
        self.clients: list[ClientProfile] = []
        if custom_pool_path:
            self._load_from_file(custom_pool_path)
        else:
            self._generate_pool(size)

    def _load_from_file(self, path: str):
        try:
            with Path(path).open("r") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Client pool JSON file not found at path: {path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Client pool JSON file contains invalid JSON: {e}")

        if not isinstance(data, list):
            raise ValueError("Client pool JSON must be a list of objects.")
        for item in data:
            if "name" not in item or "email" not in item:
                raise ValueError(
                    "Each client in the pool must have 'name' and 'email' fields."
                )
            self.clients.append(ClientProfile(name=item["name"], email=item["email"]))

    def _generate_pool(self, size: int):
        for _ in range(size):
            name = self.fake.name()
            # Clean name to form a simple realistic email
            cleaned_name = name.lower().replace(" ", ".").replace("'", "")
            email = f"{cleaned_name}@example.com"
            self.clients.append(ClientProfile(name=name, email=email))

    def get_client(self, index: int) -> ClientProfile:
        """Select a client profile using round-robin index matching."""
        if not self.clients:
            raise ValueError("Client pool is empty.")
        return self.clients[index % len(self.clients)]

    def get_random_client(self) -> ClientProfile:
        if not self.clients:
            raise ValueError("Client pool is empty.")
        return random.choice(self.clients)
