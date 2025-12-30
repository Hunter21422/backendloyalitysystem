
from django.contrib import admin
from django.conf import settings
from django.urls import path,include
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from rest_framework.routers import DefaultRouter


router = DefaultRouter()

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include("Loyality.urls")),
   

]
# Медиа в DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

