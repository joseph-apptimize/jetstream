<script>
  import MarkdownRenderer from '../components/MarkdownRenderer.svelte';
  export let message;
</script>

<div class="message-container {message.sender}">
  <div class="message-content">
    {#if message.sender === 'user'}
      {message.text}
    {:else}
      {#if message.typing}
        <div class="processing-indicator">
          <div class="spinner"></div>
        </div>
      {/if}
      <MarkdownRenderer content={message.text} />
    {/if}
  </div>
</div>

<style>
  .message-container {
    display: flex;
    margin: 0;
    padding: 1.5rem 0;
    border-bottom: 1px solid #e8eaed;
  }

  .message-container.user {
    background-color: #f8f9fa;
    justify-content: flex-start;
  }

  .message-container.assistant {
    background-color: #ffffff;
    justify-content: flex-start;
  }

  .message-content {
    max-width: 100%;
    padding: 0 1.5rem;
    font-size: 1rem;
    line-height: 1.6;
    word-wrap: break-word;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #202124;
    display: flex;
    align-items: center;
  }

  .user .message-content {
    color: #1a73e8;
    font-weight: 500;
  }

  .assistant .message-content {
    color: #202124;
  }

  /* Processing indicator with spinner */
  .processing-indicator {
    display: inline-flex;
    align-items: center;
    margin-right: 8px;
    vertical-align: middle;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid #e8eaed;
    border-top: 2px solid #1a73e8;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
</style>
