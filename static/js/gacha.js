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

            // 💡 실시간으로 화면의 포인트를 깎아줍니다.
            const pointsEl = document.getElementById('current-points');
            if (pointsEl) {
                let currentPts = parseInt(pointsEl.innerText.replace(/,/g, ''));
                pointsEl.innerText = (currentPts - (120 * count)).toLocaleString(); // 콤마 유지
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

    let ownedNames = JSON.parse(ownedDataElement.dataset.owned || '[]');

    grid.innerHTML = '';

    results.forEach((card, index) => {
        const pathWithoutExt = card.path.split('.').slice(0, -1).join('.');
        const gradeKey = card.grade.toLowerCase().replace(' ', '_');
        const cardName = card.name;

        const isNew = !ownedNames.includes(cardName);

        const cardDiv = document.createElement('div');
        cardDiv.className = `card ${gradeKey}`;
        cardDiv.style.animationDelay = `${index * 0.1}s`;

        if (isNew) {
            // 💡 히든 카드 경로를 /images/thumbnails/hidden.webp로 정확히 수정!
            cardDiv.innerHTML = `
                <div class="card-inner hidden-card" onclick="revealCard(this, '${gradeKey}', '${pathWithoutExt}', '${cardName}', '${Math.random()}', '${card.path}')">
                    <div class="card-img-wrapper">
                        <img src="/images/thumbnails/hidden.webp" alt="Hidden Card">
                    </div>
                    <div class="new-tag">NEW</div>
                </div>
            `;
            ownedNames.push(cardName);
            ownedDataElement.dataset.owned = JSON.stringify(ownedNames);
        } else {
            cardDiv.innerHTML = `
                <div class="card-inner" style="cursor: pointer;" onclick="showModal('/images/${card.path}')">
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

function revealCard(el, grade, pathNoExt, cardName, dumpId, fullPath) {
    el.classList.remove('hidden-card');
    el.style.cursor = "pointer";
    el.onclick = function() { showModal('/images/' + fullPath); };
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