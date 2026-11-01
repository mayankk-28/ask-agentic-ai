"""Tools the agent can call. Every tool returns a small JSON-serialisable dict."""
import ast
import operator
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

# ---------------------------------------------------------------- calculator
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression: str):
    """Safely evaluate an arithmetic expression (no eval(), only + - * / ** % //)."""
    expr = str(expression)[:200]
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/").replace(",", "")
    try:
        result = _eval(ast.parse(expr.strip(), mode="eval"))
    except ZeroDivisionError:
        return {"error": "Cannot divide by zero."}
    except (ValueError, SyntaxError, OverflowError, TypeError) as e:
        return {"error": f"Could not evaluate expression: {e}"}
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return {"expression": expression, "result": result}


# ------------------------------------------------------------------- weather
_WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
    75: "heavy snow", 80: "rain showers", 81: "rain showers", 82: "violent rain showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


def get_weather(city: str):
    """Current weather for any city (Open-Meteo, free, no API key)."""
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=10,
        )
        geo.raise_for_status()
        places = geo.json().get("results")
        if not places:
            return {"error": f"Could not find a place called '{city}'."}
        place = places[0]

        wx = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            },
            timeout=10,
        )
        wx.raise_for_status()
        cur = wx.json()["current"]
    except (requests.RequestException, KeyError, ValueError):
        return {"error": "Weather service is unavailable right now."}

    return {
        "city": place.get("name"),
        "country": place.get("country"),
        "temperature_c": cur.get("temperature_2m"),
        "humidity_percent": cur.get("relative_humidity_2m"),
        "wind_speed_kmh": cur.get("wind_speed_10m"),
        "conditions": _WEATHER_CODES.get(cur.get("weather_code"), "unknown"),
    }


# -------------------------------------------------------------- date and time
def get_current_datetime(timezone: str = "Asia/Kolkata"):
    try:
        now = datetime.now(ZoneInfo(timezone))
    except Exception:
        return {"error": f"Unknown timezone '{timezone}'. Use names like Asia/Kolkata."}
    return {
        "timezone": timezone,
        "date": now.strftime("%A, %d %B %Y"),
        "time": now.strftime("%I:%M %p"),
    }


# ------------------------------------------------ sample user (your old tool)
def get_sample_user(user_id: int = 1):
    try:
        r = requests.get(f"https://jsonplaceholder.typicode.com/users/{int(user_id)}", timeout=5)
        if r.status_code != 200:
            return {"error": "User not found."}
        u = r.json()
        return {
            "name": u["name"],
            "username": u["username"],
            "email": u["email"],
            "city": u["address"]["city"],
            "company": u["company"]["name"],
        }
    except (requests.RequestException, KeyError, ValueError):
        return {"error": "User service is currently unavailable."}


# -------------------------------------------------------------------- memory
MAX_MEMORY_KEYS = 30


def save_memory(key: str, value: str, ctx: dict):
    """Memory lives in the user's browser, not on the server (Render's disk is wiped).
    We record the change in ctx; the frontend stores it and sends it back next time."""
    key = str(key).strip().lower()[:40]
    value = str(value).strip()[:200]
    if not key or not value:
        return {"error": "Both key and value are required."}
    if key not in ctx["memory"] and len(ctx["memory"]) >= MAX_MEMORY_KEYS:
        return {"error": "Memory is full."}
    ctx["memory"][key] = value
    ctx["updates"][key] = value
    return {"saved": {key: value}}


# ------------------------------------------------------- specs for the model
TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate an arithmetic expression exactly. Use for any math: "
                           "e.g. '12*(3+4)', '15/100*2400', '2**10'. Convert percentages to numbers first.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "Arithmetic expression"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "City name, e.g. 'Bhopal'"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Get the current date and time. Use whenever the user asks about today's date, day or time.",
            "parameters": {
                "type": "object",
                "properties": {"timezone": {"type": "string", "description": "IANA timezone, default Asia/Kolkata"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sample_user",
            "description": "Fetch a sample user profile (id 1-10) from a demo API.",
            "parameters": {
                "type": "object",
                "properties": {"user_id": {"type": "integer", "description": "User id between 1 and 10"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Remember a lasting fact the user told you about themselves "
                           "(name, city, preferences). Do not use for temporary things.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short label, e.g. 'name', 'city'"},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
            },
        },
    },
]


def run_tool(name: str, args: dict, ctx: dict):
    """Dispatch a tool call requested by the model. Never raises."""
    try:
        if name == "calculator":
            return calculator(args.get("expression", ""))
        if name == "get_weather":
            return get_weather(args.get("city", ""))
        if name == "get_current_datetime":
            return get_current_datetime(args.get("timezone") or "Asia/Kolkata")
        if name == "get_sample_user":
            return get_sample_user(args.get("user_id", 1))
        if name == "save_memory":
            return save_memory(args.get("key", ""), args.get("value", ""), ctx)
        return {"error": f"Unknown tool '{name}'."}
    except Exception as e:  # a tool bug must never crash the chat
        print(f"Tool {name} failed:", e)
        return {"error": "Tool failed unexpectedly."}
