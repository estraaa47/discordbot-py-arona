const modal = document.getElementById('cardModal');

/**
 * ✨ 프로필 드롭다운 토글
 * preventDefault: 텍스트가 파랗게 선택되는 현상 방지
 * stopPropagation: 부모(window)의 클릭 이벤트가 실행되어 메뉴가 바로 닫히는 것 방지
 */
function toggleDropdown(event) {
    event.preventDefault();
    event.stopPropagation();
    document.getElementById('dropdownMenu').classList.toggle('active');
}

/**
 * ✨ 전역 클릭 이벤트
 * 드롭다운이 열려있을 때 화면 어디든 클릭하면 닫히게 함
 */
window.onclick = function (event) {
    const dropdown = document.getElementById('dropdownMenu');
    if (dropdown && dropdown.classList.contains('active')) {
        dropdown.classList.remove('active');
    }
};

/**
 * ✨ 카드 필터링 기능
 */
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

/**
 * ✨ 모달 열기 (등급 광채 데이터 전달 추가)
 */
function openModal(cardElement) {
    const isOwned = cardElement.dataset.owned === 'true';
    const grade = cardElement.dataset.grade; // ✨ 클릭한 카드의 등급 가져오기

    const modalImg = document.getElementById('modalImg');
    modalImg.src = cardElement.dataset.img;

    // ✨ 모달 이미지에도 data-grade를 박아줌 (CSS에서 이걸 보고 광채를 냄)
    modalImg.setAttribute('data-grade', grade);

    document.getElementById('modalName').innerText = cardElement.dataset.name;
    const modalStatus = document.getElementById('modalStatus');

    modalStatus.innerText = isOwned ? "● OWNED" : "○ LOCKED";
    modalStatus.className = isOwned ? "card-status status-owned" : "card-status status-locked";

    modal.style.display = 'flex';
    setTimeout(() => { modal.classList.add('active'); }, 10);
    document.body.style.overflow = 'hidden';
}

/**
 * ✨ 모달 닫기
 */
function closeModal() {
    modal.classList.remove('active');
    setTimeout(() => { modal.style.display = 'none'; }, 300);
    document.body.style.overflow = 'auto';
}

/**
 * ✨ ESC 키로 모달 닫기
 */
window.onkeydown = function (event) {
    if (event.keyCode === 27) closeModal();
};