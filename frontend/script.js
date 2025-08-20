const form = document.getElementById('chat-form');
const input = document.getElementById('question');
const messages = document.getElementById('messages');

function appendMessage(text, from='bot'){
  const wrapper = document.createElement('div');
  wrapper.className = 'message ' + (from === 'user' ? 'user' : 'bot');
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  wrapper.appendChild(bubble);
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
}

form.addEventListener('submit', async (e) =>{
  e.preventDefault();
  const q = input.value.trim();
  if(!q) return;
  appendMessage(q, 'user');
  input.value = '';
  appendMessage('...', 'bot');

  try{
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q })
    });

    // Try to parse JSON; if response isn't JSON (e.g. HTML error page),
    // fall back to text so we can show a helpful error message instead of a parse exception.
    let data;
    try {
      data = await res.json();
    } catch (parseErr) {
      const text = await res.text();
      throw new Error(text || parseErr.message);
    }
    // remove the last '...' message
    const last = messages.querySelector('.message.bot:last-child');
    if(last) last.remove();

    if(data.error){
      appendMessage('Error: ' + data.error, 'bot');
    } else {
      appendMessage(data.answer || 'No answer', 'bot');
    }
  } catch(err){
    const last = messages.querySelector('.message.bot:last-child');
    if(last) last.remove();
    appendMessage('Network error: ' + err.message, 'bot');
  }
});
