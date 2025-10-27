# Frontend - Artifactory Database Manager

A modern Angular frontend application for managing SQLite databases stored in JFrog Artifactory. This application provides a beautiful, responsive interface for viewing database details, executing queries, and managing database synchronization.

## 🎨 Features

- **📊 Dashboard View**: Overview of all databases with health status
- **🔍 Database Details**: Detailed view of individual databases
- **⚡ Query Interface**: Execute SQL queries directly in the browser
- **🔄 Sync Management**: Sync databases with Artifactory
- **📱 Responsive Design**: Works on desktop, tablet, and mobile
- **🎯 Real-time Updates**: Live status indicators and data refresh
- **🌍 Environment Support**: Switch between different environments

## 🏗️ Architecture

### Components
- **DashboardComponent**: Main dashboard with database listing
- **DatabaseDetailComponent**: Detailed database view with query interface
- **DatabaseService**: Service for API communication

### Key Features
- **Angular Signals**: Modern reactive state management
- **Standalone Components**: No NgModules required
- **TypeScript**: Full type safety
- **Responsive Design**: Mobile-first approach
- **Error Handling**: Comprehensive error states

## 🚀 Getting Started

### Prerequisites
- Node.js 18+ 
- npm or yarn
- Backend API running on `http://localhost:5000`

### Installation

1. **Install dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Start development server**:
   ```bash
   npm run dev
   ```

3. **Open browser**:
   Navigate to `http://localhost:4200`

### Available Scripts

- `npm run dev` - Start development server with auto-open
- `npm start` - Start production server
- `npm run build` - Build for production
- `npm test` - Run tests

## 📱 User Interface

### Dashboard View
- **Database Grid**: Cards showing database information
- **Environment Selector**: Switch between environments
- **Health Status**: Real-time connection status
- **Quick Actions**: Sync and query buttons
- **Statistics**: Summary of database metrics

### Database Detail View
- **Database Stats**: Size, creation date, checksum
- **Query Interface**: SQL query execution
- **Results Table**: Formatted query results
- **Sync Controls**: Database synchronization
- **Error Handling**: Clear error messages

## 🔧 Configuration

### API Configuration
The frontend connects to the backend API at `http://localhost:5000`. To change this:

1. Update `DatabaseService` base URL:
   ```typescript
   private readonly baseUrl = 'http://your-api-url:port/api';
   ```

2. Update CORS settings in backend if needed

### Environment Variables
Create a `.env` file for environment-specific settings:
```env
API_BASE_URL=http://localhost:5000/api
ENVIRONMENT=development
```

## 🎨 Styling

### Design System
- **Color Palette**: Professional blue/purple gradient theme
- **Typography**: Segoe UI font family
- **Spacing**: Consistent 8px grid system
- **Components**: Card-based layout with shadows
- **Icons**: Emoji-based icons for simplicity

### Responsive Breakpoints
- **Desktop**: 1200px+ (full grid layout)
- **Tablet**: 768px-1199px (adjusted grid)
- **Mobile**: <768px (stacked layout)

## 🔌 API Integration

### Endpoints Used
- `GET /api/health` - Health check
- `GET /api/databases` - List databases
- `GET /api/databases/:name` - Database details
- `POST /api/databases/:name/sync` - Sync database
- `POST /api/databases/:name/query` - Execute query

### Error Handling
- **Network Errors**: Connection timeout handling
- **API Errors**: Server error display
- **Validation**: Input validation feedback
- **Loading States**: Spinner and disabled states

## 🧪 Testing

### Manual Testing
1. **Dashboard**: Verify database listing and filtering
2. **Navigation**: Test routing between views
3. **Query Interface**: Execute sample queries
4. **Responsive**: Test on different screen sizes
5. **Error States**: Test with backend offline

### Sample Queries
```sql
-- List all users
SELECT * FROM users LIMIT 10;

-- Count products by category
SELECT category, COUNT(*) as count FROM products GROUP BY category;

-- Recent orders
SELECT o.id, u.username, o.total_amount, o.status 
FROM orders o 
JOIN users u ON o.user_id = u.id 
ORDER BY o.created_at DESC 
LIMIT 5;
```

## 🚀 Deployment

### Production Build
```bash
npm run build:prod
```

### Docker Deployment
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build:prod
EXPOSE 4200
CMD ["npm", "start"]
```

### Nginx Configuration
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://backend:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🔧 Development

### Code Structure
```
src/app/
├── components/
│   ├── dashboard.component.ts
│   └── database-detail.component.ts
├── services/
│   └── database.service.ts
├── app.ts
├── app.html
├── app.scss
└── app.routes.ts
```

### Adding New Features
1. **Create Component**: Use standalone component pattern
2. **Add Service**: Extend DatabaseService if needed
3. **Update Routes**: Add new routes in app.routes.ts
4. **Style**: Follow existing design patterns

### Best Practices
- Use Angular Signals for state management
- Implement proper error handling
- Follow responsive design principles
- Use TypeScript strict mode
- Write meaningful component names

## 🐛 Troubleshooting

### Common Issues

1. **CORS Errors**:
   - Ensure backend CORS is configured
   - Check API base URL

2. **Build Errors**:
   - Clear node_modules and reinstall
   - Check TypeScript version compatibility

3. **Styling Issues**:
   - Verify CSS imports
   - Check responsive breakpoints

4. **API Connection**:
   - Verify backend is running
   - Check network connectivity

## 📄 License

This project is licensed under the Apache License 2.0.

---

**Note**: This frontend is designed to work with the Artifactory Database Manager backend. Ensure the backend is running and properly configured before starting the frontend.