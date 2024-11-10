import os
import time
import json
import requests
import urllib.parse
from bs4 import BeautifulSoup
from openai import OpenAI
from pymongo import MongoClient
from pymongo.server_api import ServerApi

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
geocoding_base_url = os.environ.get("GEOCODING_BASE_URL")
drivebc_major_events_url = os.environ.get("DRIVEBC_MAJOR_EVENTS_URL")


def get_major_events():

    response = requests.get(drivebc_major_events_url)

    if response.status_code != 200:
        print("Failed to fetch the page. HTTP Status Code:", response.status_code)
        return []

    # backup the content to cloud storage
    backup_data_to_cloud_storage(response.text)

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


def extract_key_info(open_ai_client, description):
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that extracts key information from the given major road event notifications in BC, Canada.",
        },
        {
            "role": "user",
            "content": f"""
        Extract the following information as JSON format, make it accurate. The Descrition will only contain road conditions, not project completion information or updateing timestamps.
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
            model="gpt-3.5-turbo", messages=messages, max_tokens=4000, temperature=0
        )

        json_output = response.choices[0].message.content.strip()
        return json.loads(json_output)

    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return {}


def augment_events(events):
    open_ai_client = OpenAI(api_key=OPENAI_API_KEY)
    for event in events:
        key_info = extract_key_info(open_ai_client, event["description"])
        event.update(key_info)
    return events


def get_lat_lng(address):
    encoded_address = urllib.parse.quote(address)

    # clean the encoded_address a bit
    if "," in encoded_address:
        encoded_address = encoded_address.split(",")[0]
    encoded_address = encoded_address + ", BC, Canada"

    geocoding_url = (
        geocoding_base_url + f"address={encoded_address}&key={GOOGLE_API_KEY}"
    )

    response = requests.get(geocoding_url)

    if response.status_code == 200:
        data = response.json()
        if data["status"] == "OK":
            result = data["results"][0]  # obtain the first result
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


def backup_data_to_cloud_storage(html):
    # save the html to a tmp file using tempfile and upload it
    import tempfile
    from google.cloud import storage

    tmp_file = tempfile.NamedTemporaryFile(delete=False)
    file_path = tmp_file.name
    with open(file_path, "w") as f:
        f.write(html)

    CLOUD_STORAGE_BUCKET_NAME = os.environ.get("CLOUD_STORAGE_BUCKET_NAME")

    # Create a storage client
    storage_client = storage.Client()

    # Get the bucket
    bucket = storage_client.get_bucket(CLOUD_STORAGE_BUCKET_NAME)

    # Create a new blob with timestamp as the name, file extension is html
    blob = bucket.blob(time.strftime("_%Y%m%d-%H%M%S") + ".html")

    # upon successful upload, delete the tmp file
    try:
        blob.upload_from_filename(file_path)
        print("File uploaded to Cloud Storage.")
    except Exception as e:
        print(f"Failed to upload file to Cloud Storage: {e}")
    finally:
        os.unlink(file_path)


def backup_data_to_mongodb(data):

    # MongoDB connection string with password placeholder
    host = os.environ.get("MONGODB_HOST")
    username = os.environ.get("MONGODB_USERNAME")
    password = os.environ.get("MONGODB_PASSWORD")
    db_name = os.environ.get("MONGODB_DBNAME")
    collection_name = os.environ.get("MONGODB_COLLECTIONNAME")  + time.strftime("_%Y%m%d-%H")
    uri = f"mongodb+srv://{username}:{password}@{host}"
    try:
        client = MongoClient(uri, server_api=ServerApi("1"))

        # Database and collection names
        db = client.get_database(db_name)  # replace with your actual database name

        # Check if the collection exists, if not create it
        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name)

        # Insert records into the collection in bulk
        collection = db[collection_name]

        # Batch insert
        collection.insert_many(data)
        print("Records inserted successfully.")
    except Exception as e:
        print("Failed to insert records: ", e)


if __name__ == "__main__":
    events = get_major_events()
    if events:
        augmented_events = augment_events(events)
    else:
        print("No events found.")

    if augment_events:
        for idx, event in enumerate(augmented_events, start=1):
            location = event.get("Location")
            if location:
                lat_lng = get_lat_lng(location)
                if lat_lng:
                    event["latitude"] = lat_lng["latitude"]
                    event["longitude"] = lat_lng["longitude"]
                else:
                    print(f"Event {idx} Location: {location}")
                    print(
                        "  Failed to get latitude and longitude for the location: ",
                        location,
                    )
            else:
                print(f"Event {idx} Location: N/A")
                print("No location information found.")

    backup_data_to_mongodb(augmented_events)

    # remove the _id field from the augmented_events
    for event in augmented_events:
        event.pop("_id", None)

    # save augmented event with lat and lng
    with open("src/data/data.json", "w") as f:
        json.dump(augmented_events, f, indent=2)
