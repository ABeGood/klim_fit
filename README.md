# FitCoach - Flask Fitness Coach Application

A modern Flask web application designed for fitness coaches to manage clients and workouts.

## Features

- 🔐 **User Authentication** - Secure login system
- 📊 **Dashboard** - Overview of clients, sessions, and statistics
- 👥 **Client Management** - Track client progress and information
- 🏋️ **Workout Library** - Organize workout plans by categories
- 📱 **Responsive Design** - Mobile-friendly interface

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application**
   ```bash
   python app.py
   ```

3. **Access the App**
   - Open your browser to `http://localhost:5000`
   - Use demo credentials:
     - Email: `coach@fitness.com`
     - Password: `password123`

## Project Structure

```
klim_fit/
├── app.py                 # Main FastAPI application
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── base.html         # Base template (auth pages)
│   ├── login.html        # Login page
│   ├── signup.html       # Signup page
│   ├── change_password.html  # Password change
│   ├── admin/            # Admin (coach) pages
│   └── user/             # User (client) pages
└── static/              # Static assets
    ├── css/
    │   └── style.css     # Main stylesheet
    └── js/
        └── main.js       # JavaScript functionality
```

## Customization

- **Colors**: Modify CSS variables in `static/css/style.css`
- **Features**: Add new routes in `app.py`
- **Database**: Replace in-memory storage with a proper database
- **Authentication**: Implement user registration and password reset

## Security Notes

- Change the `secret_key` in production
- Use environment variables for sensitive data
- Implement proper password hashing for user registration
- Add CSRF protection for forms

## License

MIT License