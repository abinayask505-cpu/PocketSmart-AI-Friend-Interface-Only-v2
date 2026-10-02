from app.models.schemas import (
    HomePlannerInput,
    PartyPlannerInput,
    JewelryPlannerInput,
)
from app.services.gemini_service import generate_json


# ============================================================
# PLATFORM LINKS
# ============================================================

def _platform_links(query: str, platforms: list[str]):
    """
    Generate simulated/search links for the platforms required
    by the PocketSmart AI PDF specification.

    No live availability or exact current price is claimed.
    """
    from urllib.parse import quote_plus

    q = quote_plus(query)

    platform_urls = {
        "Amazon": f"https://www.amazon.in/s?k={q}",
        "IKEA": f"https://www.ikea.com/in/en/search/?q={q}",
        "Flipkart": f"https://www.flipkart.com/search?q={q}",
        "Swiggy": f"https://www.swiggy.com/search?query={q}",
        "Zomato": f"https://www.zomato.com/search?q={q}",
        "OYO": f"https://www.oyorooms.com/search?location={q}",
    }

    links = []

    for platform in platforms:
        if platform in platform_urls:
            links.append(
                {
                    "platform": platform,
                    "url": platform_urls[platform],
                }
            )

    return links


# ============================================================
# GENERAL HELPERS
# ============================================================

def _safe_float(value, default=0):
    """
    Convert Gemini numeric output into a safe float.

    Handles:
        25000
        "25000"
        "₹25,000"
        "25,000"
        "INR 25000"
    """

    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = (
            value.replace("₹", "")
            .replace(",", "")
            .replace("INR", "")
            .strip()
        )

        try:
            return float(cleaned)
        except ValueError:
            return default

    return default


def _clean_text(value, default=""):
    if value is None:
        return default

    return str(value).strip()


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize_allocation(allocation, total_budget):
    """
    Normalize Gemini allocation output.
    """

    if not isinstance(allocation, list):
        return [
            {
                "category": "Budget",
                "amount": float(total_budget),
            }
        ]

    normalized = []

    for item in allocation:

        if isinstance(item, dict):

            category = (
                item.get("category")
                or item.get("name")
                or item.get("type")
                or "Other"
            )

            amount = (
                item.get("amount")
                if item.get("amount") is not None
                else item.get("budget")
            )

            if amount is None:
                amount = item.get("allocated_amount", 0)

            normalized.append(
                {
                    "category": str(category),
                    "amount": _safe_float(amount),
                }
            )

        elif isinstance(item, str):

            normalized.append(
                {
                    "category": item,
                    "amount": 0,
                }
            )

        elif isinstance(item, (int, float)):

            normalized.append(
                {
                    "category": "Allocation",
                    "amount": _safe_float(item),
                }
            )

    if not normalized:
        normalized.append(
            {
                "category": "Budget",
                "amount": float(total_budget),
            }
        )

    return normalized


def _normalize_platforms(platforms):
    """
    Normalize platform information returned by Gemini.
    """

    if not isinstance(platforms, list):
        return []

    normalized = []

    for platform in platforms:

        if isinstance(platform, dict):

            name = (
                platform.get("platform")
                or platform.get("name")
                or "View"
            )

            url = platform.get("url") or "#"

            normalized.append(
                {
                    "platform": str(name),
                    "url": str(url),
                }
            )

        elif isinstance(platform, str):

            normalized.append(
                {
                    "platform": platform,
                    "url": "#",
                }
            )

    return normalized


def _normalize_recommendations(recommendations):
    """
    Normalize Gemini recommendation output.

    Also removes duplicate recommendation names.
    """

    if not isinstance(recommendations, list):
        return []

    normalized = []
    seen_names = set()

    for item in recommendations:

        if isinstance(item, dict):

            name = (
                item.get("name")
                or item.get("item")
                or item.get("product")
                or item.get("category")
                or "Recommended Item"
            )

            name = str(name).strip()

            # Prevent duplicate recommendations.
            name_key = name.lower()

            if name_key in seen_names:
                continue

            seen_names.add(name_key)

            price = (
                item.get("estimated_price")
                if item.get("estimated_price") is not None
                else item.get("price")
            )

            if price is None:
                price = item.get("estimated_cost", 0)

            reason = (
                item.get("reason")
                or item.get("description")
                or item.get("why")
                or "Recommended based on your requirements and budget."
            )

            platforms = _normalize_platforms(
                item.get("platforms", [])
            )

            normalized.append(
                {
                    "name": name,
                    "estimated_price": _safe_float(price),
                    "reason": str(reason),
                    "platforms": platforms,
                }
            )

        elif isinstance(item, str):

            name = item.strip()

            if not name:
                continue

            name_key = name.lower()

            if name_key in seen_names:
                continue

            seen_names.add(name_key)

            normalized.append(
                {
                    "name": name,
                    "estimated_price": 0,
                    "reason": (
                        "Recommended based on your exact "
                        "requirements and budget."
                    ),
                    "platforms": [],
                }
            )

    return normalized


