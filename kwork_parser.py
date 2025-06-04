import os
import time
import logging
import sqlite3
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

import requests

# Endpoint template that returns project list in JSON format. Adjust if Kwork
# changes the API. The ``page`` placeholder will be replaced with the page
# number during requests.
API_URL_TEMPLATE = (
    "https://kwork.ru/projects?format=json&kworks-filters%5B%5D=0&a=1&page={page}"
)
SLEEP_SECONDS = 40
MAX_PAGES = int(os.getenv("MAX_PAGES", "10"))
DB_PATH = "orders.db"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def init_db(path: str = DB_PATH) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS sent_orders (id TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()


def is_sent(order_id: str, path: str = DB_PATH) -> bool:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sent_orders WHERE id=?", (order_id,))
    res = cur.fetchone()
    conn.close()
    return res is not None


def mark_sent(order_id: str, path: str = DB_PATH) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO sent_orders (id) VALUES (?)", (order_id,))
    conn.commit()
    conn.close()


def send_to_telegram(text: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram credentials are not set. Skipping send.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        r.raise_for_status()
        logging.info("Message sent to Telegram")
    except Exception:
        logging.exception("Failed to send message to Telegram")


def parse_page(page: int) -> List[Dict[str, str]]:
    """Fetch project list from API and convert it to a unified structure."""
    url = API_URL_TEMPLATE.format(page=page)
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    try:
        data = r.json()
    except Exception:
        logging.exception("Failed to decode JSON from API")
        return []

    items = data.get("data") if isinstance(data, dict) else None
    if items is None:
        items = data if isinstance(data, list) else []

    orders = []
    for item in items:
        order_id = str(item.get("id")) if isinstance(item, dict) else None
        if not order_id:
            continue
        title = str(item.get("title", ""))
        link = (
            item.get("url")
            or item.get("link")
            or f"https://kwork.ru/projects/{order_id}"
        )
        description = str(item.get("description", ""))
        budget = item.get("price") or item.get("budget") or 0
        if isinstance(budget, str):
            digits = "".join(ch for ch in budget if ch.isdigit())
            budget = int(digits) if digits else 0
        offers_count = item.get("offers_count") or item.get("offers") or 0
        if isinstance(offers_count, str):
            digits = "".join(ch for ch in offers_count if ch.isdigit())
            offers_count = int(digits) if digits else 0
        orders.append({
            "id": order_id,
            "title": title,
            "link": link,
            "description": description,
            "budget": budget,
            "offers_count": offers_count,
        })
    return orders


def fetch_pages(max_pages: int) -> List[Dict[str, str]]:
    """Fetch multiple pages concurrently and combine the results."""
    orders: List[Dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max_pages) as exe:
        results = exe.map(parse_page, range(1, max_pages + 1))
        for page_orders in results:
            orders.extend(page_orders)
    return orders


def main() -> None:
    init_db()
    while True:
        try:
            orders = fetch_pages(MAX_PAGES)
            logging.info("Found %d orders", len(orders))
            for order in orders:
                if not is_sent(order["id"]):
                    message = (
                        "\U0001F195 Новый заказ на Kwork:\n"
                        f"\U0001F4CC <b>Название:</b> {order['title']}\n"
                        f"\U0001F4B0 <b>Бюджет:</b> до {order['budget']} ₽\n"
                        f"\U0001F4C8 <b>Предложений:</b> {order['offers_count']}\n"
                        f"\U0001F4C4 <b>Описание:</b> {order['description']}\n"
                        f"\u27A1\uFE0F {order['link']}"
                    )
                    send_to_telegram(message)
                    mark_sent(order["id"])
        except Exception:
            logging.exception("Failed to parse page")
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
