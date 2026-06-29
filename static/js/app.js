// Web App Logic - App.js
// socket is defined in index.html as SSE + fetch shim

// State
let currentTab = 'welcome';
let isConnected = false;
let ytPlayer;
let volume = 50;

// E-commerce state
let carouselAngle = 0;
let numProducts = 0;
let angleStep = 0;
let cartItems = [];
let wishCount = 0;
let ecomProducts = [];

// Setup Socket
socket.on('status', (data) => {
    const statusText = document.getElementById('conn-status');
    if(statusText) {
        statusText.innerText = data.msg;
        if (data.msg.includes("Connected")) {
            statusText.style.color = "var(--sidebar-text)";
            isConnected = true;
        } else {
            statusText.style.color = "var(--sidebar-text)";
            isConnected = false;
        }
    }
});

socket.on('gesture', (data) => {
    handleGesture(data.gesture);
    
    
    // Update main sidebar dynamic badge
    const img = document.getElementById('main-predicted-img');
    if (img) { img.src = `/assets/gestures/${data.gesture}.png`; img.style.opacity = "1"; }
    const mg = document.getElementById('main-gesture-display');
    if (mg) {
        mg.innerText = data.gesture;
        mg.style.background = "var(--success)";
        setTimeout(() => mg.style.background = "rgba(0,0,0,0.6)", 500);
    }
});

// Unified Gesture Simulation (Works offline/locally & updates server)
window.simulateGesture = (g) => {
    // 1. Emit to server for logs & multi-client sync
    socket.emit('demo_event', {gesture: g});
    
    // 2. Process locally immediately for 100% responsiveness
    handleGesture(g);
    
    // 3. Update main sidebar dynamic badge
    const img = document.getElementById('main-predicted-img');
    if (img) { 
        img.src = `/assets/gestures/${g}.png`; 
        img.style.opacity = "1"; 
    }
    const mg = document.getElementById('main-gesture-display');
    if (mg) {
        mg.innerText = g;
        mg.style.background = "var(--success)";
        setTimeout(() => mg.style.background = "rgba(0,0,0,0.6)", 500);
    }
};

// Demo Keys Keyboard Hook
document.addEventListener('keydown', (e) => {
    const keyMap = {'1': 'Extend', '2': 'Flex', '3': 'Fist_Close', '4': 'Thumbs_Up', '5': 'Thumbs_Down'};
    if (keyMap[e.key]) {
        simulateGesture(keyMap[e.key]);
    }
});



function switchTab(tabId, el) {
    currentTab = tabId;
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.nav-links li').forEach(l => l.classList.remove('active'));
    
    document.getElementById(tabId).classList.add('active');
    el.classList.add('active');
    
    // Dynamic Instructions mapping
    const panel = document.getElementById('instructions-panel');
    const ul = document.getElementById('dynamic-instructions');
    if (tabId === 'welcome') {
        panel.style.display = 'none';
        ul.innerHTML = '';
    } else {
        panel.style.display = 'flex';
        let items = '';
        if (tabId === 'media') {
            items = `
                <li><img src="/assets/gestures/Thumbs_Up.png" alt="Thumbs Up"> Play</li>
                <li><img src="/assets/gestures/Thumbs_Down.png" alt="Thumbs Down"> Pause</li>
                <li><img src="/assets/gestures/Extend.png" alt="Extend"> Vol +</li>
                <li><img src="/assets/gestures/Flex.png" alt="Flex"> Vol -</li>
                <li><img src="/assets/gestures/Fist_Close.png" alt="Fist"> Mute</li>
            `;
        } else if (tabId === 'game') {
            items = `
                <li><img src="/assets/gestures/Flex.png" alt="Flex"> Move Left</li>
                <li><img src="/assets/gestures/Extend.png" alt="Extend"> Move Right</li>
                <li><img src="/assets/gestures/Thumbs_Up.png" alt="Thumbs Up"> Jump</li>
                <li><img src="/assets/gestures/Thumbs_Down.png" alt="Thumbs Down"> Pause</li>
                <li><img src="/assets/gestures/Fist_Close.png" alt="Fist"> Attack</li>
            `;
        } else if (tabId === 'ecommerce') {
            items = `
                <li><img src="/assets/gestures/Thumbs_Up.png" alt="Thumbs Up"> Cart / Buy</li>
                <li><img src="/assets/gestures/Thumbs_Down.png" alt="Thumbs Down"> Close</li>
                <li><img src="/assets/gestures/Extend.png" alt="Extend"> Rotate Left</li>
                <li><img src="/assets/gestures/Flex.png" alt="Flex"> Rotate Right</li>
                <li><img src="/assets/gestures/Fist_Close.png" alt="Fist"> Add to Cart</li>
            `;
        }
        ul.innerHTML = items;
    }
    
    // Resume/pause game
    if (tabId === 'game') {
        // Resize canvas on tab enter; game starts via player choice (Space / Thumbs Up)
        if (window.startGame && !window._gameInitialised) {
            window._gameInitialised = true; // triggers the init overlay once
        }
    }
    if (tabId !== 'game' && window.pauseGame) window.pauseGame();

    // Initialise analysis charts lazily when tab first opens
    if (tabId === 'analysis' && window.onAnalysisTabOpen) {
        setTimeout(window.onAnalysisTabOpen, 50); // slight delay so CSS layout finishes
    }
}

