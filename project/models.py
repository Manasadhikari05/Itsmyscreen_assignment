"""
Database models for the Real-Time Poll Application.

This module defines the SQLAlchemy ORM models for Poll, Option, and Vote entities.
Includes proper relationships, indexes, and constraints for data integrity.
"""

import uuid
import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime,
    ForeignKey, UniqueConstraint, Index, func
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker

# Create declarative base for model definitions
Base = declarative_base()


class Poll(Base):
    """
    Poll entity representing a single poll with a question and multiple options.

    Attributes:
        id: Primary key
        question: The poll question text
        poll_code: Unique 8-character code for sharing
        created_at: Timestamp of poll creation
        options: List of associated options
        votes: List of all votes cast
    """

    __tablename__ = 'polls'

    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(String(500), nullable=False)
    poll_code = Column(String(8), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    options = relationship(
        'Option',
        back_populates='poll',
        cascade='all, delete-orphan',
        order_by='Option.id'
    )
    votes = relationship(
        'Vote',
        back_populates='poll',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Poll(id={self.id}, question="{self.question[:30]}...", code={self.poll_code})>'

    def to_dict(self, include_options=True):
        """
        Convert poll to dictionary representation.

        Args:
            include_options: Whether to include options in the output

        Returns:
            dict: Poll data as dictionary
        """
        data = {
            'id': self.id,
            'question': self.question,
            'poll_code': self.poll_code,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'total_votes': sum(opt.vote_count for opt in self.options)
        }

        if include_options:
            data['options'] = [opt.to_dict() for opt in self.options]

        return data


class Option(Base):
    """
    Option entity representing a single choice within a poll.

    Attributes:
        id: Primary key
        poll_id: Foreign key to the parent poll
        option_text: The text of this option
        vote_count: Number of votes for this option
        poll: Parent poll relationship
        votes: Votes for this option
    """

    __tablename__ = 'options'

    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(
        Integer,
        ForeignKey('polls.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    option_text = Column(String(200), nullable=False)
    vote_count = Column(Integer, default=0, nullable=False)

    # Relationships
    poll = relationship('Poll', back_populates='options')
    votes = relationship('Vote', back_populates='option')

    # Table-level constraints
    __table_args__ = (
        Index('idx_option_poll_id', 'poll_id'),
    )

    def __repr__(self):
        return f'<Option(id={self.id}, text="{self.option_text[:30]}...", votes={self.vote_count})>'

    def to_dict(self):
        """
        Convert option to dictionary representation.

        Returns:
            dict: Option data as dictionary
        """
        return {
            'id': self.id,
            'poll_id': self.poll_id,
            'option_text': self.option_text,
            'vote_count': self.vote_count
        }


class Vote(Base):
    """
    Vote entity representing a single vote cast by a user.

    Attributes:
        id: Primary key
        poll_id: Foreign key to the voted poll
        option_id: Foreign key to the selected option
        ip_address: Client IP address (for fairness control)
        browser_token: Unique browser identifier (for fairness control)
        timestamp: When the vote was cast
        poll: Parent poll relationship
        option: Voted option relationship
    """

    __tablename__ = 'votes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(
        Integer,
        ForeignKey('polls.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    option_id = Column(
        Integer,
        ForeignKey('options.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    ip_address = Column(String(45), nullable=False)  # IPv6 compatible
    browser_token = Column(String(36), nullable=False)  # UUID format
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    poll = relationship('Poll', back_populates='votes')
    option = relationship('Option', back_populates='votes')

    # Table-level constraints
    __table_args__ = (
        # Prevent duplicate votes from same IP per poll
        UniqueConstraint('poll_id', 'ip_address', name='uq_vote_poll_ip'),
        # Prevent duplicate votes from same browser token per poll
        UniqueConstraint('poll_id', 'browser_token', name='uq_vote_poll_token'),
        Index('idx_vote_poll_id', 'poll_id'),
        Index('idx_vote_ip', 'ip_address'),
        Index('idx_vote_token', 'browser_token'),
    )

    def __repr__(self):
        return f'<Vote(id={self.id}, poll_id={self.poll_id}, option_id={self.option_id})>'

    def to_dict(self):
        """
        Convert vote to dictionary representation.

        Returns:
            dict: Vote data as dictionary
        """
        return {
            'id': self.id,
            'poll_id': self.poll_id,
            'option_id': self.option_id,
            'ip_address': self.ip_address,
            'browser_token': self.browser_token,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


# Database initialization function
def init_db(database_url='sqlite:///polls.db'):
    """
    Initialize the database and create all tables.

    Args:
        database_url: SQLAlchemy database URL

    Returns:
        tuple: (engine, SessionLocal)
    """
    engine = create_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session factory
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

    return engine, SessionLocal


def generate_poll_code(length=8):
    """
    Generate a unique poll code using UUID.

    Args:
        length: Length of the code to generate

    Returns:
        str: Unique poll code
    """
    # Use UUID4 and remove dashes, then take first 'length' characters
    return uuid.uuid4().hex[:length].upper()


def generate_browser_token():
    """
    Generate a unique browser token (UUID).

    Returns:
        str: UUID string
    """
    return str(uuid.uuid4())
