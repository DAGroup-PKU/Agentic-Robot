(() => {
  const sidebar = document.querySelector('.site-sidebar');
  const toggle = document.querySelector('.sidebar-toggle');
  const backdrop = document.querySelector('.sidebar-backdrop');
  const groups = [...document.querySelectorAll('[data-nav-group]')];
  const mobile = matchMedia('(max-width:760px)');
  const setGroup = (group, open) => {
    group.querySelector('.submenu-toggle').setAttribute('aria-expanded', String(open));
    group.querySelector('.nav-contents').hidden = !open;
  };
  const openGroup = group => groups.forEach(other => setGroup(other, other === group));
  const closeMenu = () => {
    sidebar.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Open navigation');
    backdrop.hidden = true;
    document.body.style.overflow = '';
    groups.forEach(group => setGroup(group, false));
  };
  groups.forEach(group => {
    const button = group.querySelector('.submenu-toggle');
    group.addEventListener('pointerenter', event => {
      if (event.pointerType === 'mouse' && !mobile.matches) openGroup(group);
    });
    group.addEventListener('pointerleave', () => {
      if (!group.contains(document.activeElement)) setGroup(group, false);
    });
    group.addEventListener('focusin', event => {
      if (!mobile.matches && event.target !== button) openGroup(group);
    });
    group.addEventListener('focusout', event => {
      if (!group.contains(event.relatedTarget)) setGroup(group, false);
    });
    button.addEventListener('click', () => {
      const opening = button.getAttribute('aria-expanded') !== 'true';
      groups.forEach(other => setGroup(other, other === group && opening));
    });
  });
  toggle.addEventListener('click', () => {
    const open = !sidebar.classList.contains('open');
    closeMenu();
    if (open) {
      sidebar.classList.add('open');
      toggle.setAttribute('aria-expanded', 'true');
      toggle.setAttribute('aria-label', 'Close navigation');
      backdrop.hidden = false;
      document.body.style.overflow = 'hidden';
    }
  });
  backdrop.addEventListener('click', closeMenu);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      if (sidebar.classList.contains('open')) { closeMenu(); toggle.focus(); }
      else {
        const open = groups.find(group => group.querySelector('.submenu-toggle').getAttribute('aria-expanded') === 'true');
        if (open) { setGroup(open, false); open.querySelector('.submenu-toggle').focus(); }
      }
    }
    if (event.key === 'Tab' && sidebar.classList.contains('open')) {
      const focusable = [...sidebar.querySelectorAll('a, button')].filter(el => el.getClientRects().length);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  mobile.addEventListener('change', closeMenu);

  const journal = document.querySelector('[data-journal]');
  if (journal) {
    let category = 'all';
    const input = journal.querySelector('[data-search-input]');
    const cards = [...journal.querySelectorAll('[data-post]')];
    const buttons = [...journal.querySelectorAll('[data-filter]')];
    const refresh = () => {
      const query = input.value.trim().toLowerCase();
      let count = 0;
      cards.forEach(card => {
        const match = (category === 'all' || card.dataset.category === category) &&
          query.split(/\s+/).every(word => card.dataset.search.includes(word));
        card.hidden = !match;
        if (match) count++;
      });
      buttons.forEach(button => {
        const active = button.dataset.filter === category;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      journal.querySelector('[data-empty]').hidden = count !== 0;
      journal.querySelector('[data-search-status]').textContent = `${count} ${count === 1 ? 'article' : 'articles'}.`;
    };
    buttons.forEach(button => button.addEventListener('click', () => { category = button.dataset.filter; refresh(); }));
    input.addEventListener('input', refresh);
    journal.querySelector('[data-reset]').addEventListener('click', () => { category = 'all'; input.value = ''; refresh(); input.focus(); });
    refresh();
  }

  const directory = document.querySelector('[data-project-directory]');
  if (directory) {
    const buttons = [...directory.querySelectorAll('[data-project-filter]')];
    buttons.forEach(button => button.addEventListener('click', () => {
      const environment = button.dataset.projectFilter;
      let count = 0;
      directory.querySelectorAll('[data-project]').forEach(card => {
        card.hidden = environment !== 'all' && card.dataset.environment !== environment;
        if (!card.hidden) count++;
      });
      buttons.forEach(other => {
        other.classList.toggle('active', other === button);
        other.setAttribute('aria-pressed', String(other === button));
      });
      const text = `${count} ${count === 1 ? 'project' : 'projects'}`;
      directory.querySelector('[data-project-count]').textContent = text;
      directory.querySelector('[data-project-status]').textContent = text;
    }));
  }

  const example = document.querySelector('[data-primitive-example]');
  if (example) {
    const reference = example.querySelector('[data-primitive-links] a').href.split('#')[0];
    const stages = {
      read: { title: 'Read the board and select a legal move', description: 'Validate permitted inputs, reconstruct the visible board and tokens, then use explicit game logic to select a legal target cell. These are classical geometry and symbolic decisions.', skills: [['contracts', 'Input/action contracts'], ['shape-geometry', 'Shape reconstruction'], ['symbols', 'Symbolic logic']] },
      plan: { title: 'Find a reachable token-to-cell transfer', description: 'Use robot geometry and inverse kinematics to plan motion. Screen reachability and clearance, then compose a transfer using the side-grasp and bimanual-transfer helpers. Integration does not imply a handover happens on every move.', skills: [['kinematics', 'Robot kinematics'], ['clearance', 'Clearance and reachability'], ['handover', 'Side grasps and bimanual transfer']] },
      act: { title: 'Execute, check placement, then observe again', description: 'Waypoint execution produces joint and gripper commands. Visual feedback and grasp checks assess retention and placement; the task controller reads the board again before continuing. Input/action contracts also validate output commands.', skills: [['waypoints', 'Cartesian waypoint execution'], ['feedback', 'Visual feedback and grasp checks']] }
    };
    const nodes = [...example.querySelectorAll('[data-primitive-stage]')];
    const select = node => {
      const stage = stages[node.dataset.primitiveStage];
      nodes.forEach(other => {
        other.classList.toggle('selected', other === node);
        other.setAttribute('aria-pressed', String(other === node));
      });
      example.querySelector('[data-primitive-title]').textContent = stage.title;
      example.querySelector('[data-primitive-description]').textContent = stage.description;
      const links = stage.skills.map(([id, label]) => {
        const link = document.createElement('a');
        link.href = `${reference}#primitive-${id}`;
        link.textContent = `${label} ↗`;
        return link;
      });
      example.querySelector('[data-primitive-links]').replaceChildren(...links);
    };
    nodes.forEach(node => {
      node.addEventListener('click', () => select(node));
      node.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(node); }
        if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
          event.preventDefault();
          const next = nodes[(nodes.indexOf(node) + (event.key === 'ArrowRight' ? 1 : -1) + nodes.length) % nodes.length];
          next.focus(); select(next);
        }
      });
    });
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const field = document.createElement('textarea');
      field.value = text; field.style.position = 'fixed'; field.style.opacity = '0';
      document.body.appendChild(field); field.select();
      const copied = document.execCommand('copy'); field.remove();
      if (!copied) throw new Error('Clipboard unavailable');
    }
  }

  document.querySelectorAll('[data-copy-citation]').forEach(button => {
    button.addEventListener('click', async () => {
      const block = button.closest('[data-citation]');
      const status = block.querySelector('[data-citation-status]');
      try {
        await copyText(block.querySelector('[data-citation-text]').textContent);
        button.textContent = 'Copied ✓';
        status.textContent = 'BibTeX citation copied.';
      } catch {
        status.textContent = 'Select and copy the citation above.';
      }
    });
  });

  const copy = document.querySelector('[data-copy]');
  if (copy) copy.addEventListener('click', async () => {
    const status = document.querySelector('[data-copy-status]');
    const url = location.href.split('#')[0];
    try {
      await copyText(url);
      copy.textContent = 'Link copied ✓'; status.textContent = 'Article link copied to clipboard.';
    } catch {
      copy.textContent = 'Copy the address above'; status.textContent = 'Clipboard unavailable. Copy this page’s address from your browser.';
    }
  });

  const tocLinks = [...document.querySelectorAll('.toc a')];
  if (tocLinks.length) {
    const sections = tocLinks.map(link => document.getElementById(link.hash.slice(1))).filter(Boolean);
    const updateToc = () => {
      let active = sections[0];
      sections.forEach(section => { if (section.getBoundingClientRect().top <= 160) active = section; });
      tocLinks.forEach(link => {
        const selected = link.hash === `#${active.id}`;
        link.classList.toggle('active', selected);
        if (selected) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    };
    window.addEventListener('scroll', updateToc, { passive: true }); updateToc();
  }

  // The preview endpoint exists only on serve.py. Static exports stop polling after a 404.
  let version;
  let disconnected = false;
  const liveReload = async () => {
    try {
      const response = await fetch('/__version', { cache: 'no-store' });
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
      const state = await response.json();
      if (version !== undefined && (version !== state.version || disconnected) && !state.error) { location.reload(); return; }
      version = state.version; disconnected = false;
      let error = document.querySelector('.dev-error');
      if (state.error) {
        if (!error) { error = document.createElement('div'); error.className = 'dev-error'; error.setAttribute('role', 'alert'); document.body.appendChild(error); }
        error.textContent = `Local build error — check your terminal and source files.\n${state.error}`;
      } else if (error) error.remove();
    } catch { disconnected = true; }
    setTimeout(liveReload, 1200);
  };
  if (['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)) liveReload();
})();
