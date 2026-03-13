// static/js/gacha.js

async function performGacha(count) {
    const grid = document.getElementById('gacha-deck');
    grid.innerHTML = '<div class="loading">아로나가 모집 공고를 확인 중입니다...</div>';

    try {
        const response = await fetch('/api/gacha', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ count: count })
        });

        const data = await response.json();

        if (data.success) {
            renderGacha(data.results);

            // 💡 [핵심] 가챠 성공 시 실시간으로 화면의 포인트를 깎아줍니다.
            const pointsEl = document.getElementById('current-points');
            if (pointsEl) {
                // 콤마(,)가 있으면 제거하고 숫자로 변환 후 차감 (1회당 120P)
                let currentPts = parseInt(pointsEl.innerText.replace(/,/g, ''));
                pointsEl.innerText = currentPts - (120 * count);
            }
        } else {
            alert(data.message || "가챠 실패!");
            grid.innerHTML = '<div class="empty-state">포인트가 부족하거나 오류가 발생했습니다.</div>';
        }
    } catch (e) {
        console.error("Gacha Error: ", e);
        grid.innerHTML = '<div class="error">서버 연결 오류!</div>';
    }
}

function renderGacha(results) {
    const grid = document.getElementById('gacha-deck');
    const ownedDataElement = document.getElementById('owned-data');

    // HTML에 숨겨둔 데이터를 여기서 실시간으로 다시 읽어옵니다.
    let ownedNames = JSON.parse(ownedDataElement.dataset.owned || '[]');

    grid.innerHTML = '';

    results.forEach((card, index) => {
        const pathWithoutExt = card.path.split('.').slice(0, -1).join('.');
        const gradeKey = card.grade.toLowerCase().replace(' ', '_');
        const cardName = card.name;

        // 신규 여부 판독
        const isNew = !ownedNames.includes(cardName);

        const cardDiv = document.createElement('div');
        cardDiv.className = `card ${gradeKey}`;

        // 💡 [핵심] 10장이 0.1초 간격으로 순서대로 촤르르 나타나는 마법의 한 줄
        cardDiv.style.animationDelay = `${index * 0.1}s`;

        if (isNew) {
            // 신규 카드는 hidden.jpg로 가리고 NEW 태그
            // 클릭 시 카드 이름을 정확히 띄우기 위해 cardName 파라미터 추가
            cardDiv.innerHTML = `
                <div class="card-inner hidden-card" onclick="revealCard(this, '${gradeKey}', '${pathWithoutExt}', '${cardName}')">
                    <img src="/images/hidden.jpg" alt="Hidden Card">
                    <div class="new-tag">NEW</div>
                </div>
            `;
            ownedNames.push(cardName); // 중복 방지용 추가

            // HTML 데이터 속성도 업데이트 (다음에 다시 읽을 때를 위해)
            ownedDataElement.dataset.owned = JSON.stringify(ownedNames);
        } else {
            // 중복 카드는 바로 공개
            cardDiv.innerHTML = `
                <div class="card-inner">
                    <div class="card-img-wrapper">
                        <img src="/images/thumbnails/${pathWithoutExt}.webp" alt="${cardName}">
                    </div>
                    <div class="card-info">
                        <div class="card-name">${cardName}</div>
                        <div class="card-status"><span class="status-owned">● ${card.grade}</span></div>
                    </div>
                </div>
            `;
        }
        grid.appendChild(cardDiv);
    });
}

// 클릭 시 카드가 뒤집어지며 결과가 나오는 함수
function revealCard(el, grade, pathNoExt, cardName) {
    el.classList.remove('hidden-card');
    el.innerHTML = `
        <div class="card-img-wrapper">
            <img src="/images/thumbnails/${pathNoExt}.webp" alt="${cardName}">
        </div>
        <div class="card-info">
            <div class="card-name">${cardName}</div>
            <div class="card-status"><span class="status-owned">● ${grade.toUpperCase().replace('_', ' ')}</span></div>
        </div>
    `;
}