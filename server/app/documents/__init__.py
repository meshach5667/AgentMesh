"""MongoDB documents (Beanie), one collection per former PostgreSQL table, with the same ids and fields."""

from app.documents.agent import AgentAction, AgentTask
from app.documents.ai import AiInferenceNode, AiInferenceRequest, AiRun, AiRunEvent
from app.documents.api_key import ApiKey
from app.documents.audit import AuditLog, Event
from app.documents.base import Doc
from app.documents.billing import Charge, Payment, PaymentEvent, Payout, PayoutAccount, PricingRule, Refund
from app.documents.deployment import Deployment, DeploymentEvent
from app.documents.model import Model, ModelArtifact
from app.documents.node import Node, NodeHardware, NodePricing
from app.documents.reservation import ResourceReservation
from app.documents.session import AuthSession, RefreshToken
from app.documents.sponsorship import AdSettings, SponsorCampaign, SponsorStat, SponsorView
from app.documents.transaction import Transaction
from app.documents.usage import UsageRecord
from app.documents.user import Customer, Provider, User
from app.documents.wallet import Wallet
from app.documents.worker import NodeCommand, NodeEnrollmentToken
from app.documents.workload import Workload, WorkloadStatus

DOCUMENTS: list[type[Doc]] = [
    AdSettings,
    AgentAction,
    AgentTask,
    AiInferenceNode,
    AiInferenceRequest,
    AiRun,
    AiRunEvent,
    ApiKey,
    AuditLog,
    AuthSession,
    Charge,
    Customer,
    Deployment,
    DeploymentEvent,
    Event,
    Model,
    ModelArtifact,
    Node,
    NodeCommand,
    NodeEnrollmentToken,
    NodeHardware,
    NodePricing,
    Payment,
    PaymentEvent,
    Payout,
    PayoutAccount,
    PricingRule,
    Provider,
    RefreshToken,
    Refund,
    ResourceReservation,
    SponsorCampaign,
    SponsorStat,
    SponsorView,
    Transaction,
    UsageRecord,
    User,
    Wallet,
    Workload,
]

__all__ = [d.__name__ for d in DOCUMENTS] + ["DOCUMENTS", "Doc", "WorkloadStatus"]
