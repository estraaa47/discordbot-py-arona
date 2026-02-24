const modal = document.getElementById('cardModal');

function filterCards(grade, btnElement) {
    const btns = document.querySelectorAll('.filter-btn');
    btns.forEach(btn => btn.classList.remove('active'));
    btnElement.classList.add('active');

    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        const cardGrade = card.getAttribute('data-grade');
        if (grade === 'all' || cardGrade === grade) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

function openModal(cardElement) {
    const isOwned = cardElement.dataset.owned === 'true';
    document.getElementById('modalImg').src = cardElement.dataset.img;
    document.getElementById('modalName').innerText = cardElement.dataset.name;
    const modalStatus = document.getElementById('modalStatus');
    modalStatus.innerText = isOwned ? "● OWNED" : "○ LOCKED";
    modalStatus.className = isOwned ? "card-status status-owned" : "card-status status-locked";
    modal.style.display = 'flex';
    setTimeout(() => { modal.classList.add('active'); }, 10);
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    modal.classList.remove('active');
    setTimeout(() => { modal.style.display = 'none'; }, 300);
    document.body.style.overflow = 'auto';
}

window.onkeydown = function (event) {
    if (event.keyCode === 27) closeModal();
};