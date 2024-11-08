import os
import json
import requests
import urllib.parse
from bs4 import BeautifulSoup
from openai import OpenAI
from tqdm import tqdm

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

open_ai_client = OpenAI(api_key=OPENAI_API_KEY)


def get_lat_lng(address):
    encoded_address = urllib.parse.quote(address)

    geocoding_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={GOOGLE_API_KEY}"
    
    response = requests.get(geocoding_url)

    if response.status_code == 200:
        data = response.json()
        if data["status"] == "OK":
            result = data["results"][0] # obtain the first result
            location = result["geometry"]["location"]
            latitude = location["lat"]
            longitude = location["lng"]
            return {"latitude": latitude, "longitude": longitude}
        else:
            print("Geocoding failed. Status:", data["status"])
    else:
        print(
            "Failed to connect to Google Geocoding API. HTTP Status Code:",
            response.status_code,
        )

    return None


def get_major_events():

    url = "https://www.drivebc.ca/mobile/pub/events/majorevents.html"
    response = requests.get(url)

    if response.status_code != 200:
        print("Failed to fetch the page. HTTP Status Code:", response.status_code)
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    events = []
    event_rows = soup.select("table#event-table tr")

    for row in event_rows:
        highway_info = row.find_all("td")[0].get_text(strip=True)
        event_link_tag = row.find("a", class_="Major")

        if event_link_tag:
            event_description = event_link_tag.get_text(strip=True)
            event_link = (
                f"https://www.drivebc.ca/mobile/pub/events/{event_link_tag['href']}"
            )

            events.append(
                {
                    "title": highway_info,
                    "description": event_description,
                    "link": event_link,
                }
            )

    return events


def extract_key_info(description):
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that extracts key information from the given event description.",
        },
        {
            "role": "user",
            "content": f"""
        Extract the following information as JSON format, make it precise and accurate:
        - Location
        - Description
        - Next update time
        - Last update time

        Text: "{description}"

        Output:
        """,
        },
    ]

    try:
        response = open_ai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=messages, max_tokens=250, temperature=0
        )

        json_output = response.choices[0].message.content.strip()
        return json.loads(json_output)

    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return {}


def augment_events(events):
    for event in events:
        key_info = extract_key_info(event["description"])
        event.update(key_info)
    return events


if __name__ == "__main__":
    events = get_major_events()

    if events:
        augmented_events = augment_events(events)
    else:
        print("No events found.")
    
    if augment_events:
        for idx, event in tqdm(enumerate(augmented_events, start=1)):
            location = event.get('Location')
            if location:
                lat_lng = get_lat_lng(location)
                if lat_lng:
                    event['latitude'] = lat_lng['latitude']
                    event['longitude'] = lat_lng['longitude']
                else:
                    print(f"Event {idx} Location: {location}")
                    print("  Failed to get latitude and longitude for the location: ", location)
            else:
                print(f"Event {idx} Location: N/A")
                print("  No location information found.")
    # save augmented event with lat and lng
    with open("src/data/data.json", "w") as f:
        json.dump(augmented_events, f, indent=2)