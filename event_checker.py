from email.mime.text import MIMEText
import json
import logging
import os
import smtplib
from typing import Any

import requests

API_KEY = os.getenv("TICKETMASTER_API_KEY")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECIPIENTS = os.getenv("RECIPIENTS")

ARTIST_ID = "K8vZ9171o9f"  # Masayoshi Takanaka attraction id
DB_FILE = "known_events.json"


def main() -> None:
    """Checks if TicketMaster has created a new Masayoshi Takanaka event."""
    if not API_KEY:
        raise ValueError("Error: TICKETMASTER_API_KEY environment variable is not set.")

    logging.info(f"--- Running concert check for artist ID: {ARTIST_ID} ---")

    known_event_ids = load_known_events()
    logging.info(f"Found {len(known_event_ids)} known events.")

    current_events = get_artist_events(ARTIST_ID)

    current_event_ids = {event["id"] for event in current_events}
    logging.info(f"Fetched {len(current_event_ids)} current events from API.")

    new_event_ids = current_event_ids - known_event_ids

    if not new_event_ids:
        logging.info("No new events found.")
    else:
        logging.info(
            f"Found {len(new_event_ids)} new event(s)! Sending notifications..."
        )
        new_events = [event for event in current_events if event["id"] in new_event_ids]
        notify_email(new_events)

    logging.info("Saving updated event list.")
    save_known_events(current_event_ids)
    logging.info("--- Check complete. ---")


def load_known_events() -> set[str]:
    """Loads the set of known event IDs from our JSON file."""
    try:
        with open(DB_FILE, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        logging.info("%s file not found.", DB_FILE)
        return set()


def save_known_events(event_ids: set[str]) -> None:
    """Saves a set of event IDs to our JSON file."""
    with open(DB_FILE, "w") as f:
        json.dump(list(event_ids), f, indent=4)


def get_artist_events(attraction_id: str) -> list[dict[str, Any]]:
    """Fetches all upcoming events for a given artist from the Ticketmaster API."""
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "attractionId": attraction_id,
        "apikey": API_KEY,
        "sort": "date,asc",
        "size": 10,
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("_embedded", {}).get("events", [])
    except requests.exceptions.RequestException as e:
        logging.exception("Error fetching data from Ticketmaster API.")
        raise


def notify_email(events: list[dict[str, Any]]) -> None:
    """Sends an email notification for a new event."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not RECIPIENTS:
        logging.exception("Missing Gmail credentials.")
        raise ValueError("Email credentials not set.")

    num_events = len(events)

    plural_s = "s" if num_events > 1 else ""
    subject = f"Masayoshi Takanaka added {num_events} new concert{plural_s}!"

    body_parts = [
        f"Hello! {num_events} new event{plural_s} have been added for your tracked artist:\n"
    ]

    for event in events:
        event_name = event.get("name")
        event_url = event.get("url")
        event_date = event.get("dates", {}).get("start", {}).get("localDate", "N/A")
        venue_info = event.get("_embedded", {}).get("venues", [{}])[0]
        venue_name = venue_info.get("name", "N/A")
        city = venue_info.get("city", {}).get("name", "N/A")

        event_details = (
            f"----------------------------------------\n"
            f"Event: {event_name}\n"
            f"Date: {event_date}\n"
            f"Venue: {venue_name} in {city}\n"
            f"Link: {event_url}\n"
        )
        body_parts.append(event_details)

    body = "\n".join(body_parts)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENTS

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            recipient_emails = [email.strip() for email in RECIPIENTS.split(",")]
            server.sendmail(GMAIL_USER, recipient_emails, msg.as_string())
        logging.info(
            f"Summary notification for {num_events} new event{plural_s} sent successfully!"
        )
    except smtplib.SMTPException as e:
        logging.exception(f"Failed to send email notification:")
        raise


if __name__ == "__main__":
    if not API_KEY:
        raise ValueError("Error: TICKETMASTER_API_KEY environment variable is not set.")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    main()
