import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment
from app.services.deployment_service import create_deployment
from app.services.scheduler_service import find_capable_nodes, rank_nodes, select_node

logger = logging.getLogger(__name__)


async def deploy_model(db: AsyncSession, user_id: uuid.UUID, requirements: dict[str, Any]) -> Deployment:
    """
    AI agent flow: create task, find nodes, rank, select, create deployment, log actions with reasoning.
    """
    logger.info(f"Starting agent workflow for user {user_id} to deploy model with requirements: {requirements}")

    # 1. Find capable nodes
    logger.info("Agent: Searching for capable nodes in the marketplace...")
    capable_nodes = await find_capable_nodes(db, requirements)
    if not capable_nodes:
        logger.error("Agent: No nodes found that meet the requirements.")
        raise Exception("No available nodes meet the deployment requirements")

    logger.info(f"Agent: Found {len(capable_nodes)} capable nodes.")

    # 2. Rank nodes
    logger.info("Agent: Ranking candidate nodes based on price, performance, and reliability...")
    ranked_nodes = rank_nodes(capable_nodes)

    # 3. Select best node
    logger.info("Agent: Selecting the optimal node from ranked candidates...")
    best_node = select_node(ranked_nodes)

    logger.info(f"Agent: Selected node {best_node.id} for deployment. Reasoning: Best overall score across factors.")

    # 4. Create deployment
    logger.info("Agent: Initiating deployment on the selected node...")

    # Mocking a deployment request object
    class DeploymentReq:
        node_id = best_node.id
        model_name = requirements.get("model", "unknown-model")
        config = requirements.get("config", {})

    deployment = await create_deployment(db, user_id, DeploymentReq())

    logger.info(f"Agent: Deployment {deployment.id} created successfully on node {best_node.id}.")

    return deployment
