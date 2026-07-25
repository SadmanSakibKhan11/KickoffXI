/**
 * Champions Page — JavaScript
 * =============================
 * Handles: Champion player popup modal, scroll animations.
 * Completely separate from the main player modal in main.js.
 */

document.addEventListener('DOMContentLoaded', () => {

    // ============================================================
    // CHAMPION DATA (injected from template)
    // ============================================================
    const championData = window.CHAMPION_DATA || {};
    const startingXI = championData.starting_xi || [];
    const bench = championData.bench || [];


    // ============================================================
    // CHAMPION MODAL ELEMENTS
    // ============================================================
    const modal = document.getElementById('champion-modal');
    const modalOverlay = document.getElementById('champion-modal-overlay');
    const modalContent = document.getElementById('champion-modal-content');
    const modalClose = document.getElementById('champion-modal-close');

    // Modal data fields
    const modalFrameImage = document.getElementById('champion-modal-frame-image');
    const modalPlayerImage = document.getElementById('champion-modal-player-image');
    const modalPlayerName = document.getElementById('champion-modal-name');
    const modalCaptainBadge = document.getElementById('champion-modal-captain-badge');
    const modalNationality = document.getElementById('champion-modal-nationality');
    const modalPrimary = document.getElementById('champion-modal-primary');
    const modalSecondary = document.getElementById('champion-modal-secondary');
    const modalSecondaryContainer = document.getElementById('champion-modal-secondary-container');
    const modalMatches = document.getElementById('champion-modal-matches');
    const modalGoals = document.getElementById('champion-modal-goals');
    const modalAssists = document.getElementById('champion-modal-assists');
    const modalMinutes = document.getElementById('champion-modal-minutes');
    const modalRating = document.getElementById('champion-modal-rating');
    const modalAwards = document.getElementById('champion-modal-awards');
    const modalNumber = document.getElementById('champion-modal-number');


    /**
     * Generate an inline <img> tag for a country flag.
     */
    function flagImgHtml(nationality, size = 16) {
        const flags = window.COUNTRY_FLAGS || {};
        const code = flags[nationality];
        if (!code) return '';
        const h = Math.round(size * 0.75);
        return `<img src="https://flagcdn.com/${code}.svg" alt="" width="${size}" height="${h}" style="display:inline-block;vertical-align:middle;border-radius:2px;" loading="lazy">`;
    }


    /**
     * Open the champion player popup.
     * @param {number} index - Player index in the array
     * @param {string} type  - 'xi' for starting XI, 'bench' for bench
     */
    window.openChampionModal = function(index, type) {
        if (!modal) return;

        const squad = type === 'bench' ? bench : startingXI;
        const player = squad[index];
        if (!player) return;

        // Populate image layers
        if (modalFrameImage) modalFrameImage.src = player.frame_image_url || window.DEFAULT_FRAME_IMAGE_URL;
        if (modalPlayerImage) {
            modalPlayerImage.src = player.player_image_url || window.DEFAULT_PLAYER_IMAGE_URL;
            modalPlayerImage.alt = player.name;
        }

        // Name + Captain badge
        if (modalPlayerName) modalPlayerName.textContent = player.name;
        if (modalCaptainBadge) {
            modalCaptainBadge.classList.toggle('hidden', !player.is_captain);
        }

        // Number
        if (modalNumber) modalNumber.textContent = '#' + player.number;

        // Nationality
        if (modalNationality) {
            modalNationality.innerHTML = flagImgHtml(player.nationality, 20) + ' ' + player.nationality;
        }

        // Position
        if (modalPrimary) modalPrimary.textContent = player.position;

        // Secondary position
        if (modalSecondary && modalSecondaryContainer) {
            if (player.secondary_position) {
                modalSecondary.textContent = player.secondary_position;
                modalSecondaryContainer.classList.remove('hidden');
            } else {
                modalSecondaryContainer.classList.add('hidden');
            }
        }

        // Tournament Stats
        const stats = player.stats || {};
        if (modalMatches) modalMatches.textContent = stats.matches || 0;
        if (modalGoals) modalGoals.textContent = stats.goals || 0;
        if (modalAssists) modalAssists.textContent = stats.assists || 0;
        if (modalMinutes) modalMinutes.textContent = stats.minutes || 0;
        if (modalRating) modalRating.textContent = stats.avg_rating ? stats.avg_rating.toFixed(1) : '—';

        // Awards
        if (modalAwards) {
            const awards = player.awards || [];
            if (awards.length > 0) {
                modalAwards.innerHTML = awards.map(a =>
                    `<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-gold-500/15 text-gold-600 dark:text-gold-400 border border-gold-500/20">
                        <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                        ${a}
                    </span>`
                ).join(' ');
                modalAwards.parentElement.classList.remove('hidden');
            } else {
                modalAwards.parentElement.classList.add('hidden');
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
    };


    /**
     * Close the champion modal with animation.
     */
    function closeChampionModal() {
        if (!modal) return;
        modalOverlay.classList.remove('opacity-100');
        modalContent.classList.remove('opacity-100', 'scale-100');
        modalContent.classList.add('opacity-0', 'scale-95');
        document.body.style.overflow = '';
        setTimeout(() => modal.classList.add('hidden'), 250);
    }

    if (modalClose) modalClose.addEventListener('click', closeChampionModal);
    if (modalOverlay) modalOverlay.addEventListener('click', closeChampionModal);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal && !modal.classList.contains('hidden')) {
            closeChampionModal();
        }
    });


    // ============================================================
    // SCROLL ANIMATIONS (page-specific observer)
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

    document.querySelectorAll('.champ-scroll-animate').forEach(el => {
        scrollObserver.observe(el);
    });

});