def _normalize_result(result, budget):
    """
    Normalize the complete Gemini response.
    """

    if not isinstance(result, dict):
        return None

    normalized = {
        "summary": str(
            result.get(
                "summary",
                "Here is your personalized PocketSmart AI plan.",
            )
        ),
        "budget": _safe_float(
            result.get("budget", budget),
            budget,
        ),
        "allocation": _normalize_allocation(
            result.get("allocation", []),
            budget,
        ),
        "recommendations": _normalize_recommendations(
            result.get("recommendations", [])
        ),
        "note": str(
            result.get(
                "note",
                "Prices are estimates and may change.",
            )
        ),
    }

    return normalized


# ============================================================
# FALLBACK — HOME
# ============================================================

def _fallback_home(data):
    """
    Fallback recommendation when Gemini is unavailable.

    IMPORTANT:
    The recommendation is generated directly from:
        - room type
        - quantity
        - style
        - needs
        - budget

    This prevents the fallback from returning the same generic
    recommendation for every Home Planner request.
    """

    room = _clean_text(data.room_type, "Room")
    style = _clean_text(data.style, "Modern")
    needs = _clean_text(data.needs, "essential items")

    quantity = max(data.quantity, 1)

    per_item_budget = round(
        data.budget / quantity,
        2,
    )

    query = (
        f"{room} {style} {needs}"
    ).strip()

    # Convert user's needs into separate recommendation
    # concepts instead of returning one generic item.
    need_parts = [
        part.strip()
        for part in needs.replace(",", " ").split()
        if part.strip()
    ]

    recommendations = []

    # Primary exact requirement.
    recommendations.append(
        {
            "name": f"{style} {room} setup for {needs}",
            "estimated_price": round(data.budget * 0.45, 2),
            "reason": (
                f"Designed specifically for your {room} requirement "
                f"with a {style} style and the requested need of "
                f"{needs}."
            ),
            "platforms": _platform_links(
                query,
                ["Amazon", "IKEA"],
            ),
        }
    )

    # Quantity-based recommendation.
    recommendations.append(
        {
            "name": (
                f"{quantity} {style} {room} "
                f"essential item"
                f"{'s' if quantity > 1 else ''}"
            ),
            "estimated_price": round(data.budget * 0.30, 2),
            "reason": (
                f"Matches your requested quantity of {quantity} "
                f"and keeps the estimated cost within the "
                f"available budget."
            ),
            "platforms": _platform_links(
                f"{room} {style} quantity {quantity}",
                ["Amazon", "IKEA"],
            ),
        }
    )

    # Need-focused recommendation.
    recommendations.append(
        {
            "name": f"{needs} for {room}",
            "estimated_price": round(data.budget * 0.25, 2),
            "reason": (
                f"Focused specifically on the requirement you "
                f"entered: {needs}."
            ),
            "platforms": _platform_links(
                f"{room} {needs} {style}",
                ["Amazon", "IKEA"],
            ),
        }
    )

    return {
        "summary": (
            f"{style} {room} plan for {quantity} "
            f"item{'s' if quantity > 1 else ''}, "
            f"focused on {needs}, within "
            f"₹{data.budget:,.0f}."
        ),
        "budget": data.budget,
        "allocation": [
            {
                "category": f"{style} {room} requirements",
                "amount": round(data.budget * 0.45, 2),
            },
            {
                "category": "Quantity-based essentials",
                "amount": round(data.budget * 0.30, 2),
            },
            {
                "category": needs,
                "amount": round(data.budget * 0.25, 2),
            },
        ],
        "recommendations": recommendations,
        "note": (
            "Prices are estimates. "
            "Gemini was unavailable, so these recommendations "
            "were generated directly from your entered room, "
            "quantity, style and needs."
        ),
    }


