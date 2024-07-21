# Real-Time Chat Application

Welcome to the Real-Time Chat Application repository! This project is built using Django, HTML, CSS, and JavaScript. It provides an intuitive and efficient platform for real-time communication.

## Features

- **Real-Time Online User Display**: See which users are currently online.
- **Messaging**:
  - **Private Messaging**: Send direct messages to other users.
  - **Group Messaging**: Communicate within groups.
- **User Last Seen**: View when a user was last active.
- **Unread Messages**: Notification for unread messages.
- **Active Users**: Display of currently active users.
- **Group Administration**: Manage group settings and members.
- **Join Requests**: Handle requests to join groups.

## Technologies Used

- **Backend**:
  - Django
  - Django Channels
  - WebSocket Protocols
  - Asynchronous Programming

- **Frontend**:
  - HTML
  - CSS
  - JavaScript

## Getting Started

### Prerequisites

Make sure you have the following installed:

- Python (v3.8 or higher)
- Django (v3.0 or higher)
- Node.js (for JavaScript dependencies, if applicable)

### Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/ayushg212/RealTime_Chat_Web_Application_Using_Django.git 
    cd RealTime_Chat_Web_Application_Using_Django
    ```

2. Install backend dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Set up the database:

    ```bash
    python manage.py migrate
    ```

4. Create a superuser for admin access:

    ```bash
    python manage.py createsuperuser
    ```

5. Start the Django development server:

    ```bash
    python manage.py runserver
    ```

6. Open your browser and navigate to `http://localhost:8000` to start using the application.

