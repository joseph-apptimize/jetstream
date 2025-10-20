import functions_framework
from google.cloud import storage
import json
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Content # Ensure Content/Part are imported
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
    # (This function remains the same as the last working version)
    bucket = storage_client.bucket(BUCKET_NAME)
    def update_status(status_message, result_text=""):
        # ... (update_status logic) ...
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
        web_context = "Web search disabled."
        update_status("Identifying key business challenges...")
        time.sleep(1)
        update_status("Summarizing stakeholder goals...")
        prompt = f"""
        You are an intelligent business analyst at Airship...
        Internal Notes/Transcripts: --- {notes} ---
        Web Search Results: --- {web_context} ---
        """ # Use your full prompt
        response = gemini_pro_model.generate_content(prompt)
        update_status("complete", response.text)
        print(f"[{task_id}] Analysis complete.")
    except Exception as e:
        error_str = f"Error during analysis: {str(e)}"
        print(f"[{task_id}] {error_str}")
        update_status(error_str)


# --- Synchronous Follow-up Function (Using Content Objects - Proven Reliable) ---
def get_follow_up_response(chat_history: list, new_question: str) -> str:
    """Directly calls Gemini for follow-up questions using correctly formatted Content objects."""
    history_for_gemini = []
    for message in chat_history:
        role = "user" if message["sender"] == "user" else "model"
        if message['text'] and message['text'].strip():
            history_for_gemini.append(Content(role=role, parts=[Part.from_text(message['text'])]))
    try:
        chat = gemini_pro_model.start_chat(history=history_for_gemini)
        print(f"Sending follow-up question to Gemini: {new_question}")
        response = chat.send_message(new_question)
        if not response.text.strip():
             print("WARNING: Gemini returned an empty response for follow-up.")
             return "I apologize, but I couldn't generate a response based on our conversation."
        print("Follow-up response received from Gemini.")
        return response.text
    except Exception as e:
        print(f"ERROR: Follow-up response failed: {e}")
        return f"Sorry, I encountered an error trying to respond. Technical details: {str(e)}"


@functions_framework.http
def main_orchestrator(request):
    """Handles both initial analysis (background) and follow-up Q&A (synchronous)."""
    headers = { "Access-Control-Allow-Origin": "https://airship-jetstream.surge.sh", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" }
    if request.method == "OPTIONS": return ("", 204, headers)

    try:
        request_json = request.get_json(silent=True)
        if request_json is None: raise ValueError("Invalid JSON payload received.")
        project_id = request_json.get("projectId")
        user_message = request_json.get("message", "").strip()
        file_content = request_json.get("fileContent")
        chat_history = request_json.get("chatHistory", [])  # Get chat history from frontend
    except Exception as e:
        print(f"ERROR parsing request: {e}")
        return ({"error": f"Invalid JSON payload: {e}"}, 400, headers)

    if not project_id: return ({"error": "projectId is required"}, 400, headers)

    bucket = storage_client.bucket(BUCKET_NAME)
    state_blob = bucket.blob(f"Jetstream/{project_id}/project_state.json")

    # --- CORRECTED STATE LOADING ---
    # Always load the state at the beginning to get the latest chat history
    try:
        project_state = json.loads(state_blob.download_as_string())
        print(f"[{project_id}] Loaded existing state. History length: {len(project_state.get('chatHistory', []))}")
    except Exception:
        project_state = {"projectId": project_id, "stage": "ESR", "summary": "", "chatHistory": [], "assets": {}}
        print(f"[{project_id}] Creating new state.")
    # --- END CORRECTION ---

    if file_content:
        # --- Flow 1: Initial Analysis (Background Task) ---
        notes_to_analyze = file_content
        if user_message:
             notes_to_analyze += f"\n\n--- Additional Notes ---\n{user_message}"
             project_state["chatHistory"].append({"sender": "user", "text": f"(File Uploaded) {user_message}"})
        else:
             # Add a placeholder user message for the history even if only file uploaded
             project_state["chatHistory"].append({"sender": "user", "text": "(File Uploaded)"})


        if not notes_to_analyze:
             return ({"error": "No content provided in file to analyze"}, 400, headers)

        task_id = str(uuid.uuid4())
        print(f"[{project_id}] Starting background analysis task: {task_id}")
        thread = threading.Thread(target=run_analysis_in_background, args=(task_id, notes_to_analyze, project_id))
        thread.start()

        # Save state *before* returning task ID to record the user's upload message
        state_blob.upload_from_string(json.dumps(project_state, indent=2), content_type="application/json")
        return ({"taskId": task_id}, 202, headers)

    elif user_message:
        # --- Flow 2: Follow-up Question (Synchronous Task) ---
        print(f"[{project_id}] Handling follow-up question...")
        print(f"[{project_id}] Received chat history from frontend: {len(chat_history)} messages")
        
        # Use the chat history from the frontend (which includes the current message)
        # instead of the stored project state
        if chat_history:
            # The frontend already includes the current user message in chat_history
            complete_history = chat_history
        else:
            # Fallback to stored history if frontend didn't send it
            complete_history = project_state["chatHistory"]
            complete_history.append({"sender": "user", "text": user_message})

        # Call the synchronous function with the COMPLETE history from frontend
        assistant_response = get_follow_up_response(complete_history, user_message)
        
        # Add the assistant's response to the history
        complete_history.append({"sender": "assistant", "text": assistant_response})
        
        # Update project state with the complete history
        project_state["chatHistory"] = complete_history

        # Save the updated history and return it directly
        state_blob.upload_from_string(json.dumps(project_state, indent=2), content_type="application/json")
        print(f"[{project_id}] Follow-up response generated. History length: {len(complete_history)}")
        return ({"chatHistory": complete_history}, 200, headers)

    else:
        # No file and no message - return current state or error
        print(f"[{project_id}] No new input received, returning current state.")
        if not project_state["chatHistory"]:
             project_state["chatHistory"] = [{"sender": "assistant", "text": f"Welcome to Project {project_id}!"}]
        # Save state just in case it was newly created
        state_blob.upload_from_string(json.dumps(project_state, indent=2), content_type="application/json")
        return ({"chatHistory": project_state["chatHistory"]}, 200, headers)