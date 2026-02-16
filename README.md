# Real-Time Poll Application - System Design Document

## 🚀 Project Overview

This is a production-ready real-time poll web application built with Flask, Flask-SocketIO, and SQLAlchemy. The system follows clean architecture principles with clear separation of concerns.

---

## 🏗 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            CLIENT LAYER                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ Create Poll │  │ Share Page  │  │  Poll Page  │  │ Results UI  │   │
│  │    Form     │  │  (Copy URL) │  │  (Voting)   │  │ (Chart.js)  │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
└─────────┼───────────────┼────────────────┼───────────────┼───────────┘
          │               │                │               │
          ▼               ▼                ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          API GATEWAY LAYER                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Flask Application                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │
│  │  │ HTTP Routes │  │ WebSocket   │  │  Rate Limiting          │ │   │
│  │  │ (REST API)  │  │ (SocketIO)  │  │  (In-Memory)            │ │   │
│  │  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │   │
│  └─────────┼────────────────┼─────────────────────┼───────────────┘   │
└────────────┼────────────────┼─────────────────────┼───────────────────┘
             │                │                     │
             ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        SERVICE LAYER                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      PollService                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │
│  │  │  Creation   │  │   Voting    │  │  Real-Time Broadcast    │ │   │
│  │  │   Logic     │  │   Logic     │  │       Logic             │ │   │
│  │  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │   │
│  └─────────┼────────────────┼─────────────────────┼───────────────┘   │
└────────────┼────────────────┼─────────────────────┼───────────────────┘
             │                │                     │
             ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      DATA ACCESS LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    SQLAlchemy ORM                               │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │   │
│  │  │  Poll    │  │  Option  │  │  Vote    │  │  Transactions   │  │   │
│  │  │  Model   │  │  Model   │  │  Model   │  │  (ACID)         │  │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATABASE LAYER                                  │
│  ┌─────────────────────┐    ┌──────────────────────────────────────┐   │
│  │    SQLite (Dev)     │    │     PostgreSQL (Production)          │   │
│  │  - Single file DB   │    │  - ACID compliant                    │   │
│  │  - Development only │    │  - Row-level locking                  │   │
│  └─────────────────────┘    │  - Connection pooling               │   │
│                              └──────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Component Breakdown

### 1. **Presentation Layer** (Templates)
- `base.html` - Base template with common layout
- `create_poll.html` - Poll creation form
- `share.html` - Poll sharing page with copy functionality
- `poll.html` - Voting interface with real-time results
- `404.html` - Error page for invalid polls

### 2. **API Layer** (Flask Routes)
- `/` - Home/Create poll page
- `/create` - POST endpoint for poll creation
- `/poll/<poll_code>` - GET poll page
- `/poll/<poll_code>/vote` - POST vote submission
- `/poll/<poll_code>/results` - GET results (for Chart.js polling fallback)
- `/socket.io/*` - WebSocket endpoint

### 3. **Service Layer** (Business Logic)
- `PollService.create_poll()` - Validate and create new poll
- `PollService.get_poll()` - Fetch poll with options
- `PollService.submit_vote()` - Process vote with fairness checks
- `PollService.get_results()` - Get aggregated results
- `PollService.validate_fairness()` - Check IP and token restrictions
- `PollService.check_rate_limit()` - Rate limiting logic

### 4. **Data Access Layer** (SQLAlchemy Models)
- `Poll` - Poll entity with question and metadata
- `Option` - Poll options with vote counters
- `Vote` - Individual vote records with IP/token

### 5. **Real-Time Layer** (WebSockets)
- Room-based broadcasting per poll
- Event: `vote_update` - Pushes new vote counts to all clients
- Event: `vote_error` - Handles duplicate vote attempts
- Event: `connect/disconnect` - Manages client connections

---

## 🔄 Data Flow Diagrams

