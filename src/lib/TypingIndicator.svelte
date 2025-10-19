<script>
  // Simple typing indicator with animated dots
</script>

<div class="typing-indicator">
  <div class="typing-dots">
    <span class="dot"></span>
    <span class="dot"></span>
    <span class="dot"></span>
  </div>
  <span class="typing-text">Assistant is typing...</span>
</div>

<style>
  .typing-indicator {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1.5rem;
    background-color: #ffffff;
    border-bottom: 1px solid #e8eaed;
    animation: fadeIn 0.3s ease-in;
  }

  .typing-dots {
    display: flex;
    gap: 0.25rem;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #1a73e8;
    animation: typing 1.4s infinite ease-in-out;
  }

  .dot:nth-child(1) {
    animation-delay: -0.32s;
  }

  .dot:nth-child(2) {
    animation-delay: -0.16s;
  }

  .dot:nth-child(3) {
    animation-delay: 0s;
  }

  .typing-text {
    font-size: 0.875rem;
    color: #5f6368;
    font-style: italic;
  }

  @keyframes typing {
    0%, 80%, 100% {
      transform: scale(0.8);
      opacity: 0.5;
    }
    40% {
      transform: scale(1);
      opacity: 1;
    }
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>

