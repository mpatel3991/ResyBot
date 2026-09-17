import sys
import os
import io
import json
import queue
import threading
import time

# Add client directory to path so we can import task_executor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))

from flask import Flask, render_template, request, jsonify, Response
import task_executor

app = Flask(__name__)

# --- Log capture ---
log_queue = queue.Queue(maxsize=5000)

class LogCapture(io.TextIOBase):
    def __init__(self, original):
        self.original = original

    def write(self, text):
        self.original.write(text)
        if text.strip():
            log_queue.put(text.strip())
        return len(text)

    def flush(self):
        self.original.flush()

sys.stdout = LogCapture(sys.stdout)

# --- Task state ---
task_thread = None
stop_event = threading.Event()
is_running = False
_original_sleep = time.sleep


def interruptible_sleep(seconds):
    """Replacement for time.sleep that checks stop_event every 0.5s."""
    end_time = time.time() + seconds
    while time.time() < end_time:
        if stop_event.is_set():
            raise InterruptedError("Task stopped by user")
        _original_sleep(min(0.5, end_time - time.time()))


def run_task_wrapper(task, proxies, webhook_url):
    """Run a single task with stop support via monkey-patched sleep."""
    global is_running
    # Monkey-patch sleep in the executor module
    task_executor.time.sleep = interruptible_sleep
    try:
        task_executor.execute_task(
            task,
            capsolver_key='',
            capmonster_key='',
            proxies=proxies,
            webhook_url=webhook_url,
        )
    except InterruptedError:
        print(f"[STOPPED] Task for restaurant {task['restaurant_id']} stopped by user")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        task_executor.time.sleep = _original_sleep
        is_running = False
        print("[INFO] Task finished.")


# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    accounts_path = os.path.join(os.path.dirname(__file__), 'client', 'accounts.json')
    if os.path.exists(accounts_path):
        with open(accounts_path) as f:
            return jsonify(json.load(f))
    return jsonify([])


@app.route('/api/accounts', methods=['POST'])
def save_account():
    data = request.json
    auth_token = data.get('auth_token', '').strip()
    payment_id = data.get('payment_id', '').strip()
    account_name = data.get('account_name', '').strip()

    if not auth_token or not payment_id or not account_name:
        return jsonify({'error': 'All fields are required'}), 400

    accounts_path = os.path.join(os.path.dirname(__file__), 'client', 'accounts.json')
    accounts = []
    if os.path.exists(accounts_path):
        with open(accounts_path) as f:
            accounts = json.load(f)

    account = {
        'auth_token': auth_token,
        'payment_id': payment_id,
        'account_name': account_name,
    }
    accounts.append(account)

    with open(accounts_path, 'w') as f:
        json.dump(accounts, f, indent=4)

    return jsonify({'status': 'saved', 'account_name': account_name})


PRESETS_FILE = os.path.join(os.path.dirname(__file__), 'client', 'presets.json')


@app.route('/api/presets', methods=['GET'])
def get_presets():
    if os.path.exists(PRESETS_FILE):
        with open(PRESETS_FILE) as f:
            return jsonify(json.load(f))
    return jsonify([])


@app.route('/api/presets', methods=['POST'])
def save_preset():
    data = request.json
    name = data.get('preset_name', '').strip()
    if not name:
        return jsonify({'error': 'Preset name is required'}), 400

    presets = []
    if os.path.exists(PRESETS_FILE):
        with open(PRESETS_FILE) as f:
            presets = json.load(f)

    preset = {
        'preset_name': name,
        'venue_id': data.get('venue_id', ''),
        'party_size': data.get('party_size', '2'),
        'start_date': data.get('start_date', ''),
        'end_date': data.get('end_date', ''),
        'date_ranges': data.get('date_ranges', []),
        'time_windows': data.get('time_windows', [[17, 21]]),
        'table_type': data.get('table_type', ''),
        'delay': data.get('delay', '60000'),
        'account_name': data.get('account_name', ''),
        'proxies': data.get('proxies', ''),
        'discord_webhook': data.get('discord_webhook', ''),
    }
    presets.append(preset)

    with open(PRESETS_FILE, 'w') as f:
        json.dump(presets, f, indent=4)

    return jsonify({'status': 'saved', 'preset_name': name})


