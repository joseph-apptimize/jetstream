import functions_framework
from google.cloud import storage
import json
import vertexai
from vertexai.generative_models import GenerativeModel
import threading
import uuid
import time

# --- Configuration & Clients ---
BUCKET_NAME = "jetstream-bucket-poc-2024"
GCP_PROJECT_ID = "airship-ai-value-poc-2024"
GCP_REGION = "us-central1"
storage_client = storage.Client()
vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)
gemini_pro_model = GenerativeModel("gemini-2.5-pro")

# --- Background Analysis Function (Unchanged) ---
def run_analysis_in_background(task_id, notes, prospect_name_guess):
    """Runs the initial analysis + web search in a thread."""
    bucket = storage_client.bucket(BUCKET_NAME)
    
    def update_status(status_message, result_text=""):
        status_blob = bucket.blob(f"Jetstream/tasks/{task_id}.json")
        status_data = {"status": status_message, "result": result_text}
        try:
            status_blob.upload_from_string(json.dumps(status_data), content_type="application/json")
            print(f"[{task_id}] Status updated: {status_message}")
        except Exception as e:
            print(f"[{task_id}] ERROR updating status: {e}")

    try:
        update_status("Analyzing notes...")
        time.sleep(1)
        
        # NOTE: Web search is still commented out until API keys are added
        # update_status("Searching the web for context...")
        web_context = "Web search disabled." # search_web_for_context(prospect_name_guess)
        # time.sleep(1)

        update_status("Identifying key business challenges...")
        time.sleep(1)
        update_status("Summarizing stakeholder goals...")
        
        prompt = f"""
        You are an intelligent business analyst at Airship (www.airship.com). 
        Read the following raw notes/transcripts AND recent web search results...
        (Your full analysis prompt here)
        Internal Notes/Transcripts: --- {notes} ---
        Web Search Results: --- {web_context} ---
        """

        response = gemini_pro_model.generate_content(prompt)
        update_status("complete", response.text)
        print(f"[{task_id}] Analysis complete.")

    except Exception as e:
        error_str = f"Error during analysis: {str(e)}"
        print(f"[{task_id}] {error_str}")
        update_status(error_str)

# --- NEW: Synchronous Follow-up Function ---
def get_follow_up_response(chat_history: list, new_question: str) -> str:
    """Directly calls Gemini for follow-up questions using history."""
    
    # Construct the conversation history for the prompt
    full_conversation = ""
    for message in chat_history:
        # Gemini API expects alternating 'user' and 'model' roles
        role = "user" if message["sender"] == "user" else "model" 
        full_conversation += f"Part {role}: {message['text']}\n"
            
    prompt = f"""
    You are an intelligent business analyst at Airship. Continue the following conversation based on the history provided.
    Answer the user's latest question concisely and accurately, using only the information present in the conversation history.
    
    Conversation History:
    {full_conversation}
    
    Latest Question from User:
    {new_question}
    """
    try:
        response = gemini_pro_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"ERROR: Follow-up response failed: {e}")
        return "Sorry, I encountered an error trying to respond based on our conversation."


@functions_framework.http
def main_orchestrator(request):
    """Handles both initial analysis (background) and follow-up Q&A (synchronous)."""
    headers = { "Access-Control-Allow-Origin": "https://airship-jetstream.surge.sh", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" }
    if request.method == "OPTIONS": return ("", 204, headers)

    try:
        request_json = request.get_json(silent=True)
        if request_json is None: raise ValueError("Invalid JSON payload received.")
        project_id = request_json.get("projectId")
        user_message = request_json.get("message", "").strip() # Ensure message is stripped
        file_content = request_json.get("fileContent") # Check if file content exists
    except Exception as e:
        print(f"ERROR parsing request: {e}")
        return ({"error": f"Invalid JSON payload: {e}"}, 400, headers)

    if not project_id: return ({"error": "projectId is required"}, 400, headers)

    bucket = storage_client.bucket(BUCKET_NAME)
    state_blob = bucket.blob(f"Jetstream/{project_id}/project_state.json")

    try:
        project_state = json.loads(state_blob.download_as_string())
    except Exception:
        project_state = {"projectId": project_id, "stage": "ESR", "summary": "", "chatHistory": [], "assets": {}}

    # --- CORE LOGIC CHANGE: Determine Flow ---
    if file_content:
        # --- Flow 1: Initial Analysis (Background Task) ---
        notes_to_analyze = file_content
        if user_message: # Append message if user typed something along with upload
             notes_to_analyze += f"\n\n--- Additional Notes ---\n{user_message}"
             project_state["chatHistory"].append({"sender": "user", "text": f"(File Uploaded) {user_message}"})
        else:
             project_state["chatHistory"].append({"sender": "user", "text": "(File Uploaded)"})

        if not notes_to_analyze:
             return ({"error": "No content provided in file to analyze"}, 400, headers)

        task_id = str(uuid.uuid4())
        print(f"[{project_id}] Starting background analysis task: {task_id}")
        thread = threading.Thread(target=run_analysis_in_background, args=(task_id, notes_to_analyze, project_id))
        thread.start()
        
        # Save state immediately *before* returning task ID
        state_blob.upload_from_string(json.dumps(project_state, indent=2), content_type="application/json")
        return ({"taskId": task_id}, 202, headers) # Return task ID for polling

    elif user_message:
        # --- Flow 2: Follow-up Question (Synchronous Task) ---
        print(f"[{project_id}] Handling follow-up question...")
        project_state["chatHistory"].append({"sender": "user", "text": user_message})
        
        # Call the synchronous function
        assistant_response = get_follow_up_response(project_state["chatHistory"], user_message)
        project_state["chatHistory"].append({"sender": "assistant", "text": assistant_response})
        
        # Save updated history and return it directly
        state_blob.upload_from_string(json.dumps(project_state, indent=2), content_type="application/json")
        print(f"[{project_id}] Follow-up response generated.")
        return ({"chatHistory": project_state["chatHistory"]}, 200, headers) # Return full history immediately

    else:
        # No file and no message - invalid request
        return ({"error": "No message or file content provided"}, 400, headers)