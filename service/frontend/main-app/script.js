document.querySelectorAll('.model-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.model-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        document.querySelector('.model-info strong').textContent = this.textContent;
    });
});

document.querySelector('.input-container input').addEventListener('input', function() {
    const icon = this.nextElementSibling.querySelector('img');
    icon.src = this.value.trim() ? 'svgs/pointer.svg' : 'svgs/upload.svg';
});

document.getElementById('submit-button').addEventListener('click', function() {
    const input = document.getElementById('product-input');
    if (input.value.trim() === '') {
        const login = sessionStorage.getItem('login');
        if (login) {
            const url = `${STREAMLIT_URL}?login=${encodeURIComponent(login)}`;
            window.open(url, '_blank', 'noopener,noreferrer');
        } else {
            const url = `${STREAMLIT_URL}`;
            window.open(url, '_blank', 'noopener,noreferrer');
        }
        return;
    } else {
        handleLinkSubmit()
    }
});

// replacing raw browser alert
function showAnimatedAlert(message, type = 'info') {
    const alertBox = document.createElement('div');
    alertBox.className = `custom-alert ${type}`;
    alertBox.textContent = message;
    document.body.appendChild(alertBox);

    requestAnimationFrame(() => {
        alertBox.classList.add('visible');
    });

    setTimeout(() => {
        alertBox.classList.remove('visible');
        setTimeout(() => alertBox.remove(), 300);
    }, 3000);
}

// model mapping
function getModelKeyFromText(text) {
    const map = {
        "Фильмы": "films",
        "Одежда": "clothes",
        "Товары": "goods",
        "Товары и одежда": "goods-and-clothes",
    };
    return map[text.trim()];
}

// handle inserted link
async function handleLinkSubmit() {
    const input = document.getElementById("product-input");
    const link = input.value.trim();
    const login = sessionStorage.getItem("login") || "guest";
    const modelText = document.querySelector('.model-info strong').textContent;
    const model = getModelKeyFromText(modelText);

    const mustappRegex = /^https:\/\/mustapp\.com\/.+/;
    if (!mustappRegex.test(link)) {
        showAnimatedAlert("Пока поддерживается только mustapp.com", "error");
        return;
    }

    try {
        document.getElementById("loading-overlay").classList.remove("hidden");

        const formData = new FormData();
        formData.append("link", link);
        formData.append("login", login);

        const response = await fetch(`${API_BASE_URL}/predict_by_link/mustapp/${model}`, {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Ошибка при анализе");
        }

        const predictId = await response.json();
        showAnimatedAlert("Анализ успешно запущен", "success");
        window.open(`${STREAMLIT_URL}?login=${encodeURIComponent(login)}&data_id=${predictId}`, "_blank");
    } catch (err) {
        showAnimatedAlert(`Ошибка: ${err.message}`, "error");
    } finally {
        document.getElementById("loading-overlay").classList.add("hidden");
    }
}


// popup base
function createPopup(contentHtml) {
    const popup = document.createElement('div');
    popup.className = 'popup-overlay';
    popup.innerHTML = `
        <div class="popup-window animated-popup">
            <span class="popup-close">&times;</span>
            ${contentHtml}
        </div>
    `;
    document.body.appendChild(popup);
    popup.querySelector('.popup-close').addEventListener('click', () => popup.remove());
    return popup;
}

// reg. popup
function openRegisterPopup() {
    const popup = createPopup(`
        <h2>Регистрация</h2>
        <input type="text" id="reg-name" placeholder="Имя" />
        <input type="text" id="reg-login" placeholder="Логин" />
        <input type="password" id="reg-password" placeholder="Пароль" />
        <button id="register-btn">Создать аккаунт</button>
    `);

    popup.querySelector('#register-btn').addEventListener('click', async () => {
        const name = popup.querySelector('#reg-name').value;
        const login = popup.querySelector('#reg-login').value;
        const password = popup.querySelector('#reg-password').value;
        if (!name || !login || !password) {
            showAnimatedAlert('Заполните все поля!', 'error');
            return;
        }
        await register(name, login, password);
        popup.remove();
    });
}

// login popup
function openLoginPopup() {
    const popup = createPopup(`
        <h2>Вход</h2>
        <input type="text" id="login-login" placeholder="Логин" />
        <input type="password" id="login-password" placeholder="Пароль" />
        <button id="login-btn">Войти</button>
    `);

    popup.querySelector('#login-btn').addEventListener('click', async () => {
        const login = popup.querySelector('#login-login').value;
        const password = popup.querySelector('#login-password').value;
        if (!login || !password) {
            showAnimatedAlert('Заполните все поля!', 'error');
            return;
        }
        await loginUser(login, password);
        popup.remove();
    });
}

// histiry popup
function openHistoryPopup(historyItems) {
    const itemsHtml = historyItems.map(([id, date]) => `
        <div class="history-item" data-id="${id}">
            📅 ${date}, ID ${id}
        </div>
    `).join('');
    const popup = createPopup(`
        <h2>История</h2>
        <div class="history-list-scroll">
            ${itemsHtml}
        </div>
    `);

    popup.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', () => {
            const id = item.getAttribute('data-id');
            const login = sessionStorage.getItem('login');
            const url = `${STREAMLIT_URL}?login=${encodeURIComponent(login)}&data_id=${encodeURIComponent(id)}`;
            window.open(url, '_blank', 'noopener,noreferrer');
        });
    });
}

