"""
Poll Service - Business Logic Layer

This module contains all business logic for poll operations including:
- Poll creation with validation
- Vote submission with fairness checks
- Rate limiting
- Real-time result calculations
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from models import Poll, Option, Vote, generate_poll_code

# Configure logging
logger = logging.getLogger(__name__)


class PollServiceError(Exception):
    """Base exception for poll service errors."""
    pass


class ValidationError(PollServiceError):
    """Raised when input validation fails."""
    pass


class DuplicateVoteError(PollServiceError):
    """Raised when user tries to vote twice."""
    pass


class PollNotFoundError(PollServiceError):
    """Raised when poll doesn't exist."""
    pass


class RateLimitError(PollServiceError):
    """Raised when rate limit is exceeded."""
    pass


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.

    Tracks requests per IP address within a configurable time window.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in the window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}

    def is_allowed(self, ip_address: str) -> bool:
        """
        Check if request is allowed for the given IP.

        Args:
            ip_address: Client IP address

        Returns:
            bool: True if allowed, False if rate limited
        """
        current_time = time.time()
        window_start = current_time - self.window_seconds

        # Get or initialize request list for this IP
        if ip_address not in self._requests:
            self._requests[ip_address] = []

        # Filter out old requests outside the window
        self._requests[ip_address] = [
            req_time for req_time in self._requests[ip_address]
            if req_time > window_start
        ]

        # Check if under limit
        if len(self._requests[ip_address]) >= self.max_requests:
            return False

        # Add current request
        self._requests[ip_address].append(current_time)
        return True

    def get_remaining(self, ip_address: str) -> int:
        """Get remaining requests for an IP."""
        if ip_address not in self._requests:
            return self.max_requests

        current_time = time.time()
        window_start = current_time - self.window_seconds

        # Filter out old requests
        recent_requests = [
            req_time for req_time in self._requests[ip_address]
            if req_time > window_start
        ]

        return max(0, self.max_requests - len(recent_requests))