# ============================================================
# FALLBACK — PARTY
# ============================================================

def _fallback_party(data):
    """
    Fallback recommendation when Gemini is unavailable.

    Recommendations are generated from:
        - event type
        - guest count
        - venue
        - preferences
        - budget
    """

    event = _clean_text(data.event_type, "Event")
    venue = _clean_text(data.venue, "your selected venue")
    preferences = _clean_text(
        data.preferences,
        "general event requirements",
    )

    guests = max(data.guest_count, 1)

    allocations = [
        (
            "Food & Catering",
            round(data.budget * 0.50, 2),
        ),
        (
            "Decoration",
            round(data.budget * 0.20, 2),
        ),
        (
            "Venue",
            round(data.budget * 0.20, 2),
        ),
        (
            "Entertainment",
            round(data.budget * 0.10, 2),
        ),
    ]

    recommendations = [
        {
            "name": f"{event} catering for {guests} guests",
            "estimated_price": allocations[0][1],
            "reason": (
                f"Planned specifically for your {event} with "
                f"{guests} guests and your preference: "
                f"{preferences}."
            ),
            "platforms": _platform_links(
                f"{event} catering {guests} guests {preferences}",
                ["Swiggy", "Zomato"],
            ),
        },
        {
            "name": f"{event} decoration for {venue}",
            "estimated_price": allocations[1][1],
            "reason": (
                f"Decoration recommendation based on your "
                f"{event} and venue details: {venue}."
            ),
            "platforms": _platform_links(
                f"{event} decoration {venue} {preferences}",
                ["Amazon", "Flipkart"],
            ),
        },
        {
            "name": f"{venue} option for {event}",
            "estimated_price": allocations[2][1],
            "reason": (
                f"Venue recommendation is based on the "
                f"venue information you provided: {venue}."
            ),
            "platforms": _platform_links(
                f"{event} venue {venue}",
                ["OYO"],
            ),
        },
        {
            "name": f"{event} entertainment",
            "estimated_price": allocations[3][1],
            "reason": (
                f"Entertainment is included specifically for "
                f"your {event} and guest count of {guests}."
            ),
            "platforms": _platform_links(
                f"{event} entertainment {guests} guests",
                ["Amazon"],
            ),
        },
    ]

    return {
        "summary": (
            f"{event} plan for {guests} guests at "
            f"{venue}, focused on {preferences}, "
            f"within ₹{data.budget:,.0f}."
        ),
        "budget": data.budget,
        "allocation": [
            {
                "category": category,
                "amount": amount,
            }
            for category, amount in allocations
        ],
        "recommendations": recommendations,
        "note": (
            "Prices are estimates. "
            "Gemini was unavailable, so the plan was generated "
            "directly from your event type, guest count, venue "
            "and preferences."
        ),
    }


# ============================================================
# FALLBACK — JEWELRY
# ============================================================

