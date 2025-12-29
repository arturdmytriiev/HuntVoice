"""Menu service for loading and managing restaurant menu."""

import json
from typing import Dict, List, Optional
from pathlib import Path


class MenuItem:
    """Represents a menu item."""

    def __init__(self, name: str, description: str, price: float, category: str):
        self.name = name
        self.description = description
        self.price = price
        self.category = category

    def to_dict(self) -> Dict:
        """Convert menu item to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "category": self.category
        }


class MenuService:
    """Service for managing restaurant menu."""

    def __init__(self):
        self.menu_items: List[MenuItem] = []
        self.categories: Dict[str, List[MenuItem]] = {}

    def load_menu(self, file_path: str) -> None:
        """
        Load menu from JSON file.

        Args:
            file_path: Path to menu JSON file
        """
        menu_file = Path(file_path)

        if not menu_file.exists():
            raise FileNotFoundError(f"Menu file not found: {file_path}")

        with open(menu_file, 'r') as f:
            menu_data = json.load(f)

        self.menu_items = []
        self.categories = {}

        for item_data in menu_data.get('items', []):
            menu_item = MenuItem(
                name=item_data['name'],
                description=item_data['description'],
                price=item_data['price'],
                category=item_data['category']
            )
            self.menu_items.append(menu_item)

            if menu_item.category not in self.categories:
                self.categories[menu_item.category] = []
            self.categories[menu_item.category].append(menu_item)

    def get_all_items(self) -> List[MenuItem]:
        """Get all menu items."""
        return self.menu_items

    def get_items_by_category(self, category: str) -> List[MenuItem]:
        """Get menu items by category."""
        return self.categories.get(category, [])

    def get_categories(self) -> List[str]:
        """Get all menu categories."""
        return list(self.categories.keys())

    def search_items(self, query: str) -> List[MenuItem]:
        """
        Search menu items by name or description.

        Args:
            query: Search query string

        Returns:
            List of matching menu items
        """
        query_lower = query.lower()
        return [
            item for item in self.menu_items
            if query_lower in item.name.lower() or query_lower in item.description.lower()
        ]

    def get_item_by_name(self, name: str) -> Optional[MenuItem]:
        """
        Get menu item by exact name match.

        Args:
            name: Item name

        Returns:
            MenuItem if found, None otherwise
        """
        for item in self.menu_items:
            if item.name.lower() == name.lower():
                return item
        return None


# Global menu service instance
menu_service = MenuService()
