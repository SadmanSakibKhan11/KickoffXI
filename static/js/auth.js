/**
 * KickoffXI — Auth JavaScript
 * ============================
 * Handles: Password visibility toggles, user menu dropdown,
 * and global toast notifications.
 */

document.addEventListener('DOMContentLoaded', () => {

    // ============================================================
    // 1. PASSWORD VISIBILITY TOGGLE
    // ============================================================

    document.querySelectorAll('.auth-password-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target');
            const input = document.getElementById(targetId);
            if (!input) return;

            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';

            const eyeOpen = btn.querySelector('.eye-open');
            const eyeClosed = btn.querySelector('.eye-closed');
            if (eyeOpen && eyeClosed) {
                eyeOpen.classList.toggle('hidden', !isPassword);
                eyeClosed.classList.toggle('hidden', isPassword);
            }
        });
    });


    // ============================================================
    // 2. USER MENU DROPDOWN (Navbar)
    // ============================================================

    const userMenuToggle = document.getElementById('user-menu-toggle');
    const userMenuDropdown = document.getElementById('user-menu-dropdown');

    if (userMenuToggle && userMenuDropdown) {
        userMenuToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            userMenuDropdown.classList.toggle('hidden');
        });

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!userMenuToggle.contains(e.target) && !userMenuDropdown.contains(e.target)) {
                userMenuDropdown.classList.add('hidden');
            }
        });

        // Close on Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                userMenuDropdown.classList.add('hidden');
            }
        });
    }


    // ============================================================
    // 3. TOAST NOTIFICATION (global)
    // ============================================================

    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const bgClass = type === 'error'
            ? 'bg-red-700 dark:bg-red-800'
            : type === 'success'
                ? 'bg-green-700 dark:bg-green-800'
                : 'bg-navy-800 dark:bg-navy-700';

        toast.className = `fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] px-5 py-2.5 rounded-xl ${bgClass} text-white text-sm font-semibold shadow-xl transition-all duration-300 opacity-0 translate-y-4`;
        toast.textContent = message;
        document.body.appendChild(toast);

        requestAnimationFrame(() => {
            toast.classList.remove('opacity-0', 'translate-y-4');
            toast.classList.add('opacity-100', 'translate-y-0');
        });

        setTimeout(() => {
            toast.classList.remove('opacity-100', 'translate-y-0');
            toast.classList.add('opacity-0', 'translate-y-4');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // Expose globally for match_simulator.js integration
    window.showAuthToast = showToast;

});
