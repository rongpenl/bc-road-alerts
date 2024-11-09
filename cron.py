import os
import time
import json
import requests
import urllib.parse
from bs4 import BeautifulSoup
from openai import OpenAI

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
geocoding_base_url = os.environ.get("GEOCODING_BASE_URL")
drivebc_major_events_url = os.environ.get("DRIVEBC_MAJOR_EVENTS_URL")

open_ai_client = OpenAI(api_key=OPENAI_API_KEY)


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
            model="gpt-3.5-turbo", messages=messages, max_tokens=2000, temperature=0
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

def get_lat_lng(address):
    encoded_address = urllib.parse.quote(address)

    geocoding_url = geocoding_base_url + f"address={encoded_address}&key={GOOGLE_API_KEY}"
    
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


def backup_data_to_cloud_storage(html):
    # save the html to a tmp file using tempfile and upload it
    import tempfile
    from google.cloud import storage
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    file_path = tmp_file.name
    with open(file_path, "w") as f:
        f.write(html)
    
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    CLOUD_STORAGE_BUCKET_NAME = os.environ.get("CLOUD_STORAGE_BUCKET_NAME")

    # Create a storage client
    storage_client = storage.Client()

    # Get the bucket
    bucket = storage_client.get_bucket(CLOUD_STORAGE_BUCKET_NAME)

    # Create a new blob with timestamp as the name, file extension is html
    blob = bucket.blob(f"{os.path.basename(file_path)}" + time.strftime("_%Y%m%d-%H%M%S") + ".html")
    
    # upon successful upload, delete the tmp file
    try:
        blob.upload_from_filename(file_path)
        print("File uploaded to Cloud Storage.")
    except Exception as e:
        print(f"Failed to upload file to Cloud Storage: {e}")
    finally:
        os.unlink(file_path)

    


def backup_data_to_documentdb(data):
    from pymongo import MongoClient

    # MongoDB connection string with password placeholder
    password = os.environ.get("DOCUMENTDB_PASSWORD")
    user = os.environ.get("DOCUMENTDB_USER")
    db_name = os.environ.get("DOCUMENTDB_DB_NAME")
    collection_name = os.environ.get("DOCUMENTDB_COLLECTION_NAME")
    client = MongoClient(f"mongodb://{user}:{password}@{db_name}.cluster-coqjo5ckblxs.us-east-1.docdb.amazonaws.com:27017/?tls=true&tlsCAFile=global-bundle.pem&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false")

    # Database and collection names
    db = client.get_database(db_name)  # replace with your actual database name

    # Check if the collection exists, if not create it
    if collection_name not in db.list_collection_names():
        db.create_collection(collection_name)

    # Insert records into the collection in bulk
    collection = db[collection_name]

    # Batch insert
    if data:
        collection.insert_many(data)
        print("Records inserted successfully.")
    else:
        print("No records to insert.")



if __name__ == "__main__":
    events = get_major_events()
    if events:
        augmented_events = augment_events(events)
        try:
            backup_data_to_documentdb(augmented_events)
        except Exception as e:
            print(f"Failed to backup data to DocumentDB: {e}")
    else:
        print("No events found.")
    
    if augment_events:
        for idx, event in enumerate(augmented_events, start=1):
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
                print("No location information found.")
    # save augmented event with lat and lng
    with open("src/data/data.json", "w") as f:
        json.dump(augmented_events, f, indent=2)