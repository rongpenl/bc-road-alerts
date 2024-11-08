import requests
import urllib.parse
from bs4 import BeautifulSoup
from openai import OpenAI
import json
from tqdm import tqdm


# Google Geocoding API 密钥
GOOGLE_API_KEY = "AIzaSyB4yGe5DRg_HVw0sO0f1XrOTMvJFG1CJsA"
OPENAI_API_KEY = "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"

open_ai_client = OpenAI(api_key=OPENAI_API_KEY)


def get_lat_lng(address):
    """
    根据输入地址获取经纬度信息。

    参数:
        address (str): 要查询的地址。

    返回:
        dict: 包含 'latitude' 和 'longitude' 的字典，如果查询失败，返回 None。
    """
    # 对地址进行URL编码
    encoded_address = urllib.parse.quote(address)

    # 构建Geocoding API请求URL
    geocoding_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={GOOGLE_API_KEY}"

    # 发送HTTP请求到Google Geocoding API
    response = requests.get(geocoding_url)

    # 检查响应状态
    if response.status_code == 200:
        data = response.json()
        if data["status"] == "OK":
            # 提取第一个匹配结果的经纬度
            result = data["results"][0]
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


# 获取DriveBC重大事件的列表
def get_major_events():
    """
    获取DriveBC重大事件的列表。

    返回:
        list: 包含每个事件信息的字典列表，每个字典包含以下字段：
            - 'title': 事件标题
            - 'description': 事件详细描述
            - 'link': 链接到详细事件页面的URL
    """
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

            # 添加事件到列表
            events.append(
                {
                    "title": highway_info,
                    "description": event_description,
                    "link": event_link,
                }
            )

    return events


# 使用 OpenAI API 提取关键信息
def extract_key_info(description):
    """
    使用 OpenAI 的 ChatCompletion API 从描述中提取关键信息。

    参数:
        description (str): 事件描述。

    返回:
        dict: 包含 'Location', 'Description', 'Next update time', 'Last update time' 的字典。
    """
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

    # 调用 OpenAI API

    try:
        response = open_ai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=messages, max_tokens=250, temperature=0
        )

        # 提取并返回解析后的JSON
        json_output = response.choices[0].message.content.strip()
        return json.loads(json_output)

    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return {}


# Augment 事件列表，添加解析后的关键信息
def augment_events(events):
    """
    使用 OpenAI API 为事件列表中的每个事件提取地点等信息，并添加到事件字典中。

    参数:
        events (list): 事件字典的列表。

    返回:
        list: 更新后的事件字典列表。
    """
    for event in events:
        key_info = extract_key_info(event["description"])
        event.update(key_info)

        # # 限制请求频率，避免过多请求触发API限制
        # time.sleep(1)

    return events


# 主程序
if __name__ == "__main__":
    # Step 1: 获取事件列表
    events = get_major_events()
    # save raw event
    with open("events.json", "w") as f:
        json.dump(events, f, indent=2)

    # Step 2: 使用 OpenAI 提取事件中的关键信息并进行增强
    if events:
        augmented_events = augment_events(events)
    else:
        print("No events found.")
    # save augmented event
    with open("augmented_events.json", "w") as f:
        json.dump(augmented_events, f, indent=2)
    
    # step 3 获取经纬度信息
    if augment_events:
        for idx, event in tqdm(enumerate(augmented_events, start=1)):
            location = event.get('Location')
            if location:
                lat_lng = get_lat_lng(location)
                if lat_lng:
                    print(f"Event {idx} Location: {location}")
                    print(f"  Latitude: {lat_lng['latitude']}")
                    print(f"  Longitude: {lat_lng['longitude']}\n")
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