def _fallback_jewelry(data):
    """
    Fallback recommendation when Gemini is unavailable.

    The recommendation changes according to:
        - occasion
        - style
        - outfit notes
        - budget

    This prevents the same jewelry recommendation from being
    returned for every outfit.
    """

    occasion = _clean_text(
        data.occasion,
        "special occasion",
    )

    style = _clean_text(
        data.style,
        "classic",
    )

    outfit = _clean_text(
        data.outfit_notes,
        "",
    )

    outfit_lower = outfit.lower()

    # --------------------------------------------------------
    # Detect outfit context
    # --------------------------------------------------------

    if any(
        word in outfit_lower
        for word in [
            "saree",
            "sari",
            "silk saree",
            "kanjeevaram",
            "pattu",
        ]
    ):
        outfit_type = "saree"
        outfit_jewelry = [
            (
                f"{style} necklace set for saree",
                "Matches the saree-based outfit and the selected style."
            ),
            (
                f"{style} jhumka earrings for saree",
                "Adds an outfit-compatible traditional earring option."
            ),
            (
                f"{style} bangles for saree",
                "Complements the saree styling with a matching accessory."
            ),
        ]

    elif any(
        word in outfit_lower
        for word in [
            "lehenga",
            "lehenga choli",
            "choli",
        ]
    ):
        outfit_type = "lehenga"
        outfit_jewelry = [
            (
                f"{style} choker necklace for lehenga",
                "Designed to complement the neckline and festive lehenga styling."
            ),
            (
                f"{style} statement earrings for lehenga",
                "Provides a stronger accessory focus suitable for lehenga styling."
            ),
            (
                f"{style} maang tikka for lehenga",
                "Adds a traditional festive accessory that coordinates with the outfit."
            ),
        ]

    elif any(
        word in outfit_lower
        for word in [
            "dress",
            "gown",
            "western",
            "party dress",
            "maxi",
        ]
    ):
        outfit_type = "dress"
        outfit_jewelry = [
            (
                f"{style} minimalist necklace for dress",
                "Keeps the jewellery balanced with a modern dress-based outfit."
            ),
            (
                f"{style} stud earrings for dress",
                "Provides a clean and simple accessory option."
            ),
            (
                f"{style} bracelet for dress",
                "Adds a subtle wrist accessory without overpowering the outfit."
            ),
        ]

    elif any(
        word in outfit_lower
        for word in [
            "kurti",
            "salwar",
            "salwar suit",
            "anarkali",
        ]
    ):
        outfit_type = "ethnic outfit"
        outfit_jewelry = [
            (
                f"{style} pendant necklace for ethnic outfit",
                "Coordinates naturally with the ethnic outfit style."
            ),
            (
                f"{style} earrings for ethnic outfit",
                "Provides an outfit-compatible earring choice."
            ),
            (
                f"{style} bangles for ethnic outfit",
                "Adds a coordinated traditional accessory."
            ),
        ]

    else:
        outfit_type = "your outfit"
        outfit_jewelry = [
            (
                f"{style} necklace for {occasion}",
                "Selected from your occasion and preferred jewelry style."
            ),
            (
                f"{style} earrings for {occasion}",
                "Provides a different jewelry category while matching the occasion."
            ),
            (
                f"{style} bracelet for {occasion}",
                "Adds another accessory option while maintaining the selected style."
            ),
        ]

    # --------------------------------------------------------
    # Detect color context
    # --------------------------------------------------------

    detected_colors = []

    color_words = [
        "red",
        "blue",
        "green",
        "black",
        "white",
        "pink",
        "yellow",
        "gold",
        "silver",
        "maroon",
        "purple",
        "violet",
        "orange",
        "cream",
        "beige",
        "navy",
    ]

    for color in color_words:
        if color in outfit_lower:
            detected_colors.append(color)

    color_context = ""

    if detected_colors:
        color_context = (
            " Outfit color context detected: "
            + ", ".join(detected_colors)
            + "."
        )

    # --------------------------------------------------------
    # Budget distribution
    # --------------------------------------------------------

    necklace_budget = round(data.budget * 0.45, 2)
    earrings_budget = round(data.budget * 0.30, 2)
    accessory_budget = round(data.budget * 0.25, 2)

    budgets = [
        necklace_budget,
        earrings_budget,
        accessory_budget,
    ]

    recommendations = []

    for index, (name, reason) in enumerate(outfit_jewelry):

        recommendations.append(
            {
                "name": name,
                "estimated_price": budgets[index],
                "reason": (
                    f"{reason} "
                    f"Occasion: {occasion}. "
                    f"Preferred style: {style}. "
                    f"Outfit context: {outfit or 'not provided'}."
                    f"{color_context}"
                ),
                "platforms": _platform_links(
                    f"{name} {occasion} {style} {outfit}",
                    ["Amazon", "Flipkart"],
                ),
            }
        )

    return {
        "summary": (
            f"{style} jewelry plan for {occasion}, "
            f"matched to {outfit_type}"
            f"{' and its detected colors' if detected_colors else ''}, "
            f"within ₹{data.budget:,.0f}."
        ),
        "budget": data.budget,
        "allocation": [
            {
                "category": f"{style} Necklace",
                "amount": necklace_budget,
            },
            {
                "category": f"{style} Earrings",
                "amount": earrings_budget,
            },
            {
                "category": f"{style} Accessory",
                "amount": accessory_budget,
            },
        ],
        "recommendations": recommendations,
        "note": (
            "Prices are estimates. "
            "Gemini was unavailable, so the recommendations were "
            "generated from your occasion, style and outfit details. "
            "When an outfit image is supplied, Gemini can additionally "
            "analyze its visible colors and visual style."
        ),
    }


