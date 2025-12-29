"""
Recommender Service for filtering and recommending menu items based on user preferences.
Implements logic to suggest dishes based on dietary restrictions, preferences, and context.
"""
from typing import List, Dict, Optional, Any, Set
from collections import Counter
import logging

from services.menu_service import MenuService, get_menu_service


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RecommenderService:
    """Service for recommending menu items based on user preferences."""

    def __init__(self, menu_service: Optional[MenuService] = None):
        """
        Initialize RecommenderService.

        Args:
            menu_service: MenuService instance (uses singleton if not provided)
        """
        self.menu_service = menu_service or get_menu_service()

    def recommend_by_preferences(
        self,
        dietary_restrictions: Optional[List[str]] = None,
        exclude_allergens: Optional[List[str]] = None,
        max_price: Optional[float] = None,
        preferred_categories: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recommend menu items based on user preferences.

        Args:
            dietary_restrictions: List of dietary requirements (e.g., ['vegetarian', 'gluten-free'])
            exclude_allergens: List of allergens to avoid (e.g., ['dairy', 'nuts'])
            max_price: Maximum price constraint
            preferred_categories: Preferred categories (e.g., ['main_courses', 'desserts'])
            limit: Maximum number of recommendations

        Returns:
            List of recommended menu items with scores
        """
        # Start with all available items
        all_items = self.menu_service.get_all_items()
        available_items = [item for item in all_items if item.get('available', False)]

        scored_items = []

        for item in available_items:
            score = 0
            match_reasons = []

            # Filter by dietary restrictions (must match all)
            if dietary_restrictions:
                item_dietary = set(item.get('dietary', []))
                required = set(dietary_restrictions)

                if not required.issubset(item_dietary):
                    continue  # Skip items that don't meet dietary requirements

                score += 20
                match_reasons.append(f"соответствует диете: {', '.join(dietary_restrictions)}")

            # Filter by allergens (must not contain any)
            if exclude_allergens:
                item_allergens = set(item.get('allergens', []))
                excluded = set(exclude_allergens)

                if item_allergens.intersection(excluded):
                    continue  # Skip items with excluded allergens

                score += 15
                match_reasons.append("без аллергенов")

            # Filter by price
            if max_price:
                item_price = item.get('price', 0)
                if item_price > max_price:
                    continue  # Skip items over budget

                # Give bonus for better value
                price_ratio = item_price / max_price
                if price_ratio <= 0.7:
                    score += 10
                    match_reasons.append("хорошая цена")

            # Boost score for preferred categories
            if preferred_categories:
                item_category = item.get('category', '')
                if item_category in preferred_categories:
                    score += 25
                    match_reasons.append(f"из предпочитаемой категории")

            # Add variety bonus for different categories
            score += self._calculate_variety_bonus(item)

            # Boost popular items (items with shorter preparation time might be more popular)
            prep_time = item.get('preparation_time_minutes', 30)
            if prep_time <= 15:
                score += 5
                match_reasons.append("быстрое приготовление")

            scored_items.append({
                'item': item,
                'score': score,
                'match_reasons': match_reasons
            })

        # Sort by score (descending) and return top items
        scored_items.sort(key=lambda x: x['score'], reverse=True)

        results = []
        for scored_item in scored_items[:limit]:
            result = scored_item['item'].copy()
            result['recommendation_score'] = scored_item['score']
            result['match_reasons'] = scored_item['match_reasons']
            results.append(result)

        logger.info(f"Generated {len(results)} recommendations")
        return results

    def _calculate_variety_bonus(self, item: Dict[str, Any]) -> int:
        """
        Calculate variety bonus for item.

        Args:
            item: Menu item

        Returns:
            Bonus score for variety
        """
        # Give small bonus to items from underrepresented categories
        category = item.get('category', '')

        # Desserts and beverages get small bonus for meal completion
        if category in ['desserts', 'beverages']:
            return 3

        return 0

    def recommend_for_group(
        self,
        party_size: int,
        dietary_restrictions: Optional[List[str]] = None,
        exclude_allergens: Optional[List[str]] = None,
        budget_per_person: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Recommend a complete meal for a group.

        Args:
            party_size: Number of people in the group
            dietary_restrictions: Dietary requirements for the group
            exclude_allergens: Allergens to avoid
            budget_per_person: Budget per person

        Returns:
            Dict with recommended appetizers, mains, desserts, and beverages
        """
        recommendations = {
            'appetizers': [],
            'main_courses': [],
            'desserts': [],
            'beverages': [],
            'total_estimated_cost': 0,
            'per_person_cost': 0
        }

        # Calculate individual budget per category if budget provided
        category_budgets = {}
        if budget_per_person:
            category_budgets = {
                'appetizers': budget_per_person * 0.25,
                'main_courses': budget_per_person * 0.50,
                'desserts': budget_per_person * 0.15,
                'beverages': budget_per_person * 0.10
            }

        # Get recommendations for each category
        for category in ['appetizers', 'main_courses', 'desserts', 'beverages']:
            max_price = category_budgets.get(category) if budget_per_person else None

            items = self.recommend_by_preferences(
                dietary_restrictions=dietary_restrictions,
                exclude_allergens=exclude_allergens,
                max_price=max_price,
                preferred_categories=[category],
                limit=3  # Top 3 per category
            )

            recommendations[category] = items

            # Calculate estimated cost (assuming group shares appetizers/desserts)
            if category in ['appetizers', 'desserts']:
                # Assume 1 item per 2 people
                num_items = max(1, party_size // 2)
            elif category == 'beverages':
                # 1 beverage per person
                num_items = party_size
            else:
                # 1 main per person
                num_items = party_size

            if items:
                # Use the top recommended item for cost estimation
                item_price = items[0].get('price', 0)
                recommendations['total_estimated_cost'] += item_price * num_items

        # Calculate per person cost
        if party_size > 0:
            recommendations['per_person_cost'] = recommendations['total_estimated_cost'] / party_size

        logger.info(f"Generated group recommendations for {party_size} people")
        return recommendations

    def recommend_similar_items(
        self,
        item_id: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Recommend items similar to a given item.

        Args:
            item_id: ID of the reference item
            limit: Maximum number of recommendations

        Returns:
            List of similar menu items
        """
        reference_item = self.menu_service.get_item_by_id(item_id)

        if not reference_item:
            logger.warning(f"Item {item_id} not found for similarity recommendations")
            return []

        all_items = self.menu_service.get_all_items()
        available_items = [
            item for item in all_items
            if item.get('available', False) and item.get('id') != item_id
        ]

        scored_items = []

        reference_category = reference_item.get('category', '')
        reference_dietary = set(reference_item.get('dietary', []))
        reference_allergens = set(reference_item.get('allergens', []))
        reference_ingredients = set(reference_item.get('ingredients', []))
        reference_price = reference_item.get('price', 0)

        for item in available_items:
            score = 0

            # Same category: high score
            if item.get('category') == reference_category:
                score += 30

            # Similar dietary attributes
            item_dietary = set(item.get('dietary', []))
            dietary_overlap = len(reference_dietary.intersection(item_dietary))
            score += dietary_overlap * 10

            # Similar allergens (people might have consistent dietary needs)
            item_allergens = set(item.get('allergens', []))
            allergen_overlap = len(reference_allergens.intersection(item_allergens))
            score += allergen_overlap * 5

            # Shared ingredients
            item_ingredients = set(item.get('ingredients', []))
            ingredient_overlap = len(reference_ingredients.intersection(item_ingredients))
            score += ingredient_overlap * 8

            # Similar price range (within 30%)
            item_price = item.get('price', 0)
            price_diff_ratio = abs(item_price - reference_price) / reference_price if reference_price > 0 else 1
            if price_diff_ratio <= 0.3:
                score += 15

            scored_items.append({
                'item': item,
                'score': score
            })

        # Sort by score and return top items
        scored_items.sort(key=lambda x: x['score'], reverse=True)

        results = []
        for scored_item in scored_items[:limit]:
            result = scored_item['item'].copy()
            result['similarity_score'] = scored_item['score']
            results.append(result)

        logger.info(f"Found {len(results)} similar items to {item_id}")
        return results

    def recommend_by_keywords(
        self,
        keywords: List[str],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recommend items based on keyword matching.

        Args:
            keywords: List of keywords to match (in Russian or English)
            limit: Maximum number of recommendations

        Returns:
            List of matching menu items
        """
        all_items = self.menu_service.get_all_items()
        available_items = [item for item in all_items if item.get('available', False)]

        scored_items = []

        for item in available_items:
            score = 0
            matched_keywords = []

            # Searchable text fields
            searchable = [
                item.get('name', '').lower(),
                item.get('name_en', '').lower(),
                item.get('description', '').lower(),
                item.get('description_en', '').lower(),
            ] + [ing.lower() for ing in item.get('ingredients', [])]

            for keyword in keywords:
                keyword_lower = keyword.lower()

                # Check each searchable field
                for text in searchable:
                    if keyword_lower in text:
                        score += 10
                        matched_keywords.append(keyword)
                        break  # Don't double-count same keyword

            if score > 0:
                scored_items.append({
                    'item': item,
                    'score': score,
                    'matched_keywords': matched_keywords
                })

        # Sort by score
        scored_items.sort(key=lambda x: x['score'], reverse=True)

        results = []
        for scored_item in scored_items[:limit]:
            result = scored_item['item'].copy()
            result['keyword_score'] = scored_item['score']
            result['matched_keywords'] = scored_item['matched_keywords']
            results.append(result)

        logger.info(f"Found {len(results)} items matching keywords: {keywords}")
        return results

    def recommend_chef_specials(
        self,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Recommend chef's special items.

        Currently returns high-value items (good ingredients, reasonable price).

        Args:
            limit: Maximum number of recommendations

        Returns:
            List of chef's special recommendations
        """
        all_items = self.menu_service.get_all_items()
        available_items = [item for item in all_items if item.get('available', False)]

        scored_items = []

        for item in available_items:
            score = 0

            # Prefer main courses and appetizers
            category = item.get('category', '')
            if category in ['main_courses', 'appetizers']:
                score += 20

            # Prefer items with more ingredients (more complex/special)
            num_ingredients = len(item.get('ingredients', []))
            score += num_ingredients * 3

            # Prefer items with special ingredients
            special_ingredients = [
                'truffle', 'трюфель', 'salmon', 'лосось',
                'steak', 'стейк', 'porcini', 'белые грибы'
            ]
            ingredients = [ing.lower() for ing in item.get('ingredients', [])]
            for special in special_ingredients:
                if any(special in ing for ing in ingredients):
                    score += 15

            # Moderate preparation time (not too quick, not too slow)
            prep_time = item.get('preparation_time_minutes', 20)
            if 15 <= prep_time <= 30:
                score += 10

            scored_items.append({
                'item': item,
                'score': score
            })

        # Sort by score
        scored_items.sort(key=lambda x: x['score'], reverse=True)

        results = []
        for scored_item in scored_items[:limit]:
            result = scored_item['item'].copy()
            result['special_score'] = scored_item['score']
            result['recommendation_reason'] = "Рекомендация шеф-повара"
            results.append(result)

        logger.info(f"Selected {len(results)} chef's specials")
        return results


# Singleton instance
_recommender_service_instance: Optional[RecommenderService] = None


def get_recommender_service(menu_service: Optional[MenuService] = None) -> RecommenderService:
    """
    Get or create RecommenderService singleton instance.

    Args:
        menu_service: Optional MenuService instance

    Returns:
        RecommenderService instance
    """
    global _recommender_service_instance

    if _recommender_service_instance is None:
        _recommender_service_instance = RecommenderService(menu_service)

    return _recommender_service_instance
