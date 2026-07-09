"""Schéma relationnel (SQLAlchemy 2) et fabrique de sessions.

Les identifiants sont des chaînes lisibles (ex. `O-2024-0103`, `C-marc-dubois`,
`mu-1999-treble`) pour faciliter le débogage. Les types sont portables : Postgres
en production, SQLite en mémoire pour les tests.
"""

from __future__ import annotations

import enum
import logging
import os
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool


logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Segment(str, enum.Enum):
    particulier = "particulier"
    pro = "pro"
    revendeur = "revendeur"


class Condition(str, enum.Enum):
    mint = "mint"
    neuf = "neuf"
    occasion = "occasion"


class Size(str, enum.Enum):
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"
    XXL = "XXL"


class OrderStatus(str, enum.Enum):
    paid = "paid"
    prepared = "prepared"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    returned = "returned"


class ReturnStatus(str, enum.Enum):
    requested = "requested"
    accepted = "accepted"
    refused = "refused"
    refunded = "refunded"


class RefundStatus(str, enum.Enum):
    auto = "auto"
    escalated = "escalated"
    approved = "approved"
    refused = "refused"


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    full_name: Mapped[str] = mapped_column(String)
    segment: Mapped[Segment] = mapped_column(Enum(Segment), default=Segment.particulier)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime(2024, 1, 1))
    orders: Mapped[list[Order]] = relationship(back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    ref: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    club: Mapped[str] = mapped_column(String)
    season: Mapped[str] = mapped_column(String)
    edition: Mapped[str] = mapped_column(String, default="")
    condition: Mapped[Condition] = mapped_column(Enum(Condition), default=Condition.neuf)
    base_price: Mapped[float] = mapped_column(Numeric(10, 2))
    variants: Mapped[list[ProductVariant]] = relationship(back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    product_ref: Mapped[str] = mapped_column(ForeignKey("products.ref"))
    size: Mapped[Size] = mapped_column(Enum(Size))
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=0)
    product: Mapped[Product] = relationship(back_populates="variants")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.paid)
    total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime(2024, 1, 1))
    shipping_address: Mapped[dict] = mapped_column(JSON, default=dict)
    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    variant_id: Mapped[str] = mapped_column(ForeignKey("product_variants.id"))
    size: Mapped[Size] = mapped_column(Enum(Size))
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
    order: Mapped[Order] = relationship(back_populates="items")


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    carrier: Mapped[str] = mapped_column(String)
    tracking_number: Mapped[str] = mapped_column(String)
    estimated_delivery: Mapped[str] = mapped_column(String, default="")
    actual_delivery: Mapped[str | None] = mapped_column(String, nullable=True)


class Return(Base):
    __tablename__ = "returns"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    reason: Mapped[str] = mapped_column(String)
    status: Mapped[ReturnStatus] = mapped_column(Enum(ReturnStatus), default=ReturnStatus.requested)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime(2024, 1, 1))


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    reason: Mapped[str] = mapped_column(String)
    status: Mapped[RefundStatus] = mapped_column(Enum(RefundStatus), default=RefundStatus.auto)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime(2024, 1, 1))


class Escalation(Base):
    __tablename__ = "escalations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime(2024, 1, 1))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# --- Mémoire (Chantier 1) ---------------------------------------------------
# Table distincte de `Customer` : la mémoire (faits par utilisateur conversationnel)
# est un concept séparé des données métier (commandes/clients).


class MemoryUser(Base):
    """Faits durables à clé connue d'avance (mémoire sémantique, R2)."""

    __tablename__ = "memory_users"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # user_id métier
    pointure: Mapped[str | None] = mapped_column(String, nullable=True)
    segment: Mapped[str | None] = mapped_column(String, nullable=True)
    tutoiement: Mapped[str | None] = mapped_column(String, nullable=True)
    langue: Mapped[str | None] = mapped_column(String, nullable=True)
    canal_contact: Mapped[str | None] = mapped_column(String, nullable=True)


class MessageBrut(Base):
    """Tampon de capture synchrone en attente de traitement asynchrone (R2/R3/R5)."""

    __tablename__ = "message_brut"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid
    user_id: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String)
    contenu: Mapped[str] = mapped_column(String)
    horodatage: Mapped[datetime] = mapped_column(DateTime, default=datetime(2024, 1, 1))


class MemoryEpisode(Base):
    """Mémoire épisodique : événements nettoyés (léger), recherchables par mots-clés.

    Un épisode consolidé (`consolidated_key` renseignée) reste stocké comme trace
    d'audit (R6) mais n'est plus la source de vérité pour la lecture — c'est le
    fait sémantique dérivé (`memory_users`/`memory_facts`) qui l'est.
    """

    __tablename__ = "memory_episodes"
    id_episode: Mapped[str] = mapped_column(String, primary_key=True)  # uuid
    user_id: Mapped[str] = mapped_column(String, index=True)
    contenu: Mapped[str] = mapped_column(String)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime(2024, 1, 1))
    consolidated: Mapped[bool] = mapped_column(Boolean, default=False)
    consolidated_key: Mapped[str | None] = mapped_column(String, nullable=True)


class MemoryFact(Base):
    """Mémoire sémantique à clé imprévisible (fallback relationnel hors vectoriel)."""

    __tablename__ = "memory_facts"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid
    user_id: Mapped[str] = mapped_column(String, index=True)
    key: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(String)


def make_engine(url: str | None = None):
    """Crée un engine SQLAlchemy (Postgres en prod, fourni via `DB_URL`)."""
    url = url or os.getenv("DB_URL", "postgresql+psycopg://app:app@localhost:5432/velmo")
    return create_engine(url, future=True)


def session_factory(url: str | None = None):
    return sessionmaker(bind=make_engine(url), expire_on_commit=False, future=True)


def fresh_sqlite_session():
    """Session SQLite en mémoire avec le schéma créé (tests / évaluation hors-ligne).

    `check_same_thread=False` + `StaticPool` : les outils de l'agent LangGraph
    (`create_agent()`) s'exécutent dans un thread différent de celui qui a ouvert
    la connexion. Sans `check_same_thread=False`, SQLite refuse tout accès
    cross-thread ; sans `StaticPool`, chaque connexion prise dans le pool par défaut
    ouvrirait une base `:memory:` distincte et vide (une base en mémoire vit et
    meurt avec sa connexion physique).
    """
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)()


_MEMORY_ENGINE = None


def memory_session_factory():
    """Fabrique de sessions pour le stockage mémoire (long terme, partagé entre process).

    Réutilise `DB_URL` si joignable (Postgres prod), sinon un fichier SQLite stable
    partagé entre instances `MemoryManager` (nécessaire pour la persistance inter-session,
    R2) — jamais le défaut Postgres `localhost` qui échouerait sans service disponible.
    """
    global _MEMORY_ENGINE
    if _MEMORY_ENGINE is None:
        url = os.getenv("DB_URL")
        engine = None
        if url:
            try:
                candidate = create_engine(url, future=True)
                with candidate.connect():
                    pass
                engine = candidate
            except Exception:
                engine = None
        if engine is None:
            db_path = os.getenv("VELMO_MEMORY_DB_PATH", ".velmo_memory.db")
            logger.warning(
                "DB_URL (%s) injoignable : repli sur SQLite local (%s). "
                "Les écritures mémoire n'iront PAS dans Postgres.",
                url, db_path,
            )
            engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(engine)
        _MEMORY_ENGINE = engine
    return sessionmaker(bind=_MEMORY_ENGINE, expire_on_commit=False, future=True)