function showGlobalBadge(text) {
    const badge = document.getElementById('global-action');
    badge.innerText = text;
    badge.classList.remove('hidden');
    clearTimeout(window.badgeTimer);
    window.badgeTimer = setTimeout(() => badge.classList.add('hidden'), 1500);
}

function showOverlay(id, text) {
    const overlay = document.getElementById(id);
    overlay.innerText = text;
    overlay.classList.remove('hidden');
    setTimeout(() => overlay.classList.add('hidden'), 1000);
}

let selectedNavCardIndex = 0;

// Router
function handleGesture(g) {
    if (currentTab === 'welcome') handleWelcome(g);
    else if (currentTab === 'media') handleMedia(g);
    else if (currentTab === 'ecommerce') handleEcommerce(g);
    else if (currentTab === 'game') { if (window.handleGameGesture) window.handleGameGesture(g); }
}

function handleWelcome(g) {
    const cards = document.querySelectorAll('.welcome-nav-cards .nav-card');
    if (!cards || cards.length === 0) return;
    if (g === 'Extend') {
        selectedNavCardIndex = Math.min(cards.length - 1, selectedNavCardIndex + 1);
    } else if (g === 'Flex') {
        selectedNavCardIndex = Math.max(0, selectedNavCardIndex - 1);
    } else if (g === 'Thumbs_Up') {
        cards[selectedNavCardIndex].click();
        return;
    }
    cards.forEach((c, i) => c.classList.toggle('selected-card', i === selectedNavCardIndex));
}

// Media
function onYouTubeIframeAPIReady() {
    ytPlayer = new YT.Player('player', {
        videoId: 'JkaxUblCGz0', // Initial random video
        playerVars: { 'autoplay': 1, 'controls': 0, 'mute': 1 },
    });
}
window.changeVideo = (videoId) => {
    if (ytPlayer && ytPlayer.loadVideoById) {
        ytPlayer.loadVideoById(videoId);
    }
};
function handleMedia(g) {
    if (!ytPlayer || !ytPlayer.getPlayerState) return;
    if (g === 'Thumbs_Up') { ytPlayer.playVideo(); showOverlay('media-overlay', '▶️ Play'); }
    else if (g === 'Thumbs_Down') { ytPlayer.pauseVideo(); showOverlay('media-overlay', '⏸️ Pause'); }
    else if (g === 'Extend') { 
        volume = Math.min(100, volume + 10); ytPlayer.setVolume(volume); 
        showOverlay('media-overlay', `🔊 Vol ${volume}%`); 
    }
    else if (g === 'Flex') { 
        volume = Math.max(0, volume - 10); ytPlayer.setVolume(volume); 
        showOverlay('media-overlay', `🔉 Vol ${volume}%`); 
    }
    else if (g === 'Fist_Close') { 
        if (ytPlayer.isMuted()) ytPlayer.unMute(); else ytPlayer.mute();
        showOverlay('media-overlay', '🔇 Mute Toggle'); 
    }
}

// Ecommerce Dynamic API Integration & Cart Logic
const carouselEl = document.getElementById('carousel');
const spinner = document.getElementById('loading-spinner');

async function loadCategory(catName, el) {
    if(el) {
        document.querySelectorAll('.cat-wrapper').forEach(w => w.classList.remove('active'));
        el.classList.add('active');
    }
    
    // Hide carousel, show spinner
    carouselEl.style.display = 'none';
    spinner.style.display = 'block';

    const url = `https://dummyjson.com/products/category/${catName}`;

    try {
        const res = await fetch(url);
        const data = await res.json();
        let items = data.products || data; 
        
        // Mathematically guarantee exactly 10 items to preserve 3D arc shapes safely
        if(items.length > 0) {
            while(items.length < 10) { items = items.concat(items); }
        }
        
        ecomProducts = items.slice(0, 10); // Enforce exactly 10 items for carousel
        numProducts = ecomProducts.length;
        angleStep = 360 / Math.max(1, numProducts);
        carouselAngle = 0;
        
        buildCarousel(ecomProducts);
    } catch(err) {
        console.error("API Fetch Error:", err);
        spinner.innerText = "Error loading products.";
    }
}

