import functions_framework
from google.cloud import storage
import json

BUCKET_NAME = "jetstream-bucket-poc-2024"
storage_client = storage.Client()

@functions_framework.http
def status_checker(request):
    headers = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" }
    if request.method == "OPTIONS": return ("", 204, headers)

    request_json = request.get_json(silent=True)
    task_id = request_json.get("taskId")
    if not task_id: return ({"error": "taskId is required"}, 400, headers)

    bucket = storage_client.bucket(BUCKET_NAME)
    status_blob = bucket.blob(f"Jetstream/tasks/{task_id}.json")

    try:
        status_data = json.loads(status_blob.download_as_string())
        return (status_data, 200, headers)
    except Exception:
        return ({"status": "pending"}, 200, headers)