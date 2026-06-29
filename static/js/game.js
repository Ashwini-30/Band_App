// =========================================================
//  NATURE SPHERE — Red Ball 4 Aesthetic (Highly Polished)
//  Extremely detailed water, shadows, planted obstacles,
//  and completely fixed robust jump logic. Includes Day/Night Cycle!
// =========================================================

(function () {
  const canvas = document.getElementById('gameCanvas');
  const ctx    = canvas.getContext('2d');

  function resizeCanvas() {
    const p = canvas.parentElement;
    if (!p) return;
    canvas.width  = p.clientWidth  || 860;
    canvas.height = p.clientHeight || 500;
  }
  resizeCanvas();
  window.addEventListener('resize', () => { resizeCanvas(); envInit(); });

  const HORIZON_F   = 0.45;
  const LANE_SPREAD = 0.35; 
  const BASE_SPEED  = 4.2;
  const BALL_R      = 32; 
  const JUMP_DUR    = 75; // Expanded jump duration
  const ATK_DUR     = 55; // 0.9s punch
  const SPAWN_Z     = -0.15; 

  let S = {
    running: false, over: false,
    score: 0, dist: 0, speed: BASE_SPEED,
    lane: 1, toLane: 1, laneT: 1,
    jumpT: 0, atkT: 0,
    shieldOn: false, boostOn: false, magnetOn: false,
    boostTimer: 0, magnetTimer: 0, frames: 0,
    hi: parseInt(localStorage.getItem('ns3_hi') || '0'),
  };

  let obstacles    = [];
  let collectibles = [];
  let particles    = [];
  let clouds       = [];
  let hills        = [];
  let backgroundProps = []; 
  let stars        = [];

  const rnd = (a, b) => a + Math.random() * (b - a);

  function horizonY() { return canvas.height * HORIZON_F; }
  function floorY()   { return canvas.height; }

  function trackCurveOffset(z) {
    if (z < 0) z = 0;
    const wave1 = Math.sin((S.dist * 0.00035 + (1-z) * Math.PI)) * 0.45;
    return wave1 * canvas.width * 0.5 * (1-z);
  }

  function proj(laneIdx, z) {
    if (z < 0.005) z = 0.005; 
    const hw = canvas.width / 2;
    const hy = horizonY();
    const fh = floorY() - hy;
    const sy = hy + fh * Math.pow(z, 0.95);
    
    const pers = (z + 0.25) / 1.25; 
    const offsets = [-1, 0, 1];
    const sx = hw + trackCurveOffset(z) + offsets[laneIdx] * hw * LANE_SPREAD * 1.5 * pers;
    const sc = pers; 
    return { sx, sy, sc };
  }

  function projOffset(laneIdx, offsetX, z) {
    const p = proj(laneIdx, z);
    const hw = canvas.width / 2;
    p.sx += offsetX * hw * LANE_SPREAD * 0.5 * p.sc;
    return p;
  }

  function playerX(lane, toLane, t) {
    const eio = t < 0.5 ? 2*t*t : -1+(4-2*t)*t;
    function getX(l) { return proj(l, 1).sx; }
    return getX(lane) + (getX(toLane) - getX(lane)) * eio;
  }

  // =====================================================================
  //  ENVIRONMENT (Highly Detailed Farm Style)
  // =====================================================================
  function envInit() {
    const w = canvas.width, h = canvas.height, hy = horizonY();
    clouds = Array.from({length:5},()=>({ x: rnd(0, w*1.4), y: rnd(h*0.04, hy*0.4), s: rnd(0.5,1.2), spd: rnd(0.3,0.8) }));
    hills = [0, 1].map(layer => {
      const pts = []; const seg = 140;
      for (let x = -seg; x <= w + seg * 4; x += seg) {
        pts.push({ x, y: hy - rnd(20, 80) - layer * 30 });
      }
      return { pts, layer, spd: layer === 0 ? 0.08 : 0.18 };
    });
    backgroundProps = Array.from({length:15},(_,i)=>({x: (w/12)*i + rnd(-20,40), size: rnd(15,35), type: Math.random()>0.5?'tree':'bush'}));
    stars = Array.from({length:60},()=>({x: rnd(0, w), y: rnd(0, hy), s: rnd(1,3), o: rnd(0.2,1)}));
  }

  function drawSky(nightAlpha) {
    const w = canvas.width, hy = horizonY();
    
    // Base Day Sky
    const g = ctx.createLinearGradient(0, 0, 0, hy);
    g.addColorStop(0, '#4FC3F7'); g.addColorStop(1, '#E1F5FE');
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, hy);

    // Apply Night Sky Tint 
    if (nightAlpha > 0) {
      ctx.fillStyle = `rgba(10, 15, 36, ${Math.min(1, nightAlpha*1.1)})`;
      ctx.fillRect(0, 0, w, hy);
      
      // Draw Stars
      stars.forEach(st => {
        const twinkle = Math.sin(S.frames*0.05 + st.x);
        ctx.fillStyle = `rgba(255,255,255,${st.o * nightAlpha * (0.5 + 0.5*twinkle)})`;
        ctx.beginPath(); ctx.arc(st.x, st.y, st.s, 0, Math.PI*2); ctx.fill();
      });
    }

    const dayAlpha = Math.max(0, 1 - nightAlpha*1.5);
    
    // Draw Sun Array
    if (dayAlpha > 0) {
      ctx.globalAlpha = dayAlpha;
      const sx = w * 0.3, sy = hy * 0.4;
      const sg = ctx.createRadialGradient(sx, sy, 5, sx, sy, 80);
      sg.addColorStop(0, 'rgba(255,235,59,0.8)'); sg.addColorStop(1, 'rgba(255,235,59,0)');
      ctx.fillStyle=sg; ctx.beginPath(); ctx.arc(sx, sy, 80, 0, Math.PI*2); ctx.fill();
      ctx.fillStyle='#FFF59D'; ctx.beginPath(); ctx.arc(sx, sy, 25, 0, Math.PI*2); ctx.fill();
      ctx.globalAlpha = 1;
    }

    // Draw Moon Array
    if (nightAlpha > 0.2) {
      ctx.globalAlpha = Math.min(1, nightAlpha*1.2);
      const mx = w * 0.7, my = hy * 0.3;
      ctx.fillStyle='rgba(255,255,255,0.1)'; ctx.beginPath(); ctx.arc(mx, my, 60, 0, Math.PI*2); ctx.fill();
      ctx.fillStyle='#E2E8F0'; ctx.beginPath(); ctx.arc(mx, my, 22, 0, Math.PI*2); ctx.fill();
      ctx.fillStyle='#94A3B8'; ctx.beginPath(); ctx.arc(mx+6, my-4, 5, 0, Math.PI*2); ctx.fill();
      ctx.beginPath(); ctx.arc(mx-8, my+6, 3, 0, Math.PI*2); ctx.fill();
      ctx.globalAlpha = 1;
    }
  }

  function drawClouds(nightAlpha) {
    const w = canvas.width;
    ctx.fillStyle = `rgba(255,255,255,${1 - nightAlpha*0.6})`;
    clouds.forEach(c => {
      if (S.running) c.x -= c.spd + S.speed * 0.03;
      if (c.x < -180*c.s) c.x = w + 80;
      ctx.save(); ctx.translate(c.x, c.y); ctx.scale(c.s, c.s);
      ctx.beginPath(); ctx.arc(0, 0, 30, 0, Math.PI*2); ctx.fill();
      ctx.beginPath(); ctx.arc(35, 10, 25, 0, Math.PI*2); ctx.fill();
      ctx.beginPath(); ctx.arc(-30, 5, 20, 0, Math.PI*2); ctx.fill();
      ctx.restore();
    });
  }

  function drawScenery(nightAlpha) {
    const w = canvas.width, hy = horizonY();
    
    // Smooth Rolling Hills
    hills.forEach(h2 => {
      if (S.running) h2.pts.forEach(p => p.x -= h2.spd * S.speed);
      while (h2.pts[0].x < -200) {
        h2.pts.shift(); h2.pts.push({ x: h2.pts[h2.pts.length-1].x + 140, y: hy - rnd(30,90) - h2.layer*30 });
      }

      ctx.beginPath(); ctx.moveTo(0, hy+20); ctx.lineTo(h2.pts[0].x, h2.pts[0].y);
      for (let i = 1; i < h2.pts.length; i++) {
        const pm = h2.pts[i-1], pc = h2.pts[i];
        ctx.bezierCurveTo(pm.x+(pc.x-pm.x)*0.5, pm.y, pc.x-(pc.x-pm.x)*0.5, pc.y, pc.x, pc.y);
      }
      ctx.lineTo(w, hy+20); ctx.closePath();
      ctx.fillStyle = h2.layer === 0 ? '#66BB6A' : '#A5D6A7'; ctx.fill();

      // Hill Outline
      ctx.strokeStyle = h2.layer === 0 ? '#4CAF50' : '#81C784';
      ctx.lineWidth=4; ctx.stroke();
    });

    // Draw highly detailed cute trees on hills
    backgroundProps.forEach(bp => {
       if(S.running) bp.x -= 0.05 * S.speed;
       if(bp.x < -50) bp.x = w + 50;
       
       ctx.save(); ctx.translate(bp.x, hy - 40);
       if (bp.type === 'tree') {
         // Trunk
         ctx.fillStyle = '#5D4037'; ctx.fillRect(-4, 0, 8, 25); 
         // Fluffy canopy
         ctx.fillStyle = '#2E7D32'; 
         ctx.beginPath(); ctx.arc(0, -15, bp.size, 0, Math.PI*2); ctx.fill();
         ctx.beginPath(); ctx.arc(-bp.size*0.6, -5, bp.size*0.7, 0, Math.PI*2); ctx.fill();
         ctx.beginPath(); ctx.arc(bp.size*0.6, -5, bp.size*0.7, 0, Math.PI*2); ctx.fill();
         ctx.fillStyle = '#4CAF50'; // Highlights
         ctx.beginPath(); ctx.arc(-2, -20, bp.size*0.5, 0, Math.PI*2); ctx.fill();
       } else {
         ctx.fillStyle = '#43A047';
         ctx.beginPath(); ctx.ellipse(0, 5, bp.size*1.2, bp.size*0.6, 0, 0, Math.PI*2); ctx.fill();
       }
       ctx.restore();
    });

    // Highly Detailed Beautiful Water
    const h = canvas.height;
    ctx.fillStyle = '#039BE5'; 
    ctx.fillRect(0, hy+10, w, h-hy-10);
    
    // Wave layers tracking perspective depth
    for(let r=0; r<12; r++) {
       const zy = (S.dist*0.002 + r/12) % 1;
       const y = hy + 10 + (h-hy)*Math.pow(zy, 1.8);
       
       // Back waves are thin, front are thick
       const thick = 1 + 10 * Math.pow(zy, 2);
       const ww = 100 + 400 * zy;
       const leftOffset = Math.sin((S.dist*0.05) + r) * 30;

       ctx.fillStyle = r%2===0 ? '#81D4FA' : '#29B6F6'; 
       ctx.beginPath();
       ctx.ellipse(w/2 + leftOffset, y, ww, thick, 0, 0, Math.PI*2);
       ctx.ellipse(w/4 - leftOffset, y + thick*2, ww*0.7, thick*0.8, 0, 0, Math.PI*2);
       ctx.ellipse(3*w/4 + leftOffset, y - thick, ww*0.8, thick*0.9, 0, 0, Math.PI*2);
       ctx.fill();

       // Sun / Moon reflections on the water!
       const reflectAlpha = (1-zy) * (nightAlpha > 0.5 ? nightAlpha : 1-nightAlpha);
       ctx.fillStyle = nightAlpha > 0.5 ? `rgba(255,255,255,${reflectAlpha*0.3})` : `rgba(255,235,59,${reflectAlpha*0.4})`;
       const rx = w * (nightAlpha>0.5 ? 0.7 : 0.3) + Math.sin(S.frames*0.1 + r)*5;
       ctx.fillRect(rx - 30*zy, y, 60*zy, thick*0.5);
    }
  }

  function drawCartoonPath() {
    const zStep = 0.04;
    const baseOffset = (S.dist * 0.003) % zStep;

    const plL = []; const plR = [];
    for (let z = 1.05; z >= 0.01; z -= zStep) {
      let az = z - baseOffset;
      if (az < 0.005) az = 0.005;
      plL.push({ z: az, p: projOffset(0, -1.6, az) });
      plR.push({ z: az, p: projOffset(2,  1.6, az) });
    }

    // Top Grass Surface
    for(let i=0; i<plL.length-1; i++) {
        const curL = plL[i].p; const curR = plR[i].p;
        const nexL = plL[i+1].p; const nexR = plR[i+1].p;
        
        // Alternating grass stripes
        const cycle = i % 2 === 0;
        ctx.fillStyle = cycle ? '#8BC34A' : '#7CB342'; 
        ctx.beginPath();
        ctx.moveTo(curL.sx, curL.sy); ctx.lineTo(curR.sx, curR.sy);
        ctx.lineTo(nexR.sx, nexR.sy); ctx.lineTo(nexL.sx, nexL.sy);
        ctx.fill();

        // Thick Grass Outline highlight
        ctx.fillStyle = '#AED581';
        ctx.beginPath(); ctx.moveTo(curL.sx, curL.sy); ctx.lineTo(curL.sx + 10*curL.sc, curL.sy);
        ctx.lineTo(nexL.sx + 10*nexL.sc, nexL.sy); ctx.lineTo(nexL.sx, nexL.sy); ctx.fill();

        // Dirt Sides dropping down
        const curZ = plL[i].z, nexZ = plL[i+1].z;
        ctx.fillStyle = '#795548'; // Left
        ctx.beginPath();
        ctx.moveTo(curL.sx, curL.sy); ctx.lineTo(curL.sx, curL.sy + 45*curZ);
        ctx.lineTo(nexL.sx, nexL.sy + 45*nexZ); ctx.lineTo(nexL.sx, nexL.sy);
        ctx.fill();

        ctx.fillStyle = '#5D4037'; // Right Side (shadowed)
        ctx.beginPath();
        ctx.moveTo(curR.sx, curR.sy); ctx.lineTo(curR.sx, curR.sy + 45*curZ);
        ctx.lineTo(nexR.sx, nexR.sy + 45*nexZ); ctx.lineTo(nexR.sx, nexR.sy);
        ctx.fill();
        
        // Dirt Rock Embedded Detailing
        if(i%2!==0) {
          ctx.fillStyle = '#B0BEC5';
          ctx.beginPath(); ctx.arc(curL.sx, curL.sy + 20*curZ, 6*curZ, 0, Math.PI*2); ctx.fill();
          ctx.beginPath(); ctx.arc(curR.sx, curR.sy + 25*curZ, 4*curZ, 0, Math.PI*2); ctx.fill();
        }

        // Top depth shadow
        ctx.fillStyle = 'rgba(0,0,0,0.15)';
        ctx.beginPath(); ctx.moveTo(curL.sx, curL.sy); ctx.lineTo(curL.sx, curL.sy+6*curZ);
        ctx.lineTo(nexL.sx, nexL.sy+6*nexZ); ctx.lineTo(nexL.sx, nexL.sy); ctx.fill();
    }
  }

  // =====================================================================
  //  BALL — Character with angry face
  // =====================================================================
  function drawBall() {
    const bx = playerX(S.lane, S.toLane, S.laneT);
    const h  = canvas.height, r = BALL_R * 1.3; 

    let yOff = 0;
    // HUGE visual jump arc prevents overlap with barricade art!
    if (S.jumpT > 0) { const t = S.jumpT / JUMP_DUR; yOff = 280 * 4 * t * (1 - t); }
    const by = h - r - 25 - yOff;

    const shadowSc = Math.max(0.2, 1 - yOff/250);
    ctx.fillStyle = 'rgba(27,94,32,0.6)'; // shadow stays exactly on ground
    ctx.beginPath(); ctx.ellipse(bx, h-15, r*shadowSc, 8*shadowSc, 0, 0, Math.PI*2); ctx.fill();

    if (S.atkT > 0) {
      const af = S.atkT / ATK_DUR;
      ctx.beginPath(); ctx.arc(bx, by, r+30*af, 0, Math.PI*2);
      ctx.fillStyle = `rgba(255,255,255,${af*0.5})`; ctx.fill();
    }
    if (S.shieldOn) {
      ctx.beginPath(); ctx.arc(bx, by, r+16, 0, Math.PI*2);
      ctx.strokeStyle = `rgba(129,212,250,${0.6+0.4*Math.sin(S.frames*0.2)})`;
      ctx.lineWidth=6; ctx.stroke();
    }

    ctx.save(); ctx.translate(bx, by);

    // Ball Art...
    ctx.fillStyle = 'black'; ctx.beginPath(); ctx.arc(0,0,r+3,0,Math.PI*2); ctx.fill();

    const bg = ctx.createRadialGradient(-r*0.2,-r*0.2,r*0.1,0,0,r);
    bg.addColorStop(0,'#FF5252'); bg.addColorStop(0.5,'#E53935'); bg.addColorStop(1,'#B71C1C');
    ctx.fillStyle = bg; ctx.beginPath(); ctx.arc(0,0,r,0,Math.PI*2); ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath(); ctx.ellipse(-12, -8, 12, 14, -0.2, 0, Math.PI*2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(12, -8, 12, 14, 0.2, 0, Math.PI*2); ctx.fill();

    ctx.fillStyle = 'black';
    let look = (S.laneT<0.5) ? (S.toLane-S.lane)*4 : 0; 
    ctx.beginPath(); ctx.arc(-10+look, -6, 5, 0, Math.PI*2); ctx.fill();
    ctx.beginPath(); ctx.arc(10+look, -6, 5, 0, Math.PI*2); ctx.fill();

    ctx.lineWidth = 4; ctx.strokeStyle = 'black'; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(-25, -18); ctx.lineTo(-5, -10); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(25, -18); ctx.lineTo(5, -10); ctx.stroke();

    ctx.beginPath(); ctx.moveTo(5, 15); ctx.quadraticCurveTo(15, 20, 22, 10); ctx.stroke();

    ctx.restore();
  }

  // =====================================================================
  //  OBSTACLES — Procedural Stones & Grounded Props
  // =====================================================================
  function drawObstacles() {
    const sorted = [...obstacles].sort((a,b)=>b.z-a.z);
    sorted.forEach(o => {
      if (o.dead) return;
      const {sx, sy, sc} = proj(o.lane, o.z);
      ctx.save(); ctx.translate(sx, sy); ctx.scale(sc, sc);

      // Deep ground shadow 
      ctx.fillStyle = 'rgba(27,94,32,0.8)'; 
      ctx.beginPath(); ctx.ellipse(0, 0, 80, 15, 0, 0, Math.PI*2); ctx.fill();

      if (o.type === 'barrier') {
        const bw = 180, bh = 60, bY = -10;
        
        ctx.fillStyle = '#5D4037'; 
        ctx.fillRect(-bw/2+18, bY-bh, 24, bh + 10); 
        ctx.fillRect(bw/2-42, bY-bh, 24, bh + 10); 

        ctx.fillStyle = '#795548'; 
        ctx.fillRect(-bw/2+20, bY-bh+2, 20, bh + 10); 
        ctx.fillRect(bw/2-40, bY-bh+2, 20, bh + 10); 
        
        ctx.fillStyle = '#3E2723'; 
        ctx.fillRect(-bw/2, bY-bh+10, bw, 20);
        ctx.fillRect(-bw/2+10, bY-bh+38, bw-20, 20);

        ctx.fillStyle = '#8D6E63'; 
        ctx.fillRect(-bw/2, bY-bh+12, bw, 16);
        ctx.fillRect(-bw/2+10, bY-bh+40, bw-20, 16);

        ctx.strokeStyle = '#5D4037'; ctx.beginPath();
        ctx.moveTo(-bw/2+30, bY-bh+18); ctx.lineTo(-bw/2+80, bY-bh+16); ctx.stroke();
        ctx.moveTo(bw/2-70, bY-bh+44); ctx.lineTo(bw/2-30, bY-bh+46); ctx.stroke();

      } else if (o.type === 'stone') {
        const rw = 140, rh = 80; 
        const shY = -5;  

        // Uses procedural shape array generated at spawn
        ctx.fillStyle = 'black'; 
        ctx.beginPath(); 
        ctx.moveTo(-rw*0.4, shY);
        ctx.quadraticCurveTo(-rw*0.45 * o.shape[0], shY-rh*0.6*o.shape[1], 0, shY-rh*o.shape[2]);
        ctx.quadraticCurveTo(rw*0.45 * o.shape[3], shY-rh*0.6*o.shape[4], rw*0.4, shY);
        ctx.closePath(); ctx.fill();

        const rg = ctx.createRadialGradient(-rw*0.1, shY-rh*0.7, 5, 0, shY-rh*0.5, rw*0.6);
        rg.addColorStop(0, '#ECEFF1'); rg.addColorStop(0.5, '#90A4AE'); rg.addColorStop(1, '#546E7A');
        ctx.fillStyle = rg; 
        ctx.beginPath(); 
        ctx.moveTo(-rw*0.38, shY);
        ctx.quadraticCurveTo(-rw*0.42 * o.shape[0], shY-rh*0.6*o.shape[1], 0, shY-rh*0.95*o.shape[2]);
        ctx.quadraticCurveTo(rw*0.42 * o.shape[3], shY-rh*0.6*o.shape[4], rw*0.38, shY);
        ctx.closePath(); ctx.fill();

        ctx.fillStyle = 'rgba(0,0,0,0.15)';
        ctx.fillRect(-rw*0.35, shY-15, rw*0.7, 15);
        
        ctx.fillStyle = '#689F38';
        ctx.beginPath(); ctx.ellipse(-rw*0.1, shY-5, rw*0.2, 10, -0.1, 0, Math.PI*2); ctx.fill();
        ctx.fillStyle = '#8BC34A';
        ctx.beginPath(); ctx.arc(-rw*0.15, shY-15, 12, 0, Math.PI*2); ctx.fill();
        ctx.beginPath(); ctx.arc(-rw*0.05, shY-10, 8, 0, Math.PI*2); ctx.fill();
      }
      ctx.restore();
    });
  }

  function drawCollectibles() {
    collectibles.forEach(c => {
      if (c.collected) return;
      const {sx,sy,sc} = proj(c.lane, c.z);
      const bob = Math.sin(S.frames*0.1 + c.phase)*15*sc;
      ctx.save(); ctx.translate(sx, sy+bob); ctx.scale(sc, sc);

      if (c.type === 'coin') {
        const cr = 40; const cy = -70;
        ctx.fillStyle = 'rgba(27,94,32,0.6)'; 
        ctx.beginPath(); ctx.ellipse(0, -bob, cr*0.8, 8, 0, 0, Math.PI*2); ctx.fill();

        ctx.shadowColor = '#FDE047'; ctx.shadowBlur=10;
        ctx.lineWidth=4; ctx.strokeStyle='black';
        ctx.beginPath(); ctx.arc(0, cy, cr, 0, Math.PI*2); ctx.fill(); ctx.stroke();

        const fg = ctx.createLinearGradient(0, cy-cr, 0, cy+cr);
        fg.addColorStop(0,'#FFEE58'); fg.addColorStop(1,'#FBC02D');
        ctx.fillStyle = fg; ctx.beginPath(); ctx.arc(0, cy, cr, 0, Math.PI*2); ctx.fill();
        ctx.shadowBlur=0;
        
        ctx.lineWidth=3; ctx.strokeStyle='black';
        ctx.beginPath(); ctx.arc(0,cy,cr*0.7,0,Math.PI*2); ctx.stroke();

        ctx.fillStyle = 'black'; ctx.beginPath();
        for(let i=0;i<10;i++){
           let a=(i*Math.PI/5)-Math.PI/2; let rd=i%2===0?cr*0.4:cr*0.2;
           i===0?ctx.moveTo(Math.cos(a)*rd,cy+Math.sin(a)*rd):ctx.lineTo(Math.cos(a)*rd,cy+Math.sin(a)*rd);
        }
        ctx.closePath(); ctx.fill(); 
      } else {
        const pcol = c.type==='shield'?'#81D4FA':c.type==='boost'?'#FFCC80':'#F48FB1';
        const pico = c.type==='shield'?'🛡️':c.type==='boost'?'⚡':'🧲';
        ctx.shadowColor=pcol; ctx.shadowBlur=20; ctx.font=`48px Arial`; ctx.textAlign='center';
        ctx.fillText(pico, 0, -40); ctx.shadowBlur=0;
      }
      ctx.restore();
    });
  }

  function spawnP(x, y, col, n, spd, cfg) {
    const c=cfg||{};
    for(let i=0;i<n;i++){
      const a=Math.random()*Math.PI*2, s=spd*(0.5+Math.random());
      particles.push({ x,y, vx:Math.cos(a)*s, vy:Math.sin(a)*s-(c.up||0),
        color:col, life:c.life||24, maxLife:c.life||24, size:c.size||5, grav:c.grav??0.25, shape:c.shape||'circle' });
    }
  }

  function drawParticles() {
    particles.forEach(p=>{
      p.x+=p.vx; p.y+=p.vy; p.vy+=p.grav; p.vx*=0.95; p.life--;
      const a=p.life/p.maxLife; ctx.globalAlpha=a; ctx.fillStyle=p.color;
      if(p.shape==='circle'){
        ctx.beginPath(); ctx.arc(p.x,p.y,p.size*a,0,Math.PI*2); ctx.fill();
        ctx.strokeStyle='black'; ctx.lineWidth=1; ctx.stroke();
      } else {
        const s=p.size*a;ctx.fillRect(p.x-s/2,p.y-s/2,s,s);
      }
    });
    ctx.globalAlpha=1; particles=particles.filter(p=>p.life>0);
  }

  function drawHUD() {
    const w=canvas.width, h=canvas.height;
    const sx=w-160, sy=18, sw=140, sh=65;
    ctx.fillStyle='rgba(62,39,35,0.85)'; ctx.beginPath(); ctx.roundRect(sx,sy,sw,sh,8); ctx.fill();
    ctx.strokeStyle='#D7CCC8'; ctx.lineWidth=3; ctx.stroke();
    
    ctx.fillStyle='white'; ctx.font='10px Inter'; ctx.textAlign='left'; ctx.fillText('SCORE', sx+14, sy+18);
    ctx.textAlign='right'; ctx.fillText(`BEST ${S.hi}`, sx+sw-14, sy+18);
    ctx.fillStyle='#FFEE58'; ctx.font='bold 26px Inter'; ctx.textAlign='center'; ctx.fillText(String(S.score), sx+sw/2, sy+48);
  }

  function spawnObstacle() {
    const rShape = [rnd(0.8,1.2), rnd(0.8,1.2), rnd(0.8,1.2), rnd(0.8,1.2), rnd(0.8,1.2)];
    obstacles.push({ type: Math.random()<0.5?'barrier':'stone', lane:Math.floor(Math.random()*3), z:SPAWN_Z, evaded:false, dead:false, shape: rShape, phase:Math.random()*6 });
  }

  function spawnCollectible() {
    const r=Math.random(); const type = r>0.98?'magnet':r>0.95?'boost':r>0.92?'shield':'coin';
    const lane=Math.floor(Math.random()*3);
    const count=type==='coin'?1+Math.floor(Math.random()*2):1; 
    for(let i=0;i<count;i++){
      collectibles.push({ type, lane, z:SPAWN_Z-i*0.06, collected:false, phase:Math.random()*6 });
    }
  }

  function gameLoop(){
    if(!S.running) return;
    S.frames++; ctx.clearRect(0,0,canvas.width,canvas.height);

    // DAY / NIGHT CALCULATION (Faster cycle for gameplay)
    const nightPhase = Math.sin(S.dist * 0.001);
    const nightAlpha = Math.max(0, nightPhase); // 0 during day, goes to 1 during deep night limit

    drawSky(nightAlpha); drawClouds(nightAlpha); drawScenery(nightAlpha); drawCartoonPath();
    drawObstacles(); drawCollectibles(); drawBall(); drawParticles(); 
    
    // Apply massive Night Tint over everything EXCEPT HUD
    if (nightAlpha > 0) {
      ctx.fillStyle = `rgba(15, 23, 42, ${nightAlpha * 0.6})`;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    
    drawHUD();
    updateWorld();
    requestAnimationFrame(gameLoop);
  }

  function updateWorld(){
    if(S.laneT<1){ S.laneT=Math.min(1,S.laneT+0.12); if(S.laneT>=1) S.lane=S.toLane; }
    if(S.jumpT>0){ S.jumpT++; if(S.jumpT>JUMP_DUR) S.jumpT=0; }
    if(S.atkT>0) S.atkT--;
    
    if(S.boostOn&&--S.boostTimer<=0) S.boostOn=false;
    if(S.magnetOn&&--S.magnetTimer<=0) S.magnetOn=false;
    
    if(S.magnetOn){
      collectibles.forEach(c=>{
        if(c.collected) return;
        const {sx}=proj(c.lane,c.z), {sx:bx}=proj(S.toLane,c.z);
        if(Math.abs(sx-bx)<400) c.z+=S.speed*0.0005*0.45;
      });
    }

    const zStep = S.speed*0.0006; 
    obstacles    = obstacles.map(o=>({...o,z:o.z+zStep})).filter(o=>o.z<1.25);
    collectibles = collectibles.map(c=>({...c,z:c.z+zStep})).filter(c=>c.z<1.25);

    const of2 = Math.max(100, 150-S.dist/400); 
    const cf2 = Math.max(70, 110-S.dist/500);
    if(S.frames%Math.floor(of2)===0) spawnObstacle();
    if(S.frames%Math.floor(cf2)===0) spawnCollectible();

    S.dist += S.speed;
    if(!S.boostOn) S.speed = BASE_SPEED + S.dist/4000;
    
    checkCollisions();
  }

  function checkCollisions() {
    const bx = playerX(S.lane, S.toLane, S.laneT);
    const h  = canvas.height;
    
    obstacles.forEach(o=>{
      if(o.dead || o.evaded) return;
      if(o.z < 0.88 || o.z > 1.05) return;
      if(o.lane !== S.toLane) return;
      const {sx, sy} = proj(o.lane, o.z);
      if (Math.abs(bx - sx) > 60) return; 
      
      // EXTREME visual jump + immunity 
      if(S.jumpT > 0) {
          o.evaded = true; 
          return; 
      }

      if(o.type === 'stone' && S.atkT > 0){
        o.dead = true; S.score += 150;
        spawnP(sx,sy-40,'#B0BEC5',40,16,{life:50,size:14,shape:'circle',up:6}); 
        return;
      }
      
      if(S.shieldOn){
        S.shieldOn=false; o.dead=true;
        spawnP(sx,sy-30,'#81D4FA',30,10,{life:35,shape:'circle',up:4}); return; 
      }
      gameOver(bx, h-BALL_R-25);
    });

    collectibles.forEach(c=>{
      if(c.collected) return;
      if(c.z<0.80||c.z>0.98) return;
      const inLane=c.lane===S.toLane;
      const magnet=S.magnetOn&&Math.abs(c.lane-S.toLane)<=1;
      if(!inLane&&!magnet) return;
      const {sx,sy}=proj(c.lane,c.z);
      if(Math.hypot(bx-sx,(h-BALL_R-25)-sy)>BALL_R+50) return;
      c.collected=true; S.score+=10;
      if(c.type==='coin') spawnP(sx,sy,'#FFEE58',12,6,{life:20,shape:'circle',up:2,size:8}); 
      else if(c.type==='shield') { S.shieldOn=true; spawnP(sx,sy,'#81D4FA',20,8,{life:25}); }
      else if(c.type==='boost') { S.boostOn=true;S.boostTimer=350;S.speed=Math.min(S.speed+8,50);spawnP(sx,sy,'#FFCC80',20,8,{life:25}); }
      else if(c.type==='magnet') { S.magnetOn=true;S.magnetTimer=400;spawnP(sx,sy,'#F48FB1',20,8,{life:25}); }
    });
  }

  function gameOver(bx,by){
    if(!S.running||S.over) return;
    S.running=false; S.over=true;
    spawnP(bx,by,'#D32F2F',45,15,{life:60,size:14,shape:'circle',up:8}); 
    if(S.score>S.hi){S.hi=S.score;localStorage.setItem('ns3_hi',String(S.hi));}
    setTimeout(()=>{
      const ov=document.getElementById('game-overlay');
      ov.innerHTML=`<div style="text-align:center;font-family:Inter,sans-serif;">
        <div style="font-size:2.8rem;font-weight:900;margin-bottom:8px;color:#FF5252;text-shadow:3px 3px 0px black">💥 CRASHED!</div>
        <div style="font-size:1.6rem;margin-bottom:6px;color:white;text-shadow:2px 2px 0px black">Score: <strong style="color:#FFEE58">${S.score}</strong></div>
        <div style="font-size:1rem;color:white;margin-bottom:24px">🏆 Best: ${S.hi}</div>
        <div style="font-size:1.1rem;font-weight:bold;background:#FF5252;padding:14px 28px;border-radius:12px;border:4px solid black;color:white;box-shadow:4px 4px 0px black;cursor:pointer;">
          👍 Thumbs Up to Restart
        </div>
      </div>`;
      ov.classList.remove('hidden');
    },600);
  }

  function moveLeft(){  if(!S.running) return; if(S.toLane>0){ S.lane=S.toLane; S.toLane--; S.laneT=0; } }
  function moveRight(){ if(!S.running) return; if(S.toLane<2){ S.lane=S.toLane; S.toLane++; S.laneT=0; } }
  function doJump(){
    if(!S.running) return;
    if(S.jumpT===0){ S.jumpT=1; spawnP(playerX(S.lane,S.toLane,S.laneT),canvas.height-BALL_R-20,'#FFFFFF',12,6,{life:20,shape:'circle',up:4,size:8}); }
  }
  function doAttack(){
    if(!S.running) return;
    S.atkT = ATK_DUR; spawnP(playerX(S.lane,S.toLane,S.laneT),canvas.height-BALL_R-65,'#FFFFFF',20,8,{life:24,size:10,shape:'circle',up:6});
  }

  const keys={};
  document.addEventListener('keydown',e=>{
    if(keys[e.code]) return; keys[e.code]=true;
    if(!S.running){ if(e.code==='Space'||e.code==='ArrowUp'){startGame();return;} }
    if(e.code==='ArrowLeft')  moveLeft();
    if(e.code==='ArrowRight') moveRight();
    if(e.code==='Space'||e.code==='ArrowUp'){ e.preventDefault(); doJump(); }
    if(e.key==='z'||e.key==='Z') doAttack();
  });
  document.addEventListener('keyup',e=>{ delete keys[e.code]; });

  window.handleGameGesture=g=>{
    if(!S.running){ if(g==='Thumbs_Up'||g==='Fist_Close'){startGame();return;} }
    if(g==='Flex') moveLeft(); if(g==='Extend') moveRight();
    if(g==='Thumbs_Up') doJump(); if(g==='Fist_Close') doAttack();
    if(g==='Thumbs_Down') window.pauseGame();
  };

  function resetState(){
    Object.assign(S,{
      running:false,over:false,score:0,dist:0,speed:BASE_SPEED,
      lane:1,toLane:1,laneT:1,jumpT:0,atkT:0,shieldOn:false,boostOn:false,magnetOn:false,
      boostTimer:0,magnetTimer:0,frames:0,
    });
    obstacles=[]; collectibles=[]; particles=[]; clouds=[]; hills=[]; backgroundProps=[]; envInit();
  }

  window.startGame=()=>{
    document.getElementById('game-overlay').classList.add('hidden');
    resizeCanvas(); resetState(); S.running=true;
    requestAnimationFrame(gameLoop);
  };
  window.pauseGame=()=>{ S.running=false; };

  (function init(){
    resizeCanvas(); resetState();
    const ov=document.getElementById('game-overlay');
    ov.innerHTML=`<div style="text-align:center;font-family:Inter,sans-serif;width:100%">
      <div style="font-size:3.2rem;font-weight:900;letter-spacing:-1px;margin-bottom:6px;background:linear-gradient(to right, #EF5350, #E53935);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-shadow: 3px 3px 0px black">Nature Sphere</div>
      <div style="font-size:1.15rem;font-weight:900;color:black;margin-bottom:26px">Cartoon World Custom</div>
      
      <div style="background:rgba(255,255,255,0.8);backdrop-filter:blur(10px);border-radius:18px;padding:24px;border:3px solid black;margin-bottom:28px">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;font-size:1rem;color:black">
          <div style="display:flex;align-items:center;gap:12px;font-weight:bold"><span style="font-size:1.3rem">🤚</span> Flex/Extend ➔ Steer</div>
          <div style="display:flex;align-items:center;gap:12px;justify-content:flex-end">Collect 🟡 Big Coins</div>
          <div style="display:flex;align-items:center;gap:12px;font-weight:bold"><span style="font-size:1.3rem">👍</span> Thumbs Up ➔ Jump</div>
          <div style="display:flex;align-items:center;gap:12px;justify-content:flex-end"><span style="background:#4CAF50;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:bold;color:white;border:2px solid black">JUMP</span> Fences</div>
          <div style="display:flex;align-items:center;gap:12px;font-weight:bold"><span style="font-size:1.3rem">✊</span> Fist Close ➔ Attack</div>
          <div style="display:flex;align-items:center;gap:12px;justify-content:flex-end"><span style="background:#F44336;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:bold;color:white;border:2px solid black">SMASH</span> Stones</div>
        </div>
      </div>
      
      <div style="font-size:1.1rem;font-weight:900;background:#4CAF50;color:white;padding:16px 36px;border-radius:14px;display:inline-block;border:4px solid black;text-transform:uppercase;letter-spacing:1px;box-shadow:4px 4px 0px black">
        👍 Thumbs Up to Play
      </div>
    </div>`;
    ov.classList.remove('hidden');
    drawSky(0); drawClouds(0); drawScenery(0); drawCartoonPath(); drawBall();
  })();

})();
