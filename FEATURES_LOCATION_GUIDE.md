# 🎯 Dashboard Features - Where Everything Is Located

## Current Landing Page (Visible Now)

The landing page is what you see currently:
- **Title**: "GitHub Repository Search"
- **Description**: Explains the search capability
- **Tech Pills**: FastAPI, AI parsing, GitHub API, Redis
- **Green Button**: "Sign in with Google" 🟢
- **Search Form Below**: Advanced search interface

### Landing Page Search Features
```
Search Form:
├── Search Query (required)
├── Language Filter (optional - python, javascript, etc.)
├── Minimum Stars (optional - 0-9999)
├── Pushed After Date (optional - YYYY-MM-DD)
├── Results Count (1-30, default 10)
└── Buttons: [Search] [Reset]
```

---

## After Login - User Dashboard

Once user clicks "Sign in with Google" and authenticates, they see:

### **Dashboard Layout**
```
┌─────────────────────────────────────────────────────────┐
│  [Avatar] 👤 Nitish Singh | email@example.com [LOGOUT] │
├─────────────────────────────────────────────────────────┤
│ 🔍        ❤️          📌        📁         💡          │
│ Search   Favorites  Saved-   Collections Recommendations
│                    Searches                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│               ACTIVE TAB CONTENT AREA                    │
│             (Changes based on selected tab)             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 📍 Feature Locations in Dashboard

### **1. 🔍 SEARCH TAB (Default Active)**
**What appears**: Same search form as landing page
- Search input field
- Advanced filters
- Search/Reset buttons

**What happens**:
- User enters search query
- Clicks "Search repositories"
- Results appear below

**Results Show**:
```
Repository Card:
├── Name (clickable link to GitHub)
├── Description
├── ⭐ Stars Count
├── 🔀 Forks Count  
├── 💻 Language
├── 📈 Relevance Score (0-100%)
└── Buttons: [❤️ Add Favorites] [📁 Add to Collection]
```

---

### **2. ❤️ FAVORITES TAB**
**Location**: Click the "❤️ Favorites" tab
**What appears**: List of saved favorite repositories

**Each Favorite Shows**:
```
Favorite Repository Card:
├── Repository Name (GitHub link)
├── Owner Name
├── Description
├── ⭐ Star Count
├── 🔀 Fork Count
├── 💻 Programming Language
└── [Remove Button]
```

**Empty State**: 
- Message: "No favorite repositories yet. Add from search results!"
- Shows when user has no favorites

**How to Add**:
1. Go to Search tab
2. Find a repository you like
3. Click "❤️ Add to Favorites" button
4. Repository appears in Favorites tab

---

### **3. 📌 SAVED SEARCHES TAB**
**Location**: Click the "📌 Saved Searches" tab
**What appears**: List of saved search queries

**Each Saved Search Shows**:
```
Saved Search Card:
├── Search Name (e.g., "Python ML Projects")
├── Query Text (e.g., "machine learning python tensorflow")
└── [Run Search Button] ← Click to re-run that search
```

**Empty State**:
- Message: "No saved searches yet. Save searches from the Search tab!"
- Shows when user has no saved searches

**How to Add**:
1. Go to Search tab
2. Enter a search query
3. Click "Search repositories"
4. After getting results, click "Save Search" prompt (appears after search)
5. Enter a name for the search
6. Search appears in Saved Searches tab

**Why Use It**:
- ⏱️ Save time on frequently-used searches
- 🔄 Quickly re-run searches without typing again
- 📊 Track your research patterns

---

### **4. 📁 COLLECTIONS TAB**
**Location**: Click the "📁 Collections" tab
**What appears**: List of repository collections/playlists

**Each Collection Shows**:
```
Collection Card:
├── Collection Name
├── Description
├── Number of Repos (implied)
└── [View/Manage Options]
```

**Empty State**:
- Message: "No collections yet. Create one to organize repositories!"
- Shows when user has no collections

**How to Create**:
1. Go to Collections tab
2. Click "+ Create Collection" button
3. Enter collection name and description
4. New collection appears in list

**How to Add Repos to Collection**:
1. Go to Search tab
2. Find a repository
3. Click "📁 Add to Collection" button
4. Select which collection to add to
5. Repository is added

**Why Use It**:
- 📚 Organize repositories by project/topic
- 🎯 Group related projects together
- 📋 Build custom playlists/curated lists

---

### **5. 💡 RECOMMENDATIONS TAB**
**Location**: Click the "💡 Recommendations" tab
**What appears**: Personalized repository recommendations

**Recommendations Show**:
```
Recommendation Card (same as search results):
├── Repository Name (GitHub link)
├── Owner
├── Description
├── ⭐ Star Count
├── 🔀 Fork Count
├── 💻 Language
└── [❤️ Add to Favorites Button]
```

**Empty State**:
- Message: "No recommendations yet. Star some repositories on GitHub to get personalized recommendations!"
- Shows when insufficient data

**How Recommendations Work**:
1. System checks your GitHub starred repositories
2. Analyzes topics and languages you're interested in
3. Checks your saved searches
4. Recommends similar projects
5. Shows them sorted by relevance

**Why Use It**:
- 💡 Discover new projects based on your interests
- 🎓 Find similar/related repositories
- 🚀 Get suggestions without searching

---

## 🔐 User Profile Section

**Location**: Top of dashboard (in header)
**Shows**:
- 👤 User avatar (from Google profile)
- 📝 User name
- 📧 Email address
- [LOGOUT Button]

---

## 🎯 Complete User Journey

```
1. User lands on http://localhost:8000
   ↓
