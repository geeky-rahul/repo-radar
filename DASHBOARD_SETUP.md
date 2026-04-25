# GitHub Search Dashboard - Complete Setup Guide

## ✅ What's Implemented

Your application now has a **complete user dashboard** with all the requested features:

### 1. **Welcome Page with Sign in with Google Button**
- ✅ Beautiful landing page with GitHub Repository Search hero
- ✅ Google Sign-in button that redirects to OAuth flow
- ✅ Features showcase pills

### 2. **Search Interface with Advanced Filters**
- ✅ Natural language query input
- ✅ Optional language filter (Python, JavaScript, Go, etc.)
- ✅ Minimum stars filter
- ✅ Pushed after date filter
- ✅ Results count selector (1-30)
- ✅ Real-time search results with relevance scoring

### 3. **User Dashboard (After Login)**

After authentication, users see a tabbed dashboard:

#### **🔍 Search Tab**
- Same search interface available in the dashboard
- Results display with action buttons to add to favorites or collections
- Quick "Add to Favorites" and "Add to Collection" buttons on each repo

#### **❤️ Favorites Tab**
- View all saved favorite repositories
- Shows: Repository name, owner, description, stars, forks, language
- Remove button for each favorite
- Empty state message when no favorites yet

#### **📌 Saved Searches Tab**
- View all saved search queries
- Quick "Run Search" button to re-run any saved search
- Create new saved searches from the Search tab
- Empty state message when no searches saved

#### **📁 Collections Tab**
- View all repository collections/playlists
- Organize repositories by custom collections
- Add repositories to collections
- Empty state message when no collections yet

#### **💡 Recommendations Tab**
- Get personalized repository recommendations
- Recommendations based on:
  - Your starred repositories on GitHub
  - Your saved searches
  - Popular repositories in your preferred languages
- "Add to Favorites" button on each recommendation

### 4. **User Profile Section**
- Displays user's name and email
- Avatar from Google profile (if available)
- Logout button

---

## 🚀 What You Need to Complete Setup

### Step 1: Set Up Google OAuth Credentials

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Create a new project or select an existing one

2. **Enable Google+ API**
   - In the console, enable the Google+ API

3. **Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - Application type: **Web application**
   - Add authorized redirect URIs:
     ```
     http://localhost:8000/api/v1/users/auth/callback
     ```

4. **Copy Your Credentials**
   - Copy your **Client ID** and **Client Secret**

### Step 2: Configure Environment Variables

Update your `.env` file with:

```env
# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=your_client_id_here
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here
APP_URL=http://localhost:8000
```

### Step 3: Optional - GitHub Token (For Recommendations)

To get personalized recommendations, add your GitHub personal access token:

1. Go to https://github.com/settings/tokens
2. Create a new token with `public_repo` scope
3. Add to `.env`:
   ```env
   GITHUB_TOKEN=your_github_token_here
   ```

---

## 🎯 Features by Endpoint

### Authentication
- `GET /api/v1/users/auth/config` - Get OAuth client ID
- `GET /api/v1/users/auth/callback` - OAuth callback handler
- `POST /api/v1/users/auth/google` - Google login endpoint

### User Profile
- `GET /api/v1/users/me` - Get current user profile

### Favorites Management
- `GET /api/v1/users/favorites` - List favorite repositories
- `POST /api/v1/users/favorites` - Add repository to favorites
- `DELETE /api/v1/users/favorites/{repo_id}` - Remove from favorites

### Saved Searches
- `GET /api/v1/users/saved-searches` - List saved searches
- `POST /api/v1/users/saved-searches` - Save a new search

### Collections/Playlists
- `GET /api/v1/users/collections` - List collections
- `POST /api/v1/users/collections` - Create new collection

### Recommendations
- `GET /api/v1/users/recommendations` - Get personalized recommendations

### Search
- `POST /api/v1/search/repositories` - Search repositories

### Health
- `GET /api/v1/health` - API health check

---

## 📊 Dashboard UI Components

### Dashboard Header
- User avatar and profile info
- Logout button

### Tab Navigation
- Responsive tab buttons
- Active tab highlighting
- Smooth tab switching

