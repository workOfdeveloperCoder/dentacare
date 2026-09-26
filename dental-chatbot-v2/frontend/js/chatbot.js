(function () {
    "use strict";

    const script =
        document.currentScript ||
        document.querySelector("script[data-flow]");

    if (!script) {
        console.error("Chatbot widget: script tag not found.");
        return;
    }

    const FLOW_KEY =
        script.getAttribute("data-flow") ||
        (window.CHATBOT_CONFIG && window.CHATBOT_CONFIG.flowKey) ||
        "";

    if (!FLOW_KEY) {
        console.error(
            "Chatbot widget: set data-flow or CHATBOT_DEFAULT_FLOW in .env."
        );
        return;
    }

    const API_URL = (
        script.getAttribute("data-api") ||
        (window.CHATBOT_CONFIG && window.CHATBOT_CONFIG.apiUrl) ||
        new URL(script.src, window.location.href).origin
    ).replace(/\/$/, "");

    const POSITION =
        script.getAttribute("data-position") || "right";

    const THEME =
        script.getAttribute("data-theme") || "light";

    let branding = {
        title: script.getAttribute("data-title") || "Chat",
        subtitle: script.getAttribute("data-subtitle") || "Online",
        avatar: script.getAttribute("data-avatar") || "💬",
        primary_color: script.getAttribute("data-color") || "#0f766e",
        powered_by: script.getAttribute("data-powered-by") || "Chatbot",
        placeholder: "Type your message..."
    };

    let sessionToken = null;
    let initialized = false;
    let isOpen = false;
    let isBusy = false;

    /*
    |--------------------------------------------------------------------------
    | Load CSS
    |--------------------------------------------------------------------------
    */

    function loadCSS() {
        const existing = document.querySelector(
            'link[data-chatbot-widget-css="true"]'
        );

        if (existing) {
            return;
        }

        const css = document.createElement("link");

        css.rel = "stylesheet";
        css.href = `${API_URL}/widget.css`;

        css.setAttribute(
            "data-chatbot-widget-css",
            "true"
        );

        document.head.appendChild(css);
    }

    /*
    |--------------------------------------------------------------------------
    | Create Widget
    |--------------------------------------------------------------------------
    */

    function createWidget() {
        if (initialized) {
            return;
        }

        initialized = true;

        loadCSS();

        const root = document.createElement("div");

        root.id = "rr-chatbot-widget";

        root.className =
            "rr-chatbot-widget " +
            `rr-chatbot-position-${POSITION} ` +
            `rr-chatbot-theme-${THEME}`;

        root.style.setProperty(
            "--rr-primary",
            branding.primary_color
        );
        root.style.setProperty(
            "--rr-primary-dark",
            branding.primary_color
        );
        root.style.setProperty(
            "--rr-user",
            branding.primary_color
        );

        root.innerHTML = `
            <button
                type="button"
                class="rr-chatbot-launcher"
                aria-label="Open chat"
                aria-expanded="false"
            >
                <span class="rr-chatbot-launcher-icon">
                    <svg
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                    >
                        <path
                            d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5
                            7.4 7.4 0 0 1-3.45-.85L4 20l1.85-4.55
                            A7.45 7.45 0 0 1 5 11.5
                            7.5 7.5 0 1 1 20 11.5Z"
                        />
                    </svg>
                </span>
            </button>

            <section
                class="rr-chatbot-window"
                aria-hidden="true"
            >
                <header class="rr-chatbot-header">

                    <div class="rr-chatbot-brand">

                        <div class="rr-chatbot-avatar">
                            ${escapeHtml(branding.avatar)}
                        </div>

                        <div>
                            <div class="rr-chatbot-title">
                                ${escapeHtml(branding.title)}
                            </div>

                            <div class="rr-chatbot-status">
                                <span></span>
                                ${escapeHtml(branding.subtitle || "Online")}
                            </div>
                        </div>

                    </div>

                    <button
                        type="button"
                        class="rr-chatbot-close"
                        aria-label="Close chat"
                    >
                        ×
                    </button>

                </header>

                <div
                    class="rr-chatbot-messages"
                    aria-live="polite"
                ></div>

                <div class="rr-chatbot-typing">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>

                <footer class="rr-chatbot-footer">

                    <form class="rr-chatbot-form">

                        <input
                            type="text"
                            class="rr-chatbot-input"
                            placeholder="${escapeHtml(branding.placeholder)}"
                            autocomplete="off"
                            maxlength="2000"
                        />

                        <button
                            type="submit"
                            class="rr-chatbot-send"
                            aria-label="Send message"
                        >
                            <svg
                                viewBox="0 0 24 24"
                                aria-hidden="true"
                            >
                                <path
                                    d="M21.5 3.5 3 10.5l7 3 3 7 8.5-17Z"
                                />
                            </svg>
                        </button>

                    </form>

                    <div class="rr-chatbot-powered">
                        ${escapeHtml(branding.powered_by)}
                    </div>

                </footer>
            </section>
        `;

        document.body.appendChild(root);

        bindEvents(root);

        /*
         * Start session only when widget is opened.
         */
    }

    /*
    |--------------------------------------------------------------------------
    | Events
    |--------------------------------------------------------------------------
    */

    function bindEvents(root) {
        const launcher =
            root.querySelector(".rr-chatbot-launcher");

        const closeButton =
            root.querySelector(".rr-chatbot-close");

        const form =
            root.querySelector(".rr-chatbot-form");

        launcher.addEventListener(
            "click",
            toggleWidget
        );

        closeButton.addEventListener(
            "click",
            closeWidget
        );

        form.addEventListener(
            "submit",
            function (event) {
                event.preventDefault();

                sendTypedMessage();
            }
        );
    }

    /*
    |--------------------------------------------------------------------------
    | Open / Close
    |--------------------------------------------------------------------------
    */

    function toggleWidget() {
        if (isOpen) {
            closeWidget();
        } else {
            openWidget();
        }
    }

    function openWidget() {
        const root =
            document.getElementById(
                "rr-chatbot-widget"
            );

        if (!root) {
            return;
        }

        isOpen = true;

        root.classList.add(
            "rr-chatbot-open"
        );

        const launcher =
            root.querySelector(
                ".rr-chatbot-launcher"
            );

        const windowElement =
            root.querySelector(
                ".rr-chatbot-window"
            );

        launcher.setAttribute(
            "aria-expanded",
            "true"
        );

        windowElement.setAttribute(
            "aria-hidden",
            "false"
        );

        if (!sessionToken) {
            startChat();
        }

        setTimeout(function () {
            const input =
                root.querySelector(
                    ".rr-chatbot-input"
                );

            if (input) {
                input.focus();
            }
        }, 250);
    }

    function closeWidget() {
        const root =
            document.getElementById(
                "rr-chatbot-widget"
            );

        if (!root) {
            return;
        }

        isOpen = false;

        root.classList.remove(
            "rr-chatbot-open"
        );

        const launcher =
            root.querySelector(
                ".rr-chatbot-launcher"
            );

        const windowElement =
            root.querySelector(
                ".rr-chatbot-window"
            );

        launcher.setAttribute(
            "aria-expanded",
            "false"
        );

        windowElement.setAttribute(
            "aria-hidden",
            "true"
        );
    }

    /*
    |--------------------------------------------------------------------------
    | API
    |--------------------------------------------------------------------------
    */

    async function startChat() {
        setBusy(true);

        try {
            const response =
                await fetch(
                    `${API_URL}/chat`,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            flow_key: FLOW_KEY
                        })
                    }
                );

            if (!response.ok) {
                throw new Error(
                    "Unable to start chatbot."
                );
            }

            const data =
                await response.json();

            sessionToken =
                data.session_token;

            renderResponse(data);

        } catch (error) {
            console.error(
                "Chatbot error:",
                error
            );

            addBotMessage(
                "Sorry, we're unable to start the chat right now. Please try again."
            );

        } finally {
            setBusy(false);
        }
    }

    async function sendOption(optionKey) {
        if (isBusy) {
            return;
        }

        if (!sessionToken) {
            return;
        }

        setBusy(true);

        try {
            const response =
                await fetch(
                    `${API_URL}/chat`,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            session_token:
                                sessionToken,

                            option_key:
                                optionKey
                        })
                    }
                );

            if (!response.ok) {
                throw new Error(
                    "Chat request failed."
                );
            }

            const data =
                await response.json();

            renderResponse(data);

        } catch (error) {
            console.error(
                "Chatbot error:",
                error
            );

            addBotMessage(
                "Sorry, something went wrong. Please try again."
            );

        } finally {
            setBusy(false);
        }
    }

    async function sendMessage(message) {
        if (isBusy) {
            return;
        }

        if (!sessionToken) {
            return;
        }

        setBusy(true);

        try {
            const response =
                await fetch(
                    `${API_URL}/chat`,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            session_token:
                                sessionToken,

                            message: message
                        })
                    }
                );

            if (!response.ok) {
                throw new Error(
                    "Chat request failed."
                );
            }

            const data =
                await response.json();

            renderResponse(data);

        } catch (error) {
            console.error(
                "Chatbot error:",
                error
            );

            addBotMessage(
                "Sorry, something went wrong. Please try again."
            );

        } finally {
            setBusy(false);
        }
    }

    /*
    |--------------------------------------------------------------------------
    | Typed Message
    |--------------------------------------------------------------------------
    */

    function sendTypedMessage() {
        const root =
            document.getElementById(
                "rr-chatbot-widget"
            );

        if (!root) {
            return;
        }

        const input =
            root.querySelector(
                ".rr-chatbot-input"
            );

        if (!input) {
            return;
        }

        const message =
            input.value.trim();

        if (!message) {
            return;
        }

        addUserMessage(message);

        input.value = "";

        sendMessage(message);
    }

    /*
    |--------------------------------------------------------------------------
    | Render API Response
    |--------------------------------------------------------------------------
    */

    function renderResponse(data) {
        if (!data) {
            return;
        }

        if (data.error) {
            addBotMessage(
                data.error
            );
        }

        const node =
            data.node;

        if (!node) {
            return;
        }

        if (node.message) {
            addBotMessage(
                node.message
            );
        }

        if (
            node.options &&
            Array.isArray(node.options)
        ) {
            renderOptions(
                node.options
            );
        }
    }

    /*
    |--------------------------------------------------------------------------
    | Messages
    |--------------------------------------------------------------------------
    */

    function addBotMessage(message) {
        appendMessage(
            "bot",
            message
        );
    }

    function addUserMessage(message) {
        appendMessage(
            "user",
            message
        );
    }

    function appendMessage(
        sender,
        message
    ) {
        const root =
            document.getElementById(
                "rr-chatbot-widget"
            );

        if (!root) {
            return;
        }

        const container =
            root.querySelector(
                ".rr-chatbot-messages"
            );

        if (!container) {
            return;
        }

        const messageElement =
            document.createElement(
                "div"
            );

        messageElement.className =
            "rr-chatbot-message " +
            `rr-chatbot-message-${sender}`;

        const bubble =
            document.createElement(
                "div"
            );

        bubble.className =
            "rr-chatbot-bubble";

        /*
         * Preserve line breaks but never
         * inject API text as HTML.
         */
        bubble.textContent =
            message;

        messageElement.appendChild(
            bubble
        );

        container.appendChild(
            messageElement
        );

        scrollToBottom();
    }

    /*
    |--------------------------------------------------------------------------
    | Options
    |--------------------------------------------------------------------------
    */

    function renderOptions(options) {
        const root =
            document.getElementById(
                "rr-chatbot-widget"
            );

        if (!root) {
            return;
        }

        const container =
            root.querySelector(
                ".rr-chatbot-messages"
            );

        if (!container) {
            return;
        }

        const optionsWrapper =
            document.createElement(
                "div"
            );

        optionsWrapper.className =
            "rr-chatbot-options";

        options.forEach(function (option) {
            if (
                !option ||
                !option.option_key
            ) {
                return;
            }

            const button =
                document.createElement(
                    "button"
                );

            button.type = "button";

            button.className =
                "rr-chatbot-option";

            button.textContent =
                option.label ||
                option.option_key;

            button.addEventListener(
                "click",
                function () {
                    if (isBusy) {
                        return;
                    }

                    addUserMessage(
                        option.label ||
                        option.option_key
                    );

                    /*
                     * Remove current option
                     * buttons after selection.
                     */
                    optionsWrapper.remove();

                    sendOption(
                        option.option_key
                    );
                }
            );

            optionsWrapper.appendChild(
                button
            );
        });

        if (
            optionsWrapper.children.length
        ) {
            container.appendChild(
                optionsWrapper
            );

            scrollToBottom();
        }
    }

    /*
    |--------------------------------------------------------------------------
    | Typing State
    |--------------------------------------------------------------------------
    */

    function setBusy(busy) {
        isBusy = busy;

        const root =
            document.getElementById(
                "rr-chatbot-widget"
            );

        if (!root) {
            return;
        }

        const typing =
            root.querySelector(
                ".rr-chatbot-typing"
            );

        if (typing) {
            typing.classList.toggle(
                "rr-chatbot-typing-visible",
                busy
            );
        }

        const input =
            root.querySelector(
                ".rr-chatbot-input"
            );

        if (input) {
            input.disabled = busy;
        }

        scrollToBottom();
    }

    /*
    |--------------------------------------------------------------------------
    | Scroll
    |--------------------------------------------------------------------------
    */

    function scrollToBottom() {
        const root =
            document.getElementById(
                "rr-chatbot-widget"
            );

        if (!root) {
            return;
        }

        const container =
            root.querySelector(
                ".rr-chatbot-messages"
            );

        if (!container) {
            return;
        }

        requestAnimationFrame(
            function () {
                container.scrollTop =
                    container.scrollHeight;
            }
        );
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    async function loadBranding() {
        try {
            const response = await fetch(
                `${API_URL}/flows/${encodeURIComponent(FLOW_KEY)}/config`
            );

            if (!response.ok) {
                return;
            }

            const data = await response.json();
            const remote = data.branding || {};

            branding = {
                title: script.getAttribute("data-title") || remote.title || branding.title,
                subtitle: script.getAttribute("data-subtitle") || remote.subtitle || branding.subtitle,
                avatar: script.getAttribute("data-avatar") || remote.avatar || branding.avatar,
                primary_color: script.getAttribute("data-color") || remote.primary_color || branding.primary_color,
                powered_by: script.getAttribute("data-powered-by") || remote.powered_by || branding.powered_by,
                placeholder: remote.placeholder || branding.placeholder
            };
        } catch (error) {
            console.warn("Chatbot widget: using fallback branding.", error);
        }
    }

    /*
    |--------------------------------------------------------------------------
    | Boot
    |--------------------------------------------------------------------------
    */

    async function boot() {
        await loadBranding();
        createWidget();
    }

    if (
        document.readyState ===
        "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            boot
        );
    } else {
        boot();
    }
})();