# Telegram File Storage & Calculator Bot

## Features
- File storage system with authentication
- Advanced calculator with 10 levels
- Admin panel for user management
- Always online with keep-alive system

## Deployment on Render
1. Create new Web Service
2. Connect to GitHub repository
3. Set environment variable: `TOKEN=your_bot_token`
4. Use `web: gunicorn app:app` in Procfile