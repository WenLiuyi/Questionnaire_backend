from django.urls import path
from user import views

urlpatterns = [
    path('login', views.send_registration_email, name="send-registration-email-url"),
    path('user/updateUserInfo',views.update_user_email, name='update-user-info-url'),
    path('user/updateUserPassword',views.update_user_password,name='update-user-password-url'),
    path('questionnaire/GetDraftQs',views.get_drafted_qs,name='get-drafted-qs-url'),
]