### Poll Creation Flow
```
User (Browser)
     │
     ▼
┌──────────────────────────┐
│  1. User fills form      │
│  - Question (required)   │
│  - Options (min 2)       │
└──────────┬───────────────┘
           │ POST /create
           ▼
┌──────────────────────────┐
│  2. Flask Route          │
│  - Validate input        │
│  - Check CSRF (optional) │
└──────────┬───────────────┘
           │ Call PollService
           ▼
┌──────────────────────────┐
│  3. PollService          │
│  - Generate UUID code    │
│  - Create Poll + Options │
│  - Commit to DB          │
└──────────┬───────────────┘
           │ Transaction
           ▼
┌──────────────────────────┐
│  4. SQLAlchemy/DB        │
│  - INSERT Poll           │
│  - INSERT Options        │
│  - Commit transaction    │
└──────────┬───────────────┘
           │ Return poll_code
           ▼
┌──────────────────────────┐
│  5. Redirect to          │
│  /poll/<poll_code>/share │
└──────────────────────────┘
```

### Voting Flow
```
User (Browser)
     │
     ▼
┌──────────────────────────┐
│  1. Load poll page       │
│  - Check localStorage    │
│  - Generate browser token│
│    if not exists         │
└──────────┬───────────────┘
           │ POST /poll/<code>/vote
           ▼
┌──────────────────────────┐
│  2. Rate Limiting        │
│  - Check IP in memory    │
│  - Block if > 10 req/min │
└──────────┬───────────────┘
           │ Pass/Block
           ▼
┌──────────────────────────┐
│  3. PollService          │
│  Fairness Validation:    │
│  - Check IP in Vote table│
│  - Check token in Vote   │
│  - Validate poll exists  │
└──────────┬───────────────┘
           │ Pass/Error
           ▼
┌──────────────────────────┐
│  4. Database Transaction │
│  - BEGIN TRANSACTION     │
│  - SELECT FOR UPDATE     │
│    (row-level lock)      │
│  - Increment vote_count  │
│  - INSERT Vote record    │
│  - COMMIT                │
└──────────┬───────────────┘
           │ Success
           ▼
┌──────────────────────────┐
│  5. WebSocket Broadcast │
│  - Emit 'vote_update'   │
│    to poll room          │
│  - Include new counts    │
│    and percentages       │
└──────────┬───────────────┘
           │
           ▼ (SocketIO)
     All Connected Clients
           │
           ▼
┌──────────────────────────┐
│  6. Client Updates      │
│  - Update Chart.js      │
│  - Disable vote button  │
│  - Show "Voted" state   │
└──────────────────────────┘
```

---

## ⚡ Concurrency Handling

### Problem Statement
Multiple users can vote simultaneously on the same poll option, causing race conditions where:
1. Two reads of the same vote_count
2. Both increment to count+1
3. Final count is only incremented once

### Solution: Row-Level Locking with Atomic Operations

```python
# Using SELECT FOR UPDATE (PostgreSQL)
with db.session.begin_nested():
    option = db.session.query(Option).filter_by(
        id=option_id, poll_id=poll_id
    ).with_for_update().first()
    
    if option:
        option.vote_count += 1
        db.session.flush()
```

### Alternative: Database-Level Atomic Increment
```python
# More efficient - single SQL statement
db.session.execute(
    update(Option).where(
        Option.id == option_id
    ).values(vote_count=Option.vote_count + 1)
)
```

### Transaction Isolation
- Use READ COMMITTED isolation level
- Immediate write visibility
- No phantom reads for vote counts

---

## 🛡 Fairness & Anti-Abuse Controls

### Control 1: IP Address Restriction
```
Threat: Prevents single user from multiple votes from same network

Implementation:
- Store client IP in Vote table
- Check before each vote: SELECT * FROM Vote WHERE poll_id=? AND ip_address=?

Limitations:
- ✓ Prevents casual multiple votes
- ✗ Cannot prevent VPN users
- ✗ Blocks shared WiFi users legitimately
```

