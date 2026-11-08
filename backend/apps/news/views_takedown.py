"""The public complaint form (anonymous, rate-limited, always answers the same way) and the staff takedown queue."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit import service as audit
from apps.core.pagination import StandardPagination
from apps.core.text import clean_plain_text

from .models import NewsTakedown
from .permissions import NewsPublicEnabled
from .services import takedown as service
from .views import StaffView


class TakedownFormSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField(max_length=254)
    article = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    claim = serializers.ChoiceField(choices=["copyright", "accuracy", "other"], default="copyright")
    message = serializers.CharField(max_length=4000, min_length=10)

    def validate_name(self, value):
        return clean_plain_text(value, max_length=120, allow_blank=False)

    def validate_message(self, value):
        return clean_plain_text(value, max_length=4000, multiline=True, allow_blank=False)

    def validate_article(self, value):
        return clean_plain_text(value, max_length=300)


class TakedownReceiveView(APIView):
    """POST /news/takedown/ . The answer never says whether the article exists, so the form cannot be used to probe for hidden articles."""

    authentication_classes = []
    permission_classes = [NewsPublicEnabled, AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "news_takedown"
    parser_classes = [JSONParser]
    http_method_names = ["post", "options"]

    def post(self, request, **kwargs):
        serializer = TakedownFormSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        takedown = service.receive(name=d["name"], email=d["email"], ref=d["article"], claim=d["claim"], message=d["message"])
        audit.log(None, "news.takedown_receive", takedown, claim=takedown.claim, matched=takedown.article_id is not None)
        return Response({"received": True}, status=201)


def takedown_data(t):
    return {
        "id": t.pk, "status": t.status, "claim": t.claim, "contact_name": t.contact_name, "contact_email": t.contact_email, "message": t.message,
        "article_ref": t.article_ref, "article": {"id": t.article_id, "title": t.article.title, "status": t.article.status, "slug": t.article.slug} if t.article_id else None,
        "resolution_note": t.resolution_note, "handled_at": t.handled_at, "created_at": t.created_at,
    }


class AdminTakedownListView(StaffView):
    def get(self, request, **kwargs):
        qs = NewsTakedown.objects.select_related("article")
        status_ = request.query_params.get("status")
        if status_ in NewsTakedown.Status.values:
            qs = qs.filter(status=status_)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([takedown_data(t) for t in page])


class AdminTakedownActionView(StaffView):
    """POST hold | uphold | dismiss (uphold and dismiss need a `note`)."""

    def post(self, request, pk, action, **kwargs):
        takedown = get_object_or_404(NewsTakedown.objects.select_related("article"), pk=pk)
        note = request.data.get("note")
        try:
            with transaction.atomic():
                if action == "hold":
                    service.hold(takedown, request.user)
                    audit.log(request, "news.takedown_hold", takedown, article=takedown.article.title)
                elif action == "uphold":
                    service.uphold(takedown, request.user, note)
                    audit.log(request, "news.takedown_uphold", takedown, note=takedown.resolution_note)
                elif action == "dismiss":
                    service.dismiss(takedown, request.user, note)
                    audit.log(request, "news.takedown_dismiss", takedown, note=takedown.resolution_note)
                else:
                    raise service.TakedownError("Unknown action.")
        except service.TakedownError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response(takedown_data(takedown))

