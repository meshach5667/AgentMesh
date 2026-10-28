"""MongoDB documents (Beanie), one collection each."""

from app.documents.ai import AiInferenceRequest, AiRun, AiRunEvent
from app.documents.api_key import ApiKey
from app.documents.audit import AuditLog
from app.documents.base import Doc
from app.documents.billing import CostEstimate, NodePrice
from app.documents.credit import CreditBalance, CreditEntry, CreditPayment, ProviderGateway
from app.documents.deployment import Deployment, DeploymentAttempt, DeploymentEvent
from app.documents.model import Model, ModelArtifact
from app.documents.node import Node, NodeHardware
from app.documents.node_session import NodeChallenge, NodeSession
from app.documents.reservation import ResourceReservation
from app.documents.session import AuthSession, RefreshToken
from app.documents.sponsorship import AdSettings, SponsorCampaign, SponsorStat, SponsorView
from app.documents.usage import UsageRecord
from app.documents.user import Customer, Provider, User
from app.documents.worker import NodeCommand, NodeEnrollmentToken

DOCUMENTS: list[type[Doc]] = [
    AdSettings,
    AiInferenceRequest,
    AiRun,
    AiRunEvent,
    ApiKey,
    AuditLog,
    AuthSession,
    CostEstimate,
    CreditBalance,
    CreditEntry,
    CreditPayment,
    Customer,
    Deployment,
    DeploymentAttempt,
    DeploymentEvent,
    Model,
    ModelArtifact,
    Node,
    NodeChallenge,
    NodeCommand,
    NodeEnrollmentToken,
    NodeHardware,
    NodePrice,
    NodeSession,
    Provider,
    ProviderGateway,
    RefreshToken,
    ResourceReservation,
    SponsorCampaign,
    SponsorStat,
    SponsorView,
    UsageRecord,
    User,
]

__all__ = [d.__name__ for d in DOCUMENTS] + ["DOCUMENTS", "Doc"]