### Control 2: Browser Token (localStorage)
```
Threat: Prevents same browser from voting multiple times

Implementation:
- Generate UUID on first visit, store in localStorage
- Send token with each vote request
- Check: SELECT * FROM Vote WHERE poll_id=? AND browser_token=?

Limitations:
- ✓ Works across sessions
- ✗ Can be bypassed by clearing localStorage
- ✗ Can be bypassed in incognito mode
- ✗ Different browsers allowed
```

### Control 3: Rate Limiting (In-Memory)
```
Threat: Prevents automated voting attacks

Implementation:
- Track requests per IP in sliding window
- Block if > 10 requests per minute

Limitations:
- ✓ Basic spam protection
- ✗ Resets on server restart
- ✗ Not shared across multiple servers
```

### Threat Model Summary
| Attack Vector | Prevention | Effectiveness |
|---------------|------------|---------------|
| Multiple votes from same IP | IP Restriction | Medium |
| Same browser multiple votes | Token + localStorage | Medium |
| Automated voting scripts | Rate Limiting | Low-Medium |
| VPN voting | Not preventable | N/A |
| Shared network voting | Not preventable | N/A |

---

## 📈 Scaling Strategy

### Current Architecture (Single Server)
```
                    ┌─────────────────┐
                    │   Flask + SocketIO │
                    │   (Gunicorn)       │
                    │   - 4 workers      │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
              ┌─────▼─────┐       ┌─────▼─────┐
              │  SQLite   │       │  Static   │
              │  Database │       │  Files    │
              └───────────┘       └───────────┘
```

### Production Architecture (Scaled)
```
                         ┌─────────────────────┐
                         │   Load Balancer     │
                         │   (Nginx/HAProxy)   │
                         └──────────┬──────────┘
                                    │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
    ┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
    │  Web Server │         │  Web Server │         │  Web Server │
    │   (Gunicorn)│         │   (Gunicorn)│         │   (Gunicorn)│
    │   Worker 1  │         │   Worker 2  │         │   Worker 3  │
    └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
           │                       │                       │
           └───────────────────────┼───────────────────────┘
                                   │
                         ┌─────────┴─────────┐
                         │                  │
                   ┌─────▼─────┐      ┌─────▼─────┐
                   │ PostgreSQL│      │   Redis   │
                   │  Primary  │◄────►│  Cache &  │
                   └───────────┘      │  Message  │
                                      │   Broker  │
                                      └───────────┘
```

### Scaling Components

#### 1. Database: SQLite → PostgreSQL
- **Change**: Replace SQLite with PostgreSQL
- **Why**: ACID compliance, row-level locking, connection pooling
- **Migration**: Use SQLAlchemy Alembic for schema migrations

#### 2. Rate Limiting: In-Memory → Redis
- **Change**: Store rate limit counters in Redis
- **Why**: Shared across all backend instances
- **Implementation**: Use `redis-py` for sliding window rate limit

#### 3. WebSocket: SocketIO → Redis Adapter
- **Change**: Use `flask-socketio[redis]` for message queue
- **Why**: Broadcast messages across multiple server instances
- **Implementation**: `socketio = SocketIO(app, message_queue=redis_url)`

#### 4. Static Assets: Local → CDN
- **Change**: Serve CSS/JS via CDN (CloudFlare, CloudFront)
- **Why**: Reduce server load, global distribution
- **Implementation**: Nginx configuration or CDN URL rewriting

#### 5. Session Management: Cookies → Redis
- **Change**: Store sessions in Redis
- **Why**: Share sessions across instances
- **Implementation**: Use `Flask-Session` with Redis backend

### Horizontal Scaling Considerations
- **Sticky Sessions**: Required for WebSocket connections
- **Stateless Design**: All state in database/Redis
- **Connection Pooling**: PostgreSQL connection pool (PgBouncer)
- **Monitoring**: Application metrics (Prometheus, Grafana)

