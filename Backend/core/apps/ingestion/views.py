from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import IngestionPipeline
from .serializers import IngestionPipelineSerializer
from .services import PipelineService


class IngestionPipelineViewSet(viewsets.ModelViewSet):
    queryset = IngestionPipeline.objects.select_related(
        "source",
        "destination"
    )
    serializer_class = IngestionPipelineSerializer

    @action(detail=False, methods=["get"], url_path="count")
    def count(self, request):
        return Response({
            "count": self.get_queryset().count()
        })

    @action(detail=True, methods=["post"], url_path="run")
    def run(self, request, pk=None):

        pipeline = self.get_object()

        try:
            PipelineService(pipeline).run()

            return Response(
                {
                    "success": True,
                    "message": "Pipeline executed successfully."
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