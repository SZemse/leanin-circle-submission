"""Normalized domain schema for the seeded Lean In snapshot."""
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from .database import Base


class Topic(Base):
    __tablename__ = 'topics'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    has_photo: Mapped[bool] = mapped_column(nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    job_title: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(200))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    profile_completeness: Mapped[float] = mapped_column(Float)
    interests: Mapped[list['UserInterest']] = relationship(back_populates='user')
    memberships: Mapped[list['Membership']] = relationship(back_populates='user')
    __table_args__ = (CheckConstraint('profile_completeness BETWEEN 0 AND 1', name='user_profile_completeness_range'),)


class UserInterest(Base):
    __tablename__ = 'user_interests'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    topic_slug: Mapped[str] = mapped_column(ForeignKey('topics.slug'), primary_key=True)
    user: Mapped[User] = relationship(back_populates='interests')
    topic: Mapped[Topic] = relationship()
    __table_args__ = (Index('ix_interests_topic', 'topic_slug'),)


class Circle(Base):
    __tablename__ = 'circles'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    topic_slug: Mapped[str | None] = mapped_column(ForeignKey('topics.slug'))
    cover_image_url: Mapped[str | None] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(20))
    access: Mapped[str] = mapped_column(String(20))
    join_policy: Mapped[str] = mapped_column(String(20))
    max_members: Mapped[int | None] = mapped_column(Integer)
    member_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    feed_posts_30d: Mapped[int] = mapped_column(Integer)
    chat_messages_30d: Mapped[int] = mapped_column(Integer)
    topic: Mapped[Topic | None] = relationship()
    tags: Mapped[list['CircleTag']] = relationship(back_populates='circle')
    memberships: Mapped[list['Membership']] = relationship(back_populates='circle')
    __table_args__ = (
        CheckConstraint('member_count >= 0', name='circle_member_count_nonnegative'),
        CheckConstraint('max_members IS NULL OR max_members >= 0', name='circle_capacity_nonnegative'),
        CheckConstraint('feed_posts_30d >= 0 AND chat_messages_30d >= 0', name='circle_activity_nonnegative'),
        CheckConstraint("format IN ('virtual','hybrid','in_person')", name='circle_format_enum'),
        CheckConstraint("access IN ('public','unlisted')", name='circle_access_enum'),
        CheckConstraint("join_policy IN ('open','request')", name='circle_join_policy_enum'),
        Index('ix_circles_discovery', 'access', 'last_activity_at'),
        Index('ix_circles_topic', 'topic_slug'),
    )


class CircleTag(Base):
    __tablename__ = 'circle_tags'
    circle_id: Mapped[int] = mapped_column(ForeignKey('circles.id'), primary_key=True)
    tag: Mapped[str] = mapped_column(String(100), primary_key=True)
    circle: Mapped[Circle] = relationship(back_populates='tags')
    __table_args__ = (Index('ix_circle_tags_tag', 'tag'),)


class Membership(Base):
    __tablename__ = 'memberships'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey('circles.id'), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates='memberships')
    circle: Mapped[Circle] = relationship(back_populates='memberships')
    __table_args__ = (
        CheckConstraint("role IN ('leader','member')", name='membership_role_enum'),
        Index('ix_memberships_circle_id', 'circle_id'),
    )


class Activity(Base):
    __tablename__ = 'activity'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey('circles.id'))
    author_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    reaction_count: Mapped[int] = mapped_column(Integer)
    comment_count: Mapped[int] = mapped_column(Integer)
    save_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index('ix_activity_circle_created_at', 'circle_id', 'created_at'),
        CheckConstraint('reaction_count >= 0 AND comment_count >= 0 AND save_count >= 0', name='activity_engagement_nonnegative'),
    )
