<script>
  import ChatBubble from './lib/ChatBubble.svelte';
  import MarkdownRenderer from './components/MarkdownRenderer.svelte';

  // --- NEW: Project State ---
  let projectId = ''; // This will store the name of our current project.

  let messages = [
    {
      id: 1,
      sender: 'assistant',
      // The first message now prompts for the project name.
      text: 'Hello! Welcome to Jetstream. To begin, please enter a name for this new project.'
    }
  ];
  
  let messageInput = '';
  let messageId = 2;
  let textareaElement;
  let selectedFiles = [];
  let isDragOver = false;
  let isUploading = false;

  // Prevent default drag behavior on the entire page
  function preventDefaultDrag(event) {
    event.preventDefault();
  }
  
  // Function to auto-resize textarea
  function autoResize() {
    if (textareaElement) {
      textareaElement.style.height = 'auto';
      textareaElement.style.height = textareaElement.scrollHeight + 'px';
    }
  }

  // Function to reset textarea height
  function resetTextarea() {
    if (textareaElement) {
      textareaElement.style.height = 'auto';
      // Force a reflow to ensure the height is reset
      textareaElement.offsetHeight;
    }
  }

  // Call autoResize when messageInput changes, but only if there's content
  $: if (textareaElement && messageInput) {
    autoResize();
  }

  // File handling functions
  function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    selectedFiles = files;
  }

  function removeFile(index) {
    selectedFiles = selectedFiles.filter((_, i) => i !== index);
  }

  // Drag and drop handlers
  function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = 'copy';
    isDragOver = true;
  }

  function handleDragEnter(event) {
    event.preventDefault();
    event.stopPropagation();
    isDragOver = true;
  }

  function handleDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    // Only set isDragOver to false if we're leaving the entire drop zone
    if (!event.currentTarget.contains(event.relatedTarget)) {
      isDragOver = false;
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    isDragOver = false;
    const files = Array.from(event.dataTransfer.files);
    selectedFiles = files;
  }
  
  async function handleSend() {
    // --- NEW: Logic to handle the first message as the Project ID ---
    if (!projectId) {
      if (!messageInput.trim()) return; // Don't allow an empty project name
      
      projectId = messageInput.trim();
      messages = [...messages, { id: Date.now(), sender: 'user', text: messageInput }];
      
      // Update the assistant's next message
      const welcomeText = `Great! We've started project "${projectId}". You can now upload files or paste your notes to begin the analysis.`;
      messages = [...messages, { id: Date.now() + 1, sender: 'assistant', text: welcomeText }];
      
      messageInput = ''; // Clear input for the next message
      return; // Stop here for the first message
    }
    // --- End of new logic ---

    // Determine if this is primarily a file upload or a text message
    const isFileUpload = selectedFiles.length > 0;
    const userMessageText = messageInput || (isFileUpload ? `(Files: ${selectedFiles.map(f => f.name).join(', ')})` : '');
    
    if (!userMessageText && !isFileUpload) return; // Don't send if truly empty

    messages = [...messages, { id: Date.now(), sender: 'user', text: userMessageText }];
    const assistantMessageId = Date.now() + 1;
    // Use a more generic initial status
    const assistantMessage = { id: assistantMessageId, sender: 'assistant', text: 'Processing...', typing: true };
    messages = [...messages, assistantMessage];

    const filesToProcess = [...selectedFiles];
    const messageFromInput = messageInput;
    messageInput = '';
    selectedFiles = [];
    isUploading = true; 
    setTimeout(() => { resetTextarea(); }, 0);

    let fileContent = '';
    if (filesToProcess.length > 0) {
        // --- Multi-file reading logic ---
        const fileContents = [];
        for (let i = 0; i < filesToProcess.length; i++) {
            const file = filesToProcess[i];
            const readFileAsText = (fileToRead) => new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = (error) => reject(error);
                reader.readAsText(fileToRead);
            });
            try {
                const content = await readFileAsText(file);
                fileContents.push(`--- NEW FILE: ${file.name} ---\n${content}`);
            } catch (e) {
                 console.error("Error reading file:", e);
                 messages = messages.map(msg => msg.id === assistantMessageId ? { ...msg, text: `Sorry, error reading file: ${file.name}` } : msg);
                 isUploading = false;
                 return;
            }
        }
        fileContent = fileContents.join('\n\n');
        // --- End file reading ---
    }

    // --- CORE LOGIC CHANGE: Determine Fetch Path ---
    try {
        const payload = {
            projectId: projectId,
            message: messageFromInput,
            fileContent: fileContent
        };

        const response = await fetch("https://us-central1-airship-ai-value-poc-2024.cloudfunctions.net/jetstream-main-orchestrator", {
            method: 'POST',
            body: JSON.stringify(payload),
            headers: { 'Content-Type': 'application/json' },
        });

        // --- NEW: Check response status to determine flow ---
        if (response.status === 202) {
            // --- Flow 1: Background Task Started (Initial Analysis) ---
            const { taskId } = await response.json();
            if (!taskId) throw new Error("Did not receive a task ID from the orchestrator.");
            
            // Start polling (pass taskId and assistantMessageId as parameters)
            setTimeout(() => pollStatus(taskId, assistantMessageId), 1000); 

        } else if (response.status === 200) {
            // --- Flow 2: Immediate Response Received (Follow-up Question) ---
            const data = await response.json();
            messages = data.chatHistory; // Update history directly
            isUploading = false; // Mark task as complete

        } else {
             // Handle unexpected backend errors
             const errorData = await response.json();
             throw new Error(`Backend returned an error: ${errorData.error || response.statusText}`);
        }

    } catch (error) {
        console.error("Error in handleSend:", error);
        let currentAssistantMessage = messages.find(m => m.id === assistantMessageId);
        if (currentAssistantMessage) {
            currentAssistantMessage.text = `Sorry, an error occurred: ${error.message}`;
            currentAssistantMessage.typing = false; // Remove typing indicator
            messages = messages;
        }
        isUploading = false;
    }
  }

  // Ensure pollStatus function accepts taskId and assistantMessageId as arguments
  async function pollStatus(taskId, assistantMessageId) {
    try {
        const statusResponse = await fetch("https://us-central1-airship-ai-value-poc-2024.cloudfunctions.net/jetstream-status-checker", {
            method: 'POST',
            body: JSON.stringify({ taskId }),
            headers: { 'Content-Type': 'application/json' },
        });

        if (!statusResponse.ok) {
            throw new Error(`Status check failed: ${statusResponse.statusText}`);
        }

        const statusData = await statusResponse.json();
        let currentAssistantMessage = messages.find(m => m.id === assistantMessageId);

        if (statusData.status === 'complete') {
            if (currentAssistantMessage) {
                currentAssistantMessage.text = statusData.result;
                currentAssistantMessage.typing = false; // Remove typing indicator
                messages = messages; // Trigger reactivity
                isUploading = false;
            }
        } else if (statusData.status.startsWith('Error:')) {
             if (currentAssistantMessage) {
                currentAssistantMessage.text = `Analysis Failed: ${statusData.status}`;
                currentAssistantMessage.typing = false; // Remove typing indicator
                messages = messages;
                isUploading = false;
            }
        }
        else {
            if (currentAssistantMessage) {
                currentAssistantMessage.text = statusData.status + '...';
                currentAssistantMessage.typing = true; // Add typing indicator
                messages = messages;
            }
            setTimeout(() => pollStatus(taskId, assistantMessageId), 3000); // Poll again with parameters
        }
    } catch (pollError) {
         console.error("Error polling status:", pollError);
         let currentAssistantMessage = messages.find(m => m.id === assistantMessageId);
         if (currentAssistantMessage) {
            currentAssistantMessage.text = "Sorry, lost connection while checking status.";
            currentAssistantMessage.typing = false; // Remove typing indicator
            messages = messages;
         }
         isUploading = false;
    }
  }

  
  function handleKeyPress(event) {
    if (event.key === 'Enter') {
      handleSend();
    }
  }