### Search Results
- Repository cards with:
  - Name and link
  - Description
  - Stars count
  - Forks count
  - Language
  - Relevance score
  - Action buttons (Add to Favorites, Add to Collection)

### Lists
- Favorite repositories list
- Saved searches list
- Collections list
- Recommendations feed

---

## 🔄 Data Flow

```
1. User clicks "Sign in with Google"
   ↓
2. Redirected to Google OAuth login
   ↓
3. User authenticates and consents
   ↓
4. Redirected to callback with auth code
   ↓
5. Backend exchanges code for Google ID token
   ↓
6. User profile created/loaded from storage
   ↓
7. Session token created and stored
   ↓
8. Redirected to dashboard with token in localStorage
   ↓
9. Dashboard fetches user data using token:
   - GET /api/v1/users/me (profile)
   - GET /api/v1/users/favorites (favorites)
   - GET /api/v1/users/saved-searches (saved searches)
   - GET /api/v1/users/collections (collections)
   ↓
10. All dashboard features available
```

---

## 💾 Data Storage

- **Redis** (primary): Caches sessions, favorites, saved searches, collections
- **In-Memory Fallback**: If Redis unavailable, uses temporary in-memory storage
- **Session TTL**: 30 days for user sessions

---

## 🧪 Testing the Dashboard

### Without OAuth Setup:
1. Open browser console (F12)
2. Paste this to simulate login:
   ```javascript
   localStorage.setItem('githubSearchUserToken', 'test-token');
   location.reload();
   ```
3. The dashboard will attempt to load (will show as logged in but API calls will fail without real token)

### With OAuth Setup:
1. Complete the setup steps above
2. Restart the server
3. Click "Sign in with Google"
4. Go through Google authentication
5. Dashboard loads with your user data

---

## 📱 Mobile Responsive

Dashboard is fully responsive:
- Desktop: Multi-column tabs and cards
- Tablet: Responsive grid layout
- Mobile: Single column, stacked layout
- Touch-friendly buttons and spacing

---

## 🎨 UI Features

- **Dark theme** with gradient accents (Indigo/Purple)
- **Smooth animations** for tab switching and interactions
- **Loading states** with spinners
- **Empty states** with helpful messages
- **Hover effects** on interactive elements
- **Error handling** with user-friendly messages

---

## 🔐 Security Notes

- Session tokens stored in localStorage (consider httpOnly cookie for production)
- Bearer token authentication on all protected endpoints
- ID token verified with Google's public keys
- Tokens expire after 30 days
- Fallback in-memory storage is session-scoped (data lost on server restart)

---

## ❓ Troubleshooting

### "Google OAuth client ID is not configured"
- Add `GOOGLE_OAUTH_CLIENT_ID` to `.env` file
- Restart server

### Dashboard shows but API calls fail
- Check browser console for error details
- Verify token in localStorage
- Check server logs for API errors

### Favorites/Searches not saving
- Ensure Redis is running or fallback is working
- Check server logs for errors
- Verify user is authenticated (check Authorization header)

### Recommendations show empty
- Link GitHub token to profile
- Star some repositories on GitHub
- Wait a moment and refresh

---

## 📚 Example Requests

### Login Example
```bash
curl -X POST http://localhost:8000/api/v1/users/auth/google \
  -H "Content-Type: application/json" \
  -d '{"id_token": "your_google_id_token"}'
```

### Get Favorites
```bash
curl -X GET http://localhost:8000/api/v1/users/favorites \
  -H "Authorization: Bearer your_session_token"
```

### Add to Favorites
```bash
curl -X POST http://localhost:8000/api/v1/users/favorites \
  -H "Authorization: Bearer your_session_token" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 12345,
    "name": "repo-name",
    "full_name": "owner/repo-name",
    "html_url": "https://github.com/owner/repo-name",
    ...
  }'
```

### Save Search
```bash
curl -X POST http://localhost:8000/api/v1/users/saved-searches \
  -H "Authorization: Bearer your_session_token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Python ML Projects",
    "query": "machine learning python tensorflow pytorch"
  }'
```

---

**Status**: ✅ Ready for OAuth Configuration

Once you configure Google OAuth credentials, your dashboard will be fully operational!
