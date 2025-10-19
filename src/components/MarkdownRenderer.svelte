<script>
    import { marked } from 'marked';
    export let content;

    $: renderedHtml = marked.parse(content || '');
</script>

<div class="markdown-content">
    {@html renderedHtml}
</div>

<style>
    .markdown-content :global(h1),
    .markdown-content :global(h2),
    .markdown-content :global(h3) {
        margin-top: 1em;
        margin-bottom: 0.5em;
        padding-bottom: 0.2em;
        border-bottom: 1px solid #e8eaed;
        font-weight: bold;
    }

    .markdown-content :global(h1) { font-size: 1.8em; }
    .markdown-content :global(h2) { font-size: 1.5em; }
    .markdown-content :global(h3) { font-size: 1.2em; }

    .markdown-content :global(p) {
        margin-bottom: 0.8em;
        line-height: 1.5;
    }

    .markdown-content :global(ul),
    .markdown-content :global(ol) {
        margin-bottom: 0.8em;
        padding-left: 1.5em;
    }

    .markdown-content :global(strong),
    .markdown-content :global(b) {
        font-weight: bold;
    }

    /* Basic styling for code blocks if you expect them */
    .markdown-content :global(pre) {
        background-color: #f4f4f4;
        padding: 10px;
        border-radius: 5px;
        overflow-x: auto;
    }
    .markdown-content :global(code) {
        font-family: monospace;
    }
</style>