class PollService:
    """
    Service class for poll-related operations.

    Handles all business logic including validation, voting, and result calculation.
    """

    def __init__(self, db_session: Session, rate_limiter: RateLimiter = None):
        """
        Initialize poll service.

        Args:
            db_session: SQLAlchemy database session
            rate_limiter: Rate limiter instance
        """
        self.db = db_session
        self.rate_limiter = rate_limiter or RateLimiter()

    def create_poll(
        self,
        question: str,
        options: List[str],
        min_options: int = 2,
        max_options: int = 10,
        max_question_length: int = 500,
        max_option_length: int = 200
    ) -> Poll:
        """
        Create a new poll with the given question and options.

        Args:
            question: The poll question
            options: List of option texts
            min_options: Minimum number of options required
            max_options: Maximum number of options allowed
            max_question_length: Maximum question length
            max_option_length: Maximum option text length

        Returns:
            Poll: The created poll

        Raises:
            ValidationError: If validation fails
        """
        # Validate question
        if not question or not question.strip():
            raise ValidationError("Question is required")

        question = question.strip()
        if len(question) > max_question_length:
            raise ValidationError(
                f"Question must be {max_question_length} characters or less"
            )

        # Validate options
        if not options or len(options) < min_options:
            raise ValidationError(f"At least {min_options} options are required")

        if len(options) > max_options:
            raise ValidationError(f"Maximum {max_options} options allowed")

        # Clean and validate each option
        cleaned_options = []
        for opt in options:
            opt = opt.strip()
            if not opt:
                raise ValidationError("Options cannot be empty")
            if len(opt) > max_option_length:
                raise ValidationError(
                    f"Each option must be {max_option_length} characters or less"
                )
            cleaned_options.append(opt)

        # Check for duplicate options
        if len(cleaned_options) != len(set(cleaned_options)):
            raise ValidationError("Options must be unique")

        # Generate unique poll code
        poll_code = self._generate_unique_poll_code()

        # Create poll
        poll = Poll(question=question, poll_code=poll_code)

        # Add options
        for opt_text in cleaned_options:
            option = Option(option_text=opt_text, vote_count=0)
            poll.options.append(option)

        # Save to database
        try:
            self.db.add(poll)
            self.db.commit()
            self.db.refresh(poll)
            logger.info(f"Created poll with code: {poll_code}")
            return poll
        except IntegrityError:
            self.db.rollback()
            # Code collision - try again (rare)
            return self.create_poll(question, options, min_options, max_options)

    def _generate_unique_poll_code(self) -> str:
        """
        Generate a unique poll code.

        Returns:
            str: Unique poll code

        Raises:
            ValidationError: If unable to generate unique code after retries
        """
        max_attempts = 10
        for _ in range(max_attempts):
            code = generate_poll_code(8)
            # Check if code exists
            existing = self.db.query(Poll).filter_by(poll_code=code).first()
            if not existing:
                return code

        raise ValidationError("Unable to generate unique poll code")

    def get_poll_by_code(self, poll_code: str) -> Optional[Poll]:
        """
        Get a poll by its code.

        Args:
            poll_code: The poll's unique code

        Returns:
            Poll or None if not found
        """
        return self.db.query(Poll).filter_by(poll_code=poll_code).first()

    def get_poll_or_404(self, poll_code: str) -> Poll:
        """
        Get a poll by code or raise PollNotFoundError.

        Args:
            poll_code: The poll's unique code

        Returns:
            Poll: The poll

        Raises:
            PollNotFoundError: If poll doesn't exist
        """
        poll = self.get_poll_by_code(poll_code)
        if not poll:
            raise PollNotFoundError(f"Poll with code '{poll_code}' not found")
        return poll

    def validate_vote(
        self,
        poll_code: str,
        ip_address: str,
        browser_token: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a vote can be submitted (fairness checks).

        Args:
            poll_code: The poll code
            ip_address: Client IP address
            browser_token: Browser identifier token

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get poll
        poll = self.get_poll_by_code(poll_code)
        if not poll:
            return False, "Poll not found"

        # Check IP restriction
        existing_ip_vote = self.db.query(Vote).filter(
            Vote.poll_id == poll.id,
            Vote.ip_address == ip_address
        ).first()

        if existing_ip_vote:
            return False, "You have already voted from this IP address"

        # Check browser token restriction
        existing_token_vote = self.db.query(Vote).filter(
            Vote.poll_id == poll.id,
            Vote.browser_token == browser_token
        ).first()

        if existing_token_vote:
            return False, "You have already voted"

        return True, None

    def submit_vote(
        self,
        poll_code: str,
        option_id: int,
        ip_address: str,
        browser_token: str
    ) -> Dict[str, Any]:
        """
        Submit a vote for a poll option.

        Args:
            poll_code: The poll code
            option_id: The option ID to vote for
            ip_address: Client IP address
            browser_token: Browser identifier token

        Returns:
            dict: Result with success status and poll data

        Raises:
            PollNotFoundError: If poll doesn't exist
            ValidationError: If option is invalid
            DuplicateVoteError: If user already voted
        """
        # Get poll
        poll = self.get_poll_by_code(poll_code)
        if not poll:
            raise PollNotFoundError(f"Poll not found")

        # Validate option belongs to poll
        option = self.db.query(Option).filter(
            Option.id == option_id,
            Option.poll_id == poll.id
        ).first()

        if not option:
            raise ValidationError("Invalid option selected")

        # Check for duplicate vote (fairness)
        existing_vote = self.db.query(Vote).filter(
            Vote.poll_id == poll.id,
            Vote.ip_address == ip_address
        ).first()

        if existing_vote:
            raise DuplicateVoteError("You have already voted from this IP address")

        existing_token_vote = self.db.query(Vote).filter(
            Vote.poll_id == poll.id,
            Vote.browser_token == browser_token
        ).first()

        if existing_token_vote:
            raise DuplicateVoteError("You have already voted")

        try:
            # Create vote record
            vote = Vote(
                poll_id=poll.id,
                option_id=option_id,
                ip_address=ip_address,
                browser_token=browser_token
            )

            # Atomic increment of vote count
            # Use direct SQL update for atomicity
            from sqlalchemy import update
            stmt = (
                update(Option)
                .where(Option.id == option_id)
                .values(vote_count=Option.vote_count + 1)
            )
            self.db.execute(stmt)

            # Add vote record
            self.db.add(vote)

            # Commit transaction
            self.db.commit()

            logger.info(f"Vote submitted: poll={poll_code}, option={option_id}, ip={ip_address}")

            # Return updated poll data
            self.db.refresh(poll)
            return {
                'success': True,
                'poll': poll.to_dict(),
                'voted_option_id': option_id
            }

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during vote: {e}")
            raise DuplicateVoteError("You have already voted")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error submitting vote: {e}")
            raise PollServiceError("Failed to submit vote")

    def get_results(self, poll_code: str) -> Dict[str, Any]:
        """
        Get poll results with vote counts and percentages.

        Args:
            poll_code: The poll code

        Returns:
            dict: Results data including options with votes and percentages

        Raises:
            PollNotFoundError: If poll doesn't exist
        """
        poll = self.get_poll_by_code(poll_code)
        if not poll:
            raise PollNotFoundError("Poll not found")

        # Calculate total votes
        total_votes = sum(opt.vote_count for opt in poll.options)

        # Build options with percentages
        options_data = []
        for opt in poll.options:
            percentage = (opt.vote_count / total_votes * 100) if total_votes > 0 else 0
            options_data.append({
                'id': opt.id,
                'option_text': opt.option_text,
                'vote_count': opt.vote_count,
                'percentage': round(percentage, 1)
            })

        return {
            'poll_code': poll_code,
            'question': poll.question,
            'total_votes': total_votes,
            'options': options_data,
            'created_at': poll.created_at.isoformat() if poll.created_at else None
        }

    def check_rate_limit(self, ip_address: str) -> bool:
        """
        Check if IP is within rate limits.

        Args:
            ip_address: Client IP address

        Returns:
            bool: True if allowed, False if rate limited
        """
        return self.rate_limiter.is_allowed(ip_address)

    def get_rate_limit_info(self, ip_address: str) -> Dict[str, Any]:
        """
        Get rate limit information for an IP.

        Args:
            ip_address: Client IP address

        Returns:
            dict: Rate limit info
        """
        return {
            'remaining': self.rate_limiter.get_remaining(ip_address),
            'limit': self.rate_limiter.max_requests,
            'window': self.rate_limiter.window_seconds
        }
