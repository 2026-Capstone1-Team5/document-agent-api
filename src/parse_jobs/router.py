from uuid import UUID

from fastapi import APIRouter, Depends

from src.auth.dependencies import get_current_document_user
from src.auth.models import UserModel
from src.common.errors import ApiError
from src.parse_jobs.dependencies import get_parse_job_service
from src.parse_jobs.exceptions import ParseJobNotFoundError
from src.parse_jobs.schemas import ParseJobResponse
from src.parse_jobs.service import ParseJobService

router = APIRouter(prefix="/api/v1/parse-jobs", tags=["parse-jobs"])


@router.get("/{job_id}", response_model=ParseJobResponse)
def get_parse_job(
    job_id: UUID,
    current_user: UserModel = Depends(get_current_document_user),
    service: ParseJobService = Depends(get_parse_job_service),
) -> ParseJobResponse:
    try:
        return service.get_job(job_id, owner_user_id=current_user.id)
    except ParseJobNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="parse_job_not_found",
            message=str(exc),
        ) from exc