# ============================================================
# HOME PLANNER
# ============================================================

async def generate_home_recommendations(
    data: HomePlannerInput,
):

    prompt = f"""
You are PocketSmart AI's Home Interior Budget Planner.

Your most important task is to understand the USER'S EXACT
REQUIREMENT and recommend items specifically for that requirement.

Return ONLY valid JSON.
Do NOT return markdown.
Do NOT return code fences.

The JSON MUST follow EXACTLY this structure:

{{
    "summary": "short personalized summary",
    "budget": {data.budget},
    "allocation": [
        {{
            "category": "specific requirement category",
            "amount": 10000
        }}
    ],
    "recommendations": [
        {{
            "name": "specific recommended item",
            "estimated_price": 5000,
            "reason": "specific reason based on the user's input",
            "platforms": [
                {{
                    "platform": "Amazon",
                    "url": "https://www.amazon.in/"
                }},
                {{
                    "platform": "IKEA",
                    "url": "https://www.ikea.com/in/en/"
                }}
            ]
        }}
    ],
    "note": "important note"
}}

STRICT PERSONALIZATION RULES:

1. Room type MUST directly affect the recommendations.
2. Quantity MUST directly affect the recommendations.
3. Style MUST directly affect the recommendations.
4. Needs MUST directly affect the recommendations.
5. Do NOT give generic home recommendations.
6. Do NOT recommend unrelated rooms or products.
7. Create 3 to 5 DIFFERENT recommendations.
8. Do NOT repeat the same product/category.
9. Each recommendation must address a different part of the user's
   stated requirement.
10. The recommendation names must clearly reflect the user's
    requested room/style/needs.
11. Keep the total allocation within the user's budget.
12. estimated_price MUST be a number.
13. allocation amounts MUST be numbers.
14. Do not claim live availability.
15. Do not claim exact current prices.
16. Use only:
    - Amazon
    - IKEA
17. Platforms must contain platform and url.
18. Return valid JSON only.

USER DETAILS:

Budget: INR {data.budget}
Room Type: {data.room_type}
Quantity: {data.quantity}
Style: {data.style}
Needs: {data.needs}

IMPORTANT:
The answer must be about the exact requirement above.
Do not replace the user's requirement with generic suggestions.
"""

    result = await generate_json(prompt)

    normalized = _normalize_result(
        result,
        data.budget,
    )

    if normalized and normalized["recommendations"]:
        return normalized

    return _fallback_home(data)


# ============================================================
# PARTY PLANNER
# ============================================================

async def generate_party_recommendations(
    data: PartyPlannerInput,
):

    prompt = f"""
You are PocketSmart AI's Party Budget Planner.

Your most important task is to understand the USER'S EXACT
EVENT REQUIREMENT and create a personalized plan.

Return ONLY valid JSON.
Do NOT return markdown.
Do NOT return code fences.

The JSON MUST follow EXACTLY this structure:

{{
    "summary": "short personalized party summary",
    "budget": {data.budget},
    "allocation": [
        {{
            "category": "specific event category",
            "amount": 10000
        }}
    ],
    "recommendations": [
        {{
            "name": "specific recommended item or service",
            "estimated_price": 5000,
            "reason": "specific reason based on user's event details",
            "platforms": [
                {{
                    "platform": "Swiggy",
                    "url": "https://www.swiggy.com/"
                }},
                {{
                    "platform": "Zomato",
                    "url": "https://www.zomato.com/"
                }},
                {{
                    "platform": "OYO",
                    "url": "https://www.oyorooms.com/"
                }}
            ]
        }}
    ],
    "note": "important note"
}}

STRICT PERSONALIZATION RULES:

1. Event type MUST directly affect recommendations.
2. Guest count MUST directly affect food/catering planning.
3. Venue MUST directly affect recommendations.
4. Preferences MUST directly affect recommendations.
5. Do NOT give generic party recommendations.
6. Do NOT recommend an unrelated event type.
7. Create 3 to 5 DIFFERENT recommendations.
8. Do NOT repeat the same service/category.
9. Cover different requirements such as food, venue,
   decoration or entertainment only when relevant to the user's
   event details.
10. Recommendation names must clearly reflect the user's
    event details.
11. Keep total allocation within the user's budget.
12. estimated_price MUST be a number.
13. allocation amounts MUST be numbers.
14. Do not claim live availability.
15. Do not claim exact current prices.
16. Use only:
    - Swiggy
    - Zomato
    - OYO
17. Platforms must contain platform and url.
18. Return valid JSON only.

USER DETAILS:

Budget: INR {data.budget}
Guest Count: {data.guest_count}
Event Type: {data.event_type}
Venue: {data.venue}
Preferences: {data.preferences}

IMPORTANT:
The answer must be about the exact event described above.
Do not replace the user's event with generic party suggestions.
"""

    result = await generate_json(prompt)

    normalized = _normalize_result(
        result,
        data.budget,
    )

    if normalized and normalized["recommendations"]:
        return normalized

    return _fallback_party(data)


