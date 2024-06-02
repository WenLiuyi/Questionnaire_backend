from django.urls import path
from user import views

urlpatterns = [
    path('getUserMessage/', views.send_registration_email, name="send-registration-email-url"),
]