</script>

<div class="app" 
     role="application"
     on:dragover={preventDefaultDrag}
     on:drop={preventDefaultDrag}>
  <!-- Header -->
  <header class="header">
    <div class="header-content">
      <h1>Jetstream</h1>
      <img src="/airship-logo.png" alt="Airship" class="airship-logo" />
  </div>
  </header>
  
  <!-- Main Chat Area -->
  <main class="chat-area">
    <div class="messages-container">
      {#each messages as message (message.id)}
        <ChatBubble {message} />
      {/each}
  </div>
</main>
  
  <!-- Footer with Input -->
  <footer class="input-footer">
    <div class="chat-input-area {isDragOver ? 'drag-over' : ''}" 
         role="button"
         tabindex="0"
         on:dragover={handleDragOver}
         on:dragenter={handleDragEnter}
         on:dragleave={handleDragLeave}
         on:drop={handleDrop}>
      <input type="file" id="fileUpload" class="file-input" multiple accept="*/*" on:change={handleFileSelect} />
      <label for="fileUpload" class="file-input-label">
        <span class="material-icons">attach_file</span>
      </label>

      <div class="input-container">
        <!-- Drag Overlay -->
        {#if isDragOver}
          <div class="drag-overlay">
            <div class="drag-indicator">
              <span class="material-icons">cloud_upload</span>
              <span>Drop files here</span>
            </div>
          </div>
        {/if}

        <!-- Gemini-style File Cards -->
        {#if selectedFiles.length > 0}
          <div class="file-cards-container">
            {#each selectedFiles as file, index (index)}
              <div class="file-card {isUploading ? 'uploading' : ''}">
                <div class="file-thumbnail">
                  {#if isUploading}
                    <div class="upload-spinner">
                      <div class="spinner-ring"></div>
                    </div>
                  {:else}
                    <div class="file-type-icon">
                      {#if file.name.toLowerCase().endsWith('.pdf')}
                        <span class="file-type">PDF</span>
                      {:else if file.name.toLowerCase().endsWith('.txt')}
                        <span class="file-type">TXT</span>
                      {:else if file.name.toLowerCase().endsWith('.doc') || file.name.toLowerCase().endsWith('.docx')}
                        <span class="file-type">DOC</span>
                      {:else}
                        <span class="file-type">FILE</span>
                      {/if}
                    </div>
                  {/if}
                </div>
                <div class="file-details">
                  <div class="file-name">{file.name}</div>
                  <div class="file-size">{(file.size / 1024).toFixed(1)} KB</div>
                </div>
                {#if !isUploading}
                  <button class="remove-file-btn" on:click={() => removeFile(index)}>
                    <span class="material-icons">close</span>
                  </button>
                {/if}
              </div>
            {/each}
          </div>
        {/if}

        <textarea
          bind:this={textareaElement}
          bind:value={messageInput}
          on:input={autoResize}
          on:keydown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Type your message or paste notes..."
          rows={1}
          class="chat-input"
        ></textarea>
      </div>
      
      <button 
        class="send-button" 
        on:click={handleSend}
        disabled={!messageInput.trim() && selectedFiles.length === 0}
      >
        <span class="material-icons">send</span>
      </button>
    </div>
  </footer>
</div>

<style>
  .app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: #ffffff;
  }
  
  .header {
    background-color: #ffffff;
    border-bottom: 1px solid #e8eaed;
    padding: 1rem 0;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  }
  
  .header-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1.5rem;
  }
  
  .airship-logo {
    width: 36px;
    height: auto;
    object-fit: contain;
  }
  
  .header h1 {
    margin: 0;
    font-size: 1.375rem;
    font-weight: 400;
    color: #202124;
    letter-spacing: 0;
  }
  
  .chat-area {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background-color: #ffffff;
  }
  
  .messages-container {
    flex: 1;
    overflow-y: auto;
    scroll-behavior: smooth;
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
  }
  
  .input-footer {
    background-color: #ffffff;
    border-top: 1px solid #e8eaed;
    padding: 1.5rem;
  }
  
  .chat-input-area {
    display: flex;
    align-items: flex-end;
    padding: 10px;
    background-color: #ffffff;
    border-top: 1px solid #e8eaed;
    max-width: 800px;
    margin: 0 auto;
    position: relative;
    transition: all 0.2s ease;
  }

  .chat-input-area.drag-over {
    background-color: #e3f2fd;
    border-color: #1a73e8;
    border-style: dashed;
  }

  .drag-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(26, 115, 232, 0.1);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
    border-radius: 8px;
  }

  .drag-indicator {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    color: #1a73e8;
    font-weight: 500;
  }

  .drag-indicator .material-icons {
    font-size: 2rem;
  }

  .input-container {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    margin-right: 10px;
  }

  .file-cards-container {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 16px;
  }

  .file-card {
    display: flex;
    flex-direction: column;
    background-color: #2d2d2d;
    border: 1px solid #404040;
    border-radius: 12px;
    padding: 12px;
    width: 120px;
    height: 100px;
    position: relative;
    transition: all 0.3s ease;
  }

  .file-card.uploading {
    background-color: #1a1a1a;
    border-color: #4a4a4a;
  }

  .file-thumbnail {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 40px;
    margin-bottom: 8px;
  }

  .file-type-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    background-color: #404040;
    border-radius: 6px;
  }

  .file-type {
    font-size: 10px;
    font-weight: 600;
    color: #ffffff;
    text-transform: uppercase;
  }

  .upload-spinner {
    position: relative;
    width: 24px;
    height: 24px;
  }

  .spinner-ring {
    width: 24px;
    height: 24px;
    border: 2px solid #404040;
    border-top: 2px solid #ffffff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .file-details {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }

  .file-name {
    font-size: 11px;
    font-weight: 500;
    color: #ffffff;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-bottom: 4px;
    line-height: 1.2;
  }

  .file-size {
    font-size: 10px;
    color: #a0a0a0;
    opacity: 0.8;
  }

  .remove-file-btn {
    position: absolute;
    top: 4px;
    right: 4px;
    background: rgba(0, 0, 0, 0.6);
    border: none;
    color: #ffffff;
    cursor: pointer;
    padding: 2px;
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    transition: background-color 0.2s ease;
  }

  .remove-file-btn:hover {
    background: rgba(0, 0, 0, 0.8);
  }

  .remove-file-btn .material-icons {
    font-size: 12px;
  }

  .chat-input {
    flex-grow: 1;
    padding: 10px 15px;
    border: 1px solid #dadce0;
    border-radius: 20px;
    font-size: 1em;
    resize: none;
    overflow-y: auto;
    max-height: 150px;
    line-height: 1.4;
    box-sizing: border-box;
    outline: none;
    transition: all 0.2s ease;
    background-color: #ffffff;
    color: #202124;
  }

  .chat-input:focus {
    border-color: #1a73e8;
    box-shadow: 0 0 0 1px #1a73e8;
  }

  .chat-input::placeholder {
    color: #5f6368;
  }

  .send-button, .file-input-label {
    background-color: #1a73e8;
    color: white;
    border: none;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    display: flex;
    justify-content: center;
    align-items: center;
    cursor: pointer;
    font-size: 1.2em;
    margin-left: 5px;
    transition: background-color 0.2s ease-in-out;
  }

  .send-button:hover:not(:disabled), .file-input-label:hover {
    background-color: #1557b0;
  }

  .send-button:disabled {
    background-color: #dadce0;
    color: #5f6368;
    cursor: not-allowed;
  }

  .file-input {
    display: none;
  }
</style>
