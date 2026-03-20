List of planned features for AjaxChess.com

F1 Create initial project structure
  FastAPI application with uvicorn on port 8001
  SQLite database with SQLAlchemy ORM (UserProfile, BlogComment, ServerStats)
  Google OAuth 2.0 authentication via Authlib
  Coming soon landing page with Google Sign-In button at the top
  Feature preview cards (Play, Learn, Puzzles, Tournaments)
  Privacy policy and terms of service pages
  Blog with Markdown support and comment system
  Admin dashboard: operations, users, kanban, blog moderation
  Base templates and CSS modeled on minesweeper.org
  KANBAN.md, Features.md, Bugs.md for project management

F2 Play Online — Real-time chess
  WebSocket-based real-time games
  Matchmaking by Elo rating
  Timed games (bullet, blitz, rapid, classical)
  Game result recording and rating updates

F3 Opening Explorer
  Interactive tree of chess openings
  Annotated lines from master games
  Search by name (e.g. "Sicilian", "King's Indian")
  ECO code lookup

F4 Daily Puzzles
  New puzzle every day
  Multiple difficulty levels (beginner → grandmaster)
  Solve streak tracking
  Puzzle rating system

F5 Tournaments
  Open Swiss-system tournaments
  Round-robin invitational tournaments
  Real-time brackets and standings
  Trophy / achievement system

F6 Learn — Structured courses
  Beginner: piece values, basic tactics, simple endgames
  Intermediate: positional play, pawn structure, piece coordination
  Advanced: complex endgames, grandmaster openings, long-term planning
  Progress tracking and certificates

F7 Elo Rating System
  FIDE-style Elo calculation
  Separate ratings by time control (bullet, blitz, rapid)
  Rating history chart on user profile
  Provisional rating for new players

F8 Mobile Support
  Responsive chess board with touch controls
  Drag-and-drop piece movement on mobile
  Landscape and portrait support
  PWA / installable app

F9 SEO Improvements
  JSON-LD structured data for game pages
  XML sitemap auto-generation
  Open Graph tags for social sharing
  Canonical URLs

F10 Game Analysis
  Post-game engine analysis (Stockfish WebAssembly)
  Move annotations: best move, inaccuracy, mistake, blunder
  Interactive review of the game with engine suggestions
  Export to PGN

F11 Friends & Social
  Follow / friend system
  Challenge a friend to a game
  Real-time chat during games
  User profiles with game stats and rating history

F12 Game History
  Persistent storage of all completed games
  Searchable and filterable game log
  Replay any game with forward/backward navigation
  Download games as PGN

F13 Leaderboards
  Daily leaderboard (most games, win rate, best performance)
  Monthly rankings by rating gain
  All-time records (highest rating, longest win streak)
  Country-based leaderboards

F14 FICS Client — Browser-based Free Internet Chess Server terminal
  WebSocket relay between browser and freechess.org:5000 TCP
  Login handshake with username/password or guest access
  Terminal output with ANSI stripping and auto-scroll
  Command history with up/down arrow navigation
  Status indicator (connecting / connected / disconnected / error)
  Requires Google login to access the page

F16 Blog & Content
  Blog with Markdown support and front-matter metadata
  Comment system with admin moderation
  Kanban board in admin for project tracking

F17 Admin Dashboard
  User management (view, search, ban)
  Server metrics (CPU, memory, disk) with historical charts
  Blog comment moderation
  Kanban board view from KANBAN.md

D1 Initial project setup
  FastAPI application with uvicorn on port 8001
  SQLite database with SQLAlchemy ORM
  Google OAuth 2.0 authentication
  Base templates modeled on minesweeper.org

D2 Repository management
  MIT license
  Python .gitignore
  ads.txt for Google AdSense

D3 Development environment
  Development on Mac, deployment to Ubuntu server on AWS
  Run with: uvicorn main:app --host 0.0.0.0 --port 8001 --reload
