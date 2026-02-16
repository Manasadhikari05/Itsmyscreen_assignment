"""
Main Flask Application for Real-Time Poll System.

This module contains:
- Flask application factory
- HTTP routes for poll operations
- WebSocket handlers for real-time updates
- Error handlers
- Application initialization
"""

import os
import logging
from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    flash, session
)
from flask_socketio import SocketIO, emit, join_room, leave_room

from config import get_config
from models import init_db, Poll, Option, Vote, generate_browser_token
from services.poll_service import (
    PollService, PollServiceError, ValidationError,
    DuplicateVoteError, PollNotFoundError, RateLimitError,
    RateLimiter
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize SocketIO with eventlet for async support
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='gevent',
    ping_timeout=60,
    ping_interval=25
)

# Global rate limiter instance
rate_limiter = RateLimiter(
    max_requests=int(os.environ.get('RATE_LIMIT_REQUESTS', 10)),
    window_seconds=int(os.environ.get('RATE_LIMIT_WINDOW', 60))
)


def create_app(config=None):
    """
    Application factory for creating Flask app.

    Args:
        config: Optional configuration override

    Returns:
        Flask application instance
    """
    app = Flask(__name__)

    # Load configuration
    if config is None:
        config = get_config()

    app.config.from_object(config)

    # Initialize database
    engine, SessionLocal = init_db(app.config['SQLALCHEMY_DATABASE_URI'])

    # Store in app for access in routes
    app.db_engine = engine
    app.db_session = SessionLocal

    # Initialize SocketIO
    socketio.init_app(app, message_queue=app.config.get('SOCKETIO_MESSAGE_QUEUE'))

    # Register routes
    register_routes(app, SessionLocal)

    # Register WebSocket handlers
    register_socket_handlers()

    # Register error handlers
    register_error_handlers(app)

    logger.info("Application initialized successfully")

    return app


def get_db_session():
    """Get a new database session."""
    return SessionLocal()


