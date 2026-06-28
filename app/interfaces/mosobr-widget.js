(function () {
  const DEFAULT_TITLE = "AI-помощник по колледжам";
  const DEFAULT_API = "/api/chat";

  const LABELS = {
    parent: "Родитель",
    applicant: "Абитуриент / поступающий",
    end: "Завершить сессию",
    menu: "Главное меню",
  };

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
        width: 58px;
        height: 58px;
        border: 0;
        border-radius: 18px;
        background: #2457d6;
        color: #fff;
        font: 700 16px/1 Arial, sans-serif;
        box-shadow: 0 14px 34px rgba(30, 64, 175, .28);
        cursor: pointer;
      }

      .mosobr-panel {
        position: fixed;
        right: 22px;
        bottom: 92px;
        z-index: 2147483000;
        width: min(390px, calc(100vw - 28px));
        height: min(620px, calc(100vh - 116px));
        display: none;
        flex-direction: column;
        overflow: hidden;
        border: 1px solid #d6dbe7;
        border-radius: 8px;
        background: #fff;
        color: #172033;
        box-shadow: 0 22px 64px rgba(17, 24, 39, .22);
        font-family: Arial, sans-serif;
      }

      .mosobr-panel.is-open { display: flex; }

      .mosobr-header {
        min-height: 58px;
        padding: 12px 14px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #f6f8fc;
        border-bottom: 1px solid #d6dbe7;
      }

      .mosobr-title { min-width: 0; }
      .mosobr-title strong { display: block; font-size: 15px; line-height: 1.2; }
      .mosobr-title span { display: block; margin-top: 3px; color: #667085; font-size: 12px; }

      .mosobr-icon-button {
        width: 34px;
        height: 34px;
        border: 1px solid #d6dbe7;
        border-radius: 8px;
        background: #fff;
        color: #344054;
        cursor: pointer;
      }

      .mosobr-messages {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        background: #fbfcff;
      }

      .mosobr-message {
        max-width: 88%;
        padding: 10px 12px;
        border-radius: 8px;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        font-size: 14px;
        line-height: 1.4;
      }

      .mosobr-message.bot { align-self: flex-start; background: #eef3ff; border: 1px solid #d9e4ff; }
      .mosobr-message.user { align-self: flex-end; background: #e9f8ef; border: 1px solid #ccebd7; }
      .mosobr-message.system {
        align-self: center;
        max-width: 100%;
        padding: 4px;
        background: transparent;
        color: #667085;
        font-size: 12px;
      }

      .mosobr-suggestions {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
        padding: 10px 12px 0;
        border-top: 1px solid #edf0f6;
        background: #fff;
      }

      .mosobr-chip {
        border: 1px solid #cad3e3;
        border-radius: 8px;
        background: #fff;
        color: #24324a;
        padding: 8px 10px;
        font: 600 12px/1.2 Arial, sans-serif;
        cursor: pointer;
      }

      .mosobr-chip:hover { background: #f6f8fc; }
      .mosobr-chip.secondary { color: #475467; font-weight: 500; }

      .mosobr-form {
        display: flex;
        gap: 8px;
        padding: 10px 12px 12px;
        background: #fff;
      }

      .mosobr-input {
        flex: 1;
        min-width: 0;
        height: 40px;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 0 11px;
        font: 14px Arial, sans-serif;
        outline: none;
      }

      .mosobr-input:focus {
        border-color: #2457d6;
        box-shadow: 0 0 0 3px rgba(36, 87, 214, .12);
      }

      .mosobr-send {
        width: 44px;
        height: 40px;
        border: 0;
        border-radius: 8px;
        background: #2457d6;
        color: #fff;
        font: 700 18px Arial, sans-serif;
        cursor: pointer;
      }

      .mosobr-send:disabled,
      .mosobr-input:disabled {
        opacity: .58;
        cursor: not-allowed;
      }

      @media (max-width: 520px) {
        .mosobr-launcher { right: 14px; bottom: 14px; }
        .mosobr-panel {
          right: 8px;
          bottom: 82px;
          width: calc(100vw - 16px);
          height: calc(100vh - 96px);
        }
      }
    `;
    document.head.appendChild(style);
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
    return apiUrl.replace(/\/api\/chat$/, `/api/session/${name}`);
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
    launcher.textContent = "AI";
    launcher.title = "Открыть чат";

    const panel = document.createElement("section");
    panel.className = "mosobr-panel";
    panel.setAttribute("aria-label", config.title);
    panel.innerHTML = `
      <div class="mosobr-header">
        <div class="mosobr-title">
          <strong></strong>
          <span>Колледжи, профессии и поступление</span>
        </div>
        <button class="mosobr-icon-button" type="button" title="Свернуть">x</button>
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
    const closeButton = panel.querySelector(".mosobr-icon-button");
    const messages = panel.querySelector(".mosobr-messages");
    const suggestions = panel.querySelector(".mosobr-suggestions");
    const form = panel.querySelector(".mosobr-form");
    const input = panel.querySelector(".mosobr-input");
    const sendButton = panel.querySelector(".mosobr-send");
    title.textContent = config.title;

    function addMessage(role, text) {
      const node = document.createElement("div");
      node.className = "mosobr-message " + role;
      node.textContent = text;
      messages.appendChild(node);
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
        list.push(
          { label: LABELS.parent, action: "set_user_type_parent" },
          { label: LABELS.applicant, action: "set_user_type_applicant" }
        );
      }
      if (userType && !list.some((item) => getSuggestionLabel(item) === LABELS.menu)) {
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
      messages.innerHTML = "";
      addMessage(
        "bot",
        "Я помогу с колледжами Москвы, специальностями, профессиями и поступлением.\n\nКто вы?"
      );
      setSuggestions([LABELS.parent, LABELS.applicant]);
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
