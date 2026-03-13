// static/js/gacha.js

function startGacha(count) {
    document.getElementById('gacha-home').style.display = 'none';
    document.getElementById('gacha-result-view').style.display = 'block';
    
    // 모바일 등에서 버튼 누를 시 스크롤 위로 초기화
    window.scrollTo(0, 0);

    performGacha(count);
}

function returnToHome() {
    document.getElementById('gacha-result-view').style.display = 'none';
    document.getElementById('gacha-home').style.display = 'block';
    
    // 이전 결과 초기화
    const grid = document.getElementById('gacha-deck');
    if(grid) grid.innerHTML = '';
}

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
    
    // 레이아웃 잡히기 전까지 투명하게 숨김
    grid.style.opacity = '0';
    grid.style.pointerEvents = 'none';

    results.forEach((card, index) => {
        const pathWithoutExt = card.path.split('.').slice(0, -1).join('.');
        const gradeKey = card.grade.toLowerCase().replace(' ', '_');
        const cardName = card.name;

        const isNew = !ownedNames.includes(cardName);

        const cardDiv = document.createElement('div');
        cardDiv.className = `card ${gradeKey}`;

        if (isNew) {
            // 히든 카드 경로 (새로운 카드)
            cardDiv.innerHTML = `
                <div class="card-inner hidden-card" onclick="revealCard(this, '${gradeKey}', '${pathWithoutExt}', '${cardName}', '${Math.random()}', '${card.path}', true)">
                    <div class="card-img-wrapper">
                        <img src="/images/thumbnails/hidden.webp" alt="Hidden Card">
                    </div>
                </div>
            `;
            ownedNames.push(cardName);
            ownedDataElement.dataset.owned = JSON.stringify(ownedNames);
        } else {
            // 히든 카드 경로 (중복 카드)
            cardDiv.innerHTML = `
                <div class="card-inner hidden-card" onclick="revealCard(this, '${gradeKey}', '${pathWithoutExt}', '${cardName}', '${Math.random()}', '${card.path}', false)">
                    <div class="card-img-wrapper">
                        <img src="/images/thumbnails/hidden.webp" alt="Hidden Card">
                    </div>
                </div>
            `;
        }
        grid.appendChild(cardDiv);
    });

    // 최고 등급 계산 로직 (가장 높은 아우라를 부여하기 위함)
    const gradeHierarchy = {
        'ultra_rare': 4,
        'super_rare': 3,
        'rare': 2,
        'normal': 1
    };
    
    let highestGrade = 'normal';
    let highestValue = 0;
    
    results.forEach(card => {
        const gradeKey = card.grade.toLowerCase().replace(' ', '_');
        const val = gradeHierarchy[gradeKey] || 1;
        if(val > highestValue) {
            highestValue = val;
            highestGrade = gradeKey;
        }
    });

    // 중앙 스택 애니메이션 계산
    setTimeout(() => {
        const gridRect = grid.getBoundingClientRect();
        const centerX = gridRect.left + gridRect.width / 2;
        // 헤더 등을 고려하여 살짝 아래쪽(중앙)으로 스택 지정
        const centerY = window.innerHeight / 2 + 50; 
        
        const cards = grid.querySelectorAll('.card');
        cards.forEach((card, index) => {
            card.style.transition = 'none'; // 초기 이동 트랜지션 무효화
            
            const rect = card.getBoundingClientRect();
            const cardX = rect.left + rect.width / 2;
            const cardY = rect.top + rect.height / 2;
            
            const dx = centerX - cardX;
            const dy = centerY - cardY;
            
            // 중앙 위치로 이동값 할당
            card.style.setProperty('--dx', `${dx}px`);
            card.style.setProperty('--dy', `${dy}px`);
            card.style.setProperty('--rot', `0deg`); // 반듯하게 모임
            card.style.zIndex = 100 + index;
        });
        
        // 투명도 복원 및 클릭 이벤트 활성화
        grid.style.opacity = '1';
        grid.style.pointerEvents = 'auto';
        grid.className = `gacha-grid deck-stacked deck-stacked-${highestGrade}`; // 최고 등급 아우라 부여

        grid.onclick = function(e) {
            // 뭉치를 클릭하면 촤라락 펴지게 함
            grid.onclick = null;
            grid.className = 'gacha-grid'; // 스택 애니메이션 해제
            
            cards.forEach((card, index) => {
                // 부드럽게 각자 제자리로 펴지는 애니메이션
                card.style.transition = `transform 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) ${index * 0.05}s`;
                card.style.setProperty('--dx', `0px`);
                card.style.setProperty('--dy', `0px`);
                card.style.setProperty('--rot', `0deg`);
                
                // 애니메이션 끝난 후 속성 정리
                setTimeout(() => {
                    card.style.zIndex = '';
                    card.style.transition = ''; // JS 트랜지션 해제 (CSS 호버 속성 복구)
                }, 600 + index * 50);
            });
        };
    }, 50);
}

function revealCard(el, grade, pathNoExt, cardName, dumpId, fullPath, isNew) {
    el.classList.remove('hidden-card');
    el.style.cursor = "pointer";
    el.onclick = function() { showModal('/images/' + fullPath); };

    // isNew 플래그가 true면 NEW 뱃지, false면 중복 카드 효과
    const duplicateClass = isNew ? '' : 'duplicated-card';
    const newTagHtml = isNew ? '<div class="new-tag">NEW</div>' : '';

    el.innerHTML = `
        <div class="card-img-wrapper ${duplicateClass}">
            <img src="/images/thumbnails/${pathNoExt}.webp" alt="${cardName}">
        </div>
        <div class="card-info">
            <div class="card-name">${cardName}</div>
            <div class="card-status"><span class="status-owned">● ${grade.toUpperCase().replace('_', ' ')}</span></div>
        </div>
        ${newTagHtml}
    `;
}