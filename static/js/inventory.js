/**
 * ARONA ARCHIVE - Inventory Logic (Final)
 */

// 1. 드롭다운 토글
function toggleDropdown(event) {
    event.stopPropagation();
    const menu = document.getElementById('dropdownMenu');
    if (menu) menu.classList.toggle('active');
}

window.addEventListener('click', () => {
    const menu = document.getElementById('dropdownMenu');
    if (menu) menu.classList.remove('active');
});

// 2. 자물쇠 토글 (클래스 토글 방식)
async function toggleLock(event, btnElement) {
    event.stopPropagation();

    const cardId = btnElement.getAttribute('data-id');
    const isLocked = btnElement.classList.contains('locked');
    const newStatus = !isLocked;

    // UI 선반영: 클래스만 토글하면 CSS가 이미지를 자동으로 바꿉니다.
    btnElement.classList.toggle('locked');

    try {
        const response = await fetch('/api/inventory/lock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ card_id: cardId, lock: newStatus })
        });

        const result = await response.json();
        if (!result.success) throw new Error();

        console.log(`[Success] 카드 ${cardId} 잠금 상태: ${newStatus}`);
    } catch (error) {
        console.error('[Error] 저장 실패');
        // 실패 시 UI 복구
        btnElement.classList.toggle('locked');
        alert('잠금 상태 변경에 실패했습니다.');
    }
}

// 3. 모달 확장 기능 (강화 등급 & 색상 동기화)
const originalOpenModal = window.openModal;

window.openModal = function (cardElement) {
    // 기존 collection.js의 모달 로직 실행
    if (typeof originalOpenModal === 'function') {
        originalOpenModal(cardElement);
    }

    const modalUpgrade = document.getElementById('modalUpgrade');
    const upgradeBadge = cardElement.querySelector('.upgrade-badge');

    if (modalUpgrade && upgradeBadge) {
        // 텍스트 설정
        modalUpgrade.innerText = "UPGRADE LEVEL: " + upgradeBadge.innerText;

        // 💡 색상 동기화 로직 추가
        // 기존에 붙어있을 수 있는 등급 클래스들을 초기화
        modalUpgrade.classList.remove('tier-white', 'tier-gold', 'tier-rainbow');

        // 현재 배지가 가지고 있는 클래스를 모달 텍스트에도 그대로 적용
        if (upgradeBadge.classList.contains('tier-rainbow')) {
            modalUpgrade.classList.add('tier-rainbow');
        } else if (upgradeBadge.classList.contains('tier-gold')) {
            modalUpgrade.classList.add('tier-gold');
        } else {
            modalUpgrade.classList.add('tier-white');
        }
    }

    // 모달 이미지 테두리 광채용 등급 데이터 연동
    const modalImg = document.getElementById('modalImg');
    const grade = cardElement.getAttribute('data-grade');
    if (modalImg) {
        modalImg.setAttribute('data-grade', grade);
    }
}