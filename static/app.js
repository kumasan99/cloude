const chatContainer = document.getElementById("chatContainer");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");

let currentMode = "chat";
let conversations = {
  chat: [],
  financial: [],
  plan: [],
  sebastian: [],
};

const assistantAvatars = {
  chat: "🎯",
  financial: "🎯",
  plan: "🎯",
  sebastian: "🤵",
};

const welcomeMessages = {
  chat: {
    icon: "🏢",
    title: "経営相談モード",
    desc: "経営に関するお悩みをお聞かせください。<br>具体的な状況を教えていただけると、より的確なアドバイスが可能です。",
    examples: [
      "売上が伸び悩んでいます。どう改善すればいいですか？",
      "新規事業を始めたいのですが、何から手をつければいいですか？",
      "人材採用がうまくいきません。アドバイスをください。",
    ],
  },
  financial: {
    icon: "📊",
    title: "財務アドバイスモード",
    desc: "売上・コスト・利益率などの数値をお伝えください。<br>財務状況を分析し、改善策をご提案します。",
    examples: [
      "月商500万円で利益率が5%です。改善策はありますか？",
      "資金繰りが厳しくなっています。キャッシュフロー改善のアドバイスをください。",
      "設備投資3000万円を検討中です。投資判断のポイントを教えてください。",
    ],
  },
  plan: {
    icon: "📋",
    title: "事業計画作成モード",
    desc: "事業計画書の作成をお手伝いします。<br>まずは事業の概要をお聞かせください。",
    examples: [
      "カフェを開業したいです。事業計画書を一緒に作ってください。",
      "ECサイトの立ち上げを計画しています。計画書の構成を教えてください。",
      "既存事業の拡大計画を作りたいです。何を準備すればいいですか？",
    ],
  },
  sebastian: {
    icon: "🤵",
    title: "セバス（執事）モード",
    desc: "お帰りなさいませ、旦那様。<br>経営のお悩みから日々の雑事まで、何なりとセバスにお申し付けください。",
    examples: [
      "セバス、最近少し疲れが溜まっていてね。",
      "今日の会議がうまくいかなかった。話を聞いてくれないか。",
      "来週の商談に向けて、心構えを助言してほしい。",
    ],
  },
};

// Tab switching
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelector(".tab.active").classList.remove("active");
    tab.classList.add("active");
    currentMode = tab.dataset.mode;
    renderChat();
  });
});

// Auto-resize textarea
messageInput.addEventListener("input", () => {
  messageInput.style.height = "auto";
  messageInput.style.height = messageInput.scrollHeight + "px";
});

// Enter to send (Shift+Enter for newline)
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

function renderChat() {
  const msgs = conversations[currentMode];
  if (msgs.length === 0) {
    renderWelcome();
    return;
  }
  chatContainer.innerHTML = "";
  msgs.forEach((msg) => appendMessageToDOM(msg.role, msg.content));
  scrollToBottom();
}

function renderWelcome() {
  const w = welcomeMessages[currentMode];
  chatContainer.innerHTML = `
    <div class="welcome-message">
      <div class="welcome-icon">${w.icon}</div>
      <h2>${w.title}</h2>
      <p>${w.desc}</p>
      <div class="example-questions">
        ${w.examples.map((q) => `<button class="example-btn" onclick="sendExample(this)">${q}</button>`).join("")}
      </div>
    </div>
  `;
}

function appendMessageToDOM(role, content) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const avatar = role === "assistant" ? (assistantAvatars[currentMode] || "🎯") : "👤";
  const rendered = role === "assistant" ? renderMarkdown(content) : escapeHtml(content);

  div.innerHTML = `
    <div class="message-avatar">${avatar}</div>
    <div class="message-bubble">${rendered}</div>
  `;
  chatContainer.appendChild(div);
}

function renderMarkdown(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/### (.+)/g, "<h3>$1</h3>")
    .replace(/## (.+)/g, "<h2>$1</h2>")
    .replace(/# (.+)/g, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^\- (.+)/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
    .replace(/(<\/ul>\s*<ul>)/g, "")
    .replace(/^\d+\. (.+)/gm, "<li>$1</li>");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "message assistant";
  div.id = "typingMessage";
  div.innerHTML = `
    <div class="message-avatar">${assistantAvatars[currentMode] || "🎯"}</div>
    <div class="message-bubble">
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  chatContainer.appendChild(div);
  scrollToBottom();
}

function removeTyping() {
  const el = document.getElementById("typingMessage");
  if (el) el.remove();
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text) return;

  messageInput.value = "";
  messageInput.style.height = "auto";

  // Remove welcome if present
  const welcome = chatContainer.querySelector(".welcome-message");
  if (welcome) welcome.remove();

  // Add user message
  conversations[currentMode].push({ role: "user", content: text });
  appendMessageToDOM("user", text);
  scrollToBottom();

  // Disable input
  sendBtn.disabled = true;
  messageInput.disabled = true;
  showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: currentMode,
        messages: conversations[currentMode],
      }),
    });

    const data = await res.json();
    removeTyping();

    conversations[currentMode].push({
      role: "assistant",
      content: data.content,
    });
    appendMessageToDOM("assistant", data.content);
    scrollToBottom();
  } catch (err) {
    removeTyping();
    appendMessageToDOM("assistant", "申し訳ありません。エラーが発生しました。しばらくしてからお試しください。");
  } finally {
    sendBtn.disabled = false;
    messageInput.disabled = false;
    messageInput.focus();
  }
}

function sendExample(btn) {
  messageInput.value = btn.textContent;
  sendMessage();
}
