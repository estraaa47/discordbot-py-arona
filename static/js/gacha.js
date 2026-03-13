// static/js/gacha.js

async function performGacha(count) {
    const grid = document.getElementById('gacha-deck');
    grid.innerHTML = '<div class="loading">아로나가 준비 중이에요...</div>';

    try {
        const response = await fetch('/api/gacha', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ count: count })
        });

        const data = await response.json();
        if (data.success) {
            renderGacha(data.results);
        } else {
            alert(data.message || "가챠 실패!");
            grid.innerHTML = '<div class="empty-state">포인트가 부족하거나 오류가 발생했습니다.</div>';
        }
    } catch (e) {
        grid.innerHTML = '<div class="error">서버 연결 오류!</div>';
    }
}

function renderGacha(results) {
    const grid = document.getElementById('gacha-deck');
    const ownedDataElement = document.getElementById('owned-data');
    // HTML에 숨겨둔 데이터를 여기서 실시간으로 다시 읽어옵니다.
    let ownedNames = JSON.parse(ownedDataElement.dataset.owned || '[]');

    grid.innerHTML = '';

    results.forEach(card => {
        const pathWithoutExt = card.path.split('.').slice(0, -1).join('.');
        const gradeKey = card.grade.toLowerCase().replace(' ', '_');
        const cardName = card.name;

        // 신규 여부 판독
        const isNew = !ownedNames.includes(cardName);

        const cardDiv = document.createElement('div');
        cardDiv.className = `card ${gradeKey}`;

        if (isNew) {
            cardDiv.innerHTML = `
                <div class="card-inner hidden-card" onclick="revealCard(this, '${gradeKey}', '${pathWithoutExt}')">
                    <img src="/images/hidden.jpg" alt="Hidden Card">
                    <div class="new-tag">NEW</div>
                </div>
            `;
            ownedNames.push(cardName); // 중복 방지용 추가
            // HTML 데이터 속성도 업데이트 (다음에 다시 읽을 때를 위해)
            ownedDataElement.dataset.owned = JSON.stringify(ownedNames);
        } else {
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

function revealCard(el, grade, pathNoExt) {
    el.classList.remove('hidden-card');
    el.innerHTML = `
        <div class="card-img-wrapper">
            <img src="/images/thumbnails/${pathNoExt}.webp">
        </div>
        <div class="card-info">
            <div class="card-name">${pathNoExt.split('/').pop()}</div>
            <div class="card-status"><span class="status-owned">● ${grade.toUpperCase().replace('_', ' ')}</span></div>
        </div>
    `;
}