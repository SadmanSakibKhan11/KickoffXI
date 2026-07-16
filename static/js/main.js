/**
 * FIFA World Cup 2026 — Main JavaScript
 * =======================================
 * Handles: Theme toggle, player modal, live search, filters, scroll animations.
 * All logic is namespaced to avoid global scope pollution.
 */

document.addEventListener('DOMContentLoaded', () => {

    // ============================================================
    // 1. THEME TOGGLE
    // ============================================================

    const themeToggle = document.getElementById('theme-toggle');
    const sunIcon = document.getElementById('theme-toggle-sun');
    const moonIcon = document.getElementById('theme-toggle-moon');

    /**
     * Update the visibility of sun/moon icons based on current theme.
     */
    function updateThemeIcons() {
        const isDark = document.documentElement.classList.contains('dark');
        if (sunIcon && moonIcon) {
            sunIcon.classList.toggle('hidden', !isDark);   // Show sun in dark mode (to switch to light)
            moonIcon.classList.toggle('hidden', isDark);    // Show moon in light mode (to switch to dark)
        }
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            document.documentElement.classList.toggle('dark');
            const isDark = document.documentElement.classList.contains('dark');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            updateThemeIcons();
        });
    }

    // Initialize icons on page load
    updateThemeIcons();


    // ============================================================
    // 2. MOBILE MENU
    // ============================================================

    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const mobileMenu = document.getElementById('mobile-menu');
    const menuIconOpen = document.getElementById('menu-icon-open');
    const menuIconClose = document.getElementById('menu-icon-close');

    if (mobileMenuToggle && mobileMenu) {
        mobileMenuToggle.addEventListener('click', () => {
            const isHidden = mobileMenu.classList.contains('hidden');
            mobileMenu.classList.toggle('hidden');
            menuIconOpen.classList.toggle('hidden', !isHidden ? false : true);
            menuIconClose.classList.toggle('hidden', !isHidden ? true : false);
        });
    }


    // ============================================================
    // 3. PLAYER MODAL
    // ============================================================

    const modal = document.getElementById('player-modal');
    const modalOverlay = document.getElementById('modal-overlay');
    const modalContent = document.getElementById('modal-content');
    const modalClose = document.getElementById('modal-close');

    // Modal data elements
    const modalFrameImage = document.getElementById('modal-frame-image');
    const modalImage = document.getElementById('modal-player-image');
    const modalName = document.getElementById('modal-player-name');
    const modalNationality = document.getElementById('modal-player-nationality');
    const modalPrimary = document.getElementById('modal-player-primary');
    const modalSecondary = document.getElementById('modal-player-secondary');
    const modalSecondaryContainer = document.getElementById('modal-secondary-container');

    /**
     * Open the player modal with data from the clicked card.
     * Fetches player details from the API endpoint.
     */
    window.openPlayerModal = function(playerId) {
        if (!modal) return;

        fetch(`/api/players/${playerId}`)
            .then(res => res.json())
            .then(player => {
                if (modalFrameImage) modalFrameImage.src = player.frame_image_url;
                if (modalImage) modalImage.src = player.player_image_url;
                if (modalImage) modalImage.alt = player.name;
                if (modalName) modalName.textContent = player.name;
                if (modalNationality) modalNationality.textContent = player.nationality;
                if (modalPrimary) modalPrimary.textContent = player.primary_position;

                if (modalSecondary && modalSecondaryContainer) {
                    if (player.secondary_position) {
                        modalSecondary.textContent = player.secondary_position;
                        modalSecondaryContainer.classList.remove('hidden');
                    } else {
                        modalSecondaryContainer.classList.add('hidden');
                    }
                }

                // Show modal with animation
                modal.classList.remove('hidden');
                document.body.style.overflow = 'hidden';
                requestAnimationFrame(() => {
                    modalOverlay.classList.add('opacity-100');
                    modalContent.classList.add('opacity-100', 'scale-100');
                    modalContent.classList.remove('opacity-0', 'scale-95');
                });
            })
            .catch(err => console.error('Failed to load player:', err));
    };

    /**
     * Close the player modal with animation.
     */
    function closeModal() {
        if (!modal) return;
        modalOverlay.classList.remove('opacity-100');
        modalContent.classList.remove('opacity-100', 'scale-100');
        modalContent.classList.add('opacity-0', 'scale-95');
        document.body.style.overflow = '';
        setTimeout(() => modal.classList.add('hidden'), 200);
    }

    if (modalClose) modalClose.addEventListener('click', closeModal);
    if (modalOverlay) modalOverlay.addEventListener('click', closeModal);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });


    // ============================================================
    // 4. LIVE SEARCH & FILTERS
    // ============================================================

    const searchInput = document.getElementById('player-search');
    const filterNationality = document.getElementById('filter-nationality');
    const filterPrimary = document.getElementById('filter-primary');
    const filterSecondary = document.getElementById('filter-secondary');
    const playerGrid = document.getElementById('player-grid');
    const playerCount = document.getElementById('player-count');
    const noResults = document.getElementById('no-results');

    let searchTimeout = null;

    /**
     * Fetch players from the API with current search/filter params.
     * Uses debouncing to avoid excessive API calls while typing.
     */
    function fetchPlayers() {
        if (!playerGrid) return;

        const params = new URLSearchParams();
        if (searchInput && searchInput.value.trim()) params.set('q', searchInput.value.trim());
        if (filterNationality && filterNationality.value) params.set('nationality', filterNationality.value);
        if (filterPrimary && filterPrimary.value) params.set('position', filterPrimary.value);
        if (filterSecondary && filterSecondary.value) params.set('secondary', filterSecondary.value);

        fetch(`/api/players?${params.toString()}`)
            .then(res => res.json())
            .then(data => {
                const players = data.players || data;
                renderPlayerCards(players);
                if (playerCount) playerCount.textContent = `${players.length} player${players.length !== 1 ? 's' : ''}`;
                if (noResults) noResults.classList.toggle('hidden', players.length > 0);
            })
            .catch(err => console.error('Search failed:', err));
    }

    /**
     * Render player cards into the grid container.
     */
    function renderPlayerCards(players) {
        if (!playerGrid) return;

        playerGrid.innerHTML = players.map(player => `
            <div class="player-card group cursor-pointer" onclick="openPlayerModal(${player.id})">
                <div class="relative overflow-hidden rounded-2xl bg-gray-100 dark:bg-navy-900 border border-gray-200/50 dark:border-navy-800/50 hover:border-gold-500/30 dark:hover:border-gold-500/30 transition-all duration-300 hover:shadow-xl hover:shadow-navy-900/5 dark:hover:shadow-gold-500/5 hover:-translate-y-1">
                    <div class="aspect-[3/4] player-card-img">
                        <img src="${player.frame_image_url}" alt="" class="frame-layer"
                             onerror="this.src='${window.DEFAULT_FRAME_IMAGE_URL}'">
                        <img src="${player.player_image_url}" alt="${player.name}" class="player-layer"
                             onerror="this.src='${window.DEFAULT_PLAYER_IMAGE_URL}'" loading="lazy">
                    </div>
                    <div class="p-4">
                        <h3 class="font-bold text-navy-900 dark:text-white text-lg truncate">${player.name}</h3>
                        <div class="flex items-center gap-2 mt-1.5">
                            <span class="text-sm text-gray-500 dark:text-gray-400">${player.nationality}</span>
                        </div>
                        <div class="mt-2">
                            <span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold bg-navy-100 text-navy-700 dark:bg-navy-800 dark:text-navy-200">${player.primary_position}</span>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    }

    // Debounced search handler
    function handleSearch() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(fetchPlayers, 250);
    }

    // Attach event listeners for search & filters
    if (searchInput) searchInput.addEventListener('input', handleSearch);
    if (filterNationality) filterNationality.addEventListener('change', fetchPlayers);
    if (filterPrimary) filterPrimary.addEventListener('change', fetchPlayers);
    if (filterSecondary) filterSecondary.addEventListener('change', fetchPlayers);


    // ============================================================
    // 5. HERO SEARCH (Home Page)
    // ============================================================

    const heroSearch = document.getElementById('hero-search');
    if (heroSearch) {
        heroSearch.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const query = heroSearch.value.trim();
                if (query) {
                    window.location.href = `/players?q=${encodeURIComponent(query)}`;
                }
            }
        });
    }


    // ============================================================
    // 6. SCROLL ANIMATIONS (Intersection Observer)
    // ============================================================

    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px',
    };

    const scrollObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-visible');
                scrollObserver.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe all elements with the scroll-animate class
    document.querySelectorAll('.scroll-animate').forEach(el => {
        scrollObserver.observe(el);
    });

});
