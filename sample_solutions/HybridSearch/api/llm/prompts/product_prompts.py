"""
Product Response Prompts
Prompt templates for different product search response types
"""

from typing import List, Dict, Any


class ProductPrompts:
    """Product-specific prompt templates"""
    
    @staticmethod
    def semantic_browse_prompt(query: str, products: List[Dict]) -> str:
        """
        Generate prompt for semantic browse (recommendation style)
        
        Args:
            query: User query
            products: List of product dictionaries
            
        Returns:
            Formatted prompt string
        """
        products_json = "\n".join([
            f"- {p.get('name', 'Unknown')} (${p.get('price', 'N/A')}) - {p.get('description', '')[:100]}... "
            f"Rating: {p.get('rating', 'N/A')} stars"
            for p in products[:10]
        ])
        
        return f"""You are a helpful shopping assistant. Given the user's query and search results, 
provide a friendly recommendation. Explain WHY each product matches their needs.
Keep it concise - 2-3 sentences per product, focus on relevance to their query.

User Query: {query}
Top Results:
{products_json}

Format: Brief intro, then for each recommended product:
- Product name and price
- Why it matches their query
- Key highlight (rating, feature, value)

Be conversational and helpful. Do not include any internal thought process or monologue. Provide ONLY the final recommendation."""
    
    @staticmethod
    def filtered_search_prompt(query: str, filters: Dict, products: List[Dict]) -> str:
        """
        Generate prompt for filtered search (factual listing)
        
        Args:
            query: User query
            filters: Applied filters
            products: List of product dictionaries
            
        Returns:
            Formatted prompt string
        """
        filter_summary = []
        if filters.get('price_max'):
            filter_summary.append(f"under ${filters['price_max']}")
        if filters.get('price_min'):
            filter_summary.append(f"over ${filters['price_min']}")
        if filters.get('rating_min'):
            filter_summary.append(f"{filters['rating_min']}+ stars")
        if filters.get('categories'):
            filter_summary.append(f"in {', '.join(filters['categories'])}")
        
        filter_text = " and ".join(filter_summary) if filter_summary else "all products"
        
        products_json = "\n".join([
            f"- {p.get('name', 'Unknown')} - ${p.get('price', 'N/A')} - "
            f"Rating: {p.get('rating', 'N/A')} stars ({p.get('review_count', 0)} reviews)"
            for p in products[:10]
        ])
        
        return f"""Present these filtered search results clearly. Confirm the filters applied,
then list products with key details. Be factual and concise.

Query: {query}
Filters Applied: {filter_text}
Results:
{products_json}

Format: "Found X products {filter_text}. Here are the top matches:" 
Then list with name, price, rating, and one key feature each. Do not include any internal thought process."""
    
    @staticmethod
    def comparison_prompt(products: List[Dict], priorities: List[str] = None) -> str:
        """
        Generate prompt for product comparison
        
        Args:
            products: List of product dictionaries to compare
            priorities: User's priorities (e.g., ["price", "rating"])
            
        Returns:
            Formatted prompt string
        """
        products_json = "\n".join([
            f"Product {i+1}: {p.get('name', 'Unknown')}\n"
            f"  Price: ${p.get('price', 'N/A')}\n"
            f"  Rating: {p.get('rating', 'N/A')} stars ({p.get('review_count', 0)} reviews)\n"
            f"  Description: {p.get('description', '')[:150]}...\n"
            f"  Category: {p.get('category', 'N/A')}"
            for i, p in enumerate(products[:5])
        ])
        
        priorities_text = f"\nUser's Priorities: {', '.join(priorities)}" if priorities else ""
        
        return f"""Compare these products objectively. Create a brief comparison highlighting
key differences in price, features, and ratings. Help the user decide.

Products to Compare:
{products_json}{priorities_text}

Format: Structured comparison, then a recommendation based on different use cases.
Be objective and helpful. Do not include any internal thought process."""
    
    @staticmethod
    def quick_results_template(query: str, filters: Dict, products: List[Dict]) -> str:
        """
        Generate quick template-based response (no LLM)
        
        Args:
            query: User query
            filters: Applied filters
            products: List of product dictionaries
            
        Returns:
            Template-based response string
        """
        filter_text = ""
        if filters.get('price_max'):
            filter_text += f" under ${filters['price_max']}"
        if filters.get('rating_min'):
            filter_text += f" with {filters['rating_min']}+ stars"
        
        response = f"Here are {len(products)} products matching '{query}'{filter_text}:\n\n"
        
        for i, product in enumerate(products[:10], 1):
            response += f"{i}. {product.get('name', 'Unknown')}\n"
            if product.get('price'):
                response += f"   Price: ${product['price']:.2f}\n"
            if product.get('rating'):
                response += f"   Rating: {product['rating']:.1f} stars ({product.get('review_count', 0)} reviews)\n"
            response += "\n"
        
        return response

