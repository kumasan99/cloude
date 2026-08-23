const chatContainer = document.getElementById("chatContainer");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");

let currentMode = "chat";
let conversations = {
  chat: [],
  financial: [],
  plan: [],
  kodama: [],
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
  kodama: {
    icon: "🎙️",
    title: "コダマ（音声記録部）",
    desc: "会議・商談・アイデアを声で吹き込むと、議事録や整理されたメモに変換します。<br>マイクボタン（🎤）を押して話すか、文字起こしテキストを貼り付けてください。",
    examples: [
      "えーと、今日の営業会議のメモ。新商品の価格は税込1980円に決定。田中さんが来週金曜までにチラシ案を作成。あと駅前店の改装は10月に延期。これを議事録にして。",
      "音声メモです。新しくランチ営業を始めるアイデアを思いついた。近くのオフィス街がターゲットで、テイクアウト中心。これを整理して課題も挙げて。",
      "今日の日報。午前は3件訪問、うち1件は見積もり依頼あり。午後は在庫確認と発注作業。明日は銀行と面談。整理してまとめて。",
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

  const avatar = role === "assistant" ? "🎯" : "👤";
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
    <div class="message-avatar">🎯</div>
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
  if (isRecording) stopRecording();

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

// --- コダマ: 音声入力 (Web Speech API) ---
const micBtn = document.getElementById("micBtn");
const recordingBar = document.getElementById("recordingBar");
const recordingTime = document.getElementById("recordingTime");

const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

let recognition = null;
let isRecording = false;
let transcriptBase = "";
let recordingSeconds = 0;
let recordingTimer = null;

if (!SpeechRecognitionAPI) {
  micBtn.disabled = true;
  micBtn.title = "このブラウザは音声入力に対応していません（Chrome / Edge / Safari をお使いください）";
}

function toggleRecording() {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

function startRecording() {
  if (!SpeechRecognitionAPI || isRecording) return;

  recognition = new SpeechRecognitionAPI();
  recognition.lang = "ja-JP";
  recognition.continuous = true;
  recognition.interimResults = true;

  transcriptBase = messageInput.value ? messageInput.value.replace(/\s+$/, "") + " " : "";

  recognition.onresult = (event) => {
    let finalText = "";
    let interimText = "";
    for (let i = 0; i < event.results.length; i++) {
      const result = event.results[i];
      if (result.isFinal) {
        finalText += result[0].transcript;
      } else {
        interimText += result[0].transcript;
      }
    }
    messageInput.value = transcriptBase + finalText + interimText;
    messageInput.style.height = "auto";
    messageInput.style.height = messageInput.scrollHeight + "px";
  };

  recognition.onerror = (event) => {
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      stopRecording();
      alert("マイクの使用が許可されていません。ブラウザの設定でマイクへのアクセスを許可してください。");
    }
    // "no-speech" 等は onend の自動再開に任せる
  };

  // Chromeは無音が続くと自動停止するため、録音中は再開する
  recognition.onend = () => {
    if (isRecording) {
      transcriptBase = messageInput.value ? messageInput.value.replace(/\s+$/, "") + " " : "";
      try {
        recognition.start();
      } catch (e) {
        stopRecording();
      }
    }
  };

  try {
    recognition.start();
  } catch (e) {
    return;
  }

  isRecording = true;
  micBtn.classList.add("recording");
  recordingBar.hidden = false;
  recordingSeconds = 0;
  recordingTime.textContent = "0:00";
  recordingTimer = setInterval(() => {
    recordingSeconds++;
    const m = Math.floor(recordingSeconds / 60);
    const s = String(recordingSeconds % 60).padStart(2, "0");
    recordingTime.textContent = `${m}:${s}`;
  }, 1000);
}

function stopRecording() {
  isRecording = false;
  if (recognition) {
    recognition.onend = null;
    try {
      recognition.stop();
    } catch (e) {}
    recognition = null;
  }
  micBtn.classList.remove("recording");
  recordingBar.hidden = true;
  clearInterval(recordingTimer);
  recordingTimer = null;
  messageInput.focus();
}
