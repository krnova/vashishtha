"""
tools/memory_tool.py — Agent Memory Tool
Gives the agent explicit read/write access to long-term memory.
Agent calls these tools to remember, recall, search, and forget information.
"""

import json

# Memory instance injected at runtime via init()
_memory = None

def init(memory_instance):
    """Called from tools/__init__.py to inject the memory instance."""
    global _memory
    _memory = memory_instance


def remember(key: str, value: str | list | dict | int | float | bool, category: str = "fact", importance: int = 1) -> str:
    """
    Store something in long-term memory.

    Args:
        key:        Unique identifier. Use snake_case. e.g. "user_name", "pref_language"
        value:      What to remember. Infer the correct type:
                    - int/float for numbers
                    - bool for true/false
                    - list for multiple values: ["Navo", "Nova"]
                    - dict for structured data: {"day": 22, "month": 12}
                    - str only for plain text
        category:   user | fact | preference | project | context
        importance: 1 = normal, 2 = important, 3 = critical
    """
    if _memory is None:
        return "Error: memory not initialized"

    # Auto-parse stringified JSON — if value is a string that looks like JSON
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")) or stripped in ("true", "false", "null"):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                pass

    return _memory.remember(key, value, category=category, source="agent", importance=importance)


def recall(key: str) -> str:
    """
    Retrieve a specific memory entry by key.

    Args:
        key: The exact key used when remembering.

    Returns:
        The stored value, or a not-found message.
    """
    if _memory is None:
        return "Error: memory not initialized"
    value = _memory.recall(key)
    if value is None:
        return f"Nothing found for key: {key}"
    return str(value)


def search_memory(query: str) -> str:
    """
    Search long-term memory for entries matching a query.
    Searches both keys and values.

    Args:
        query: Search term.

    Returns:
        Formatted list of matching entries.
    """
    if _memory is None:
        return "Error: memory not initialized"

    results = _memory.search(query)
    if not results:
        return f"No memory entries found for: {query}"

    lines = [f"Memory search results for '{query}':"]
    for r in results:
        imp = "★" * r["importance"]
        lines.append(f"  [{r['category']}] {r['key']}: {r['value']}  {imp}")

    return "\n".join(lines)


def list_memory(category: str = "") -> str:
    """
    List long-term memory entries, optionally filtered by category.

    Args:
        category: Filter by category (user/fact/preference/project/context).
                  Leave empty to list all.

    Returns:
        Formatted list of entries.
    """
    if _memory is None:
        return "Error: memory not initialized"

    if category:
        entries = _memory.list_by_category(category)
        label = f"Memory entries [{category}]:"
    else:
        all_entries = _memory.get_all()
        entries = [
            {"key": k, "value": v["value"], "importance": v["importance"]}
            for k, v in all_entries.items()
        ]
        label = "All memory entries:"

    if not entries:
        return f"No entries found{' for category: ' + category if category else ''}."

    lines = [label]
    for e in sorted(entries, key=lambda x: -x["importance"]):
        imp = "★" * e["importance"]
        val = e["value"]
        if isinstance(val, dict):
            val = json.dumps(val, ensure_ascii=False)
        elif isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        else:
            val = str(val)
        lines.append(f"  {e['key']}: {val}  {imp}")

    return "\n".join(lines)


def forget(key: str) -> str:
    """
    Remove an entry from long-term memory.

    Args:
        key: The exact key to remove.

    Returns:
        Confirmation or not-found message.
    """
    if _memory is None:
        return "Error: memory not initialized"
    return _memory.forget(key)
