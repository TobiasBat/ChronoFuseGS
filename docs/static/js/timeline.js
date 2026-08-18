(function () {
  // --- Combinations ---
  const COMBOS_3 = [
    [false, false, false],
    [true,  false, false],
    [false, true,  false],
    [false, false, true ],
    [true,  true,  false],
    [true,  false, true ],
    [false, true,  true ],
    [true,  true,  true ],
  ];

  const COMBOS_4 = [
    [false, false, false, false],
    [true,  false, false, false],
    [false, true,  false, false],
    [false, false, true,  false],
    [false, false, false, true ],
    [true,  true,  false, false],
    [true,  false, true,  false],
    [true,  false, false, true ],
    [false, true,  true,  false],
    [false, true,  false, true ],
    [false, false, true,  true ],
    [false, true,  true,  true ],
    [true,  false, true,  true ],
    [true,  true,  false, true ],
    [true,  true,  true,  false],
    [true,  true,  true,  true ],
  ];

  // --- Bar colors ---
  // magenta_green_3x3_07: [T1-all3, T2-all3, T3-all3, first-of-2, second-of-2, single]
  const BAR_COLORS_3 = [
    'rgb(218,  75, 199)',
    'rgb(218, 142,  74)',
    'rgb(213, 218,   0)',
    'rgb(218,  92, 179)',
    'rgb(218, 182,  13)',
    'rgb(188, 188, 188)',
  ];

  // magenta_green_4x4_07: [T1..T4 all4, T1..T3 of3, T1..T2 of2, single]
  const BAR_COLORS_4 = [
    'rgb(218,  68, 206)',
    'rgb(218, 118, 120)',
    'rgb(218, 145,  24)',
    'rgb(188, 218,   0)',
    'rgb(218,  75, 199)',
    'rgb(218, 142,  74)',
    'rgb(213, 218,   0)',
    'rgb(218,  92, 179)',
    'rgb(218, 182,  13)',
    'rgb(188, 188, 188)',
  ];

  function getBarColor3(numSelected, pos) {
    if (numSelected >= 3) return BAR_COLORS_3[pos];
    if (numSelected === 2) return BAR_COLORS_3[3 + pos];
    return BAR_COLORS_3[5];
  }

  function getBarColor4(numSelected, pos) {
    if (numSelected === 4) return BAR_COLORS_4[pos];
    if (numSelected === 3) return BAR_COLORS_4[4 + pos];
    if (numSelected === 2) return BAR_COLORS_4[7 + pos];
    return BAR_COLORS_4[9];
  }

  // --- Sprite position helpers ---
  function getSingleSelectBgPosition(selectedIndex, n) {
    const x = n === 1 ? 0 : (selectedIndex / (n - 1)) * 100;
    return `${x}% 0%`;
  }

  function getMultiSelectBgPosition3(selected) {
    const idx = COMBOS_3.findIndex(c => c.every((v, i) => v === selected[i]));
    const s = idx === -1 ? 7 : idx;
    const row = Math.floor(s / 3), col = s % 3;
    return `${(col / 2) * 100}% ${(row / 2) * 100}%`;
  }

  function getMultiSelectBgPosition4(selected) {
    const idx = COMBOS_4.findIndex(c => c.every((v, i) => v === selected[i]));
    const s = idx === -1 ? 15 : idx;
    const row = Math.floor(s / 4), col = s % 4;
    return `${(col / 3) * 100}% ${(row / 3) * 100}%`;
  }

  // --- Widget builder ---
  function buildWidget(container, imageSrc) {
    const mode = container.dataset.mode; // 'single' | 'multi'
    const n = parseInt(container.dataset.n, 10);

    const selected = mode === 'single'
      ? Array.from({ length: n }, (_, i) => i === 0)
      : Array.from({ length: n }, () => true);

    const bgSize = mode === 'single'
      ? `${n * 100}% 100%`
      : `${n * 100}% ${n * 100}%`;

    const frameEl    = container.querySelector('.tl-image-frame');
    const controlsEl = container.querySelector('.tl-controls');

    controlsEl.style.gridTemplateColumns = `repeat(${n}, 1fr)`;

    function updateImage() {
      let pos;
      if (mode === 'single') {
        pos = getSingleSelectBgPosition(selected.indexOf(true), n);
      } else if (n === 4) {
        pos = getMultiSelectBgPosition4(selected);
      } else {
        pos = getMultiSelectBgPosition3(selected);
      }
      frameEl.style.backgroundImage    = `url(${imageSrc})`;
      frameEl.style.backgroundSize     = bgSize;
      frameEl.style.backgroundPosition = pos;
    }

    function updateControls() {
      const numSelected = selected.filter(Boolean).length;
      let colorIdx = 0;

      container.querySelectorAll('.tl-option').forEach((opt, i) => {
        const bar  = opt.querySelector('.tl-bar');
        const icon = opt.querySelector('.tl-icon');
        const eye  = opt.querySelector('.tl-eye');

        if (selected[i]) {
          bar.classList.add('active');
          icon.classList.add('selected');
          eye.classList.replace('fa-eye-slash', 'fa-eye');

          if (mode === 'multi') {
            bar.style.backgroundColor = n === 4
              ? getBarColor4(numSelected, colorIdx++)
              : getBarColor3(numSelected, colorIdx++);
          } else {
            bar.style.backgroundColor = '';
          }
        } else {
          bar.classList.remove('active');
          bar.style.backgroundColor = '';
          icon.classList.remove('selected');
          eye.classList.replace('fa-eye', 'fa-eye-slash');
        }
      });
    }

    // Build controls
    controlsEl.innerHTML = '';
    for (let i = 0; i < n; i++) {
      const opt = document.createElement('div');
      opt.className = 'tl-option';

      const bar = document.createElement('div');
      bar.className = 'tl-bar';

      const labelGroup = document.createElement('div');
      labelGroup.className = 'tl-label-group';

      const icon = document.createElement('div');
      icon.className = 'tl-icon';
      const eye = document.createElement('i');
      eye.className = 'fas fa-eye tl-eye';
      icon.appendChild(eye);

      const label = document.createElement('span');
      label.className = 'tl-text';
      label.textContent = `T${i + 1}`;

      labelGroup.appendChild(icon);
      labelGroup.appendChild(label);
      opt.appendChild(bar);
      opt.appendChild(labelGroup);
      controlsEl.appendChild(opt);

      opt.addEventListener('click', () => {
        if (mode === 'single') {
          selected.fill(false);
          selected[i] = true;
        } else {
          if (selected[i] && selected.filter(Boolean).length <= 1) return;
          selected[i] = !selected[i];
        }
        updateImage();
        updateControls();
      });
    }

    updateImage();
    updateControls();

    container._setImage = function (src) {
      imageSrc = src;
      updateImage();
    };
  }

  // --- Scene switching ---
  function sceneKey(scene) {
    return scene.replace(/-/g, '');
  }

  function initScene(scene, n) {
    document.querySelectorAll('.timeline-widget').forEach(container => {
      const key = sceneKey(scene);
      const src = container.dataset[key];
      if (!src) return;
      const prevN = parseInt(container.dataset.n, 10);
      // Rebuild if n changed (e.g. switching between 3- and 4-timestep scenes)
      if (n !== prevN) {
        container.dataset.n = n;
        container._setImage = null;
      }
      if (container._setImage) {
        container._setImage(src);
      } else {
        buildWidget(container, src);
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    const tabs = document.querySelectorAll('#scene-tabs li');
    let currentScene = 'flood-2';
    let currentN = 3;
    initScene(currentScene, currentN);

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('is-active'));
        tab.classList.add('is-active');
        currentScene = tab.dataset.scene;
        currentN = parseInt(tab.dataset.n, 10);
        initScene(currentScene, currentN);
      });
    });
  });
})();