2. Sees landing page with:
   • Project title and description
   • Tech stack pills
   • "Sign in with Google" button
   • Search form
   ↓
3. Clicks "Sign in with Google"
   ↓
4. Redirected to Google login
   ↓
5. User authenticates with Google
   ↓
6. Redirected back to app with auth code
   ↓
7. Backend creates/loads user profile
   ↓
8. Dashboard loads with:
   • User info in header
   • 5 navigation tabs
   • Default Search tab active
   ↓
9. User can:
   ├─ Search repositories (Search tab)
   ├─ View favorites (Favorites tab)
   ├─ View saved searches (Saved tab)
   ├─ View collections (Collections tab)
   ├─ Get recommendations (Recommendations tab)
   └─ Logout (Header button)
   ↓
10. All data saved to Redis (or memory fallback)
    for persistent access across sessions
```

---

## 📱 Responsive Design

### **Desktop (>880px)**
- All tabs visible horizontally
- Full width content
- Multi-column grids
- Hover effects on buttons

### **Tablet (640px - 880px)**
- Tabs may wrap to multiple lines
- 2-column grid layouts
- Touch-friendly spacing
- Adjusted padding

### **Mobile (<640px)**
- Tabs in vertical scroll
- Single column layout
- Larger touch targets
- Stacked components
- Full-width cards

---

## 🔄 API Calls Behind the Scenes

When user navigates dashboard:

```
On Dashboard Load:
GET /api/v1/users/me
  └─ Returns: User profile (name, email, avatar)
GET /api/v1/users/favorites  
  └─ Returns: List of favorite repositories
GET /api/v1/users/saved-searches
  └─ Returns: List of saved searches
GET /api/v1/users/collections
  └─ Returns: List of collections

When User Searches:
POST /api/v1/search/repositories
  └─ Returns: Ranked repository results

When User Adds Favorite:
POST /api/v1/users/favorites
  └─ Saves repository to favorites

When User Adds to Collection:
POST /api/v1/users/collections/{id}/add
  └─ Adds repository to collection

When User Gets Recommendations:
GET /api/v1/users/recommendations
  └─ Returns: Personalized recommendations
```

---

## ✨ Key Features Summary

| Feature | Location | Status | How to Use |
|---------|----------|--------|-----------|
| Search Repos | Search Tab | ✅ Working | Enter query, click Search |
| Save Favorites | Search Results | ✅ Working | Click [❤️ Add] on any repo |
| View Favorites | Favorites Tab | ✅ Working | Click tab to see all |
| Save Searches | After Search | ✅ Working | Prompt appears after search |
| Run Saved | Saved Searches Tab | ✅ Working | Click [Run Search] button |
| Collections | Collections Tab | ✅ Working | Create + add repos |
| Recommendations | Recommendations Tab | ✅ Working | Click tab to see suggestions |
| User Profile | Dashboard Header | ✅ Working | Visible in top section |
| Logout | Dashboard Header | ✅ Working | Click [LOGOUT] button |

---

## 🎓 Example Usage Scenarios

### **Scenario 1: Find ML Repos for Learning**
1. Log in
2. Go to Search tab
3. Enter: "machine learning python tensorflow"
4. Click Search
5. See results ranked by popularity
6. Add interesting ones to Favorites
7. Save search as "ML Learning Resources"

### **Scenario 2: Organize Projects**
1. Create Collection: "Web Development"
2. Search for web framework repos
3. Add relevant ones to "Web Development" collection
4. Later, click Collections tab to see organized list

### **Scenario 3: Get Smart Recommendations**
1. Star some repos on GitHub
2. Go to Recommendations tab
3. See personalized suggestions
4. Add interesting ones to Favorites
5. Build a curated list

### **Scenario 4: Compare Saved Searches**
1. Save multiple searches: "Python CLI", "Go Web", "Rust Systems"
2. Click Saved Searches tab
3. Quickly jump between searches
4. Find best resources for each topic

---

## 🚀 What's Next

**To get it fully working**:

1. **Configure Google OAuth** (see DASHBOARD_SETUP.md)
2. **Add Google credentials to .env**
3. **Restart server**
4. **Test login flow**
5. **Enjoy the complete dashboard!**

---

## 📞 Troubleshooting

### "Google OAuth client was not found"
- ✅ Expected without credentials
- ⚠️ Add `GOOGLE_OAUTH_CLIENT_ID` to .env
- 🔄 Restart server

### Dashboard loads but APIs fail
- 📋 Check browser console (F12)
- 🔐 Verify token in localStorage
- 📊 Check server logs

### Recommendations are empty
- 🌟 Star some repos on GitHub
- 🔗 Link GitHub token to profile
- ⏰ Recommendations update periodically

### Favorites/Searches not saving
- 🔄 Check if Redis is running
- 💾 Verify server logs
- 🔐 Ensure you're logged in

---

**Status**: ✅ All features implemented and ready!

Proceed to DASHBOARD_SETUP.md for complete configuration guide.