function buildCarousel(items) {
    carouselEl.innerHTML = '';
    items.forEach((item, i) => {
        const deg = i * angleStep;
        const imgUrl = item.thumbnail || item.image; 
        const price = typeof item.price === 'number' ? (item.price * 83).toFixed(2) : item.price;
        const desc = item.description ? item.description.substring(0, 80) + '...' : '';
        const ratingVal = item.rating ? Math.round(item.rating) : 4;
        const stars = '★'.repeat(ratingVal) + '☆'.repeat(5 - ratingVal);
        
        const card = document.createElement('div');
        card.className = 'carousel-card';
        card.style.transform = `rotateY(${deg}deg) translateZ(450px)`;
        card.innerHTML = `
            <img src="${imgUrl}" alt="${item.title}">
            <div class="product-rating">${stars} <span>(${item.rating || '4.0'})</span></div>
            <h3>${item.title}</h3>
            <div class="desc">${desc}</div>
            <p class="price">₹${price}</p>
        `;
        carouselEl.appendChild(card);
    });

    spinner.style.display = 'none';
    carouselEl.style.display = 'block';
    carouselEl.style.transform = `rotateY(0deg)`;
}

// Fetch Initial Default
loadCategory('smartphones', document.querySelector('.cat-wrapper.active'));

function flyToBin(binId) {
    if(numProducts === 0) return;
    const cards = document.querySelectorAll('.carousel-card');
    
    let curIdx = Math.round(-carouselAngle / angleStep) % numProducts;
    if (curIdx < 0) curIdx += numProducts;
    let frontCard = cards[curIdx];
    if (!frontCard) return;
    
    const rect = frontCard.getBoundingClientRect();
    const clone = frontCard.cloneNode(true);
    clone.className = 'fly-clone';
    clone.style.left = rect.left + 'px';
    clone.style.top = rect.top + 'px';
    clone.style.width = rect.width + 'px';
    clone.style.height = rect.height + 'px';
    document.body.appendChild(clone);
    
    setTimeout(() => {
        const bin = document.getElementById(binId);
        if(!bin) return;
        const binRect = bin.getBoundingClientRect();
        clone.style.transform = `scale(0.1)`;
        clone.style.left = (binRect.left + binRect.width/2 - rect.width/2) + 'px';
        clone.style.top = (binRect.top + binRect.height/2 - rect.height/2) + 'px';
        clone.style.opacity = '0';
        
        setTimeout(() => {
            clone.remove();
            bin.classList.add('pop');
            setTimeout(() => bin.classList.remove('pop'), 200);
        }, 600);
    }, 10);
}

window.toggleCartModal = () => {
    const ov = document.getElementById('cart-overlay');
    ov.classList.toggle('hidden');
    if(!ov.classList.contains('hidden')) {
        renderCartUI();
    }
};

window.processCheckout = () => {
    if(cartItems.length === 0) {
        showGlobalBadge("Your bag is empty!");
        return;
    }
    cartItems = [];
    updateBinCounts();
    document.getElementById('cart-overlay').classList.add('hidden');
    document.getElementById('success-overlay').classList.remove('hidden');
};

window.closeSuccessOverlay = () => {
    document.getElementById('success-overlay').classList.add('hidden');
};

window.changeCartQty = (id, delta) => {
    const existing = cartItems.find(c => c.id === id);
    if(existing) {
        existing.quantity += delta;
        if(existing.quantity <= 0) {
            cartItems = cartItems.filter(c => c.id !== id);
        }
        updateBinCounts();
        renderCartUI();
    }
};

window.removeCartItem = (id) => {
    cartItems = cartItems.filter(c => c.id !== id);
    updateBinCounts();
    renderCartUI();
};

function updateBinCounts() {
    const totalItems = cartItems.reduce((sum, item) => sum + item.quantity, 0);
    document.getElementById('cart-count').innerText = `Bag (${totalItems})`; 
}

function renderCartUI() {
    const list = document.getElementById('cart-item-list');
    const tot = document.getElementById('cart-total');
    list.innerHTML = '';
    let totalScore = 0;
    
    if(cartItems.length === 0) {
        list.innerHTML = '<p style="color:var(--muted);text-align:center;margin-top:20px;">Your bag is empty.</p>';
    } else {
        cartItems.forEach(item => {
            const img = item.thumbnail || item.image;
            const inrPrice = item.price * 83;
            const subtotal = inrPrice * item.quantity;
            totalScore += subtotal;
            list.innerHTML += `
                <div class="cart-item">
                    <img src="${img}" class="cart-img">
                    <div class="cart-info">
                        <h4>${item.title}</h4>
                        <p>₹${inrPrice.toFixed(2)}</p>
                        <div class="cart-qty-controls">
                            <button class="cart-qty-btn" onclick="changeCartQty(${item.id}, -1)">-</button>
                            <span>${item.quantity}</span>
                            <button class="cart-qty-btn" onclick="changeCartQty(${item.id}, 1)">+</button>
                        </div>
                    </div>
                    <button class="cart-delete-btn" onclick="removeCartItem(${item.id})">✕</button>
                </div>
            `;
        });
    }
    tot.innerText = `₹${totalScore.toFixed(2)}`;
}

