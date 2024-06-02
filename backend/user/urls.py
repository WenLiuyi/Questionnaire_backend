from django.urls import path
from user import views

urlpatterns = [
    path('login', views.send_registration_email, name="send-registration-email-url"),
    path('login',views.get_user_info, name="get-user-info-url"),
    path('updateUserInfo',views.update_user_email, name='update-user-info-url'),
    path('updateUserPassword',views.update_user_password,name='update-user-password-url'),
]