// API
async function register(name, login, password) {
    const formData = new FormData();
    formData.append('name', name);
    formData.append('login', login);
    formData.append('password', new Blob([password]));

    try {
        const response = await fetch(`${API_BASE_URL}/register`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            showAnimatedAlert('Регистрация прошла успешно!', 'success');
        } else {
            const error = await response.json();
            showAnimatedAlert('Ошибка регистрации: ' + error.detail, 'error');
        }
    } catch (error) {
        showAnimatedAlert('Ошибка сети при регистрации', 'error');
        console.error(error);
    }
}

async function loginUser(login, password) {
    const formData = new FormData();
    formData.append('login', login);
    formData.append('password', new Blob([password]));

    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            sessionStorage.setItem('login', login);
            changeHeaderToLoggedIn();
        } else {
            const error = await response.json();
            showAnimatedAlert('Ошибка входа: ' + error.detail, 'error');
        }
    } catch (error) {
        showAnimatedAlert('Ошибка сети при входе', 'error');
        console.error(error);
    }
}

async function fetchHistory() {
    const login = sessionStorage.getItem('login');
    const formData = new FormData();
    formData.append('login', login);

    try {
        const response = await fetch(`${API_BASE_URL}/get_history`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const history = await response.json();
            openHistoryPopup(history);
        } else {
            const error = await response.json();
            showAnimatedAlert('Ошибка загрузки истории: ' + error.detail, 'error');
        }
    } catch (error) {
        showAnimatedAlert('Ошибка сети при получении истории', 'error');
        console.error(error);
    }
}

// update header after login
function changeHeaderToLoggedIn() {
    const headerRight = document.querySelector('header .header-right');
    headerRight.innerHTML = `
        <p id="history-btn">История</p>
        <p id="logout-btn">Выйти</p>
    `;

    document.getElementById('history-btn').addEventListener('click', fetchHistory);
    document.getElementById('logout-btn').addEventListener('click', () => {
        sessionStorage.removeItem('login');
        location.reload();
    });
}

// header actions
document.addEventListener('DOMContentLoaded', () => {
    const [registerLink, loginLink] = document.querySelectorAll('header .header-right p');
    registerLink.addEventListener('click', openRegisterPopup);
    loginLink.addEventListener('click', openLoginPopup);

    if (sessionStorage.getItem('login')) {
        changeHeaderToLoggedIn();
    }
});
