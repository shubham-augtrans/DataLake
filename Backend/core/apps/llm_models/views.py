from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import LLMModel
from .serializers import LLMModelSerializer


class LLMModelViewSet(viewsets.ModelViewSet):
    queryset = LLMModel.objects.all().order_by("-created_at")
    serializer_class = LLMModelSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="count")
    def count(self, request):
        return Response({"count": self.get_queryset().count()})

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        model = self.get_object()
        model.is_default = True
        model.save()
        return Response(self.get_serializer(model).data, status=status.HTTP_200_OK)
