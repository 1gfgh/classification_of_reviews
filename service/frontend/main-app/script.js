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
        window.location.href = 'https://example.com';
        return;
    }    
    console.log('Отправка данных:', input.value);
});