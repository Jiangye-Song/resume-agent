const form = document.getElementById('chat-form');
const input = document.getElementById('question');
const messages = document.getElementById('messages');

function appendMessage(text, from='bot'){
  const wrapper = document.createElement('div');
  wrapper.className = 'message ' + (from === 'user' ? 'user' : 'bot');
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  // Hide any internal thinking/debug sections wrapped in <think>...</think>
  function hideThink(s){
    if(!s || typeof s !== 'string') return s;
    return s.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
  }

  const displayed = from === 'bot' ? hideThink(text) : text;
  if(from === 'bot'){
    // Render markdown -> HTML and sanitize it to avoid XSS
    try{
      const rawHtml = marked.parse(displayed || '');
      const clean = DOMPurify.sanitize(rawHtml);
      bubble.innerHTML = clean;
    }catch(e){
      bubble.textContent = displayed;
    }
  }else{
    bubble.textContent = displayed;
  }
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
  appendMessage('_Virtual Jiangye is typing a message..._', 'bot');

  try{
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q })
    });

    // Parse JSON when possible. If parsing fails, clone the response and
    // read the text from the clone so we don't attempt to read the same
    // body stream twice (which causes "body stream already read").
    let data;
    try {
      data = await res.json();
    } catch (parseErr) {
      try {
        const clone = res.clone();
        const text = await clone.text();
        throw new Error(text || parseErr.message);
      } catch (inner) {
        // If cloning/reading also fails, throw the original parse error message
        throw new Error(parseErr.message || 'Response parse error');
      }
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

// Quick suggestion questions functionality
const questions = [
  "What are your strongest technical skills?",
  "Can you summarize your most recent project?", 
  "Which project best demonstrates your frontend experience?",
  "Have you worked with cloud deployment or serverless architecture?",
  "Tell me about a project where you used machine learning.",
  "What is the most challenging problem you've solved so far?",
  "Which project highlights your teamwork and collaboration skills?",
  "Do you have any experience working with vector databases or RAG systems?",
  "What programming languages and frameworks do you use?",
  "Tell me about your experience with database design."
];

function pickRandom(arr, count) {
  const shuffled = [...arr].sort(() => 0.5 - Math.random());
  return shuffled.slice(0, count);
}

function renderSuggestions() {
  const container = document.getElementById("question-buttons");
  if (!container) return;
  
  container.innerHTML = "";
  const randomQs = pickRandom(questions, 3);
  
  randomQs.forEach(q => {
    const btn = document.createElement("button");
    btn.textContent = q;
    btn.className = "suggestion-btn";
    btn.type = "button"; // Prevent form submission
    btn.onclick = () => {
      const input = document.getElementById("question");
      if (input) {
        input.value = q;
        input.focus();
        // Hide suggestions after selecting one
        document.getElementById("suggestions").style.display = "none";
      }
    };
    container.appendChild(btn);
  });
}

// Show suggestions again when input is cleared
input.addEventListener('input', () => {
  const suggestionsDiv = document.getElementById("suggestions");
  if (input.value.trim() === '') {
    suggestionsDiv.style.display = "block";
    renderSuggestions(); // Refresh suggestions when input is cleared
  } else {
    suggestionsDiv.style.display = "none";
  }
});

// Initial render
document.addEventListener("DOMContentLoaded", () => {
  renderSuggestions();
});
