"""
Menu Service for loading and searching menu items.
Handles menu data access, filtering, and search operations.
"""
import json
import os
from typing import List, Dict, Optional, Any
from pathlib import Path


class MenuService:
    """Service for managing restaurant menu operations."""

    def __init__(self, menu_file_path: Optional[str] = None):
        """
        Initialize MenuService.

        Args:
            menu_file_path: Path to menu JSON file. Defaults to data/menu.sample.json
        """
        if menu_file_path is None:
            # Default to data/menu.sample.json relative to project root
            project_root = Path(__file__).parent.parent
            menu_file_path = project_root / "data" / "menu.sample.json"

        self.menu_file_path = menu_file_path
        self.menu_data: Dict[str, Any] = {}
        self._load_menu()

    def _load_menu(self) -> None:
        """Load menu from JSON file."""
        try:
            with open(self.menu_file_path, 'r', encoding='utf-8') as f:
                self.menu_data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Menu file not found: {self.menu_file_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in menu file: {e}")

    def reload_menu(self) -> None:
        """Reload menu from file (useful for updates)."""
        self._load_menu()

    def get_all_items(self) -> List[Dict[str, Any]]:
        """
        Get all menu items across all categories.

        Returns:
            List of all menu items
        """
        items = []
        categories = self.menu_data.get('categories', {})

        for category_key, category_data in categories.items():
            category_items = category_data.get('items', [])
            for item in category_items:
                # Add category information to each item
                item_with_category = item.copy()
                item_with_category['category'] = category_key
                item_with_category['category_name'] = category_data.get('name', '')
                items.append(item_with_category)

        return items

    def get_items_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all items in a specific category.

        Args:
            category: Category key (e.g., 'appetizers', 'main_courses')

        Returns:
            List of items in the category
        """
        categories = self.menu_data.get('categories', {})
        category_data = categories.get(category, {})
        items = category_data.get('items', [])

        # Add category information to each item
        result = []
        for item in items:
            item_with_category = item.copy()
            item_with_category['category'] = category
            item_with_category['category_name'] = category_data.get('name', '')
            result.append(item_with_category)

        return result

    def get_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific menu item by its ID.

        Args:
            item_id: Unique item identifier

        Returns:
            Menu item dict or None if not found
        """
        all_items = self.get_all_items()
        for item in all_items:
            if item.get('id') == item_id:
                return item
        return None

    def search_items(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        dietary: Optional[List[str]] = None,
        exclude_allergens: Optional[List[str]] = None,
        available_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search and filter menu items based on various criteria.

        Args:
            query: Search text to match against item name and description
            category: Filter by category key
            max_price: Maximum price filter
            min_price: Minimum price filter
            dietary: Filter by dietary requirements (e.g., ['vegetarian', 'gluten-free'])
            exclude_allergens: Exclude items with specific allergens
            available_only: Only return available items

        Returns:
            List of matching menu items
        """
        # Start with all items or category items
        if category:
            items = self.get_items_by_category(category)
        else:
            items = self.get_all_items()

        results = []

        for item in items:
            # Filter by availability
            if available_only and not item.get('available', False):
                continue

            # Filter by price range
            item_price = item.get('price', 0)
            if min_price is not None and item_price < min_price:
                continue
            if max_price is not None and item_price > max_price:
                continue

            # Filter by dietary requirements
            if dietary:
                item_dietary = set(item.get('dietary', []))
                required_dietary = set(dietary)
                # Item must have all required dietary attributes
                if not required_dietary.issubset(item_dietary):
                    continue

            # Filter by allergens
            if exclude_allergens:
                item_allergens = set(item.get('allergens', []))
                excluded = set(exclude_allergens)
                # Item must not contain any excluded allergens
                if item_allergens.intersection(excluded):
                    continue

            # Text search in name and description
            if query:
                query_lower = query.lower()
                name = item.get('name', '').lower()
                name_en = item.get('name_en', '').lower()
                description = item.get('description', '').lower()
                description_en = item.get('description_en', '').lower()

                # Search in all text fields
                if not any([
                    query_lower in name,
                    query_lower in name_en,
                    query_lower in description,
                    query_lower in description_en
                ]):
                    continue

            results.append(item)

        return results

    def get_categories(self) -> List[Dict[str, str]]:
        """
        Get list of all menu categories.

        Returns:
            List of category info dicts with keys: key, name, name_en
        """
        categories = self.menu_data.get('categories', {})
        result = []

        for category_key, category_data in categories.items():
            result.append({
                'key': category_key,
                'name': category_data.get('name', ''),
                'name_en': category_data.get('name_en', ''),
                'item_count': len(category_data.get('items', []))
            })

        return result

    def get_item_price(self, item_id: str) -> Optional[float]:
        """
        Get the price of a specific item.

        Args:
            item_id: Item identifier

        Returns:
            Price or None if item not found
        """
        item = self.get_item_by_id(item_id)
        return item.get('price') if item else None

    def is_item_available(self, item_id: str) -> bool:
        """
        Check if an item is currently available.

        Args:
            item_id: Item identifier

        Returns:
            True if available, False otherwise
        """
        item = self.get_item_by_id(item_id)
        return item.get('available', False) if item else False

    def get_items_by_dietary_preference(self, dietary: str) -> List[Dict[str, Any]]:
        """
        Get all items matching a dietary preference.

        Args:
            dietary: Dietary preference (e.g., 'vegetarian', 'vegan', 'gluten-free')

        Returns:
            List of matching items
        """
        return self.search_items(dietary=[dietary])

    def get_items_without_allergen(self, allergen: str) -> List[Dict[str, Any]]:
        """
        Get all items that don't contain a specific allergen.

        Args:
            allergen: Allergen to exclude (e.g., 'gluten', 'dairy', 'nuts')

        Returns:
            List of items without the allergen
        """
        return self.search_items(exclude_allergens=[allergen])

    def get_menu_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the menu.

        Returns:
            Dict with menu statistics
        """
        all_items = self.get_all_items()
        categories = self.get_categories()

        prices = [item.get('price', 0) for item in all_items]

        return {
            'total_items': len(all_items),
            'total_categories': len(categories),
            'categories': categories,
            'price_range': {
                'min': min(prices) if prices else 0,
                'max': max(prices) if prices else 0,
                'average': sum(prices) / len(prices) if prices else 0
            },
            'available_items': len([i for i in all_items if i.get('available', False)])
        }


# Singleton instance for easy access
_menu_service_instance: Optional[MenuService] = None


def get_menu_service(menu_file_path: Optional[str] = None) -> MenuService:
    """
    Get or create MenuService singleton instance.

    Args:
        menu_file_path: Optional path to menu file

    Returns:
        MenuService instance
    """
    global _menu_service_instance

    if _menu_service_instance is None:
        _menu_service_instance = MenuService(menu_file_path)

    return _menu_service_instance
