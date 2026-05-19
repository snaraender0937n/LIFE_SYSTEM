// ==================== PASSWORD TOGGLE ====================
function togglePassword(fieldId) {
    const field = document.getElementById(fieldId);
    const type = field.getAttribute('type') === 'password' ? 'text' : 'password';
    field.setAttribute('type', type);
}

// ==================== FORM VALIDATION ====================
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const inputs = this.querySelectorAll('input[required], select[required], textarea[required]');
            let isValid = true;

            inputs.forEach(input => {
                if (!input.value.trim()) {
                    input.classList.add('error');
                    isValid = false;
                } else {
                    input.classList.remove('error');
                }
            });

            if (!isValid) {
                e.preventDefault();
                showNotification('Please fill in all required fields', 'error');
            }
        });
    });

    // Remove error class when user starts typing
    document.querySelectorAll('input, select, textarea').forEach(field => {
        field.addEventListener('input', function() {
            this.classList.remove('error');
        });
    });
});

// ==================== NOTIFICATIONS ====================
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// ==================== TIME INPUT VALIDATION ====================
document.addEventListener('DOMContentLoaded', function() {
    const startTimeInputs = document.querySelectorAll('input[id*="start"]');
    const endTimeInputs = document.querySelectorAll('input[id*="end"]');
    
    function validateTimeRange() {
        const form = this.closest('form');
        if (!form) return;
        
        const startInput = form.querySelector('input[id*="start"]');
        const endInput = form.querySelector('input[id*="end"]');
        
        if (startInput && endInput && startInput.value && endInput.value) {
            if (startInput.value >= endInput.value) {
                endInput.classList.add('error');
                showNotification('End time must be after start time', 'error');
            } else {
                endInput.classList.remove('error');
            }
        }
    }
    
    startTimeInputs.forEach(input => {
        input.addEventListener('change', validateTimeRange);
    });
    
    endTimeInputs.forEach(input => {
        input.addEventListener('change', validateTimeRange);
    });
});

// ==================== AUTO-FOCUS ====================
document.addEventListener('DOMContentLoaded', function() {
    const firstInput = document.querySelector('input:not([type="hidden"])');
    if (firstInput) {
        firstInput.focus();
    }
});

// ==================== KEYBOARD SHORTCUTS ====================
document.addEventListener('keydown', function(e) {
    // Enter key to submit form
    if (e.key === 'Enter' && e.ctrlKey) {
        const form = document.querySelector('form');
        if (form) {
            form.submit();
        }
    }
    
    // Escape key to toggle password visibility
    if (e.key === 'Escape') {
        const passwordFields = document.querySelectorAll('input[type="password"]');
        passwordFields.forEach(field => {
            if (field.getAttribute('type') === 'text') {
                field.setAttribute('type', 'password');
            }
        });
    }
});

// ==================== PREVENT BACK BUTTON AFTER LOGOUT ====================
window.addEventListener('popstate', function() {
    if (!document.querySelector('input[name="user_id"]')) {
        window.location.href = '/login';
    }
});

// ==================== CONFIRMATION DIALOGS ====================
function confirmAction(message) {
    return confirm(message);
}

// Logout confirmation
document.addEventListener('DOMContentLoaded', function() {
    const logoutBtn = document.querySelector('.btn-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function(e) {
            if (!confirmAction('Are you sure you want to logout?')) {
                e.preventDefault();
            }
        });
    }
});
