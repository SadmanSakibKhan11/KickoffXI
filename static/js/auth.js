/**
 * KickoffXI — Auth JavaScript
 * ============================
 * Handles: Password visibility toggles, forgot-password OTP flow,
 * user menu dropdown, and global toast notifications.
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


    // ============================================================
    // 4. FORGOT PASSWORD — OTP FLOW
    // ============================================================

    const fpStep1 = document.getElementById('fp-step-1');
    const fpStep2 = document.getElementById('fp-step-2');
    const fpStep3 = document.getElementById('fp-step-3');
    const fpSuccess = document.getElementById('fp-success');
    const fpBackLink = document.getElementById('fp-back-link');

    // Only run OTP logic if we're on the forgot-password page
    if (!fpStep1) return;

    const fpEmail = document.getElementById('fp-email');
    const fpEmailError = document.getElementById('fp-email-error');
    const fpSendBtn = document.getElementById('fp-send-otp');
    const fpSendMessage = document.getElementById('fp-send-message');

    const fpEmailDisplay = document.getElementById('fp-email-display');
    const otpDigits = document.querySelectorAll('.otp-digit');
    const fpOtpError = document.getElementById('fp-otp-error');
    const fpVerifyBtn = document.getElementById('fp-verify-otp');
    const fpResendBtn = document.getElementById('fp-resend-otp');
    const fpResendTimer = document.getElementById('fp-resend-timer');

    const fpNewPassword = document.getElementById('fp-new-password');
    const fpConfirmPassword = document.getElementById('fp-confirm-password');
    const fpNewPasswordError = document.getElementById('fp-new-password-error');
    const fpConfirmPasswordError = document.getElementById('fp-confirm-password-error');
    const fpResetBtn = document.getElementById('fp-reset-password');

    let currentEmail = '';
    let resendCooldownInterval = null;

    // Helper: Show/hide steps
    function showStep(stepNum) {
        [fpStep1, fpStep2, fpStep3, fpSuccess].forEach(el => el?.classList.add('hidden'));
        if (stepNum === 1) fpStep1?.classList.remove('hidden');
        if (stepNum === 2) fpStep2?.classList.remove('hidden');
        if (stepNum === 3) fpStep3?.classList.remove('hidden');
        if (stepNum === 'success') {
            fpSuccess?.classList.remove('hidden');
            fpBackLink?.classList.add('hidden');
        }
    }

    // Helper: Toggle button loading state
    function setLoading(btn, loading) {
        const text = btn?.querySelector('.btn-text');
        const loader = btn?.querySelector('.btn-loading');
        if (text) text.classList.toggle('hidden', loading);
        if (loader) loader.classList.toggle('hidden', !loading);
        if (btn) btn.disabled = loading;
    }

    // Helper: Show field error
    function showError(el, msg) {
        if (!el) return;
        el.textContent = msg;
        el.classList.remove('hidden');
    }

    function hideError(el) {
        if (!el) return;
        el.textContent = '';
        el.classList.add('hidden');
    }


    // ── Step 1: Send OTP ──

    fpSendBtn?.addEventListener('click', async () => {
        hideError(fpEmailError);
        fpSendMessage?.classList.add('hidden');

        const email = fpEmail?.value.trim();
        if (!email) {
            showError(fpEmailError, 'Please enter your email address.');
            return;
        }

        // Basic client-side email check
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            showError(fpEmailError, 'Please enter a valid email address.');
            return;
        }

        setLoading(fpSendBtn, true);

        try {
            const res = await fetch('/api/auth/send-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            const data = await res.json();

            if (!res.ok) {
                if (data.cooldown) {
                    showError(fpEmailError, data.error);
                } else {
                    showError(fpEmailError, data.error || 'Something went wrong.');
                }
                setLoading(fpSendBtn, false);
                return;
            }

            // Success — move to step 2
            currentEmail = email;
            if (fpEmailDisplay) fpEmailDisplay.textContent = email;
            showStep(2);
            otpDigits[0]?.focus();
            startResendCooldown(60);

        } catch (err) {
            showError(fpEmailError, 'Network error. Please try again.');
        }
        setLoading(fpSendBtn, false);
    });

    // Enter key on email field
    fpEmail?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            fpSendBtn?.click();
        }
    });


    // ── OTP Digit Input Behavior ──

    otpDigits.forEach((input, idx) => {
        input.addEventListener('input', (e) => {
            const val = e.target.value.replace(/\D/g, '');
            e.target.value = val.slice(0, 1);

            if (val && idx < otpDigits.length - 1) {
                otpDigits[idx + 1].focus();
            }

            // Auto-submit when all 6 filled
            if (getOtpValue().length === 6) {
                fpVerifyBtn?.click();
            }
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !e.target.value && idx > 0) {
                otpDigits[idx - 1].focus();
            }
        });

        // Paste support
        input.addEventListener('paste', (e) => {
            e.preventDefault();
            const paste = (e.clipboardData.getData('text') || '').replace(/\D/g, '');
            otpDigits.forEach((d, i) => {
                d.value = paste[i] || '';
            });
            const lastIdx = Math.min(paste.length, 6) - 1;
            if (lastIdx >= 0) otpDigits[Math.min(lastIdx + 1, 5)]?.focus();
            if (paste.length >= 6) fpVerifyBtn?.click();
        });
    });

    function getOtpValue() {
        return Array.from(otpDigits).map(d => d.value).join('');
    }

    function clearOtpInputs() {
        otpDigits.forEach(d => { d.value = ''; });
    }


    // ── Step 2: Verify OTP ──

    fpVerifyBtn?.addEventListener('click', async () => {
        hideError(fpOtpError);
        const otp = getOtpValue();

        if (otp.length !== 6) {
            showError(fpOtpError, 'Please enter the complete 6-digit code.');
            return;
        }

        setLoading(fpVerifyBtn, true);

        try {
            const res = await fetch('/api/auth/verify-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: currentEmail, otp }),
            });
            const data = await res.json();

            if (!res.ok) {
                showError(fpOtpError, data.error || 'Invalid code.');
                clearOtpInputs();
                otpDigits[0]?.focus();
                setLoading(fpVerifyBtn, false);
                return;
            }

            // Success — move to step 3
            showStep(3);
            fpNewPassword?.focus();

        } catch (err) {
            showError(fpOtpError, 'Network error. Please try again.');
        }
        setLoading(fpVerifyBtn, false);
    });


    // ── Resend OTP ──

    fpResendBtn?.addEventListener('click', async () => {
        if (fpResendBtn.disabled) return;
        hideError(fpOtpError);
        clearOtpInputs();

        fpResendBtn.disabled = true;
        fpResendBtn.textContent = 'Sending...';

        try {
            const res = await fetch('/api/auth/send-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: currentEmail }),
            });
            const data = await res.json();

            if (!res.ok) {
                if (data.cooldown) {
                    startResendCooldown(data.cooldown);
                }
                showError(fpOtpError, data.error || 'Failed to resend.');
                fpResendBtn.textContent = 'Resend Code';
                fpResendBtn.disabled = false;
                return;
            }

            showToast('New code sent!', 'success');
            startResendCooldown(60);
            otpDigits[0]?.focus();

        } catch (err) {
            showError(fpOtpError, 'Network error. Please try again.');
        }
        fpResendBtn.textContent = 'Resend Code';
    });

    function startResendCooldown(seconds) {
        if (resendCooldownInterval) clearInterval(resendCooldownInterval);

        let remaining = seconds;
        fpResendBtn.disabled = true;
        fpResendTimer?.classList.remove('hidden');

        const updateTimer = () => {
            if (fpResendTimer) fpResendTimer.textContent = `(${remaining}s)`;
            if (remaining <= 0) {
                clearInterval(resendCooldownInterval);
                resendCooldownInterval = null;
                fpResendBtn.disabled = false;
                fpResendTimer?.classList.add('hidden');
            }
            remaining--;
        };

        updateTimer();
        resendCooldownInterval = setInterval(updateTimer, 1000);
    }


    // ── Step 3: Reset Password ──

    fpResetBtn?.addEventListener('click', async () => {
        hideError(fpNewPasswordError);
        hideError(fpConfirmPasswordError);

        const newPw = fpNewPassword?.value || '';
        const confirmPw = fpConfirmPassword?.value || '';
        let hasError = false;

        if (!newPw) {
            showError(fpNewPasswordError, 'New password is required.');
            hasError = true;
        } else if (newPw.length < 6) {
            showError(fpNewPasswordError, 'Password must contain at least 6 characters.');
            hasError = true;
        }

        if (newPw !== confirmPw) {
            showError(fpConfirmPasswordError, 'Passwords do not match.');
            hasError = true;
        }

        if (hasError) return;

        setLoading(fpResetBtn, true);

        try {
            const res = await fetch('/api/auth/reset-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    new_password: newPw,
                    confirm_password: confirmPw,
                }),
            });
            const data = await res.json();

            if (!res.ok) {
                if (data.errors) {
                    if (data.errors.new_password) showError(fpNewPasswordError, data.errors.new_password);
                    if (data.errors.confirm_password) showError(fpConfirmPasswordError, data.errors.confirm_password);
                } else {
                    showError(fpNewPasswordError, data.error || 'Something went wrong.');
                }
                setLoading(fpResetBtn, false);
                return;
            }

            // Success
            showStep('success');

        } catch (err) {
            showError(fpNewPasswordError, 'Network error. Please try again.');
        }
        setLoading(fpResetBtn, false);
    });

});
