"""Route aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.routes.activity import router as activity_router
from app.routes.analytics import router as analytics_router
from app.routes.api_keys import router as api_keys_router
from app.routes.billing import router as billing_router
from app.routes.brains import router as brains_router
from app.routes.corrections import router as corrections_router
from app.routes.gdpr import router as gdpr_router
from app.routes.lessons import router as lessons_router
from app.routes.meta_rules import router as meta_rules_router
from app.routes.operator import router as operator_router
from app.routes.proof import router as proof_router
from app.routes.public import router as public_router
from app.routes.rule_patches import router as rule_patches_router
from app.routes.sync import router as sync_router
from app.routes.team import router as team_router
from app.routes.users import router as users_router

router = APIRouter()
router.include_router(sync_router, tags=["sync"])
router.include_router(brains_router, tags=["brains"])
router.include_router(users_router, tags=["users"])
router.include_router(api_keys_router, tags=["api-keys"])
router.include_router(lessons_router, tags=["lessons"])
router.include_router(corrections_router, tags=["corrections"])
router.include_router(analytics_router, tags=["analytics"])
router.include_router(meta_rules_router, tags=["meta-rules"])
router.include_router(activity_router, tags=["activity"])
router.include_router(rule_patches_router, tags=["rule-patches"])
router.include_router(billing_router, tags=["billing"])
router.include_router(team_router, tags=["team"])
router.include_router(operator_router, tags=["operator"])
router.include_router(gdpr_router, tags=["gdpr"])
router.include_router(proof_router, tags=["proof"])
router.include_router(public_router, tags=["public"])