# ============================================================
# JEWELRY PLANNER
# ============================================================

async def generate_jewelry_recommendations(
    data: JewelryPlannerInput,
):

    prompt = f"""
You are PocketSmart AI's Jewelry Recommendation Assistant.

Your most important task is to understand the USER'S EXACT
JEWELRY REQUIREMENT and match recommendations to the outfit
information.

Return ONLY valid JSON.
Do NOT return markdown.
Do NOT return code fences.

The JSON MUST follow EXACTLY this structure:

{{
    "summary": "short personalized jewelry summary",
    "budget": {data.budget},
    "allocation": [
        {{
            "category": "specific jewelry category",
            "amount": 10000
        }}
    ],
    "recommendations": [
        {{
            "name": "specific jewelry item",
            "estimated_price": 5000,
            "reason": "specific reason based on occasion, style and outfit",
            "platforms": [
                {{
                    "platform": "Amazon",
                    "url": "https://www.amazon.in/"
                }},
                {{
                    "platform": "Flipkart",
                    "url": "https://www.flipkart.com/"
                }}
            ]
        }}
    ],
    "note": "important note"
}}

STRICT PERSONALIZATION RULES:

1. Occasion MUST directly affect the recommendations.
2. Jewelry style MUST directly affect the recommendations.
3. Outfit notes MUST directly affect the recommendations.
4. If outfit notes contain an outfit type, use that outfit type.
5. If outfit notes contain colors, use those colors when deciding
   suitable jewelry coordination.
6. If an outfit image is supplied, analyze only visible colors,
   patterns and visual style.
7. Do NOT identify the person in the image.
8. Do NOT give the same generic jewelry recommendation for
   different outfit requirements.
9. Create 3 to 5 DIFFERENT jewelry recommendations.
10. Recommendations must belong to different jewelry categories
    where appropriate, such as necklace, earrings, bracelet,
    bangles, choker or other suitable jewelry.
11. Do NOT repeat the same jewelry item.
12. The recommendation names must reflect the user's occasion,
    style or outfit context.
13. Keep total allocation within the user's budget.
14. estimated_price MUST be a number.
15. allocation amounts MUST be numbers.
16. Do not claim live inventory.
17. Do not claim exact current prices.
18. Use only:
    - Amazon
    - Flipkart
19. Platforms must contain platform and url.
20. Return valid JSON only.

USER DETAILS:

Budget: INR {data.budget}
Occasion: {data.occasion}
Preferred Jewelry Style: {data.style}
Outfit Notes: {data.outfit_notes}

IMPORTANT:
The answer must be specifically based on the outfit notes,
occasion and selected jewelry style.

For example, if the outfit notes describe a saree, the
recommendations should coordinate with saree styling.

If the outfit notes describe a western dress, the
recommendations should coordinate with western styling.

If the outfit notes describe a lehenga, the recommendations
should coordinate with lehenga styling.

Do NOT return the same jewelry recommendation regardless
of the outfit notes.
"""

    result = await generate_json(
        prompt,
        data.image_path,
    )

    normalized = _normalize_result(
        result,
        data.budget,
    )

    if normalized and normalized["recommendations"]:
        return normalized

    return _fallback_jewelry(data)