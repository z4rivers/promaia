/**
 * Atmospherics — skin-specific background effects
 *
 * Neo-Tokyo: floating particles (city dust, neon motes)
 * Data Temple: matrix-rain falling characters
 * Evening Garden: firefly dots that fade in/out
 *
 * Stone Garden, Ink Wash: nothing (stillness IS the design)
 * Superflat: nothing (flatness means no atmospheric depth)
 */

(function () {
  const skin = document.body.dataset.skin;
  const atmo = document.querySelector('.atmosphere');
  if (!atmo) return;

  const effects = {
    'neo-tokyo': initNeoTokyo,
    'data-temple': initDataTemple,
    'evening-garden': initEveningGarden,
  };

  if (effects[skin]) effects[skin](atmo);

  /* ================================================================
   * Neo-Tokyo: floating particles — city dust, neon motes
   * Tiny dots that drift slowly, fade, and respawn.
   * Colors: Akira Red, Neon Jade, Digital Iris at low opacity.
   * ================================================================ */
  function initNeoTokyo(container) {
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;';
    container.appendChild(canvas);
    const ctx = canvas.getContext('2d');

    const PARTICLE_COUNT = 60;
    const colors = [
      { r: 218, g: 29, b: 31 },   // Akira Red
      { r: 0, g: 212, b: 170 },    // Neon Jade
      { r: 108, g: 92, b: 231 },   // Digital Iris
      { r: 245, g: 240, b: 232 },  // Washi Warm
    ];

    let particles = [];
    let w, h;

    function resize() {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    }

    function spawn() {
      const color = colors[Math.floor(Math.random() * colors.length)];
      return {
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.2 - 0.1,
        r: Math.random() * 1.5 + 0.5,
        alpha: 0,
        maxAlpha: Math.random() * 0.25 + 0.05,
        fadeSpeed: Math.random() * 0.003 + 0.001,
        growing: true,
        color: color,
      };
    }

    function init() {
      resize();
      particles = [];
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const p = spawn();
        p.alpha = Math.random() * p.maxAlpha;
        particles.push(p);
      }
    }

    function frame() {
      ctx.clearRect(0, 0, w, h);
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.growing) {
          p.alpha += p.fadeSpeed;
          if (p.alpha >= p.maxAlpha) p.growing = false;
        } else {
          p.alpha -= p.fadeSpeed;
          if (p.alpha <= 0) {
            particles[i] = spawn();
            continue;
          }
        }

        if (p.x < -10 || p.x > w + 10 || p.y < -10 || p.y > h + 10) {
          particles[i] = spawn();
          continue;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(' + p.color.r + ',' + p.color.g + ',' + p.color.b + ',' + p.alpha + ')';
        ctx.fill();
      }
      requestAnimationFrame(frame);
    }

    window.addEventListener('resize', resize);
    init();
    frame();
  }

  /* ================================================================
   * Data Temple: matrix rain — falling monospace characters
   * Columns of characters that fall at different speeds.
   * Green on black, Ikeda-style data cascade.
   * ================================================================ */
  function initDataTemple(container) {
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;';
    container.appendChild(canvas);
    const ctx = canvas.getContext('2d');

    const FONT_SIZE = 12;
    const chars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';
    let columns, drops;
    let w, h;

    function resize() {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
      columns = Math.floor(w / FONT_SIZE);
      drops = new Array(columns).fill(0).map(function () {
        return Math.random() * -100;
      });
    }

    function frame() {
      // Fade trail
      ctx.fillStyle = 'rgba(0, 0, 0, 0.06)';
      ctx.fillRect(0, 0, w, h);

      ctx.font = FONT_SIZE + 'px JetBrains Mono, monospace';

      for (let i = 0; i < columns; i++) {
        // Only render some columns (sparse, not wall-to-wall)
        if (i % 3 !== 0) continue;

        var ch = chars[Math.floor(Math.random() * chars.length)];
        var y = drops[i] * FONT_SIZE;

        // Head character: bright
        ctx.fillStyle = 'rgba(0, 255, 65, 0.7)';
        ctx.fillText(ch, i * FONT_SIZE, y);

        // Trail character: dim
        if (y > FONT_SIZE) {
          ctx.fillStyle = 'rgba(0, 255, 65, 0.15)';
          ctx.fillText(
            chars[Math.floor(Math.random() * chars.length)],
            i * FONT_SIZE,
            y - FONT_SIZE
          );
        }

        drops[i] += 0.4 + Math.random() * 0.3;

        if (y > h && Math.random() > 0.98) {
          drops[i] = Math.random() * -20;
        }
      }

      requestAnimationFrame(frame);
    }

    window.addEventListener('resize', resize);
    resize();
    frame();
  }

  /* ================================================================
   * Evening Garden: fireflies — soft dots that fade in/out gently
   * Warm wisteria and amber tones. Slow, organic movement.
   * The "!" moment: occasional brighter flash.
   * ================================================================ */
  function initEveningGarden(container) {
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;';
    container.appendChild(canvas);
    const ctx = canvas.getContext('2d');

    const COUNT = 25;
    const colors = [
      { r: 139, g: 129, b: 195 },  // Wisteria
      { r: 213, g: 184, b: 141 },  // Amber
      { r: 123, g: 168, b: 123 },  // Garden green
    ];

    let fireflies = [];
    let w, h;

    function resize() {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    }

    function spawn() {
      var color = colors[Math.floor(Math.random() * colors.length)];
      return {
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        r: Math.random() * 2 + 1,
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.008 + 0.003,
        maxAlpha: Math.random() * 0.15 + 0.03,
        color: color,
      };
    }

    function init() {
      resize();
      fireflies = [];
      for (let i = 0; i < COUNT; i++) fireflies.push(spawn());
    }

    function frame() {
      ctx.clearRect(0, 0, w, h);

      for (let i = 0; i < fireflies.length; i++) {
        var f = fireflies[i];
        f.x += f.vx;
        f.y += f.vy;
        f.phase += f.speed;

        // Gentle wandering direction change
        f.vx += (Math.random() - 0.5) * 0.02;
        f.vy += (Math.random() - 0.5) * 0.02;
        f.vx *= 0.99;
        f.vy *= 0.99;

        var alpha = f.maxAlpha * (0.5 + 0.5 * Math.sin(f.phase));

        if (f.x < -20 || f.x > w + 20 || f.y < -20 || f.y > h + 20) {
          fireflies[i] = spawn();
          continue;
        }

        // Glow
        ctx.beginPath();
        ctx.arc(f.x, f.y, f.r * 3, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(' + f.color.r + ',' + f.color.g + ',' + f.color.b + ',' + (alpha * 0.3) + ')';
        ctx.fill();

        // Core
        ctx.beginPath();
        ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(' + f.color.r + ',' + f.color.g + ',' + f.color.b + ',' + alpha + ')';
        ctx.fill();
      }

      requestAnimationFrame(frame);
    }

    window.addEventListener('resize', resize);
    init();
    frame();
  }
})();
