import random
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import capsolver
from urllib.parse import quote
from datetime import datetime, timedelta


def format_proxy(proxy_str):
    ip, port, user, password = proxy_str.split(':')
    return {
        'http': f'http://{user}:{password}@{ip}:{port}',
        'https': f'http://{user}:{password}@{ip}:{port}',
    }

def execute_task(task, capsolver_key, capmonster_key, proxies, webhook_url):
    auth_token = task['auth_token']
    payment_id = task['payment_id']
    restaurant_id = task['restaurant_id']
    party_sz = task['party_sz']
    delay = task['delay']
    table_type = task.get('table_type', '').strip().lower()

    # Support multiple time windows: list of (start, end) tuples
    time_windows = task.get('time_windows', [])
    if not time_windows:
        time_windows = [(int(task['start_time']), int(task['end_time']))]

    # Support multiple date ranges: list of (start_date, end_date) strings
    date_ranges = task.get('date_ranges', [])
    if not date_ranges:
        date_ranges = [(task['start_date'], task['end_date'])]
    #captcha_service = task['captcha_service']

    headers = {
            'X-Resy-Auth-Token': auth_token,
            'Authorization': 'ResyAPI api_key="VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5"',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'X-Resy-Universal-Auth': auth_token,
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://resy.com/',
    }

    #captcha_key = capsolver_key if captcha_service == 'CAPSolver' else capmonster_key
    #capsolver.api_key = captcha_key

    while True:
        try:
            select_proxy = format_proxy(random.choice(proxies)) if proxies else {}

            for start_date, end_date in date_ranges:
                # API returns 500 if start_date == end_date; ensure at least 1 day range
                if start_date == end_date:
                    end_date_api = (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
                else:
                    end_date_api = end_date
                url = f"https://api.resy.com/4/venue/calendar?venue_id={restaurant_id}&num_seats={party_sz}&start_date={start_date}&end_date={end_date_api}"
                response = requests.get(url, headers=headers, proxies=select_proxy if select_proxy else None)

                if response.status_code != 200:
                    print(f'[DEBUG] URL: {url}')
                    print(f'[DEBUG] Status: {response.status_code}')
                    print(f'[DEBUG] Response: {response.text[:500]}')
                    print(f'[DEBUG] Headers sent: {headers}')
                    send_discord_notification(webhook_url, f'(1) Failed to get availability for restaurant {restaurant_id} - {response.text} - {response.status_code}')
                    continue

                data = response.json()
                if 'scheduled' not in data:
                    send_discord_notification(webhook_url, f'Unexpected response format for API1 for restaurant {restaurant_id} - {data}')
                    continue
                for entry in data['scheduled']:
                    if entry['inventory']['reservation'] == 'available':

                        url2 = f"https://api.resy.com/4/find?lat=0&long=0&day={entry['date']}&party_size={party_sz}&venue_id={restaurant_id}"
                        response2 = requests.get(url2, headers=headers, proxies=select_proxy if select_proxy else None)

                        if response2.status_code != 200:
                            send_discord_notification(webhook_url, f'(2) Failed to get availability for restaurant {restaurant_id}')
                            continue

                        data2 = response2.json()

                        if 'results' not in data2:
                            send_discord_notification(webhook_url, f'Unexpected response format for API2 for restaurant {restaurant_id} - {data2}')
                            continue

                        if 'results' in data2 and 'venues' in data2['results'] and data2['results']['venues']:
                            for slot in data2['results']['venues'][0]['slots']:
                                # Filter by table type if specified
                                slot_type = slot.get('config', {}).get('type', '').lower()
                                if table_type and table_type not in slot_type:
                                    continue
                                config_token = slot['config']['token']
                                parts = config_token.split('/')
                                time_part = parts[8].split(':')[0]
                                slot_hour = int(time_part)
                                if any(s <= slot_hour <= e for s, e in time_windows):
                                    book_token = get_details(entry['date'], party_sz, config_token, restaurant_id, headers, select_proxy)
                                    print('\nBook_token is :', book_token)
                                    reservationVal = book_reservation(book_token, auth_token, payment_id, entry['date'], party_sz, restaurant_id, config_token, headers, select_proxy)

                                    if 'reservation_id' in reservationVal or ('specs' in reservationVal and 'reservation_id' in reservationVal['specs']):
                                        send_discord_notification(webhook_url, f'Reservation booked for restaurant {restaurant_id} - {reservationVal}')
                                        return
                                    else:
                                        send_discord_notification(webhook_url, f'Failed to book reservation for restaurant {restaurant_id} - {reservationVal}')
                                        continue
                        else:
                            send_discord_notification(webhook_url, f'Unexpected response format for API2 for restaurant {restaurant_id} - {data2}')
                            continue
                    else:
                        continue
        except Exception as e:
            import traceback
            print('failed to execute task')
            traceback.print_exc()
            break
        time.sleep(delay/1000)


def get_captcha_token(captcha_key, site_key, url, proxy):
    solution = capsolver.solve({
        "type": "RecaptchaV2Task",
        "websiteKey": site_key,
        "websiteURL": url,
        "proxy": proxy['http']
    })
    gRecaptchaResponse = solution['gRecaptchaResponse']
    return gRecaptchaResponse
    
def get_details(day, party_size, config_token, restaurant_id, headers, select_proxy):
    url = 'http://127.0.0.1:8000/api/get-details'
    payload = {
        'day': day,
        'party_size': party_size,
        'config_token': config_token,
        'restaurant_id': restaurant_id,
        'headers': headers,
        'select_proxy': select_proxy
    }

    response = requests.post(url, json=payload)
    
    if response.status_code != 200:
        print(f'Failed to get details for restaurant {restaurant_id} - {response.text} - {response.status_code}')
        return

    data = response.json()
    return data['response_value']

def book_reservation(book_token, auth_token, payment_id, day, party_size, restaurant_id, config_token, headers, select_proxy):
    url = 'http://127.0.0.1:8000/api/book-reservation'
    payload = {
        'book_token': book_token,
        'auth_token': auth_token,
        'payment_id': payment_id,
        'day': day,
        'party_size': party_size,
        'restaurant_id': restaurant_id,
        'config_token': config_token,
        'headers': headers,
        'select_proxy': select_proxy
    }

    response = requests.post(url, json=payload)

    return response.json()
        
def send_discord_notification(webhook_url, message):
    print(f"[Notification] {message}")
    if not webhook_url or not webhook_url.startswith("http"):
        return
    data = {"content": message}
    try:
        requests.post(webhook_url, json=data)
    except Exception:
        pass

def run_tasks_concurrently(tasks, capsolver_key, capmonster_key, proxies, webhook_url):
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = [executor.submit(execute_task, task, capsolver_key, capmonster_key, proxies, webhook_url) for task in tasks]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print('Failed to execute task')
                print(e)