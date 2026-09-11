from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import IngestionPipeline, PipelineRun
from .serializers import IngestionPipelineSerializer, PipelineRunSerializer
from .services.pipeline_service import PipelineService


class IngestionPipelineViewSet(viewsets.ModelViewSet):

    queryset = IngestionPipeline.objects.select_related(
        "source",
        "destination",
    )

    serializer_class = IngestionPipelineSerializer
    permission_classes = [IsAuthenticated]

    @action(
        detail=False,
        methods=["get"],
        url_path="count",
    )
    def count(self, request):
        return Response({
            "count": self.get_queryset().count()
        })

    @action(
        detail=False,
        methods=["get"],
        url_path="running",
    )
    def running(self, request):
        """
        Pipelines with an in-flight run right now - a run() call is
        synchronous (blocks the /run/ request until it finishes), so a row
        only stays RUNNING for that request's lifetime. Backs the "Jobs &
        Pipelines" sidebar page, which should show live activity, not the
        full pipeline configuration list.
        """
        runs = PipelineRun.objects.filter(
            status=PipelineRun.Status.RUNNING
        ).select_related("pipeline").order_by("-started_at")
        return Response(PipelineRunSerializer(runs, many=True).data)

    @action(
        detail=False,
        methods=["get"],
        url_path="runs",
    )
    def runs(self, request):
        """Recent run history (any status), most recent first - gives the
        "Jobs & Pipelines" page something to show even when nothing is
        currently running."""
        runs = PipelineRun.objects.select_related("pipeline").order_by("-started_at")[:50]
        return Response(PipelineRunSerializer(runs, many=True).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="run",
    )
    def run(self, request, pk=None):

        pipeline = self.get_object()
        triggered_by = str(request.data.get("triggered_by") or "manual")[:50]

        try:

            result = PipelineService(
                pipeline
            ).run(triggered_by=triggered_by)

            return Response(
                {
                    "success": True,
                    "message": (
                        "Pipeline submitted successfully."
                    ),
                    "result": result,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as ex:

            return Response(
                {
                    "success": False,
                    "message": str(ex),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )