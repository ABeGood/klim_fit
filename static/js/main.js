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

// Workout Management System
class WorkoutManager {
    constructor() {
        this.selectedUser = null;
        this.selectedWorkout = null;
        this.users = [];
        this.exercises = [];
        this.currentWorkoutSets = [];
        this.isDragging = false;
        this.draggedExercise = null;
    }

    async init() {
        await this.loadUsers();
        await this.loadExercises();
        this.setupEventListeners();
        this.setupDragAndDrop();
    }

    // API Functions
    async apiCall(url, options = {}) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            FitCoachUtils.showNotification('API call failed: ' + error.message, 'error');
            throw error;
        }
    }

    // Load data functions
    async loadUsers() {
        try {
            this.users = await this.apiCall('/api/users');
            this.renderUsers();
        } catch (error) {
            document.getElementById('usersList').innerHTML = '<div class="error">Failed to load users</div>';
        }
    }

    async loadExercises() {
        try {
            this.exercises = await this.apiCall('/api/exercises');
            this.renderExercises();
        } catch (error) {
            document.getElementById('exercisesList').innerHTML = '<div class="error">Failed to load exercises</div>';
        }
    }

    async loadWorkouts(userId) {
        try {
            const workouts = await this.apiCall(`/api/users/${userId}/workouts`);
            this.renderWorkouts(workouts);
        } catch (error) {
            document.getElementById('workoutsList').innerHTML = '<div class="error">Failed to load workouts</div>';
        }
    }

    async loadExerciseSets(workoutId) {
        try {
            this.currentWorkoutSets = await this.apiCall(`/api/workouts/${workoutId}/exercise-sets`);
            this.renderExerciseSets();
            this.showSaveButton();
        } catch (error) {
            document.getElementById('exerciseSetsList').innerHTML = '<div class="error">Failed to load exercise sets</div>';
        }
    }

    // Render functions
    renderUsers() {
        const usersList = document.getElementById('usersList');
        if (this.users.length === 0) {
            usersList.innerHTML = '<div class="placeholder">No users found</div>';
            return;
        }

        usersList.innerHTML = this.users.map(user => `
            <div class="user-item" data-user-id="${user.id}" onclick="workoutManager.selectUser(${user.id})">
                <h4>${user.full_name}</h4>
                <p>${user.email}</p>
                ${user.age ? `<p>Age: ${user.age}</p>` : ''}
                ${user.weight_kg ? `<p>Weight: ${user.weight_kg} kg</p>` : ''}
            </div>
        `).join('');
    }

    renderWorkouts(workouts) {
        const workoutsList = document.getElementById('workoutsList');
        if (workouts.length === 0) {
            workoutsList.innerHTML = '<div class="placeholder">No workouts found</div>';
            return;
        }

        workoutsList.innerHTML = workouts.map(workout => `
            <div class="workout-item ${workout.completed ? 'completed' : ''}" 
                 data-workout-id="${workout.id}" 
                 onclick="workoutManager.selectWorkout(${workout.id}, '${workout.name}')">
                <h4>${workout.name}</h4>
                <p>${workout.description || 'No description'}</p>
                ${workout.workout_date ? `<p><i class="fas fa-calendar"></i> ${new Date(workout.workout_date).toLocaleDateString()}</p>` : ''}
                ${workout.duration_minutes ? `<p><i class="fas fa-clock"></i> ${workout.duration_minutes} min</p>` : ''}
                ${workout.completed ? '<p><i class="fas fa-check-circle"></i> Completed</p>' : '<p><i class="fas fa-clock"></i> In Progress</p>'}
            </div>
        `).join('');
    }

    renderExerciseSets() {
        const exerciseSetsList = document.getElementById('exerciseSetsList');
        const dropHint = exerciseSetsList.querySelector('.drop-hint');
        const placeholder = exerciseSetsList.querySelector('.placeholder');
        
        if (placeholder) placeholder.style.display = 'none';
        if (dropHint) dropHint.style.display = this.currentWorkoutSets.length === 0 ? 'block' : 'none';

        const setsHTML = this.currentWorkoutSets.map(set => {
            const parameters = [];
            if (set.reps) parameters.push(`${set.reps} reps`);
            if (set.weight_kg) parameters.push(`${set.weight_kg} kg`);
            if (set.duration_s) parameters.push(`${Math.floor(set.duration_s / 60)}:${String(set.duration_s % 60).padStart(2, '0')}`);
            if (set.distance_m) parameters.push(`${set.distance_m} m`);
            if (set.rest_seconds) parameters.push(`${set.rest_seconds}s rest`);

            return `
                <div class="exercise-set-item ${set.completed ? 'completed' : ''}" 
                     data-set-id="${set.id}"
                     onclick="workoutManager.editExerciseSet(${set.id})">
                    <div class="set-order">${set.set_order}</div>
                    <h4>${set.exercise_name}</h4>
                    <p>${set.exercise_description || 'No description'}</p>
                    ${parameters.length > 0 ? `
                        <div class="parameters">
                            ${parameters.map(param => `<span>${param}</span>`).join('')}
                        </div>
                    ` : '<div class="parameters"><span>No parameters set</span></div>'}
                </div>
            `;
        }).join('');

        // Keep placeholder and drop-hint, add sets
        const existingElements = exerciseSetsList.innerHTML;
        const placeholderAndHint = exerciseSetsList.querySelectorAll('.placeholder, .drop-hint');
        exerciseSetsList.innerHTML = '';
        placeholderAndHint.forEach(el => exerciseSetsList.appendChild(el));
        exerciseSetsList.insertAdjacentHTML('beforeend', setsHTML);
    }

    renderExercises() {
        const exercisesList = document.getElementById('exercisesList');
        if (this.exercises.length === 0) {
            exercisesList.innerHTML = '<div class="placeholder">No exercises found</div>';
            return;
        }

        exercisesList.innerHTML = this.exercises.map(exercise => `
            <div class="exercise-item" 
                 data-exercise-id="${exercise.id}"
                 draggable="true">
                <h4>${exercise.name}</h4>
                <p>${exercise.description || 'No description'}</p>
                <p><i class="fas fa-cogs"></i> ${exercise.parameter_summary}</p>
            </div>
        `).join('');

        // Re-setup drag events for new elements
        this.setupDragAndDrop();
    }

    // User and workout selection
    selectUser(userId) {
        // Clear previous selections
        document.querySelectorAll('.user-item').forEach(item => item.classList.remove('selected'));
        document.querySelector(`[data-user-id="${userId}"]`).classList.add('selected');
        
        this.selectedUser = this.users.find(u => u.id === userId);
        this.selectedWorkout = null;
        
        // Show new workout button
        document.getElementById('newWorkoutBtn').style.display = 'block';
        
        // Load workouts for this user
        this.loadWorkouts(userId);
        
        // Clear exercise sets
        document.getElementById('exerciseSetsList').innerHTML = '<div class="placeholder">Select a workout to view exercise sets</div><div class="drop-hint" style="display: none;"><i class="fas fa-plus-circle"></i><p>Drop exercises here to add them to the workout</p></div>';
        document.getElementById('workoutInfo').style.display = 'none';
        this.hideSaveButton();
    }

    selectWorkout(workoutId, workoutName) {
        // Clear previous selections
        document.querySelectorAll('.workout-item').forEach(item => item.classList.remove('selected'));
        document.querySelector(`[data-workout-id="${workoutId}"]`).classList.add('selected');
        
        this.selectedWorkout = { id: workoutId, name: workoutName };
        
        // Show workout info
        document.getElementById('workoutName').textContent = workoutName;
        document.getElementById('workoutInfo').style.display = 'block';
        
        // Load exercise sets for this workout
        this.loadExerciseSets(workoutId);
    }

    // Drag and Drop functionality
    setupDragAndDrop() {
        const exerciseItems = document.querySelectorAll('.exercise-item');
        const dropZone = document.querySelector('.exercise-sets-list');

        exerciseItems.forEach(item => {
            item.addEventListener('dragstart', (e) => {
                this.isDragging = true;
                item.classList.add('dragging');
                this.draggedExercise = {
                    id: parseInt(item.dataset.exerciseId),
                    name: item.querySelector('h4').textContent,
                    description: item.querySelector('p').textContent
                };
                
                e.dataTransfer.effectAllowed = 'copy';
                e.dataTransfer.setData('text/html', item.outerHTML);
            });

            item.addEventListener('dragend', (e) => {
                this.isDragging = false;
                item.classList.remove('dragging');
            });
        });

        if (dropZone) {
            dropZone.addEventListener('dragover', (e) => {
                if (this.isDragging && this.selectedWorkout) {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = 'copy';
                    dropZone.classList.add('drag-over');
                    
                    const dropHint = dropZone.querySelector('.drop-hint');
                    if (dropHint && this.currentWorkoutSets.length === 0) {
                        dropHint.style.display = 'block';
                    }
                }
            });

            dropZone.addEventListener('dragleave', (e) => {
                if (!dropZone.contains(e.relatedTarget)) {
                    dropZone.classList.remove('drag-over');
                }
            });

            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('drag-over');
                
                if (this.isDragging && this.selectedWorkout && this.draggedExercise) {
                    this.addExerciseToWorkout(this.draggedExercise.id);
                }
            });
        }
    }

    // Exercise set management
    async addExerciseToWorkout(exerciseId) {
        if (!this.selectedWorkout) {
            FitCoachUtils.showNotification('Please select a workout first', 'warning');
            return;
        }

        try {
            const newSet = await this.apiCall(`/api/workouts/${this.selectedWorkout.id}/exercise-sets`, {
                method: 'POST',
                body: JSON.stringify({ exercise_id: exerciseId })
            });

            this.currentWorkoutSets.push(newSet);
            this.renderExerciseSets();
            FitCoachUtils.showNotification('Exercise added to workout', 'success');
        } catch (error) {
            FitCoachUtils.showNotification('Failed to add exercise to workout', 'error');
        }
    }

    async editExerciseSet(setId) {
        const set = this.currentWorkoutSets.find(s => s.id === setId);
        if (!set) return;

        const exercise = this.exercises.find(e => e.id === set.exercise_id);
        if (!exercise) return;

        // Populate modal
        document.getElementById('setId').value = setId;
        document.getElementById('modalExerciseName').textContent = set.exercise_name;
        document.getElementById('modalExerciseDescription').textContent = set.exercise_description || 'No description';

        // Create parameter inputs
        const parametersContainer = document.getElementById('parametersContainer');
        parametersContainer.innerHTML = '';

        const parameters = [
            { key: 'reps', label: 'Repetitions', type: 'number', min: 1, condition: exercise.has_reps },
            { key: 'weight_kg', label: 'Weight (kg)', type: 'number', min: 0, step: 0.5, condition: exercise.has_weight_kg },
            { key: 'duration_s', label: 'Duration (seconds)', type: 'number', min: 1, condition: exercise.has_duration_s },
            { key: 'distance_m', label: 'Distance (meters)', type: 'number', min: 0, step: 0.1, condition: exercise.has_distance_m },
            { key: 'rest_seconds', label: 'Rest (seconds)', type: 'number', min: 0, condition: true }
        ];

        parameters.forEach(param => {
            if (param.condition) {
                const div = document.createElement('div');
                div.className = 'form-group';
                
                const input = document.createElement('input');
                input.type = param.type;
                input.id = param.key;
                input.name = param.key;
                input.value = set[param.key] || '';
                if (param.min !== undefined) input.min = param.min;
                if (param.step !== undefined) input.step = param.step;
                
                const label = document.createElement('label');
                label.htmlFor = param.key;
                label.textContent = param.label;
                
                div.appendChild(label);
                div.appendChild(input);
                parametersContainer.appendChild(div);
            }
        });

        // Show delete button for existing sets
        document.getElementById('deleteSetBtn').style.display = 'block';

        // Show modal
        document.getElementById('exerciseSetModal').style.display = 'block';
    }

    async saveExerciseSetParameters(e) {
        e.preventDefault();
        
        const setId = document.getElementById('setId').value;
        const formData = new FormData(e.target);
        const data = {};
        
        // Convert form data to object, handling empty values
        for (let [key, value] of formData.entries()) {
            if (key !== 'setId') {
                data[key] = value === '' ? null : (isNaN(value) ? value : Number(value));
            }
        }

        try {
            const updatedSet = await this.apiCall(`/api/exercise-sets/${setId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });

            // Update local data
            const index = this.currentWorkoutSets.findIndex(s => s.id == setId);
            if (index !== -1) {
                this.currentWorkoutSets[index] = updatedSet;
            }

            this.renderExerciseSets();
            this.closeExerciseSetModal();
            FitCoachUtils.showNotification('Exercise set updated successfully', 'success');
        } catch (error) {
            FitCoachUtils.showNotification('Failed to update exercise set', 'error');
        }
    }

    async deleteExerciseSet() {
        const setId = document.getElementById('setId').value;
        
        if (!confirm('Are you sure you want to delete this exercise set?')) {
            return;
        }

        try {
            await this.apiCall(`/api/exercise-sets/${setId}`, {
                method: 'DELETE'
            });

            // Remove from local data
            this.currentWorkoutSets = this.currentWorkoutSets.filter(s => s.id != setId);
            
            this.renderExerciseSets();
            this.closeExerciseSetModal();
            FitCoachUtils.showNotification('Exercise set deleted successfully', 'success');
        } catch (error) {
            FitCoachUtils.showNotification('Failed to delete exercise set', 'error');
        }
    }

    // Workout management
    openNewWorkoutModal() {
        if (!this.selectedUser) {
            FitCoachUtils.showNotification('Please select a user first', 'warning');
            return;
        }
        document.getElementById('newWorkoutModal').style.display = 'block';
    }

    closeNewWorkoutModal() {
        document.getElementById('newWorkoutModal').style.display = 'none';
        document.getElementById('newWorkoutForm').reset();
    }

    closeExerciseSetModal() {
        document.getElementById('exerciseSetModal').style.display = 'none';
        document.getElementById('exerciseSetForm').reset();
    }

    async createNewWorkout(e) {
        e.preventDefault();
        
        if (!this.selectedUser) {
            FitCoachUtils.showNotification('Please select a user first', 'warning');
            return;
        }

        const formData = new FormData(e.target);
        const data = {
            user_id: this.selectedUser.id,
            name: formData.get('name'),
            description: formData.get('description')
        };

        try {
            const newWorkout = await this.apiCall('/api/workouts', {
                method: 'POST',
                body: JSON.stringify(data)
            });

            // Reload workouts for the current user
            this.loadWorkouts(this.selectedUser.id);
            this.closeNewWorkoutModal();
            FitCoachUtils.showNotification('Workout created successfully', 'success');
        } catch (error) {
            FitCoachUtils.showNotification('Failed to create workout', 'error');
        }
    }

    // Filter exercises
    filterExercises() {
        const searchTerm = document.getElementById('exerciseSearch').value.toLowerCase();
        const exerciseItems = document.querySelectorAll('.exercise-item');
        
        exerciseItems.forEach(item => {
            const name = item.querySelector('h4').textContent.toLowerCase();
            const description = item.querySelector('p').textContent.toLowerCase();
            
            if (name.includes(searchTerm) || description.includes(searchTerm)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }

    // UI helpers
    showSaveButton() {
        document.getElementById('saveWorkout').style.display = 'block';
    }

    hideSaveButton() {
        document.getElementById('saveWorkout').style.display = 'none';
    }

    async saveWorkout() {
        if (!this.selectedWorkout) {
            FitCoachUtils.showNotification('No workout selected', 'warning');
            return;
        }

        FitCoachUtils.showNotification('Workout saved successfully!', 'success');
    }

    // Event listeners setup
    setupEventListeners() {
        // Modal event listeners
        document.getElementById('newWorkoutBtn')?.addEventListener('click', () => this.openNewWorkoutModal());
        document.getElementById('newWorkoutForm')?.addEventListener('submit', (e) => this.createNewWorkout(e));
        document.getElementById('exerciseSetForm')?.addEventListener('submit', (e) => this.saveExerciseSetParameters(e));
        document.getElementById('deleteSetBtn')?.addEventListener('click', () => this.deleteExerciseSet());
        document.getElementById('saveWorkout')?.addEventListener('click', () => this.saveWorkout());
        document.getElementById('exerciseSearch')?.addEventListener('input', () => this.filterExercises());

        // Close modals when clicking outside
        window.addEventListener('click', (event) => {
            const newWorkoutModal = document.getElementById('newWorkoutModal');
            const exerciseSetModal = document.getElementById('exerciseSetModal');
            
            if (event.target === newWorkoutModal) {
                this.closeNewWorkoutModal();
            }
            if (event.target === exerciseSetModal) {
                this.closeExerciseSetModal();
            }
        });

        // Close modals when clicking X
        document.querySelectorAll('.close').forEach(closeBtn => {
            closeBtn.addEventListener('click', () => {
                this.closeNewWorkoutModal();
                this.closeExerciseSetModal();
            });
        });
    }
}

// Initialize workout manager if on clients page
if (window.location.pathname.includes('/clients')) {
    window.workoutManager = new WorkoutManager();
    document.addEventListener('DOMContentLoaded', () => {
        workoutManager.init();
    });
}