/**
 * ARONA ARCHIVE - Inventory Logic
 */

// 1. 드롭다운 토글 (헤더 프로필용)
function toggleDropdown(event) {
    event.stopPropagation();
    const menu = document.getElementById('dropdownMenu');
    if (menu) menu.classList.toggle('active');
}

// 화면 클릭 시 드롭다운 닫기
window.addEventListener('click', () => {
    const menu = document.getElementById('dropdownMenu');
    if (menu) menu.classList.remove('active');
});

// 2. 자물쇠 토글 (DB 연동 준비)
async function toggleLock(event, btnElement) {
    event.stopPropagation(); // 카드 상세 모달이 뜨는 것을 방지

    const cardId = btnElement.getAttribute('data-id');
    const isLocked = btnElement.classList.contains('locked');
    const newStatus = !isLocked;

    // UI 선반영 (유저에게 빠른 피드백 제공)
    btnElement.classList.toggle('locked');
    btnElement.innerText = newStatus ? '🔒' : '🔓';

    try {

        const response = await fetch('/api/inventory/lock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ card_id: cardId, lock: newStatus })
        });

        if (!response.ok) throw new Error('Network response was not ok');

        console.log(`[Success] Card ${cardId} lock status: ${newStatus}`);
    } catch (error) {
        console.error('[Error] Lock toggle failed:', error);
        // 실패 시 UI 복구
        btnElement.classList.toggle('locked');
        btnElement.innerText = !newStatus ? '🔒' : '🔓';
        alert('잠금 상태 변경 중 오류가 발생했습니다.');
    }
}

// 3. 모달 확장 기능 (강화 등급 표시)
// collection.js에 있는 기본 openModal을 인벤토리 환경에 맞게 덮어씌웁니다.
const originalOpenModal = window.openModal;

window.openModal = function (cardElement) {
    // 1) 기존 모달 열기 로직 실행 (이미지, 이름 등 세팅)
    if (typeof originalOpenModal === 'function') {
        originalOpenModal(cardElement);
    }

    // 2) 인벤토리 전용 데이터(강화 수치) 추가 세팅
    const modalUpgrade = document.getElementById('modalUpgrade');
    const upgradeBadge = cardElement.querySelector('.upgrade-badge');

    if (modalUpgrade && upgradeBadge) {
        modalUpgrade.innerText = "UPGRADE LEVEL: " + upgradeBadge.innerText;
    }

    // 3) 등급별 모달 광채 효과 적용 (UR/SR)
    const modalImg = document.getElementById('modalImg');
    const grade = cardElement.getAttribute('data-grade');
    if (modalImg) {
        modalImg.setAttribute('data-grade', grade);
    }
}