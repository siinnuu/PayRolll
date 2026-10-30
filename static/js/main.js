/**
 * Employee Payroll Management System - Interactive Frontend Script
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Theme Management (Light / Dark Mode with localStorage)
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const themeIcon = document.getElementById('theme-icon');

    const getPreferredTheme = () => {
        const storedTheme = localStorage.getItem('payroll-theme');
        if (storedTheme) {
            return storedTheme;
        }
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    };

    const setTheme = (theme) => {
        document.documentElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('payroll-theme', theme);
        if (themeIcon) {
            if (theme === 'dark') {
                themeIcon.className = 'bi bi-moon-stars-fill text-warning';
            } else {
                themeIcon.className = 'bi bi-sun-fill text-warning';
            }
        }
    };

    // Initialize theme
    setTheme(getPreferredTheme());

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-bs-theme') || 'light';
            const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(nextTheme);
        });
    }

    // 2. Mobile Sidebar Toggle
    const sidebar = document.getElementById('appSidebar');
    const sidebarToggle = document.getElementById('sidebarToggleBtn');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');

    const toggleSidebar = (show) => {
        if (!sidebar) return;
        if (show === undefined) {
            sidebar.classList.toggle('show');
            if (sidebarBackdrop) sidebarBackdrop.classList.toggle('show');
        } else if (show) {
            sidebar.classList.add('show');
            if (sidebarBackdrop) sidebarBackdrop.classList.add('show');
        } else {
            sidebar.classList.remove('show');
            if (sidebarBackdrop) sidebarBackdrop.classList.remove('show');
        }
    };

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => toggleSidebar());
    }
    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', () => toggleSidebar(false));
    }

    // 3. Clipboard copy button helpers
    document.querySelectorAll('[data-copy-target]').forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('data-copy-target');
            const targetEl = document.getElementById(targetId);
            if (targetEl) {
                const textToCopy = targetEl.innerText || targetEl.value;
                navigator.clipboard.writeText(textToCopy).then(() => {
                    const originalHtml = button.innerHTML;
                    button.innerHTML = '<i class="bi bi-check2"></i> Copied!';
                    button.classList.add('btn-success');
                    button.classList.remove('btn-outline-secondary');
                    setTimeout(() => {
                        button.innerHTML = originalHtml;
                        button.classList.remove('btn-success');
                        button.classList.add('btn-outline-secondary');
                    }, 2000);
                });
            }
        });
    });

    // 4. Live Health Re-check Ajax button
    const liveHealthBtn = document.getElementById('btn-recheck-health');
    if (liveHealthBtn) {
        liveHealthBtn.addEventListener('click', async () => {
            liveHealthBtn.disabled = true;
            const originalText = liveHealthBtn.innerHTML;
            liveHealthBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Probing...';

            try {
                const res = await fetch('/api/health');
                const data = await res.json();
                
                // Update badges dynamically if elements exist
                const dbBadge = document.getElementById('live-db-badge');
                const dbMsg = document.getElementById('live-db-message');
                if (dbBadge && dbMsg) {
                    if (data.database && data.database.connected) {
                        dbBadge.className = 'status-pill status-online';
                        dbBadge.innerHTML = '<span class="status-dot"></span> Connected';
                        dbMsg.innerText = data.database.message || 'Database connected';
                        dbMsg.className = 'text-success small mt-1';
                    } else {
                        dbBadge.className = 'status-pill status-offline';
                        dbBadge.innerHTML = '<span class="status-dot"></span> Disconnected';
                        dbMsg.innerText = data.database ? data.database.message : 'Connection failed';
                        dbMsg.className = 'text-danger small mt-1';
                    }
                }
            } catch (err) {
                console.error('Health probe error:', err);
            } finally {
                liveHealthBtn.disabled = false;
                liveHealthBtn.innerHTML = originalText;
            }
        });
    }
});