function handleEcommerce(g) {
    if(numProducts === 0) return; // Wait for load
    
    // Core Navigation (Extend/Flex remain rotation)
    if (g === 'Extend') { carouselAngle -= angleStep; carouselEl.style.transform = `rotateY(${carouselAngle}deg)`; return; }
    else if (g === 'Flex') { carouselAngle += angleStep; carouselEl.style.transform = `rotateY(${carouselAngle}deg)`; return; }
    
    let curIdx = Math.round(-carouselAngle / angleStep) % numProducts;
    if (curIdx < 0) curIdx += numProducts;
    const selectedProd = ecomProducts[curIdx];

    const cartModalOverlay = document.getElementById('cart-overlay');
    const isCartOpen = !cartModalOverlay.classList.contains('hidden');
    const successOverlay = document.getElementById('success-overlay');
    const isSuccessOpen = !successOverlay.classList.contains('hidden');

    if (isSuccessOpen) {
        if (g === 'Thumbs_Down') {
            closeSuccessOverlay();
        }
        return;
    }

    if (isCartOpen) {
        // Cart is open, use Thumbs_Up to Checkout, Thumbs_Down to Close
        if (g === 'Thumbs_Up') {
            processCheckout();
        } else if (g === 'Thumbs_Down') {
            toggleCartModal();
        }
        return;
    }

    if (g === 'Thumbs_Up') { 
        // Open Cart
        toggleCartModal();
    }
    else if (g === 'Thumbs_Down') { 
        // Dislike / Do nothing
        flyToBin('bin-dislike'); 
        setTimeout(() => { carouselAngle -= angleStep; carouselEl.style.transform = `rotateY(${carouselAngle}deg)`; }, 600);
    }
    else if (g === 'Fist_Close') { 
        // Add to Cart
        const existing = cartItems.find(c => c.id === selectedProd.id);
        if(existing) {
            existing.quantity++;
        } else {
            const prod = JSON.parse(JSON.stringify(selectedProd));
            prod.quantity = 1;
            cartItems.push(prod);
        }
        updateBinCounts();
        flyToBin('bin-cart');
        setTimeout(() => { carouselAngle -= angleStep; carouselEl.style.transform = `rotateY(${carouselAngle}deg)`; }, 600);
    }
}

// ── CV Cursor Control ────────────────────────────────────────────────────────

let cvActiveMode = null;   // 'hand' | 'eye' | null

/**
 * Toggle a CV mode. Calling with the same mode that is active turns it OFF.
 * Calling with a different mode switches to that mode.
 */
function toggleCVMode(mode) {
    if (cvActiveMode === mode) {
        // Turn off
        socket.emit('cv_stop');
    } else {
        // Switch to (or start) this mode
        socket.emit('cv_start', { mode });
    }
}

/** Update the UI toggle buttons and status badge from server state */
function applyCVStatus(mode) {
    cvActiveMode = mode;

    const handBtn  = document.getElementById('cv-hand-btn');
    const eyeBtn   = document.getElementById('cv-eye-btn');
    const dot      = document.getElementById('cv-status-dot');
    const txt      = document.getElementById('cv-status-text');

    if (!handBtn) return;

    // Reset both buttons
    handBtn.classList.remove('cv-active');
    eyeBtn.classList.remove('cv-active');
    dot.classList.remove('cv-dot-active');

    if (mode === 'hand') {
        handBtn.classList.add('cv-active');
        dot.classList.add('cv-dot-active');
        txt.textContent = 'Hand Active';
    } else if (mode === 'eye') {
        eyeBtn.classList.add('cv-active');
        dot.classList.add('cv-dot-active');
        txt.textContent = 'Eye Active';
    } else {
        txt.textContent = 'Mouse';
    }
}

// Listen for server CV status updates
socket.on('cv_status', (data) => {
    const mode = data.running ? data.mode : null;
    applyCVStatus(mode);
    // Show error if any
    if (data.error) {
        showGlobalBadge('⚠ Camera error: ' + data.error);
        console.error('[CV] Error:', data.error);
    }
});

// On page load, sync state from server
fetch('/api/cv_status').then(r => r.json()).then(d => applyCVStatus(d.running ? d.mode : null)).catch(()=>{});