def register_routes(app, SessionLocal):
    """Register all HTTP routes."""

    @app.route('/')
    def index():
        """Home page - poll creation form."""
        return render_template('create_poll.html')

    @app.route('/create', methods=['POST'])
    def create_poll():
        """Create a new poll."""
        # Get client IP for rate limiting
        ip_address = request.remote_addr or '127.0.0.1'

        # Check rate limit
        if not rate_limiter.is_allowed(ip_address):
            flash('Too many requests. Please try again later.', 'error')
            return render_template('create_poll.html')

        # Get form data
        question = request.form.get('question', '').strip()
        options = []

        # Parse options from form (options[] can be multiple)
        for key in request.form:
            if key.startswith('option_'):
                value = request.form.get(key, '').strip()
                if value:
                    options.append(value)

        # Create poll service
        db_session = SessionLocal()
        try:
            poll_service = PollService(db_session, rate_limiter)

            # Create poll
            poll = poll_service.create_poll(
                question=question,
                options=options,
                min_options=app.config.get('MIN_OPTIONS', 2),
                max_options=app.config.get('MAX_OPTIONS', 10),
                max_question_length=app.config.get('MAX_QUESTION_LENGTH', 500),
                max_option_length=app.config.get('MAX_OPTION_LENGTH', 200)
            )

            logger.info(f"Poll created: {poll.poll_code}")

            # Redirect to share page
            return redirect(url_for('share_poll', poll_code=poll.poll_code))

        except ValidationError as e:
            flash(str(e), 'error')
            return render_template('create_poll.html', question=question, options=options)
        except Exception as e:
            logger.error(f"Error creating poll: {e}")
            flash('An error occurred. Please try again.', 'error')
            return render_template('create_poll.html')
        finally:
            db_session.close()

    @app.route('/poll/<poll_code>')
    def view_poll(poll_code):
        """View a poll and vote."""
        db_session = SessionLocal()
        try:
            poll_service = PollService(db_session)
            poll = poll_service.get_poll_by_code(poll_code.upper())

            if not poll:
                return render_template('404.html', poll_code=poll_code), 404

            # Check if user has already voted
            browser_token = request.cookies.get('browser_token')
            has_voted = False
            voted_option_id = None

            if browser_token:
                existing_vote = db_session.query(Vote).filter(
                    Vote.poll_id == poll.id,
                    Vote.browser_token == browser_token
                ).first()
                if existing_vote:
                    has_voted = True
                    voted_option_id = existing_vote.option_id

            # Get results for display
            results = poll_service.get_results(poll_code)

            response = make_response(render_template(
                'poll.html',
                poll=poll,
                results=results,
                has_voted=has_voted,
                voted_option_id=voted_option_id
            ))

            # Set browser token cookie if not exists
            if not browser_token:
                browser_token = generate_browser_token()
                response.set_cookie(
                    'browser_token',
                    browser_token,
                    max_age=60*60*24*365,  # 1 year
                    httponly=True,
                    samesite='Lax'
                )

            return response

        except Exception as e:
            logger.error(f"Error viewing poll: {e}")
            return render_template('404.html', poll_code=poll_code), 404
        finally:
            db_session.close()

    @app.route('/poll/<poll_code>/share')
    def share_poll(poll_code):
        """Share poll page with copy link functionality."""
        db_session = SessionLocal()
        try:
            poll_service = PollService(db_session)
            poll = poll_service.get_poll_by_code(poll_code.upper())

            if not poll:
                return render_template('404.html', poll_code=poll_code), 404

            # Build poll URL
            poll_url = f"{request.host_url}poll/{poll.poll_code}"

            return render_template(
                'share.html',
                poll=poll,
                poll_url=poll_url
            )

        except Exception as e:
            logger.error(f"Error loading share page: {e}")
            return render_template('404.html', poll_code=poll_code), 404
        finally:
            db_session.close()

    @app.route('/poll/<poll_code>/vote', methods=['POST'])
    def submit_vote(poll_code):
        """Submit a vote for a poll."""
        # Get client info
        ip_address = request.remote_addr or '127.0.0.1'
        browser_token = request.cookies.get('browser_token')

        # Auto-generate token if not exists
        if not browser_token:
            browser_token = generate_browser_token()

        # Get vote data
        data = request.get_json() or {}
        option_id = data.get('option_id')

        if not option_id:
            return jsonify({'success': False, 'error': 'Please select an option'}), 400

        try:
            option_id = int(option_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid option'}), 400

        # Check rate limit
        if not rate_limiter.is_allowed(ip_address):
            return jsonify({
                'success': False,
                'error': 'Too many requests. Please try again later.',
                'rate_limited': True
            }), 429

        # Process vote
        db_session = SessionLocal()
        try:
            poll_service = PollService(db_session, rate_limiter)

            result = poll_service.submit_vote(
                poll_code=poll_code.upper(),
                option_id=option_id,
                ip_address=ip_address,
                browser_token=browser_token
            )

            # Broadcast update via WebSocket
            poll_results = poll_service.get_results(poll_code.upper())
            socketio.emit('vote_update', poll_results, room=poll_code.upper())

            response = jsonify({
                'success': True,
                'results': poll_results
            })

            # Set cookie if not exists
            if 'browser_token' not in request.cookies:
                response.set_cookie(
                    'browser_token',
                    browser_token,
                    max_age=60*60*24*365,
                    httponly=True,
                    samesite='Lax'
                )

            return response

        except PollNotFoundError:
            return jsonify({'success': False, 'error': 'Poll not found'}), 404
        except ValidationError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except DuplicateVoteError as e:
            return jsonify({'success': False, 'error': str(e), 'already_voted': True}), 409
        except Exception as e:
            logger.error(f"Error submitting vote: {e}")
            return jsonify({'success': False, 'error': 'Failed to submit vote'}), 500
        finally:
            db_session.close()

    @app.route('/poll/<poll_code>/results')
    def get_results(poll_code):
        """Get poll results as JSON (for polling fallback)."""
        db_session = SessionLocal()
        try:
            poll_service = PollService(db_session)
            results = poll_service.get_results(poll_code.upper())
            return jsonify(results)
        except PollNotFoundError:
            return jsonify({'error': 'Poll not found'}), 404
        except Exception as e:
            logger.error(f"Error getting results: {e}")
            return jsonify({'error': 'Failed to get results'}), 500
        finally:
            db_session.close()

    @app.route('/health')
    def health_check():
        """Health check endpoint."""
        return jsonify({'status': 'healthy'}), 200


def register_socket_handlers():
    """Register WebSocket event handlers."""

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        logger.info(f"Client connected: {request.sid}")
        emit('connected', {'sid': request.sid})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        logger.info(f"Client disconnected: {request.sid}")

    @socketio.on('join_poll')
    def handle_join_poll(data):
        """
        Handle client joining a poll room for real-time updates.

        Expected data:
            poll_code: The poll code to join
        """
        poll_code = data.get('poll_code', '').upper()

        if poll_code:
            join_room(poll_code)
            logger.info(f"Client {request.sid} joined room: {poll_code}")
            emit('joined', {'poll_code': poll_code}, room=request.sid)

    @socketio.on('leave_poll')
    def handle_leave_poll(data):
        """Handle client leaving a poll room."""
        poll_code = data.get('poll_code', '').upper()

        if poll_code:
            leave_room(poll_code)
            logger.info(f"Client {request.sid} left room: {poll_code}")

    @socketio.on('request_results')
    def handle_request_results(data):
        """
        Handle client requesting current results.

        Expected data:
            poll_code: The poll code to get results for
        """
        poll_code = data.get('poll_code', '').upper()

        if not poll_code:
            return

        # Get results from database
        db_session = get_db_session()
        try:
            poll_service = PollService(db_session)
            results = poll_service.get_results(poll_code)
            emit('vote_update', results, room=request.sid)
        except Exception as e:
            logger.error(f"Error getting results for socket: {e}")
            emit('error', {'message': 'Failed to get results'}, room=request.sid)
        finally:
            db_session.close()


def register_error_handlers(app):
    """Register error handlers."""

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.error(f"Internal error: {error}")
        return render_template('404.html', error='Internal server error'), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle all unhandled exceptions."""
        logger.error(f"Unhandled exception: {error}")
        return render_template('404.html', error='Something went wrong'), 500


# Create the application
app = create_app()

# Import make_response for cookie handling
from flask import make_response

if __name__ == '__main__':
    # Run with SocketIO support
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config.get('DEBUG', False)
    )
