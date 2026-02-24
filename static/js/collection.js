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

function toggleDropdown(event) {
    const dropdown = document.getElementById('dropdownMenu');
    // 클릭된 요소가 드롭다운이 아니거나 드롭다운 내부 요소가 아니면 토글
    if (!dropdown.contains(event.target) && event.target !== document.getElementById('profile')) {
        dropdown.classList.toggle('active');
    }
}

// 다른 곳 클릭 시 드롭다운 닫기
document.addEventListener('click', function (event) {
    const dropdown = document.getElementById('dropdownMenu');
    const profile = document.querySelector('.profile');

    // 드롭다운이 열려있고, 클릭된 곳이 프로필도 아니고 드롭다운 내부도 아니면 닫음
    if (dropdown.classList.contains('active') &&
        !profile.contains(event.target) &&
        !dropdown.contains(event.target)) {
        dropdown.classList.remove('active');
    }
});