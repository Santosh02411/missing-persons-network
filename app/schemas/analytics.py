from pydantic import BaseModel


class StatusBreakdown(BaseModel):
    open: int
    lead_found: int
    resolved: int
    pending_review: int
    dismissed: int


class ResolutionTimeStats(BaseModel):
    resolved_case_count: int
    avg_days_to_resolve: float | None
    median_days_to_resolve: float | None


class VolumePoint(BaseModel):
    period_start: str
    count: int


class SightingTotals(BaseModel):
    total: int
    pending: int
    verified: int
    dismissed: int


class HeatmapPoint(BaseModel):
    lat: float
    lng: float
    status: str


class AnalyticsOverview(BaseModel):
    total_cases: int
    status_breakdown: StatusBreakdown
    resolution_time: ResolutionTimeStats
    sightings: SightingTotals