@app.route('/api/presets/<int:index>', methods=['DELETE'])
def delete_preset(index):
    if not os.path.exists(PRESETS_FILE):
        return jsonify({'error': 'No presets found'}), 404
    with open(PRESETS_FILE) as f:
        presets = json.load(f)
    if index < 0 or index >= len(presets):
        return jsonify({'error': 'Invalid preset index'}), 404
    removed = presets.pop(index)
    with open(PRESETS_FILE, 'w') as f:
        json.dump(presets, f, indent=4)
    return jsonify({'status': 'deleted', 'preset_name': removed['preset_name']})


@app.route('/api/start', methods=['POST'])
def start_task():
    global task_thread, is_running

    if is_running:
        return jsonify({'error': 'Task already running'}), 400

    data = request.json

    # Build task dict matching task_executor's expected format
    # Parse time windows: list of [start, end] pairs
    time_windows = data.get('time_windows', [])
    if not time_windows:
        time_windows = [[int(data.get('start_time', 17)), int(data.get('end_time', 21))]]
    time_windows = [(int(w[0]), int(w[1])) for w in time_windows]

    # Parse date ranges: list of [start_date, end_date] strings
    date_ranges = data.get('date_ranges', [])
    if not date_ranges:
        date_ranges = [[data.get('start_date', ''), data.get('end_date', '')]]
    date_ranges = [(r[0], r[1]) for r in date_ranges]

    task = {
        'account_name': data.get('account_name', ''),
        'auth_token': data['auth_token'],
        'payment_id': data['payment_id'],
        'restaurant_id': data['venue_id'],
        'party_sz': int(data['party_size']),
        'start_date': date_ranges[0][0],
        'end_date': date_ranges[0][1],
        'start_time': time_windows[0][0],
        'end_time': time_windows[0][1],
        'time_windows': time_windows,
        'date_ranges': date_ranges,
        'table_type': data.get('table_type', ''),
        'delay': int(data.get('delay', 60000)),
    }

    # Parse proxies (one per line, ip:port:user:pass)
    proxy_text = data.get('proxies', '').strip()
    proxies = [p.strip() for p in proxy_text.split('\n') if p.strip()] if proxy_text else []

    webhook_url = data.get('discord_webhook', '')

    # Clear state
    stop_event.clear()
    # Drain old log messages
    while not log_queue.empty():
        try:
            log_queue.get_nowait()
        except queue.Empty:
            break

    is_running = True
    print(f"[INFO] Starting task for restaurant {task['restaurant_id']}, party size {task['party_sz']}")
    dates_str = ', '.join(f"{s} to {e}" for s, e in date_ranges)
    windows_str = ', '.join(f"{s}:00-{e}:00" for s, e in time_windows)
    print(f"[INFO] Date ranges: {dates_str}")
    print(f"[INFO] Time windows: {windows_str}")
    if task['table_type']:
        print(f"[INFO] Table type filter: {task['table_type']}")

    task_thread = threading.Thread(
        target=run_task_wrapper,
        args=(task, proxies, webhook_url),
        daemon=True,
    )
    task_thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/stop', methods=['POST'])
def stop_task():
    global is_running
    if not is_running:
        return jsonify({'error': 'No task running'}), 400
    print("[INFO] Stop requested...")
    stop_event.set()
    return jsonify({'status': 'stopping'})


@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({'running': is_running})


@app.route('/api/logs')
def log_stream():
    def generate():
        while True:
            try:
                message = log_queue.get(timeout=1.0)
                # Escape for SSE
                escaped = message.replace('\n', ' ')
                yield f"data: {escaped}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, threaded=True)
