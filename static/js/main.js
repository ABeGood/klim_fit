// Mobile Navigation Toggle
document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');
    
    if (hamburger && navMenu) {
        hamburger.addEventListener('click', function() {
            hamburger.classList.toggle('active');
            navMenu.classList.toggle('active');
        });
    }
    
    // Close flash messages
    const closeBtns = document.querySelectorAll('.close-btn');
    closeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const alert = this.parentElement;
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                alert.remove();
            }, 300);
        });
    });
    
    // Auto-hide flash messages after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert.parentElement) {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    if (alert.parentElement) {
                        alert.remove();
                    }
                }, 300);
            }
        }, 5000);
    });
    
    // Form validation and enhancements
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.style.opacity = '0.7';
                submitBtn.style.pointerEvents = 'none';
                
                // Re-enable button after 2 seconds in case of errors
                setTimeout(() => {
                    submitBtn.style.opacity = '1';
                    submitBtn.style.pointerEvents = 'auto';
                }, 2000);
            }
        });
    });
    
    // Add loading state to buttons
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            // Don't add loading state to form submit buttons (handled above)
            if (this.type !== 'submit' && !this.classList.contains('no-loading')) {
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
                this.style.pointerEvents = 'none';
                
                // Reset after 2 seconds
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.style.pointerEvents = 'auto';
                }, 2000);
            }
        });
    });
    
    // Smooth scrolling for anchor links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Dashboard card animations
    const cards = document.querySelectorAll('.stat-card, .dashboard-card, .client-card, .category-card, .nutrition-card');
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    cards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(card);
    });
    
    // Add ripple effect to buttons
    buttons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.cssText = `
                position: absolute;
                width: ${size}px;
                height: ${size}px;
                left: ${x}px;
                top: ${y}px;
                background: rgba(255, 255, 255, 0.3);
                border-radius: 50%;
                transform: scale(0);
                animation: ripple 0.6s linear;
                pointer-events: none;
            `;
            
            this.style.position = 'relative';
            this.style.overflow = 'hidden';
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
    
    // Add CSS animation for ripple effect
    const style = document.createElement('style');
    style.textContent = `
        @keyframes ripple {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
    
    // Enhanced form input focus effects
    const inputs = document.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 4px 12px rgba(255, 107, 53, 0.15)';
        });
        
        input.addEventListener('blur', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '';
        });
    });
    
    // Real-time form validation for signup
    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        const nameField = document.getElementById('name');
        const surnameField = document.getElementById('surname');
        const emailField = document.getElementById('email');
        const passwordField = document.getElementById('password');
        const confirmPasswordField = document.getElementById('confirm_password');
        
        // Name validation
        if (nameField) {
            nameField.addEventListener('blur', function() {
                if (this.value && !FitCoachUtils.validateName(this.value)) {
                    this.style.borderColor = 'var(--error-color)';
                    FitCoachUtils.showNotification('Name should only contain letters, spaces, apostrophes, and hyphens', 'warning');
                } else {
                    this.style.borderColor = '';
                }
            });
        }
        
        // Surname validation
        if (surnameField) {
            surnameField.addEventListener('blur', function() {
                if (this.value && !FitCoachUtils.validateName(this.value)) {
                    this.style.borderColor = 'var(--error-color)';
                    FitCoachUtils.showNotification('Surname should only contain letters, spaces, apostrophes, and hyphens', 'warning');
                } else {
                    this.style.borderColor = '';
                }
            });
        }
        
        // Email validation
        if (emailField) {
            emailField.addEventListener('blur', function() {
                if (this.value && !FitCoachUtils.validateEmail(this.value)) {
                    this.style.borderColor = 'var(--error-color)';
                    FitCoachUtils.showNotification('Please enter a valid email address', 'warning');
                } else {
                    this.style.borderColor = '';
                }
            });
        }
        
        // Password validation
        if (passwordField) {
            passwordField.addEventListener('blur', function() {
                const errors = FitCoachUtils.validatePassword(this.value);
                if (errors.length > 0) {
                    this.style.borderColor = 'var(--error-color)';
                    FitCoachUtils.showNotification(errors[0], 'warning');
                } else {
                    this.style.borderColor = '';
                }
            });
        }
        
        // Confirm password validation
        if (confirmPasswordField && passwordField) {
            confirmPasswordField.addEventListener('blur', function() {
                if (this.value && this.value !== passwordField.value) {
                    this.style.borderColor = 'var(--error-color)';
                    FitCoachUtils.showNotification('Passwords do not match', 'warning');
                } else {
                    this.style.borderColor = '';
                }
            });
        }
    }
});

// Password toggle functionality
function togglePassword() {
    const passwordField = document.getElementById('password');
    const toggleIcon = document.getElementById('toggleIcon');
    
    if (passwordField.type === 'password') {
        passwordField.type = 'text';
        toggleIcon.classList.remove('fa-eye');
        toggleIcon.classList.add('fa-eye-slash');
    } else {
        passwordField.type = 'password';
        toggleIcon.classList.remove('fa-eye-slash');
        toggleIcon.classList.add('fa-eye');
    }
}

// Utility functions
const Utils = {
    // Show notification
    showNotification: function(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type}`;
        notification.innerHTML = `
            ${message}
            <span class="close-btn">&times;</span>
        `;
        
        const container = document.querySelector('.flash-messages') || document.querySelector('.main-content');
        container.insertBefore(notification, container.firstChild);
        
        // Add close functionality
        const closeBtn = notification.querySelector('.close-btn');
        closeBtn.addEventListener('click', function() {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                notification.remove();
            }, 300);
        });
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.style.opacity = '0';
                notification.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    if (notification.parentElement) {
                        notification.remove();
                    }
                }, 300);
            }
        }, 5000);
    },
    
    // Format date
    formatDate: function(date) {
        return new Intl.DateTimeFormat('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        }).format(new Date(date));
    },
    
    // Format currency
    formatCurrency: function(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount);
    },
    
    // Validate email
    validateEmail: function(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },
    
    // Validate password strength
    validatePassword: function(password) {
        const errors = [];
        if (password.length < 6) {
            errors.push('Password must be at least 6 characters long');
        }
        if (!/[A-Za-z]/.test(password)) {
            errors.push('Password must contain at least one letter');
        }
        if (!/[0-9]/.test(password) && password.length < 8) {
            errors.push('Password should contain numbers for better security');
        }
        return errors;
    },
    
    // Validate name (no numbers or special characters)
    validateName: function(name) {
        const re = /^[a-zA-Z\s'-]+$/;
        return re.test(name) && name.trim().length > 0;
    },
    
    // Debounce function
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// Export utilities to global scope
window.FitCoachUtils = Utils;