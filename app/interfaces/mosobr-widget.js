(function () {
  const DEFAULT_TITLE = "AI - Амбассадор профессий Амби";
  const DEFAULT_API = "/ambi/v1/dialog";
  const LINK_RE = /((?:https?:\/\/|www\.)[^\s<>"']+|(?:[a-z0-9-]+\.)+(?:ru|com|org|net|edu|gov|рф)(?:\/[^\s<>"']*)?|мос\.ру(?:\/[^\s<>"']*)?)/gi;
  const AMBI_AVATAR_SVG = `
    <svg viewBox="0 0 96 96" aria-hidden="true" focusable="false">
      <circle cx="48" cy="48" r="45" fill="#fff" stroke="#e3132c" stroke-width="6"/>
      <circle cx="31" cy="31" r="12" fill="#e3132c"/>
      <circle cx="65" cy="31" r="12" fill="#e3132c"/>
      <circle cx="31" cy="31" r="6" fill="#fff"/>
      <circle cx="65" cy="31" r="6" fill="#fff"/>
      <rect x="18" y="29" width="60" height="40" rx="20" fill="#e3132c"/>
      <rect x="25" y="36" width="46" height="24" rx="12" fill="#fff"/>
      <rect x="30" y="39" width="36" height="18" rx="9" fill="#e3132c"/>
      <circle cx="40" cy="48" r="3.5" fill="#fff"/>
      <circle cx="56" cy="48" r="3.5" fill="#fff"/>
      <path d="M43 53c3 4 7 4 10 0" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"/>
      <circle cx="76" cy="49" r="6" fill="#fff"/>
      <circle cx="76" cy="49" r="3" fill="#293241"/>
      <path d="M22 65c4 10 13 16 26 16s22-6 26-16" fill="#e3132c"/>
      <rect x="38" y="65" width="20" height="15" rx="4" fill="#fff"/>
      <path d="M43 69h10M43 69v8M53 69v8M43 77h10" fill="none" stroke="#e3132c" stroke-width="2" stroke-linecap="round"/>
    </svg>
  `;

  const LABELS = {
    parent: "Хочу узнать информацию",
    applicant: "Хочу поступить",
    end: "Завершить сессию",
    menu: "Главное меню",
  };
  const MAIN_MENU_SUGGESTIONS = [
    { label: "Выбрать колледж", action: "route_college" },
    { label: "Выбрать профессию", action: "route_profession" },
    { label: "Узнать о порядке поступления", action: "route_admission" },
    { label: "Свой вопрос", action: "route_custom" },
  ];
  const GREETING_TEXT = "Привет! Я - Амби, AI-амбассадор колледжей Москвы, помогаю выбрать профессию и ознакомиться с поступлением в колледжи Москвы.\nДавай выберем, с чего начать.";

  function ensureStyles() {
    if (document.getElementById("mosobr-widget-style")) return;

    const style = document.createElement("style");
    style.id = "mosobr-widget-style";
    style.textContent = `
      .mosobr-launcher {
        position: fixed;
        right: 22px;
        bottom: 22px;
        z-index: 2147483000;
        width: 70px;
        height: 70px;
        border: 0;
        border-radius: 22px;
        background: linear-gradient(145deg, #fff 0%, #fff 52%, #ffe8ec 100%);
        color: #fff;
        box-shadow: 0 18px 42px rgba(159, 18, 57, .28);
        cursor: pointer;
        transition: transform .16s ease, box-shadow .16s ease;
      }

      .mosobr-launcher:hover {
        transform: translateY(-2px);
        box-shadow: 0 22px 52px rgba(159, 18, 57, .32);
      }

      .mosobr-panel {
        position: fixed;
        right: 22px;
        bottom: 106px;
        z-index: 2147483000;
        width: min(470px, calc(100vw - 32px));
        height: min(720px, calc(100vh - 132px));
        display: none;
        flex-direction: column;
        overflow: hidden;
        border: 1px solid #ffd3da;
        border-radius: 8px;
        background: #fff;
        color: #172033;
        box-shadow: 0 24px 72px rgba(17, 24, 39, .24);
        font-family: Arial, sans-serif;
      }

      .mosobr-panel.is-open { display: flex; }

      .mosobr-header {
        min-height: 78px;
        padding: 14px 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        background: linear-gradient(135deg, #e3132c 0%, #ff5163 100%);
        border-bottom: 1px solid #ffd3da;
        color: #fff;
      }

      .mosobr-brand {
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .mosobr-title { min-width: 0; }
      .mosobr-title strong { display: block; font-size: 17px; line-height: 1.2; }
      .mosobr-title span { display: block; margin-top: 4px; color: rgba(255, 255, 255, .84); font-size: 12px; }

      .mosobr-icon-button {
        width: 34px;
        height: 34px;
        flex: 0 0 auto;
        border: 1px solid rgba(255, 255, 255, .36);
        border-radius: 8px;
        background: rgba(255, 255, 255, .16);
        color: #fff;
        font: 700 18px/1 Arial, sans-serif;
        cursor: pointer;
      }

      .mosobr-icon-button:hover { background: rgba(255, 255, 255, .24); }

      .mosobr-ambi-avatar {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 auto;
        border-radius: 50%;
      }

      .mosobr-ambi-avatar svg {
        display: block;
        width: 100%;
        height: 100%;
      }

      .mosobr-ambi-avatar.launcher {
        width: 58px;
        height: 58px;
        margin: 6px;
      }

      .mosobr-ambi-avatar.header {
        width: 48px;
        height: 48px;
        background: #fff;
        box-shadow: 0 8px 20px rgba(111, 10, 31, .22);
      }

      .mosobr-ambi-avatar.message {
        width: 34px;
        height: 34px;
        margin-top: 2px;
      }

      .mosobr-messages {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        padding: 18px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        background:
          radial-gradient(circle at 10% 0%, rgba(255, 232, 236, .95), transparent 30%),
          linear-gradient(180deg, #fffafb 0%, #f7f9fe 100%);
      }

      .mosobr-message-row {
        display: flex;
        align-items: flex-start;
        gap: 9px;
        max-width: 100%;
      }

      .mosobr-message-row.bot { align-self: flex-start; max-width: 94%; }
      .mosobr-message-row.user { align-self: flex-end; justify-content: flex-end; max-width: 88%; }
      .mosobr-message-row.system {
        align-self: center;
        justify-content: center;
        max-width: 100%;
      }

      .mosobr-message {
        padding: 12px 14px;
        border-radius: 8px;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        font-size: 15px;
        line-height: 1.45;
      }

      .mosobr-message.bot { background: #fff; border: 1px solid #ffd3da; box-shadow: 0 6px 18px rgba(159, 18, 57, .08); }
      .mosobr-message.user { background: #eef6ff; border: 1px solid #cae0ff; color: #102a56; }
      .mosobr-message a {
        color: #c90f25;
        font-weight: 700;
        text-decoration: underline;
        text-underline-offset: 2px;
      }

      .mosobr-message a:hover { color: #8f1027; }

      .mosobr-message.system {
        padding: 4px;
        background: transparent;
        color: #667085;
        font-size: 12px;
      }

      .mosobr-suggestions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 12px 14px 0;
        border-top: 1px solid #f1d8dd;
        background: #fff;
      }

      .mosobr-chip {
        border: 1px solid #f1bdc7;
        border-radius: 8px;
        background: #fff;
        color: #8f1027;
        padding: 9px 11px;
        font: 700 12px/1.2 Arial, sans-serif;
        cursor: pointer;
      }

      .mosobr-chip:hover { background: #fff5f7; }
      .mosobr-chip.secondary { color: #475467; font-weight: 500; }

      .mosobr-form {
        display: flex;
        gap: 8px;
        padding: 12px 14px 14px;
        background: #fff;
      }

      .mosobr-input {
        flex: 1;
        min-width: 0;
        height: 46px;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 0 13px;
        font: 15px Arial, sans-serif;
        outline: none;
      }

      .mosobr-input:focus {
        border-color: #e3132c;
        box-shadow: 0 0 0 3px rgba(227, 19, 44, .12);
      }

      .mosobr-send {
        width: 50px;
        height: 46px;
        border: 0;
        border-radius: 8px;
        background: #e3132c;
        color: #fff;
        font: 700 18px Arial, sans-serif;
        cursor: pointer;
      }

      .mosobr-send:hover { background: #c90f25; }

      .mosobr-send:disabled,
      .mosobr-input:disabled {
        opacity: .58;
        cursor: not-allowed;
      }

      @media (max-width: 520px) {
        .mosobr-launcher { right: 14px; bottom: 14px; }
        .mosobr-panel {
          right: 8px;
          bottom: 92px;
          width: calc(100vw - 16px);
          height: calc(100vh - 108px);
        }
      }
    `;
    document.head.appendChild(style);
  }

  function createAmbiAvatar(size) {
    const node = document.createElement("span");
    node.className = "mosobr-ambi-avatar " + (size || "");
    node.innerHTML = AMBI_AVATAR_SVG;
    return node;
  }

  function appendLinkedText(node, text) {
    const source = String(text || "");
    let lastIndex = 0;
    let match;

    LINK_RE.lastIndex = 0;
    while ((match = LINK_RE.exec(source)) !== null) {
      const rawUrl = match[0];
      const start = match.index;
      if (start > 0 && source[start - 1] === "@") {
        continue;
      }

      if (start > lastIndex) {
        node.appendChild(document.createTextNode(source.slice(lastIndex, start)));
      }

      let cleanUrl = rawUrl;
      let suffix = "";
      while (/[.,;:!?)\]}]$/.test(cleanUrl)) {
        suffix = cleanUrl.slice(-1) + suffix;
        cleanUrl = cleanUrl.slice(0, -1);
      }

      if (cleanUrl) {
        const link = document.createElement("a");
        const hrefUrl = cleanUrl.replace(/^мос\.ру/i, "mos.ru");
        link.href = /^https?:\/\//i.test(hrefUrl) ? hrefUrl : "https://" + hrefUrl;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = cleanUrl;
        node.appendChild(link);
      }

      if (suffix) {
        node.appendChild(document.createTextNode(suffix));
      }
      lastIndex = start + rawUrl.length;
    }

    if (lastIndex < source.length) {
      node.appendChild(document.createTextNode(source.slice(lastIndex)));
    }
  }

  function getOrCreateUserId() {
    let userId = localStorage.getItem("mosobr_widget_user_id");
    if (!userId) {
      userId = "site_" + (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36));
      localStorage.setItem("mosobr_widget_user_id", userId);
    }
    return userId;
  }

  function sessionEndpoint(apiUrl, name) {
    const raw = String(apiUrl || DEFAULT_API);
    try {
      const url = new URL(raw, window.location.href);
      const path = url.pathname.replace(/\/+$/, "") || "/";
      if (path === "/api/chat") {
        url.pathname = `/api/session/${name}`;
      } else {
        url.pathname = path.replace(/\/[^/]*$/, `/session/${name}`);
      }
      url.search = "";
      url.hash = "";
      return url.toString();
    } catch (_) {
      return raw.replace(/\/api\/chat$/, `/api/session/${name}`).replace(/\/[^/]*$/, `/session/${name}`);
    }
  }

  function createWidget(options) {
    ensureStyles();

    const config = Object.assign({ apiUrl: DEFAULT_API, title: DEFAULT_TITLE }, options || {});
    const userId = getOrCreateUserId();
    let sessionId = localStorage.getItem("mosobr_widget_session_id");
    let userType = localStorage.getItem("mosobr_widget_user_type");
    let loading = false;

    const launcher = document.createElement("button");
    launcher.className = "mosobr-launcher";
    launcher.type = "button";
    launcher.title = "Открыть чат";
    launcher.setAttribute("aria-label", "Открыть чат с Амби");
    launcher.appendChild(createAmbiAvatar("launcher"));

    const panel = document.createElement("section");
    panel.className = "mosobr-panel";
    panel.setAttribute("aria-label", config.title);
    panel.innerHTML = `
      <div class="mosobr-header">
        <div class="mosobr-brand">
          <span class="mosobr-header-avatar"></span>
          <div class="mosobr-title">
            <strong></strong>
            <span>AI-помощник поступления в колледжи Москвы</span>
          </div>
        </div>
        <button class="mosobr-icon-button" type="button" title="Свернуть" aria-label="Свернуть">&times;</button>
      </div>
      <div class="mosobr-messages"></div>
      <div class="mosobr-suggestions"></div>
      <form class="mosobr-form">
        <input class="mosobr-input" autocomplete="off" placeholder="Напишите вопрос..." />
        <button class="mosobr-send" type="submit" title="Отправить">&gt;</button>
      </form>
    `;

    document.body.appendChild(launcher);
    document.body.appendChild(panel);

    const title = panel.querySelector(".mosobr-title strong");
    const headerAvatar = panel.querySelector(".mosobr-header-avatar");
    const closeButton = panel.querySelector(".mosobr-icon-button");
    const messages = panel.querySelector(".mosobr-messages");
    const suggestions = panel.querySelector(".mosobr-suggestions");
    const form = panel.querySelector(".mosobr-form");
    const input = panel.querySelector(".mosobr-input");
    const sendButton = panel.querySelector(".mosobr-send");
    title.textContent = config.title;
    headerAvatar.appendChild(createAmbiAvatar("header"));

    function addMessage(role, text) {
      const row = document.createElement("div");
      row.className = "mosobr-message-row " + role;
      if (role === "bot") {
        row.appendChild(createAmbiAvatar("message"));
      }
      const node = document.createElement("div");
      node.className = "mosobr-message " + role;
      appendLinkedText(node, text);
      row.appendChild(node);
      messages.appendChild(row);
      messages.scrollTop = messages.scrollHeight;
    }

    function setLoading(value) {
      loading = value;
      input.disabled = value;
      sendButton.disabled = value;
    }

    function setSuggestions(items) {
      suggestions.innerHTML = "";
      const list = Array.isArray(items) && items.length ? items.slice(0, 8) : [];
      if (!list.length && !userType) {
        list.push(...MAIN_MENU_SUGGESTIONS);
      }
      if (sessionId && userType && !list.some((item) => getSuggestionLabel(item) === LABELS.menu)) {
        list.push({ label: LABELS.menu, action: "main_menu" });
      }
      if (sessionId && !list.some((item) => getSuggestionLabel(item) === LABELS.end)) {
        list.push({ label: LABELS.end, action: "end_session" });
      }

      list.forEach((item) => {
        const label = getSuggestionLabel(item);
        const action = getSuggestionAction(item);
        if (!label) return;
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "mosobr-chip" + (label === LABELS.end ? " secondary" : "");
        chip.textContent = label;
        chip.addEventListener("click", () => {
          if (label === LABELS.end) {
            closeSession();
          } else {
            send(label, action);
          }
        });
        suggestions.appendChild(chip);
      });
    }

    function getSuggestionLabel(item) {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") return String(item.label || "");
      return "";
    }

    function getSuggestionAction(item) {
      if (item && typeof item === "object" && item.action) return String(item.action);
      return null;
    }

    function startScreen() {
      sessionId = null;
      userType = "applicant";
      localStorage.removeItem("mosobr_widget_session_id");
      localStorage.setItem("mosobr_widget_user_type", userType);
      messages.innerHTML = "";
      addMessage("bot", GREETING_TEXT);
      setSuggestions(MAIN_MENU_SUGGESTIONS);
    }

    async function send(text, action) {
      const value = String(text || "").trim();
      if (!value || loading) return;

      addMessage("user", value);
      input.value = "";
      setLoading(true);

      try {
        const response = await fetch(config.apiUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            session_id: sessionId,
            message: value,
            action: action || null,
            user_type: userType,
          }),
        });

        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }

        const data = await response.json();
        sessionId = data.session_id;
        localStorage.setItem("mosobr_widget_session_id", sessionId);

        if (value === LABELS.parent || action === "set_user_type_parent") {
          userType = "parent";
          localStorage.setItem("mosobr_widget_user_type", userType);
        }
        if (value === LABELS.applicant || action === "set_user_type_applicant") {
          userType = "applicant";
          localStorage.setItem("mosobr_widget_user_type", userType);
        }

        if (data.expired_previous_session) {
          addMessage("system", "Предыдущая сессия устарела, начата новая.");
        }
        addMessage("bot", data.answer || "Не получил ответ от API.");
        setSuggestions(data.suggestions || []);
      } catch (error) {
        addMessage("system", "Ошибка API: " + error.message);
      } finally {
        setLoading(false);
        input.focus();
      }
    }

    async function closeSession() {
      try {
        await fetch(sessionEndpoint(config.apiUrl, "close"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: userId, session_id: sessionId }),
        });
      } catch (_) {}

      sessionId = null;
      userType = null;
      localStorage.removeItem("mosobr_widget_session_id");
      localStorage.removeItem("mosobr_widget_user_type");
      startScreen();
    }

    launcher.addEventListener("click", () => {
      panel.classList.toggle("is-open");
      if (panel.classList.contains("is-open")) {
        input.focus();
      }
    });

    closeButton.addEventListener("click", () => {
      panel.classList.remove("is-open");
    });

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      send(input.value);
    });

    startScreen();

    return {
      open() {
        panel.classList.add("is-open");
        input.focus();
      },
      close() {
        panel.classList.remove("is-open");
      },
      reset: closeSession,
    };
  }

  window.MosobrWidget = {
    init: createWidget,
  };
})();