---

## 🎨 UI Design

### Color Palette
- Primary: `#6366f1` (Indigo)
- Secondary: `#8b5cf6` (Violet)
- Success: `#10b981` (Emerald)
- Background: `#f8fafc` (Slate 50)
- Card: `#ffffff` (White)
- Text Primary: `#1e293b` (Slate 800)
- Text Secondary: `#64748b` (Slate 500)

### Layout
- Centered card layout (max-width: 600px)
- Responsive: Single column on mobile
- Gradient buttons with hover animations
- Smooth chart transitions with Chart.js

---

## 📂 Database Schema

### Poll Table
```sql
CREATE TABLE polls (
    id SERIAL PRIMARY KEY,
    question VARCHAR(500) NOT NULL,
    poll_code VARCHAR(8) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_poll_code ON polls(poll_code);
CREATE INDEX idx_created_at ON polls(created_at);
```

### Option Table
```sql
CREATE TABLE options (
    id SERIAL PRIMARY KEY,
    poll_id INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    option_text VARCHAR(200) NOT NULL,
    vote_count INTEGER DEFAULT 0
);

CREATE INDEX idx_option_poll_id ON options(poll_id);
```

### Vote Table
```sql
CREATE TABLE votes (
    id SERIAL PRIMARY KEY,
    poll_id INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    option_id INTEGER NOT NULL REFERENCES options(id) ON DELETE CASCADE,
    ip_address VARCHAR(45) NOT NULL,
    browser_token VARCHAR(36) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(poll_id, ip_address),
    UNIQUE(poll_id, browser_token)
);

CREATE INDEX idx_vote_poll_id ON votes(poll_id);
CREATE INDEX idx_vote_ip ON votes(ip_address);
CREATE INDEX idx_vote_token ON votes(browser_token);
```

---

## 🚨 Edge Case Handling

| Scenario | Handling |
|----------|----------|
| Invalid poll_code | Return 404 with helpful message |
| Duplicate vote attempt | Return 409 Conflict, show "Already voted" |
| Missing browser token | Auto-generate UUID on client |
| Database connection failure | Return 503, show retry message |
| WebSocket disconnect | Auto-reconnect with exponential backoff |
| Poll with zero votes | Show 0% for all options, "Be the first to vote!" |
| Server restart | All data persists in database |
| Concurrent votes | Row-level locking prevents corruption |
| Empty question/options | Server-side validation rejects request |

---

## 🔧 Deployment Configuration

### Environment Variables
```
FLASK_ENV=production
SECRET_KEY=<random-secret-key>
DATABASE_URL=postgresql://user:pass@host/dbname
REDIS_URL=redis://localhost:6379
SOCKETIO_MESSAGE_QUEUE=redis://localhost:6379
```

### Procfile (Render/Railway)
```
web: gunicorn -k eventlet -w 1 app:app --bind 0.0.0.0:$PORT
```

### Gunicorn Configuration
- Workers: 1-2 (for WebSocket compatibility)
- Worker Class: eventlet (for async I/O)
- Timeout: 30s (for long WebSocket connections)

---

## 📝 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Home page with create poll form |
| POST | `/create` | Create new poll |
| GET | `/poll/<code>` | View poll page |
| GET | `/poll/<code>/share` | Share poll page |
| POST | `/poll/<code>/vote` | Submit vote |
| GET | `/poll/<code>/results` | Get results (JSON) |
| GET | `/socket.io/` | WebSocket endpoint |

---

## 🔐 Security Considerations

1. **Input Validation**: All user inputs sanitized
2. **SQL Injection**: Parameterized queries via SQLAlchemy
3. **CSRF Protection**: Token-based (can be enhanced)
4. **Rate Limiting**: Per-IP request limiting
5. **Error Messages**: Generic error messages in production
6. **Database**: Least privilege database user
7. **Secrets**: Environment variables for all secrets


